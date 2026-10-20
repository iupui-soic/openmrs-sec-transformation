# Schema: repos.csv

Full repository inventory for in-scope orgs (openmrs). Activity filter per ULTRAPLAN §3.1: >=1 merged PR 2025-04-01..2026-06-15.

Generated: 2026-06-11T21:54:33.446047+00:00

| column | description |
|---|---|
| `repo` | org/name |
| `visibility` | public|private |
| `class` | core|module|o3_frontend|distro|qa/test|infra/docs|other (name-pattern heuristic) |
| `class_override` | manual override; final class = override if non-empty |
| `primary_language` | GitHub primary language |
| `created_at` | repo creation timestamp (ISO) |
| `default_branch` | default branch name |
| `pushed_at` | last push timestamp (ISO) |
| `archived` | 1 if archived |
| `merged_prs_in_window` | merged PRs in activity window (GraphQL path only; counted over 50 most recently updated merged PRs) |
| `active_flag` | 1 = in analysis sample |
| `active_method` | merged_pr_graphql | pushed_at_proxy (token-less fallback) |

## Provenance

GitHub GraphQL organization.repositories. Reconciliation vs project's '339 repositories' figure: enumerated 360 (delta +21) — document explanation here after review. Token present: True.
