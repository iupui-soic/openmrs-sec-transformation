"""Phase 1.2 — Intervention adoption detection (ULTRAPLAN §3.2).

For each active repo, detects first-adoption timestamps with two independent signals
per intervention where possible:
  Signal A = introduction commit of the config file (Commits API, oldest commit on path)
  Signal B = first runtime evidence (first dependabot PR, first Sonar analysis,
             first archetype workflow run, first release with .sha256 asset)

Writes data/derived/interventions.csv + a deterministic 20% verification sample
(interventions_verify_sample.csv) for the R2/R3 manual GitHub-UI check.
"""
from __future__ import annotations

import base64
import csv
import fnmatch
import os
import random
import sys

import pandas as pd

from common import (DERIVED, SONAR_ORG, cached_request, gh_paginate, gh_rest, o3_sample,
                    log, write_schema)

ARCHETYPE_PATTERNS = [p.strip() for p in os.getenv(
    "ARCHETYPE_WORKFLOW_PATTERNS", "security*.yml,*security-archetype*.yml").split(",")]

SONAR_API = "https://sonarcloud.io/api"


# ------------------------------------------------------------ helpers ----

def oldest_commit_for_path(repo, path):
    """(date, html_url) of the commit that introduced `path` (oldest commit touching it)."""
    commits = gh_paginate("/repos/%s/commits" % repo, params={"path": path})
    if not commits:
        return None, None
    c = commits[-1]  # API returns newest-first
    return c["commit"]["author"]["date"], c.get("html_url", "")


def repo_tree(repo, branch):
    r = gh_rest("/repos/%s/git/trees/%s" % (repo, branch), params={"recursive": "1"})
    if r["status"] != 200:
        return []
    return [t["path"] for t in r["json"].get("tree", []) if t["type"] == "blob"]


def file_text(repo, path):
    r = gh_rest("/repos/%s/contents/%s" % (repo, path))
    if r["status"] != 200 or "content" not in r["json"]:
        return ""
    try:
        return base64.b64decode(r["json"]["content"]).decode("utf-8", "replace")
    except Exception:
        return ""


def first_dependabot_pr(repo):
    # Issues API (core 5000/hr budget) instead of /search/issues (30/min — trips
    # secondary rate limits hard across 121 repos). dependabot[bot] authors only PRs,
    # so the oldest issue it created == the first Dependabot PR.
    r = gh_rest("/repos/%s/issues" % repo, params={
        "creator": "dependabot[bot]", "state": "all",
        "sort": "created", "direction": "asc", "per_page": 1})
    items = r["json"] if isinstance(r["json"], list) else []
    if r["status"] == 200 and items:
        return items[0]["created_at"], items[0].get("html_url", "")
    return None, None


def first_workflow_run(repo, workflow_filename):
    base = "/repos/%s/actions/workflows/%s/runs" % (repo, workflow_filename)
    r = gh_rest(base, params={"per_page": 1})
    total = (r["json"] or {}).get("total_count", 0) if r["status"] == 200 else 0
    if not total:
        return None, None
    page = min(total, 1000)  # runs are newest-first; last page (per_page=1) = oldest
    r = gh_rest(base, params={"per_page": 1, "page": page})
    runs = (r["json"] or {}).get("workflow_runs") or []
    if runs:
        return runs[0]["created_at"], runs[0]["html_url"]
    return None, None


def first_sha256_release(repo):
    releases = gh_paginate("/repos/%s/releases" % repo)
    hits = [(rel["created_at"], rel["html_url"]) for rel in releases
            if any(a["name"].endswith(".sha256") for a in rel.get("assets", []))]
    return min(hits) if hits else (None, None)


_SONAR_PROJECTS = None

def sonar_projects():
    """SonarCloud project keys for the org (public API; token not required)."""
    global _SONAR_PROJECTS
    if _SONAR_PROJECTS is None:
        out, page = {}, 1
        while True:
            r = cached_request("GET", SONAR_API + "/components/search_projects",
                               params={"organization": SONAR_ORG, "ps": 500, "p": page})
            comps = (r["json"] or {}).get("components") or []
            for c in comps:
                out[c["key"]] = c["name"]
            if r["status"] != 200 or len(comps) < 500:
                break
            page += 1
        _SONAR_PROJECTS = out
        log.info("SonarCloud org '%s': %d projects", SONAR_ORG, len(out))
    return _SONAR_PROJECTS


