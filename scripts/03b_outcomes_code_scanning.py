"""Phase 2.1b — GitHub code-scanning alerts.

A GitHub Security source beyond Dependabot (ULTRAPLAN §4 extension, added after the
team flagged them as primary signals of the SAST/disclosure transformation):

  data/derived/code_scanning_alerts.csv   alert-level: severity, tool, state, MTTR
  data/derived/code_scanning_weekly.csv   repo-week: created/fixed/open by severity

Code-scanning alerts need the `repo`/`security_events` scope; repos without code scanning
return HTTP 404 (recorded as no-coverage, not an error). MTTR/fix events are the primary
outcomes; raw counts are partly a detection/visibility effect (same caveat as Dependabot).
"""
from __future__ import annotations

import csv
import sys
from datetime import datetime

import pandas as pd

from common import (DERIVED, GITHUB_TOKEN, WINDOW_END, WINDOW_START,
                    gh_paginate_linked, iso_week, log, o3_sample, write_schema)

SEVERITIES = ["low", "medium", "high", "critical"]


def _mttr(created, end):
    if not (created and end):
        return ""
    d = (datetime.fromisoformat(end.replace("Z", "+00:00")) -
         datetime.fromisoformat(created.replace("Z", "+00:00")))
    return round(d.total_seconds() / 86400, 2)


def code_scanning(sample):
    rows = []
    for i, repo in enumerate(sample, 1):
        for a in gh_paginate_linked("/repos/%s/code-scanning/alerts" % repo,
                                    params={"per_page": 100}):
            rule = a.get("rule") or {}
            sev = (rule.get("security_severity_level")
                   or rule.get("severity") or "").lower()
            rows.append({
                "repo": repo, "number": a.get("number"),
                "rule_id": rule.get("id", ""), "severity": sev,
                # CodeQL ships security AND quality queries; security rules carry a
                # security_severity_level. This split is the specificity/placebo test.
                "category": "security" if rule.get("security_severity_level") else "quality",
                "tool": (a.get("tool") or {}).get("name", ""),
                "state": a.get("state"),
                "created_at": a.get("created_at") or "",
                "fixed_at": a.get("fixed_at") or "",
                "dismissed_at": a.get("dismissed_at") or "",
                "mttr_days": _mttr(a.get("created_at"), a.get("fixed_at")),
            })
        if i % 25 == 0:
            log.info("…code-scanning %d/%d repos, %d alerts", i, len(sample), len(rows))
    return rows




def weekly(alert_rows):
    cats = ["sec", "qual"]  # security vs non-security CodeQL rules — the placebo split
    agg_cols = (["cs_created", "cs_fixed", "cs_open"] +
                ["cs_created_%s" % s for s in SEVERITIES] +
                ["cs_fixed_%s" % s for s in SEVERITIES] +
                ["cs_%s_%s" % (cat, ev) for cat in cats
                 for ev in ("created", "fixed", "open")])
    weekly = {}
    weeks = pd.date_range(WINDOW_START, WINDOW_END, freq="W-MON").date

    def bump(repo, week, col):
        weekly.setdefault((repo, str(week)), {c: 0 for c in agg_cols})[col] += 1

    for r in alert_rows:
        sev = r["severity"] if r["severity"] in SEVERITIES else "low"
        cat = "sec" if r.get("category") == "security" else "qual"
        cw = iso_week(r["created_at"]) if r["created_at"] else None
        fw = iso_week(r["fixed_at"]) if r["fixed_at"] else None
        if cw and WINDOW_START <= cw <= WINDOW_END:
            bump(r["repo"], cw, "cs_created"); bump(r["repo"], cw, "cs_created_%s" % sev)
            bump(r["repo"], cw, "cs_%s_created" % cat)
        if fw and WINDOW_START <= fw <= WINDOW_END:
            bump(r["repo"], fw, "cs_fixed"); bump(r["repo"], fw, "cs_fixed_%s" % sev)
            bump(r["repo"], fw, "cs_%s_fixed" % cat)
        if r["created_at"]:
            start = datetime.fromisoformat(iso_week(r["created_at"])).date()
            end_ts = r["fixed_at"] or r["dismissed_at"] or WINDOW_END
            end = datetime.fromisoformat(iso_week(end_ts)).date()
            for wk in weeks:
                if start <= wk <= end:
                    bump(r["repo"], wk, "cs_open")
                    bump(r["repo"], wk, "cs_%s_open" % cat)
    return agg_cols, weekly


def main():
    if not GITHUB_TOKEN:
        log.error("GITHUB_TOKEN required (code-scanning needs repo/security_events scope)")
        return 1
    repos = pd.read_csv(DERIVED / "repos.csv")
    sample = repos[repos["repo"].isin(set(o3_sample()))]["repo"].tolist()  # O3 scope (01b)

    cs = code_scanning(sample)
    cols = ["repo", "severity", "category", "tool", "state",
            "created_at", "fixed_at", "dismissed_at", "mttr_days"]
    out_a = DERIVED / "code_scanning_alerts.csv"
    with open(out_a, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(cs)
    write_schema(out_a, "Alert-level code-scanning (CodeQL/etc.) findings; de-identified.",
                 {c: c for c in cols},
                 "REST /repos/{repo}/code-scanning/alerts (all states). MTTR=fixed-created; "
                 "counts partly a detection effect — fix events/MTTR are primary.")

    agg_cols, wk = weekly(cs)
    out_w = DERIVED / "code_scanning_weekly.csv"
    with open(out_w, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["repo", "week"] + agg_cols)
        for (repo, week), v in sorted(wk.items()):
            w.writerow([repo, week] + [v[c] for c in agg_cols])
    write_schema(out_w, "Repo-week code-scanning aggregates, %s..%s." %
                 (WINDOW_START, WINDOW_END),
                 {"repo": "org/name", "week": "Monday of ISO week",
                  **{c: "count" for c in agg_cols}}, "Aggregated from code_scanning_alerts.csv.")


    log.info("code-scanning alerts=%d (repos w/ alerts=%d)",
             len(cs), len({r["repo"] for r in cs}))
    print("cs_alerts=%d cs_weeks=%d" % (len(cs), len(wk)))


if __name__ == "__main__":
    sys.exit(main() or 0)
