# Schema: dependabot_weekly.csv

Repo-week Dependabot aggregates, 2024-10-01..2026-06-15, weeks = Mondays.

Generated: 2026-06-11T23:13:36.107754+00:00

| column | description |
|---|---|
| `repo` | org/name |
| `week` | Monday of ISO week |
| `alerts_created` | count |
| `alerts_fixed` | count |
| `alerts_open` | count |
| `alerts_created_low` | count |
| `alerts_created_medium` | count |
| `alerts_created_high` | count |
| `alerts_created_critical` | count |
| `alerts_fixed_low` | count |
| `alerts_fixed_medium` | count |
| `alerts_fixed_high` | count |
| `alerts_fixed_critical` | count |

## Provenance

Aggregated from dependabot_alerts.csv; open = created<=week<=resolved.
