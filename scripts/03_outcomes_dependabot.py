"""Phase 2.1 — Dependency vulnerabilities + MTTR (ULTRAPLAN §4.1).

Pulls Dependabot alerts (requires GITHUB_TOKEN with security_events scope), writes:
  data/derived/dependabot_alerts.csv   alert-level: severity, created/fixed/dismissed, MTTR
  data/derived/dependabot_weekly.csv   repo-week: alerts_created/fixed/open, by severity

Encoded caveat (per plan): alert created_at reflects *detection*, which Dependabot
itself enables -> counts are partly visibility effects. MTTR and fix events are the
primary outcomes; counts are descriptive only.
"""
from __future__ import annotations

import csv
import sys
from datetime import datetime, timedelta

import pandas as pd

from common import (DERIVED, GITHUB_TOKEN, WINDOW_END, WINDOW_START,
                    gh_paginate_linked, iso_week, log, o3_sample, write_schema)

SEVERITIES = ["low", "medium", "high", "critical"]


def fetch_alerts(repo):
    # NO `state` filter: the Dependabot state enum is open/fixed/dismissed/
    # auto_dismissed — there is NO "all", and passing state=all returns []. Omitting
    # state returns alerts in EVERY state (open + fixed + dismissed), which is what we want.
    return gh_paginate_linked("/repos/%s/dependabot/alerts" % repo,
                              params={"per_page": 100})


def main():
    if not GITHUB_TOKEN:
        log.error("GITHUB_TOKEN with security_events scope is required for alerts")
        return 1
    repos = pd.read_csv(DERIVED / "repos.csv")
    sample = repos[repos["repo"].isin(set(o3_sample()))]["repo"]  # O3 scope (01b)

    alert_rows = []
    for i, repo in enumerate(sample, 1):
        for a in fetch_alerts(repo):
            sev = (a.get("security_advisory") or {}).get("severity", "")
            created, fixed = a.get("created_at"), a.get("fixed_at")
            dismissed = a.get("dismissed_at")
            mttr = ""
            if created and fixed:
                dt = (datetime.fromisoformat(fixed.replace("Z", "+00:00")) -
                      datetime.fromisoformat(created.replace("Z", "+00:00")))
                mttr = round(dt.total_seconds() / 86400, 2)
            alert_rows.append({
                "repo": repo, "alert_number": a.get("number"),
                "severity": sev, "state": a.get("state"),
                "ecosystem": ((a.get("dependency") or {}).get("package") or {})
                              .get("ecosystem", ""),
                "created_at": created or "", "fixed_at": fixed or "",
                "dismissed_at": dismissed or "", "mttr_days": mttr,
            })
        if i % 25 == 0:
            log.info("…%d/%d repos, %d alerts", i, len(sample), len(alert_rows))

    out_a = DERIVED / "dependabot_alerts.csv"
    cols = ["repo", "severity", "state", "ecosystem",
            "created_at", "fixed_at", "dismissed_at", "mttr_days"]
    with open(out_a, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(alert_rows)

    # repo-week aggregation: created / fixed events by week; open = interval overlap
    df = pd.DataFrame(alert_rows)
    weekly = {}
    weeks = pd.date_range(WINDOW_START, WINDOW_END, freq="W-MON").date

    def bump(repo, week, col, n=1):
        key = (repo, str(week))
        weekly.setdefault(key, {c: 0 for c in agg_cols})
        weekly[key][col] += n

    agg_cols = (["alerts_created", "alerts_fixed", "alerts_open"] +
                ["alerts_created_%s" % s for s in SEVERITIES] +
                ["alerts_fixed_%s" % s for s in SEVERITIES])
    if not df.empty:
        for r in df.itertuples():
            sev = r.severity if r.severity in SEVERITIES else "low"
            cw = iso_week(r.created_at) if r.created_at else None
            fw = iso_week(r.fixed_at) if r.fixed_at else None
            if cw and WINDOW_START <= cw <= WINDOW_END:
                bump(r.repo, cw, "alerts_created")
                bump(r.repo, cw, "alerts_created_%s" % sev)
            if fw and WINDOW_START <= fw <= WINDOW_END:
                bump(r.repo, fw, "alerts_fixed")
                bump(r.repo, fw, "alerts_fixed_%s" % sev)
            # open in every week between created and fixed/dismissed/window-end
            if r.created_at:
                start = datetime.fromisoformat(iso_week(r.created_at)).date()
                end_ts = r.fixed_at or r.dismissed_at or WINDOW_END
                end = datetime.fromisoformat(iso_week(end_ts)).date()
                for wk in weeks:
                    if start <= wk <= end:
                        bump(r.repo, wk, "alerts_open")

    out_w = DERIVED / "dependabot_weekly.csv"
    with open(out_w, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["repo", "week"] + agg_cols)
        for (repo, week), vals in sorted(weekly.items()):
            w.writerow([repo, week] + [vals[c] for c in agg_cols])

    write_schema(out_a, "Alert-level Dependabot data (de-identified; no dependency "
                 "names beyond ecosystem).",
                 {c: c for c in cols},
                 "REST /repos/{repo}/dependabot/alerts?state=all. CAVEAT: created_at "
                 "= detection time, partly a visibility effect of Dependabot itself; "
                 "MTTR/fix events are primary outcomes (ULTRAPLAN §4.1).")
    write_schema(out_w, "Repo-week Dependabot aggregates, %s..%s, weeks = Mondays."
                 % (WINDOW_START, WINDOW_END),
                 {"repo": "org/name", "week": "Monday of ISO week",
                  **{c: "count" for c in agg_cols}},
                 "Aggregated from dependabot_alerts.csv; open = created<=week<=resolved.")
    print("alerts=%d weekly_rows=%d -> %s" % (len(alert_rows), len(weekly), out_w))


if __name__ == "__main__":
    sys.exit(main() or 0)
