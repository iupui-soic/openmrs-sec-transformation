"""Phase 2.3 — Dashboard longitudinal scans (ULTRAPLAN §4.3).

The CVSS dashboard repo receives scan results via GitHub Actions pushes — its git
history is a free longitudinal record. Clones the repo, walks commits on the default
branch, parses result JSON/CSV files at each commit, and emits a long-format series:

  data/derived/dashboard_series.csv  commit_date, week, file, module, severity, metric, value

DASHBOARD_REPO must be set in .env (TODO: confirm exact repo with team). The parser is
deliberately generic: JSON dicts/lists and CSVs are flattened to (module, severity,
metric, value) where recognizable; unrecognized payloads are logged, not dropped silently.
CVSS v3.1->v4 break handling happens downstream (12_its_models reads events.csv).
"""
from __future__ import annotations

import csv
import fnmatch
import io
import json
import os
import subprocess
import sys

from common import CLONES, DERIVED, GITHUB_TOKEN, iso_week, log, write_schema

DASHBOARD_REPO = os.getenv("DASHBOARD_REPO", "")
RESULT_GLOBS = [g.strip() for g in
                os.getenv("DASHBOARD_RESULT_GLOBS", "*.json,*.csv").split(",")]
SEVERITY_KEYS = ("critical", "high", "medium", "low", "none")


def sh(args, cwd=None):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True,
                          text=True).stdout


def clone(repo):
    CLONES.mkdir(exist_ok=True)
    dest = CLONES / repo.replace("/", "__")
    url = ("https://x-access-token:%s@github.com/%s.git" % (GITHUB_TOKEN, repo)
           if GITHUB_TOKEN else "https://github.com/%s.git" % repo)
    if dest.exists():
        sh(["git", "fetch", "--all", "--quiet"], cwd=dest)
    else:
        sh(["git", "clone", "--quiet", url, str(dest)])
    return dest


def parse_payload(name, text):
    """Yield (module, severity, metric, value) tuples from a results file."""
    if name.endswith(".json"):
        try:
            data = json.loads(text)
        except ValueError:
            return
        def walk(node, module=""):
            if isinstance(node, dict):
                for k, v in node.items():
                    kl = str(k).lower()
                    if kl in SEVERITY_KEYS and isinstance(v, (int, float)):
                        yield (module, kl, "count", v)
                    elif isinstance(v, (int, float)) and any(
                            t in kl for t in ("cvss", "score", "vuln", "finding")):
                        yield (module, "", kl, v)
                    elif isinstance(v, (dict, list)):
                        for t in walk(v, module or str(k)):
                            yield t
            elif isinstance(node, list):
                for item in node:
                    for t in walk(item, module):
                        yield t
        for t in walk(data):
            yield t
    elif name.endswith(".csv"):
        try:
            rdr = csv.DictReader(io.StringIO(text))
            for row in rdr:
                lower = {k.lower(): v for k, v in row.items() if k}
                module = lower.get("module") or lower.get("component") or \
                    lower.get("repo") or lower.get("project") or ""
                sev = (lower.get("severity") or "").lower()
                for k, v in lower.items():
                    try:
                        val = float(v)
                    except (TypeError, ValueError):
                        continue
                    if any(t in k for t in ("cvss", "score", "count", "vuln", "finding")):
                        yield (module, sev, k, val)
        except csv.Error:
            return


def main():
    if not DASHBOARD_REPO:
        log.error("DASHBOARD_REPO not set in .env — confirm the dashboard repo with "
                  "the team (ULTRAPLAN §4.3) and re-run.")
        return 1
    dest = clone(DASHBOARD_REPO)
    commits = sh(["git", "log", "--format=%H,%aI", "--reverse"], cwd=dest)
    rows, unparsed = [], set()
    commit_list = [c.split(",", 1) for c in commits.strip().splitlines()]
    log.info("%s: %d commits to walk", DASHBOARD_REPO, len(commit_list))

    for sha, date in commit_list:
        files = sh(["git", "ls-tree", "-r", "--name-only", sha], cwd=dest).splitlines()
        targets = [f for f in files
                   if any(fnmatch.fnmatch(f.split("/")[-1], g) for g in RESULT_GLOBS)]
        for f in targets:
            try:
                text = sh(["git", "show", "%s:%s" % (sha, f)], cwd=dest)
            except subprocess.CalledProcessError:
                continue
            found = False
            for module, sev, metric, value in parse_payload(f, text):
                rows.append({"commit": sha[:10], "commit_date": date,
                             "week": iso_week(date), "file": f, "module": module,
                             "severity": sev, "metric": metric, "value": value})
                found = True
            if not found:
                unparsed.add(f)

    out = DERIVED / "dashboard_series.csv"
    cols = ["commit", "commit_date", "week", "file", "module",
            "severity", "metric", "value"]
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    if unparsed:
        log.warning("unparsed result files (inspect and extend parse_payload): %s",
                    sorted(unparsed)[:20])

    write_schema(out, "Long-format longitudinal CVSS scan series reconstructed from "
                 "the dashboard repo's git history (each Actions push = one snapshot).",
                 {c: c for c in cols},
                 "git history of %s, result globs %s. CVSS v3.1->v4 measurement break "
                 "must be modeled/truncated downstream using events.csv. Unparsed "
                 "files this run: %d." % (DASHBOARD_REPO, RESULT_GLOBS, len(unparsed)))
    print("series_rows=%d commits=%d -> %s" % (len(rows), len(commit_list), out))


if __name__ == "__main__":
    sys.exit(main() or 0)
