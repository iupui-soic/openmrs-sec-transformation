"""Shared utilities for the mining pipeline (ULTRAPLAN §2 rules).

- All API calls cached to data/raw/ keyed by endpoint+params hash; re-runs hit cache.
- Exponential backoff on 403/429 secondary rate limits.
- Tokens only via env vars; nothing identifying written to data/derived/.
- Every derived CSV gets a sidecar *.schema.md (write_schema).
- Pseudonymization at ingestion time (pseudonymize); mapping lives in data/private/.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DERIVED = ROOT / "data" / "derived"
PRIVATE = ROOT / "data" / "private"
CLONES = ROOT / "clones"

load_dotenv(ROOT / ".env")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") or None
SONAR_TOKEN = os.getenv("SONAR_TOKEN") or None
SONAR_ORG = os.getenv("SONAR_ORG", "openmrs")
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "https://openmrs.atlassian.net")
NVD_API_KEY = os.getenv("NVD_API_KEY") or None
GITHUB_ORGS = [o.strip() for o in os.getenv("GITHUB_ORGS", "openmrs").split(",") if o.strip()]

from study_config import ACTIVITY_END, ACTIVITY_START, WINDOW_END, WINDOW_START  # noqa: E402,F401

GITHUB_API = "https://api.github.com"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stderr,
)
log = logging.getLogger("ose")


def _cache_path(key_parts):
    digest = hashlib.sha256(json.dumps(key_parts, sort_keys=True).encode()).hexdigest()
    host = key_parts[0].split("/")[2] if "://" in key_parts[0] else "misc"
    d = RAW / host
    d.mkdir(parents=True, exist_ok=True)
    return d / (digest + ".json")


def cached_request(method, url, params=None, headers=None, json_body=None,
                   force=False, ok_statuses=(200,), max_attempts=8):
    """HTTP request with on-disk cache and rate-limit-aware exponential backoff.

    Returns dict: {status, json, headers, fetched_at, from_cache}.
    Non-retryable non-OK statuses (404, 451, 410) are cached too so re-runs skip them.
    """
    key = [url, method, params or {}, json_body or {}]
    path = _cache_path(key)
    if path.exists() and not force:
        out = json.loads(path.read_text())
        out["from_cache"] = True
        return out

    attempt = 0
    while True:
        attempt += 1
        resp = requests.request(method, url, params=params, headers=headers,
                                json=json_body, timeout=60)
        retryable = resp.status_code in (429, 500, 502, 503, 504) or (
            resp.status_code == 403 and "rate limit" in resp.text.lower()
        )
        if retryable and attempt < max_attempts:
            wait = min(2 ** attempt, 120)
            reset = resp.headers.get("X-RateLimit-Reset")
            retry_after = resp.headers.get("Retry-After")
            if retry_after:
                wait = max(wait, int(retry_after) + 1)
            elif reset and resp.headers.get("X-RateLimit-Remaining") == "0":
                wait = max(wait, int(reset) - int(time.time()) + 2)
            log.warning("HTTP %s on %s — backing off %ss (attempt %s)",
                        resp.status_code, url, wait, attempt)
            time.sleep(wait)
            continue
        break

    try:
        body = resp.json()
    except ValueError:
        body = {"_text": resp.text[:100000]}
    out = {
        "status": resp.status_code,
        "json": body,
        "headers": {k: v for k, v in resp.headers.items()
                    if k.lower() in ("link", "x-ratelimit-remaining", "etag")},
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "from_cache": False,
    }
    if resp.status_code in ok_statuses or resp.status_code in (404, 410, 451):
        path.write_text(json.dumps(out))
    return out


# ---------------------------------------------------------------- GitHub ----

def gh_headers():
    h = {"Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28"}
    if GITHUB_TOKEN:
        h["Authorization"] = "Bearer " + GITHUB_TOKEN
    return h


def gh_rest(path, params=None, force=False, ok_statuses=(200,)):
    """Single GitHub REST call. `path` like '/repos/openmrs/openmrs-core'."""
    return cached_request("GET", GITHUB_API + path, params=params,
                          headers=gh_headers(), force=force, ok_statuses=ok_statuses)


def gh_paginate(path, params=None, max_pages=100, force=False):
    """Paginate a GitHub REST list endpoint; concatenates pages. Cached per page."""
    params = dict(params or {})
    params.setdefault("per_page", 100)
    items = []
    for page in range(1, max_pages + 1):
        params["page"] = page
        r = gh_rest(path, params=params, force=force)
        if r["status"] != 200:
            log.warning("gh_paginate %s page %s -> HTTP %s", path, page, r["status"])
            break
        batch = r["json"]
        if isinstance(batch, dict):  # e.g. workflow runs: {total_count, items-ish key}
            for k in ("items", "workflow_runs", "workflows", "artifacts", "check_runs"):
                if k in batch:
                    batch = batch[k]
                    break
        if not batch:
            break
        items.extend(batch)
        if len(batch) < params["per_page"]:
            break
    return items


def gh_paginate_linked(path, params=None, max_pages=200, force=False):
    """Paginate via the Link 'next' header — for cursor endpoints (e.g. Dependabot
    alerts) that REJECT the `page` param with HTTP 400. Each cursor page is cached
    separately. Stops without raising on 403/404 so disabled/forbidden repos yield []."""
    params = dict(params or {})
    params.setdefault("per_page", 100)
    url = GITHUB_API + path
    items = []
    for i in range(max_pages):
        r = (gh_rest(path, params=params, force=force) if i == 0
             else cached_request("GET", url, headers=gh_headers(), force=force))
        if r["status"] != 200:
            if r["status"] not in (403, 404):
                log.warning("gh_paginate_linked %s -> HTTP %s", url, r["status"])
            break
        batch = r["json"]
        if not isinstance(batch, list) or not batch:
            break
        items.extend(batch)
        hdrs = {k.lower(): v for k, v in (r.get("headers") or {}).items()}
        m = re.search(r'<([^>]+)>;\s*rel="next"', hdrs.get("link", ""))
        if not m:
            break
        url, params = m.group(1), None  # cursor now lives in `url`
    return items


def gh_graphql(query, variables=None, force=False):
    """GitHub GraphQL call (requires token). Cached by query+variables hash."""
    if not GITHUB_TOKEN:
        raise RuntimeError("GraphQL requires GITHUB_TOKEN")
    r = cached_request("POST", GITHUB_API + "/graphql",
                       headers=gh_headers(),
                       json_body={"query": query, "variables": variables or {}},
                       force=force)
    if r["status"] != 200 or "errors" in (r["json"] or {}):
        raise RuntimeError("GraphQL error: %s" % json.dumps(r["json"])[:500])
    return r["json"]["data"]


# ---------------------------------------------------- pseudonymization ----

def pseudonymize(identifier):
    """Map a username/name to P1..Pn. Mapping persists ONLY in data/private/."""
    if not identifier:
        return ""
    PRIVATE.mkdir(parents=True, exist_ok=True)
    mpath = PRIVATE / "pseudonyms.json"
    mapping = json.loads(mpath.read_text()) if mpath.exists() else {}
    if identifier not in mapping:
        mapping[identifier] = "P%d" % (len(mapping) + 1)
        mpath.write_text(json.dumps(mapping, indent=1))
    return mapping[identifier]


# ----------------------------------------------------------- schemas ----

def write_schema(csv_path, description, columns, provenance):
    """Sidecar *.schema.md for every derived CSV (ULTRAPLAN §2)."""
    csv_path = Path(csv_path)
    lines = ["# Schema: %s" % csv_path.name, "", description, "",
             "Generated: %s" % datetime.now(timezone.utc).isoformat(), "",
             "| column | description |", "|---|---|"]
    for col, desc in columns.items():
        lines.append("| `%s` | %s |" % (col, desc))
    lines += ["", "## Provenance", "", provenance, ""]
    csv_path.with_suffix(".schema.md").write_text("\n".join(lines))


def iso_week(ts):
    """Normalize an ISO timestamp string to the Monday of its week (panel grain).
    Tolerates the SonarCloud-style `+0000` offset (no colon), which py3.9
    fromisoformat rejects, and falls back to the date part if all else fails."""
    if not ts:
        return None
    s = str(ts).strip().replace("Z", "+00:00")
    s = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", s)  # +0000 -> +00:00
    try:
        d = datetime.fromisoformat(s).date()
    except ValueError:
        d = datetime.fromisoformat(s[:10]).date()    # YYYY-MM-DD portion
    monday = d.toordinal() - d.weekday()
    return datetime.fromordinal(monday).date().isoformat()


def o3_sample():
    """The O3 (Reference Application 3.x) distribution analysis set — repos derived by
    01b_o3_sample.py from the distro config (data/derived/o3_sample.csv): the bundled
    Java/OMOD backend modules + esm frontends + the distro. The team's chosen scope
    (~44 repos) instead of all 360. Falls back to [] if 01b hasn't been run."""
    import csv as _csv
    p = DERIVED / "o3_sample.csv"
    repos = set()
    if p.exists():
        with open(p) as f:
            for row in _csv.DictReader(f):
                if row.get("repo") and row.get("in_inventory") == "1":
                    repos.add(row["repo"])
    return sorted(repos)
