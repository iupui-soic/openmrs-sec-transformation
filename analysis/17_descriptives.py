"""Descriptive numbers for the comparison repos (paper, RQ3).

  - Median repository age and median merged pull requests, program vs comparison repos.
  - The largest single week of comparison-repo fixes and the repo behind it.
  - Alert data for the program repos by source and tool (repos, alerts, fixed).
  - PGP signatures on the backend modules OpenMRS hosts.

Inputs: data/derived/repos.csv, o3_sample.csv, comparison_repos.csv,
        comparison_dependabot_alerts.csv, dependabot_alerts.csv,
        code_scanning_alerts.csv, o3_backend_artifacts.csv
Output: analysis/17_descriptives.md
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from study_config import WINDOW_END  # noqa: E402

DERIVED = ROOT / "data" / "derived"
OUT = Path(__file__).resolve().parent / "17_descriptives.md"


def main():
    repos = pd.read_csv(DERIVED / "repos.csv")
    program = set(pd.read_csv(DERIVED / "o3_sample.csv").query("in_inventory == 1").repo)
    comparison = set(pd.read_csv(DERIVED / "comparison_repos.csv").repo)
    end = pd.Timestamp(WINDOW_END, tz="UTC")
    repos["age_years"] = (end - pd.to_datetime(repos.created_at, utc=True)).dt.days / 365.25

    lines = ["# Program vs comparison repos: descriptives", "",
             "| group | repos | median age (years) | median merged PRs in activity window |",
             "|---|---|---|---|"]
    for name, ids in [("program", program), ("comparison", comparison)]:
        g = repos[repos.repo.isin(ids)]
        lines.append("| %s | %d | %.1f | %.0f |" % (name, len(g), g.age_years.median(),
                                                      g.merged_prs_in_window.median()))

    a = pd.read_csv(DERIVED / "comparison_dependabot_alerts.csv")
    a = a[a.fixed_at.notna()].copy()
    fixed = pd.to_datetime(a.fixed_at, utc=True).dt.tz_localize(None)
    a["week"] = (fixed - pd.to_timedelta(fixed.dt.weekday, unit="D")).dt.normalize()
    by_week = a.groupby("week").size()
    top = by_week.idxmax()
    by_repo = a[a.week == top].groupby("repo").size().sort_values(ascending=False)
    lines += ["", "Largest week of comparison-repo fixes: week of %s, %d fixes; %d of them in %s." % (
        top.date(), by_week.max(), by_repo.iloc[0], by_repo.index[0])]
    dep = pd.read_csv(DERIVED / "dependabot_alerts.csv")
    cs = pd.read_csv(DERIVED / "code_scanning_alerts.csv")
    lines += ["", "## Alert data, program repos (whole history to the study end)", "",
              "| source | repos | alerts | fixed (has a fix date) |", "|---|---|---|---|"]
    rows = [("Dependabot", dep)] + [("Code scanning: %s" % k, g) for k, g in cs.groupby("tool")] \
        + [("Code scanning, all", cs)]
    for name, g in rows:
        lines.append("| %s | %d | %d | %d |" % (name, g.repo.nunique(), len(g), g.fixed_at.notna().sum()))
    art = pd.read_csv(DERIVED / "o3_backend_artifacts.csv")
    hosted = art[art.maven_hosted == 1]
    lines += ["", "Backend modules hosted by OpenMRS with a PGP signature: %d of %d; "
              "modules hosted elsewhere: %d, signed: %d." % (
                  int(hosted.pgp_signed.sum()), len(hosted),
                  int((art.maven_hosted == 0).sum()), int(art[art.maven_hosted == 0].pgp_signed.sum()))]
    OUT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
