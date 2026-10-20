"""Phase 2.4 — JIRA security issues, public CVEs, private disclosures (ULTRAPLAN §4.4).

Writes:
  data/derived/jira_security_issues.csv   created/resolved + resolution days
  data/derived/cve_timeline.csv           NVD 2.0 public CVE timeline for OpenMRS
  data/derived/disclosure_durations.csv   ONLY durations, computed from the IRB extract
                                          data/private/disclosures.csv (raw text never
                                          leaves the encrypted volume)
"""
from __future__ import annotations

import base64
import csv
import os
import sys
from datetime import datetime

from common import (DERIVED, JIRA_BASE_URL, NVD_API_KEY, PRIVATE,
                    cached_request, iso_week, log, write_schema)

JQL = os.getenv("JIRA_SECURITY_JQL",
                'labels in (security) OR component = "Security" ORDER BY created ASC')


def days(a, b):
    if not a or not b:
        return ""
    pa = datetime.fromisoformat(a.replace("Z", "+00:00").split(".")[0] + "+00:00"
                                if "." in a else a.replace("Z", "+00:00"))
    pb = datetime.fromisoformat(b.replace("Z", "+00:00").split(".")[0] + "+00:00"
                                if "." in b else b.replace("Z", "+00:00"))
    return round((pb - pa).total_seconds() / 86400, 2)


def jira():
    """Atlassian Cloud v3 search (issues.openmrs.org now redirects to
    openmrs.atlassian.net; /rest/api/2/search was removed upstream)."""
    rows, token = [], None
    headers = {"Accept": "application/json"}
    # Atlassian Cloud API tokens use BASIC auth (email:token), NOT Bearer (Bearer 403s).
    # With JIRA_EMAIL+JIRA_TOKEN we also capture access-restricted security issues.
    email = os.getenv("JIRA_EMAIL")
    tok = os.getenv("JIRA_TOKEN") or os.getenv("JIRA_KEY")
    if email and tok:
        headers["Authorization"] = "Basic " + base64.b64encode(
            ("%s:%s" % (email, tok)).encode()).decode()
    elif tok:
        headers["Authorization"] = "Bearer " + tok  # Server/DC PAT fallback
    while True:
        params = {"jql": JQL, "maxResults": 100,
                  "fields": "created,resolutiondate,status,priority,"
                            "project,issuetype,labels"}
        if token:
            params["nextPageToken"] = token
        r = cached_request("GET", JIRA_BASE_URL + "/rest/api/3/search/jql",
                           params=params, headers=headers)
        if r["status"] != 200:
            log.warning("JIRA search HTTP %s — check JQL/auth: %s",
                        r["status"], str(r["json"])[:200])
            break
        issues = (r["json"] or {}).get("issues") or []
        for it in issues:
            f = it["fields"]
            rows.append({
                "issue_key": it["key"],
                "project": (f.get("project") or {}).get("key", ""),
                "type": (f.get("issuetype") or {}).get("name", ""),
                "priority": (f.get("priority") or {}).get("name", ""),
                "labels": ";".join(f.get("labels") or []),
                "created": f.get("created") or "",
                "resolved": f.get("resolutiondate") or "",
                "resolution_days": days(f.get("created"), f.get("resolutiondate")),
                "created_week": iso_week((f.get("created") or "")[:10] or None) or "",
            })
        token = r["json"].get("nextPageToken")
        if not token or not issues:
            break
    out = DERIVED / "jira_security_issues.csv"
    if rows:
        with open(out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        write_schema(out, "Security-labeled/component JIRA issues with resolution time.",
                     {k: k for k in rows[0]},
                     "%s/rest/api/3/search/jql, JQL: %s" % (JIRA_BASE_URL, JQL))
    log.info("JIRA: %d issues", len(rows))
    return len(rows)


def nvd():
    rows = []
    headers = {"apiKey": NVD_API_KEY} if NVD_API_KEY else None
    for params in ({"keywordSearch": "openmrs", "resultsPerPage": 200},
                   {"virtualMatchString": "cpe:2.3:a:openmrs:openmrs",
                    "resultsPerPage": 200}):
        r = cached_request("GET", "https://services.nvd.nist.gov/rest/json/cves/2.0",
                           params=params, headers=headers)
        if r["status"] != 200:
            log.warning("NVD HTTP %s for %s", r["status"], params)
            continue
        for v in (r["json"] or {}).get("vulnerabilities", []):
            cve = v.get("cve", {})
            metrics = cve.get("metrics", {})
            score = ver = ""
            for mkey in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
                if metrics.get(mkey):
                    d = metrics[mkey][0]["cvssData"]
                    score, ver = d.get("baseScore", ""), d.get("version", "")
                    break
            rows.append({"cve_id": cve.get("id", ""),
                         "published": cve.get("published", ""),
                         "last_modified": cve.get("lastModified", ""),
                         "cvss_score": score, "cvss_version": ver,
                         "status": cve.get("vulnStatus", "")})
    dedup = {r["cve_id"]: r for r in rows}
    out = DERIVED / "cve_timeline.csv"
    with open(out, "w", newline="") as fh:
        cols = ["cve_id", "published", "last_modified", "cvss_score",
                "cvss_version", "status"]
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(sorted(dedup.values(), key=lambda r: r["published"]))
    write_schema(out, "Public CVE timeline for OpenMRS (keyword + CPE match, deduped).",
                 {"cve_id": "CVE", "published": "NVD publish ts",
                  "last_modified": "NVD modified ts", "cvss_score": "base score",
                  "cvss_version": "CVSS version of reported score",
                  "status": "NVD vuln status"},
                 "NVD API 2.0 /cves. API key present: %s." % bool(NVD_API_KEY))
    log.info("NVD: %d unique CVEs", len(dedup))
    return len(dedup)


def disclosures():
    """IRB-scoped: R1 places data/private/disclosures.csv with columns
    disclosure_id, reported_at, triaged_at, patched_at, released_at, advisory_at,
    severity. Only durations leave the encrypted volume."""
    src = PRIVATE / "disclosures.csv"
    if not src.exists():
        log.info("no private disclosures extract yet (data/private/disclosures.csv) "
                 "— R1 to supply; skipping")
        return 0
    rows = []
    with open(src, newline="") as fh:
        for r in csv.DictReader(fh):
            rows.append({
                "disclosure_id": r["disclosure_id"],
                "severity": r.get("severity", ""),
                "report_to_triage_days": days(r.get("reported_at"), r.get("triaged_at")),
                "triage_to_patch_days": days(r.get("triaged_at"), r.get("patched_at")),
                "patch_to_release_days": days(r.get("patched_at"), r.get("released_at")),
                "release_to_advisory_days": days(r.get("released_at"), r.get("advisory_at")),
                "report_to_release_days": days(r.get("reported_at"), r.get("released_at")),
                "reported_quarter": (r.get("reported_at") or "")[:7],
            })
    out = DERIVED / "disclosure_durations.csv"
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    write_schema(out, "Disclosure pipeline durations ONLY (de-identified; month-level "
                 "reported_quarter, no titles/text/reporters).",
                 {k: k for k in rows[0]},
                 "Computed from IRB-restricted data/private/disclosures.csv; raw text "
                 "never leaves the encrypted volume (ULTRAPLAN §4.4).")
    log.info("disclosures: %d duration rows", len(rows))
    return len(rows)


def main():
    j = jira()
    c = nvd()
    d = disclosures()
    print("jira=%d cves=%d disclosures=%d" % (j, c, d))


if __name__ == "__main__":
    sys.exit(main() or 0)
