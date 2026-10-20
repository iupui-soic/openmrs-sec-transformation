"""Phase 2.2 — Static-analysis outcomes from SonarCloud (ULTRAPLAN §4.2).

Writes:
  data/derived/sonar_weekly.csv      repo-week: open vulns, hotspots, quality-gate status
  data/derived/sonar_pr_checks.csv   merged PRs whose Sonar/security check failed then
                                     passed before merge -> pr_stage_fixes

SonarCloud public API needs no token for public projects; SONAR_TOKEN raises limits.
"""
from __future__ import annotations

import csv
import re
import sys

import pandas as pd

from common import (DERIVED, SONAR_ORG, SONAR_TOKEN, WINDOW_END, WINDOW_START,
                    cached_request, gh_paginate, gh_rest, iso_week, log,
                    o3_sample, write_schema)

SONAR_API = "https://sonarcloud.io/api"
# Security = primary outcomes; quality metrics added for the specificity/placebo test
# (the default "OpenMRS Quality" gate gates on new_security_rating + new_security_hotspots
# AND new_reliability/maintainability/coverage — so quality is a secondary outcome of the
# gate intervention and a placebo for the security-specific ones). All "new_*" = clean-as-
# you-code (gate scope). Kept to 15 metrics (search_history limit).
METRICS = ("vulnerabilities,security_hotspots,security_rating,new_vulnerabilities,"
           "new_security_rating,new_security_hotspots_reviewed,"
           "bugs,reliability_rating,new_reliability_rating,code_smells,sqale_rating,"
           "new_maintainability_rating,coverage,new_coverage,alert_status")
CHECK_NAME_RE = re.compile(r"sonar|security", re.I)


def sonar_get(path, params):
    headers = {"Authorization": "Bearer " + SONAR_TOKEN} if SONAR_TOKEN else None
    return cached_request("GET", SONAR_API + path, params=params, headers=headers)


def org_projects():
    out, page = [], 1
    while True:
        r = sonar_get("/components/search_projects",
                      {"organization": SONAR_ORG, "ps": 500, "p": page})
        comps = (r["json"] or {}).get("components") or []
        out.extend(comps)
        if r["status"] != 200 or len(comps) < 500:
            return out
        page += 1


def measure_history(key):
    rows, page = [], 1
    while True:
        r = sonar_get("/measures/search_history",
                      {"component": key, "metrics": METRICS, "ps": 1000, "p": page,
                       "from": WINDOW_START, "to": WINDOW_END})
        if r["status"] != 200:
            return rows
        measures = (r["json"] or {}).get("measures") or []
        for m in measures:
            for h in m.get("history", []):
                rows.append((h["date"], m["metric"], h.get("value")))
        total = (r["json"].get("paging") or {}).get("total", 0)
        if page * 1000 >= total or not measures:
            return rows
        page += 1


def main():
    projects = org_projects()
    log.info("SonarCloud '%s': %d projects", SONAR_ORG, len(projects))

    weekly = {}
    for i, p in enumerate(projects, 1):
        key = p["key"]
        for date, metric, value in measure_history(key):
            wk = iso_week(date)
            if not (wk and WINDOW_START <= wk <= WINDOW_END):
                continue
            cell = weekly.setdefault((key, wk), {})
            # last analysis in the week wins (history is chronological)
            cell[metric] = value
        if i % 25 == 0:
            log.info("…%d/%d projects", i, len(projects))

    out_w = DERIVED / "sonar_weekly.csv"
    metric_cols = METRICS.split(",")
    with open(out_w, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sonar_key", "week"] + metric_cols)
        for (key, wk), vals in sorted(weekly.items()):
            w.writerow([key, wk] + [vals.get(m, "") for m in metric_cols])

    # PR-stage resolution via GitHub Checks API: failed-then-passed before merge
    repos = pd.read_csv(DERIVED / "repos.csv")
    sample = repos[repos["repo"].isin(set(o3_sample()))]["repo"]  # O3 scope (01b)
    pr_rows = []
    for i, repo in enumerate(sample, 1):
        prs = gh_paginate("/repos/%s/pulls" % repo,
                          params={"state": "closed", "sort": "updated",
                                  "direction": "desc"}, max_pages=5)
        merged = [pr for pr in prs if pr.get("merged_at")
                  and WINDOW_START <= pr["merged_at"][:10] <= WINDOW_END]
        for pr in merged:
            commits = gh_paginate("/repos/%s/pulls/%d/commits" % (repo, pr["number"]))
            statuses = []  # (commit_order, conclusion) for sonar/security checks
            for order, c in enumerate(commits):
                r = gh_rest("/repos/%s/commits/%s/check-runs" % (repo, c["sha"]),
                            params={"per_page": 100})
                for run in (r["json"] or {}).get("check_runs", []):
                    if CHECK_NAME_RE.search(run.get("name", "")):
                        statuses.append((order, run.get("conclusion")))
            if not statuses:
                continue
            failed = any(s[1] in ("failure", "action_required") for s in statuses)
            final_pass = max(statuses)[1] == "success"
            pr_rows.append({
                "repo": repo, "pr_number": pr["number"],
                "merged_at": pr["merged_at"], "week": iso_week(pr["merged_at"]),
                "had_security_check": 1,
                "failed_then_passed": int(failed and final_pass),
            })
        if i % 25 == 0:
            log.info("…PR checks %d/%d repos, %d PRs", i, len(sample), len(pr_rows))

    out_p = DERIVED / "sonar_pr_checks.csv"
    with open(out_p, "w", newline="") as f:
        cols = ["repo", "pr_number", "merged_at", "week",
                "had_security_check", "failed_then_passed"]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(pr_rows)

    write_schema(out_w, "Repo(sonar project)-week static-analysis security measures; "
                 "value = last analysis in week.",
                 {"sonar_key": "SonarCloud project key (join to repos via 02 mapping)",
                  "week": "Monday of ISO week",
                  **{m: "SonarCloud metric" for m in metric_cols}},
                 "SonarCloud api/measures/search_history, org=%s." % SONAR_ORG)
    write_schema(out_p, "Merged PRs with Sonar/security check runs; failed_then_passed "
                 "maps to 'issues resolved during the PR process' (pr_stage_fixes).",
                 {"repo": "org/name", "pr_number": "PR", "merged_at": "ISO ts",
                  "week": "merge week", "had_security_check": "1 if any matching check",
                  "failed_then_passed": "1 if check failed at least once and final=pass"},
                 "GitHub Checks API over PR commits; check-name regex: sonar|security. "
                 "NOTE max_pages=5 of closed PRs per repo per run — raise for full pass.")
    print("sonar_weekly=%d pr_checks=%d" % (len(weekly), len(pr_rows)))


if __name__ == "__main__":
    sys.exit(main() or 0)
