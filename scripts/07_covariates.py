"""Phase 2.5 — Repo-week covariates (ULTRAPLAN §4.5).

Per repo-week: commits, unique authors (count only — identities pseudonymized and
never written to derived data), PRs opened/merged, LOC churn, plus static repo
covariates (age, language) and a GSoC-period dummy.

Source: local clones (git log --numstat) for commits/authors/churn — one clone per
active repo under clones/ (gitignored) — and the GitHub PR API for PR counts.
Writes data/derived/covariates_weekly.csv.
"""
from __future__ import annotations

import csv
import subprocess
import sys
from collections import defaultdict
from datetime import datetime

import pandas as pd

from common import (CLONES, DERIVED, GITHUB_TOKEN, WINDOW_END, WINDOW_START,
                    gh_paginate, iso_week, log, o3_sample, pseudonymize, write_schema)

# GSoC coding periods overlapping the window (events.csv carries exact org dates).
# The 2026 period is truncated at the study end; its real end date must be set
# from the GSoC 2026 timeline before the window is extended past it.
GSOC_PERIODS = [("2025-06-02", "2025-09-01"), ("2026-06-01", WINDOW_END)]


def sh(args, cwd=None):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True,
                          text=True).stdout


def clone_or_update(repo):
    CLONES.mkdir(exist_ok=True)
    dest = CLONES / repo.replace("/", "__")
    url = ("https://x-access-token:%s@github.com/%s.git" % (GITHUB_TOKEN, repo)
           if GITHUB_TOKEN else "https://github.com/%s.git" % repo)
    if dest.exists():
        sh(["git", "fetch", "--all", "--quiet"], cwd=dest)
    else:
        # full clone needed for --numstat churn; blob-less clones refetch on demand
        sh(["git", "clone", "--quiet", url, str(dest)])
    return dest


def git_weekly(repo):
    """commits, unique authors, LOC churn per week from git log --numstat."""
    dest = clone_or_update(repo)
    out = sh(["git", "log", "--numstat", "--no-merges",
              "--since=" + WINDOW_START, "--until=" + WINDOW_END,
              "--format=@%H|%aI|%aE"], cwd=dest)
    weeks = defaultdict(lambda: {"commits": 0, "authors": set(),
                                 "loc_added": 0, "loc_deleted": 0})
    week = None
    for line in out.splitlines():
        if line.startswith("@"):
            _sha, date, email = line[1:].split("|", 2)
            week = iso_week(date)
            if week:
                weeks[week]["commits"] += 1
                weeks[week]["authors"].add(pseudonymize(email))
        elif line.strip() and week:
            parts = line.split("\t")
            if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
                weeks[week]["loc_added"] += int(parts[0])
                weeks[week]["loc_deleted"] += int(parts[1])
    return weeks


def pr_weekly(repo):
    """PRs opened/merged per week (REST, paginated, cached)."""
    opened, merged = defaultdict(int), defaultdict(int)
    prs = gh_paginate("/repos/%s/pulls" % repo,
                      params={"state": "all", "sort": "created",
                              "direction": "desc"}, max_pages=20)
    for pr in prs:
        cw = iso_week(pr["created_at"])
        if cw and WINDOW_START <= cw <= WINDOW_END:
            opened[cw] += 1
        if pr.get("merged_at"):
            mw = iso_week(pr["merged_at"])
            if mw and WINDOW_START <= mw <= WINDOW_END:
                merged[mw] += 1
    return opened, merged


def gsoc_dummy(week):
    return int(any(a <= week <= b for a, b in GSOC_PERIODS))


def main():
    repos = pd.read_csv(DERIVED / "repos.csv")
    sample = repos[repos["repo"].isin(set(o3_sample()))]  # O3 distribution scope (01b)
    rows = []
    for i, r in enumerate(sample.itertuples(), 1):
        try:
            weeks = git_weekly(r.repo)
            opened, merged = pr_weekly(r.repo)
        except Exception as e:
            log.error("%s: %s", r.repo, e)
            continue
        age_origin = datetime.fromisoformat(str(r.created_at).replace("Z", "+00:00"))
        all_weeks = set(weeks) | set(opened) | set(merged)
        for wk in sorted(all_weeks):
            g = weeks.get(wk, {"commits": 0, "authors": set(),
                               "loc_added": 0, "loc_deleted": 0})
            wk_dt = datetime.fromisoformat(wk + "T00:00:00+00:00")
            rows.append({
                "repo": r.repo, "week": wk,
                "commits": g["commits"], "unique_authors": len(g["authors"]),
                "loc_added": g["loc_added"], "loc_deleted": g["loc_deleted"],
                "prs_opened": opened.get(wk, 0), "prs_merged": merged.get(wk, 0),
                "repo_age_weeks": max(0, int((wk_dt - age_origin).days // 7)),
                "primary_language": r.primary_language,
                "gsoc_period": gsoc_dummy(wk),
            })
        if i % 10 == 0:
            log.info("…covariates %d/%d repos", i, len(sample))

    out = DERIVED / "covariates_weekly.csv"
    cols = ["repo", "week", "commits", "unique_authors", "loc_added", "loc_deleted",
            "prs_opened", "prs_merged", "repo_age_weeks", "primary_language",
            "gsoc_period"]
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    write_schema(out, "Repo-week activity covariates. Author identities pseudonymized "
                 "at ingestion (mapping in data/private/ only); derived data carries "
                 "counts only.",
                 {c: c for c in cols},
                 "git log --numstat --no-merges on local clones + GitHub PR API. "
                 "GSoC dummy periods: %s (verify against events.csv)." % GSOC_PERIODS)
    print("covariate_rows=%d -> %s" % (len(rows), out))


if __name__ == "__main__":
    sys.exit(main() or 0)
