"""01b — Derive the O3 (Reference Application 3.x) distribution repo set from the distro
config. Team's chosen analysis scope: the shipped frontends + the bundled Java/OMOD
backend modules (not all 360 org repos).

Sources (cloned openmrs-distro-referenceapplication @ main):
  distro/distro.properties           -> backend OMOD modules + core war + content packs
  frontend/spa-assemble-config.json  -> @openmrs/esm-*-app frontend packages

Frontend npm packages are resolved to their GitHub repo via the npm registry (many apps
share a monorepo, so the 45 packages collapse to far fewer repos). Output:
  data/derived/o3_sample.csv   repo, source, component, groupId, in_inventory
"""
from __future__ import annotations

import csv
import json
import re
import sys

import pandas as pd

from common import CLONES, DERIVED, cached_request, gh_rest, log

DISTRO = CLONES / "openmrs__openmrs-distro-referenceapplication"


def backend_components():
    props = {}
    for line in (DISTRO / "distro" / "distro.properties").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            props[k] = v
    groupids = {k[len("omod."):-len(".groupId")]: v
                for k, v in props.items()
                if k.startswith("omod.") and k.endswith(".groupId")}
    out = []  # (repo, component_key, groupId)
    for k in props:
        if not k.startswith("omod."):
            continue
        name = k[len("omod."):]
        if name.endswith(".groupId") or name.endswith(".type"):
            continue
        out.append(("openmrs/openmrs-module-%s" % name, k,
                    groupids.get(name, "org.openmrs.module")))
    out.append(("openmrs/openmrs-core", "war.openmrs", "org.openmrs"))
    for k in props:
        if k.startswith("content."):
            out.append(("openmrs/openmrs-content-%s" % k[len("content."):], k, "content"))
    return out


def _canonical_repo(owner_repo):
    """Resolve via the GitHub API; follows renames to the live canonical full_name
    (e.g. openmrs-esm-dispensing -> openmrs-esm-dispensing-app)."""
    r = gh_rest("/repos/%s" % owner_repo)
    if r["status"] == 200:
        return (r["json"] or {}).get("full_name", owner_repo)
    return owner_repo


def frontend_components():
    cfg = json.loads((DISTRO / "frontend" / "spa-assemble-config.json").read_text())
    out = []  # (repo_or_'', pkg)
    for pkg in cfg.get("frontendModules", {}):
        r = cached_request("GET", "https://registry.npmjs.org/%s" % pkg)
        repo = ""
        if r["status"] == 200:
            rep = (r["json"] or {}).get("repository") or {}
            url = rep.get("url", "") if isinstance(rep, dict) else str(rep)
            # strip scheme noise, .git suffix and #fragment/?query/sub-paths
            m = re.search(r"github\.com[:/]+([^/\s]+)/([^/\s#?]+?)(?:\.git)?(?:[#?/].*)?$", url)
            if m:
                repo = _canonical_repo("%s/%s" % (m.group(1), m.group(2)))
        if not repo:
            log.warning("npm %s: repo unresolved (HTTP %s)", pkg, r["status"])
        out.append((repo, pkg))
    return out


def main():
    inv = set(pd.read_csv(DERIVED / "repos.csv")["repo"])
    rows = {}

    def reconcile(repo):
        """Match against the live inventory, toggling the -app suffix that npm's
        repository field and the actual repo name disagree on for a few apps."""
        if not repo or repo in inv:
            return repo
        for cand in (repo + "-app", repo[:-4] if repo.endswith("-app") else None):
            if cand and cand in inv:
                return cand
        return repo

    def add(repo, source, component, groupId=""):
        key = repo or ("UNRESOLVED:" + component)
        rows.setdefault(key, {"repo": repo, "source": source,
                              "component": component, "groupId": groupId})

    for repo, key, gid in backend_components():
        add(repo, "backend_omod", key, gid)
    for repo, pkg in frontend_components():
        add(reconcile(repo), "frontend_esm", pkg)
    add("openmrs/openmrs-distro-referenceapplication", "distro", "distro")

    out = DERIVED / "o3_sample.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["repo", "source", "component",
                                          "groupId", "in_inventory"])
        w.writeheader()
        for r in sorted(rows.values(), key=lambda x: (x["source"], x["repo"])):
            r["in_inventory"] = 1 if r["repo"] in inv else 0
            w.writerow(r)

    in_inv = sorted({r["repo"] for r in rows.values() if r["repo"] and r["in_inventory"]})
    external = sorted({r["repo"] for r in rows.values() if r["repo"] and not r["in_inventory"]})
    unresolved = [r["component"] for r in rows.values() if not r["repo"]]
    log.info("O3 sample: %d unique repos in openmrs inventory", len(in_inv))
    print("=== O3 distribution sample ===")
    print("unique repos IN openmrs inventory:", len(in_inv))
    print("  frontend repos:", len({r["repo"] for r in rows.values()
                                    if r["source"] == "frontend_esm" and r["in_inventory"]}))
    print("  backend repos :", len({r["repo"] for r in rows.values()
                                    if r["source"] == "backend_omod" and r["in_inventory"]}))
    print("external (not openmrs-org, e.g. bahmni):", external)
    print("unresolved frontend pkgs:", unresolved)
    print("->", out)


if __name__ == "__main__":
    sys.exit(main() or 0)
