# Schema: covariates_weekly.csv

Repo-week activity covariates. Author identities pseudonymized at ingestion (mapping in data/private/ only); derived data carries counts only.

Generated: 2026-06-11T23:14:32.535046+00:00

| column | description |
|---|---|
| `repo` | repo |
| `week` | week |
| `commits` | commits |
| `unique_authors` | unique_authors |
| `loc_added` | loc_added |
| `loc_deleted` | loc_deleted |
| `prs_opened` | prs_opened |
| `prs_merged` | prs_merged |
| `repo_age_weeks` | repo_age_weeks |
| `primary_language` | primary_language |
| `gsoc_period` | gsoc_period |

## Provenance

git log --numstat --no-merges on local clones + GitHub PR API. GSoC dummy periods: [('2025-06-02', '2025-09-01'), ('2026-06-01', '2026-06-15')] (verify against events.csv).