def sonar_key_for(repo):
    name = repo.split("/", 1)[1]
    cands = [k for k, v in sonar_projects().items()
             if v.lower() == name.lower() or k.lower().endswith(name.lower())]
    return cands[0] if cands else None


def first_sonar_analysis(repo):
    key = sonar_key_for(repo)
    if not key:
        return None, None
    r = cached_request("GET", SONAR_API + "/project_analyses/search",
                       params={"project": key, "ps": 1, "p": 1})
    total = (r["json"] or {}).get("paging", {}).get("total", 0)
    if not total:
        return None, None
    r = cached_request("GET", SONAR_API + "/project_analyses/search",
                       params={"project": key, "ps": 1, "p": min(total, 10000)})
    an = (r["json"] or {}).get("analyses") or []
    if an:
        return an[0]["date"], "https://sonarcloud.io/project/activity?id=" + key
    return None, None


# ------------------------------------------------ per-repo detection ----

def detect(repo, branch):
    tree = repo_tree(repo, branch or "master")
    if not tree and branch != "main":
        tree = repo_tree(repo, "main")
    workflows = [p for p in tree if p.startswith(".github/workflows/")
                 and p.endswith((".yml", ".yaml"))]
    wf_text = {p: file_text(repo, p) for p in workflows}
    rows = []

    def add(intervention, a_date, a_url, b_date, b_url, method, notes=""):
        dates = [d for d in (a_date, b_date) if d]
        if not dates and not notes:
            return
        rows.append({
            "repo": repo, "intervention": intervention,
            "signal_a_date": a_date or "", "signal_a_evidence_url": a_url or "",
            "signal_b_date": b_date or "", "signal_b_evidence_url": b_url or "",
            "adoption_date": min(dates) if dates else "",
            "detection_method": method, "verified_by": "", "notes": notes,
        })

    # SonarCloud: properties file or sonar step in a workflow; B = first analysis
    sonar_paths = [p for p in tree if p == "sonar-project.properties"]
    sonar_paths += [p for p, t in wf_text.items() if "sonar" in t.lower()]
    a = min((oldest_commit_for_path(repo, p) for p in sonar_paths),
            default=(None, None))
    b = first_sonar_analysis(repo)
    add("sonarcloud", a[0], a[1], b[0], b[1],
        "config:%s + sonar_project_analyses" % (sonar_paths[0] if sonar_paths else "none"))

    # Dependabot: config file; B = first dependabot PR (works even with no config —
    # org-level enablement has no per-repo file)
    dep_paths = [p for p in tree if p in (".github/dependabot.yml",
                                          ".github/dependabot.yaml")]
    a = oldest_commit_for_path(repo, dep_paths[0]) if dep_paths else (None, None)
    b = first_dependabot_pr(repo)
    add("dependabot", a[0], a[1], b[0], b[1],
        "config_file + first_bot_pr",
        "" if dep_paths else "no dependabot.yml (possibly org-level enablement)")

    # Actions security archetype: workflow filename matches pattern; B = first run
    arch = [p for p in workflows
            if any(fnmatch.fnmatch(p.split("/")[-1], pat) for pat in ARCHETYPE_PATTERNS)]
    if arch:
        a = oldest_commit_for_path(repo, arch[0])
        b = first_workflow_run(repo, arch[0].split("/")[-1])
        add("actions_archetype", a[0], a[1], b[0], b[1],
            "workflow_pattern:%s + first_run" % arch[0])

    # SHA-256 release integrity: workflow mentioning sha256; B = first .sha256 asset
    sha_wf = [p for p, t in wf_text.items()
              if "sha256" in t.lower() or "sha-256" in t.lower()]
    a = oldest_commit_for_path(repo, sha_wf[0]) if sha_wf else (None, None)
    b = first_sha256_release(repo)
    add("sha256_release", a[0], a[1], b[0], b[1],
        "ci_sha256_step + first_sha256_asset")

    # Quality gates / branch protection: API exposes current state only (no history)
    r = gh_rest("/repos/%s/branches/%s/protection" % (repo, branch or "master"))
    if r["status"] == 200:
        checks = (r["json"].get("required_status_checks") or {}).get("contexts", [])
        add("quality_gates", None, None, None,
            "https://github.com/%s/settings/branches" % repo,
            "branch_protection_api(current_state_only)",
            "currently required checks: %s — adoption date needs fallback: first PR "
            "blocked-then-fixed by gate (manual / transcripts)" % "; ".join(checks))
    elif r["status"] in (401, 403):
        add("quality_gates", None, None, None, "",
            "branch_protection_api",
            "HTTP %s — token lacks admin scope; use UI/transcripts" % r["status"])

    # Playwright BDD security tests (QA repos): .feature files / playwright config
    pw = [p for p in tree if p.endswith(".feature")
          or p.split("/")[-1].startswith("playwright.config")]
    if pw:
        a = min((oldest_commit_for_path(repo, p) for p in pw[:5]), default=(None, None))
        add("playwright_bdd", a[0], a[1], None, None,
            "feature_or_playwright_config",
            "signal B (first scheduled run -> dashboard) comes from 05_outcomes_dashboard")

    return rows


