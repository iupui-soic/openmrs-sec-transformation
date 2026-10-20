# Schema: dependabot_alerts.csv

Alert-level Dependabot data (de-identified; no dependency names beyond ecosystem).

Generated: 2026-06-11T23:13:36.107658+00:00

| column | description |
|---|---|
| `repo` | repo |
| `severity` | severity |
| `state` | state |
| `ecosystem` | ecosystem |
| `created_at` | created_at |
| `fixed_at` | fixed_at |
| `dismissed_at` | dismissed_at |
| `mttr_days` | mttr_days |

## Provenance

REST /repos/{repo}/dependabot/alerts?state=all. CAVEAT: created_at = detection time, partly a visibility effect of Dependabot itself; MTTR/fix events are primary outcomes (ULTRAPLAN §4.1).
