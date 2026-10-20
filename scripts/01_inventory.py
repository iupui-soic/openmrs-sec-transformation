"""Phase 1.1 — Repo inventory (ULTRAPLAN §3.1).

Enumerates all repos in the in-scope GitHub orgs, classifies them, applies the
activity filter (>=1 merged PR Apr 2025 - Jun 2026), writes data/derived/repos.csv.

With GITHUB_TOKEN: GraphQL enumeration incl. private repos + merged-PR activity check.
Without token: public REST fallback; activity approximated by pushed_at (flagged in
`active_method` so the run can be upgraded later without changing the schema).
"""
from __future__ import annotations

import csv
import re
import sys

from common import (ACTIVITY_END, ACTIVITY_START, DERIVED, GITHUB_ORGS,
                    GITHUB_TOKEN, gh_graphql, gh_paginate, log, write_schema)

EXPECTED_COUNT = 339  # project's published figure; reconcile in schema notes


def classify(name, language):
    n = name.lower()
    if n == "openmrs-core":
        return "core"
    if n.startswith("openmrs-esm-") or n.startswith("esm-"):
        return "o3_frontend"
    if n.startswith("openmrs-module-"):
        return "module"
    if "distro" in n or n.startswith("openmrs-distribution"):
        return "distro"
    if re.search(r"(^|-)(qa|test|e2e|uitest|contrib-qa)(-|$)", n) or "qaframework" in n:
        return "qa/test"
    if re.search(r"(docs?|wiki|website|guide|infra|ansible|terraform|puppet|ci|"
                 r"jenkins|docker|helm|k8s|contrib)", n):
        return "infra/docs"
    return "other"


REPO_FIELDS_QL = """
  name isPrivate isArchived createdAt pushedAt
  primaryLanguage { name }
  defaultBranchRef { name }
"""


def fetch_org_graphql(org):
    repos, cursor = [], None
    q = """
    query($org:String!, $cursor:String) {
      organization(login:$org) {
        repositories(first:100, after:$cursor) {
          pageInfo { hasNextPage endCursor }
          nodes { %s }
        }
      }
    }""" % REPO_FIELDS_QL
    while True:
        data = gh_graphql(q, {"org": org, "cursor": cursor})
        conn = data["organization"]["repositories"]
        repos.extend(conn["nodes"])
        if not conn["pageInfo"]["hasNextPage"]:
            return repos
        cursor = conn["pageInfo"]["endCursor"]


def merged_pr_activity_graphql(org, names):
    """Batched check: any PR merged inside the activity window? 20 repos/query,
    scanning the 50 most recently-updated merged PRs per repo."""
    active = {}
    q_tpl = """
      r%d: repository(owner:"%s", name:"%s") {
        pullRequests(states:[MERGED], first:50,
                     orderBy:{field:UPDATED_AT, direction:DESC}) {
          totalCount nodes { mergedAt }
        }
      }"""
    for i in range(0, len(names), 20):
        chunk = names[i:i + 20]
        body = "".join(q_tpl % (j, org, n) for j, n in enumerate(chunk))
        data = gh_graphql("query {%s}" % body)
        for j, n in enumerate(chunk):
            node = data.get("r%d" % j) or {}
            prs = (node.get("pullRequests") or {})
            merged = [p["mergedAt"] for p in prs.get("nodes", []) if p.get("mergedAt")]
            n_in_window = sum(1 for m in merged
                              if ACTIVITY_START <= m[:10] <= ACTIVITY_END)
            active[n] = (n_in_window, prs.get("totalCount", 0))
        log.info("activity check %s: %d/%d", org, min(i + 20, len(names)), len(names))
    return active


def fetch_org_rest(org):
    items = gh_paginate("/orgs/%s/repos" % org, params={"type": "all"})
    return [{
        "name": r["name"],
        "isPrivate": r["private"],
        "isArchived": r["archived"],
        "createdAt": r["created_at"],
        "pushedAt": r["pushed_at"],
        "primaryLanguage": {"name": r.get("language")},
        "defaultBranchRef": {"name": r.get("default_branch")},
    } for r in items]


def main():
    rows = []
    for org in GITHUB_ORGS:
        if GITHUB_TOKEN:
            repos = fetch_org_graphql(org)
            activity = merged_pr_activity_graphql(org, [r["name"] for r in repos])
            method = "merged_pr_graphql"
        else:
            log.warning("No GITHUB_TOKEN: public repos only; activity from pushed_at")
            repos = fetch_org_rest(org)
            activity = {r["name"]: (None, None) for r in repos}
            method = "pushed_at_proxy"
        log.info("%s: %d repos enumerated", org, len(repos))

        for r in repos:
            lang = (r.get("primaryLanguage") or {}).get("name") or ""
            n_merged, _total = activity.get(r["name"], (None, None))
            if n_merged is not None:
                active = int(n_merged > 0)
            else:
                active = int(bool(r["pushedAt"]) and
                             ACTIVITY_START <= r["pushedAt"][:10] <= ACTIVITY_END)
            rows.append({
                "repo": "%s/%s" % (org, r["name"]),
                "visibility": "private" if r["isPrivate"] else "public",
                "class": classify(r["name"], lang),
                "class_override": "",
                "primary_language": lang,
                "created_at": r["createdAt"],
                "default_branch": (r.get("defaultBranchRef") or {}).get("name") or "",
                "pushed_at": r["pushedAt"] or "",
                "archived": int(r["isArchived"]),
                "merged_prs_in_window": "" if n_merged is None else n_merged,
                "active_flag": active,
                "active_method": method,
            })

    out = DERIVED / "repos.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    n, n_active = len(rows), sum(r["active_flag"] for r in rows)
    delta = n - EXPECTED_COUNT
    write_schema(
        out,
        "Full repository inventory for in-scope orgs (%s). Activity filter per "
        "ULTRAPLAN §3.1: >=1 merged PR %s..%s." % (", ".join(GITHUB_ORGS),
                                                   ACTIVITY_START, ACTIVITY_END),
        {
            "repo": "org/name",
            "visibility": "public|private",
            "class": "core|module|o3_frontend|distro|qa/test|infra/docs|other (name-pattern heuristic)",
            "class_override": "manual override; final class = override if non-empty",
            "primary_language": "GitHub primary language",
            "created_at": "repo creation timestamp (ISO)",
            "default_branch": "default branch name",
            "pushed_at": "last push timestamp (ISO)",
            "archived": "1 if archived",
            "merged_prs_in_window": "merged PRs in activity window (GraphQL path only; "
                                    "counted over 50 most recently updated merged PRs)",
            "active_flag": "1 = in analysis sample",
            "active_method": "merged_pr_graphql | pushed_at_proxy (token-less fallback)",
        },
        "GitHub %s. Reconciliation vs project's '%d repositories' figure: "
        "enumerated %d (delta %+d) — document explanation here after review. "
        "Token present: %s." % (
            "GraphQL organization.repositories" if GITHUB_TOKEN else "REST /orgs/{org}/repos (public only)",
            EXPECTED_COUNT, n, delta, bool(GITHUB_TOKEN)),
    )
    log.info("repos.csv: %d repos (%d active) — expected ~%d (delta %+d)",
             n, n_active, EXPECTED_COUNT, delta)
    print("repos=%d active=%d delta_vs_339=%+d -> %s" % (n, n_active, delta, out))


if __name__ == "__main__":
    sys.exit(main())