def main():
    repos = pd.read_csv(DERIVED / "repos.csv")
    repos["class_final"] = repos["class_override"].fillna("").replace("", pd.NA)
    repos["class_final"] = repos["class_final"].fillna(repos["class"])
    sample = repos[repos["repo"].isin(set(o3_sample()))]  # O3 distribution scope (01b)
    log.info("detecting interventions in %d active repos", len(sample))

    all_rows = []
    for i, row in enumerate(sample.itertuples(), 1):
        try:
            all_rows.extend(detect(row.repo, row.default_branch))
        except Exception as e:  # one bad repo must not kill a long mining run
            log.error("%s: %s", row.repo, e)
            all_rows.append({"repo": row.repo, "intervention": "ERROR",
                             "signal_a_date": "", "signal_a_evidence_url": "",
                             "signal_b_date": "", "signal_b_evidence_url": "",
                             "adoption_date": "", "detection_method": "",
                             "verified_by": "", "notes": str(e)[:300]})
        if i % 25 == 0:
            log.info("…%d/%d repos", i, len(sample))

    out = DERIVED / "interventions.csv"
    cols = ["repo", "intervention", "signal_a_date", "signal_a_evidence_url",
            "signal_b_date", "signal_b_evidence_url", "adoption_date",
            "detection_method", "verified_by", "notes"]
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(all_rows)

    # Deterministic 20% sample for independent R2+R3 verification (>=85% agreement gate)
    dated = [r for r in all_rows if r["adoption_date"]]
    rng = random.Random(42)
    ver = rng.sample(dated, max(1, len(dated) // 5)) if dated else []
    vout = DERIVED / "interventions_verify_sample.csv"
    with open(vout, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols + ["r2_verdict", "r3_verdict", "resolution"])
        w.writeheader()
        for r in ver:
            w.writerow({**r, "r2_verdict": "", "r3_verdict": "", "resolution": ""})

    write_schema(
        out,
        "First-adoption timestamps per repo x intervention, two independent signals "
        "(A = config introduction commit, B = first runtime evidence). "
        "adoption_date = min(A, B). ULTRAPLAN §3.2.",
        {"repo": "org/name", "intervention": "sonarcloud|dependabot|actions_archetype|"
         "sha256_release|quality_gates|playwright_bdd|ERROR",
         "signal_a_date": "config-introduction commit date (ISO)",
         "signal_a_evidence_url": "commit URL",
         "signal_b_date": "first runtime evidence date (ISO)",
         "signal_b_evidence_url": "PR/run/release/analysis URL",
         "adoption_date": "min of available signals",
         "detection_method": "how signals were obtained",
         "verified_by": "filled during manual 20% verification",
         "notes": "caveats incl. quality_gates history limitation"},
        "GitHub REST (trees/commits/contents/search/actions/releases/branch-protection) "
        "+ SonarCloud public API (project_analyses). Archetype filename patterns: %s "
        "(TODO confirm with team/transcripts). %d rows; verification sample: %d rows "
        "in %s (seed=42)." % (ARCHETYPE_PATTERNS, len(all_rows), len(ver), vout.name))
    n_dated = len(dated)
    log.info("interventions.csv: %d rows (%d with adoption dates); verify sample %d",
             len(all_rows), n_dated, len(ver))
    print("interventions=%d dated=%d verify_sample=%d -> %s" %
          (len(all_rows), n_dated, len(ver), out))


if __name__ == "__main__":
    sys.exit(main())
