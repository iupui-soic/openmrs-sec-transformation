# Schema: code_scanning_alerts.csv

Alert-level code-scanning (CodeQL/etc.) findings; de-identified.

Generated: 2026-06-12T01:49:52.333067+00:00

| column | description |
|---|---|
| `repo` | repo |
| `severity` | severity |
| `category` | category |
| `tool` | tool |
| `state` | state |
| `created_at` | created_at |
| `fixed_at` | fixed_at |
| `dismissed_at` | dismissed_at |
| `mttr_days` | mttr_days |

## Provenance

REST /repos/{repo}/code-scanning/alerts (all states). MTTR=fixed-created; counts partly a detection effect — fix events/MTTR are primary.
