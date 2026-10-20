# Schema: panel.parquet

Analysis panel, grain repo x ISO-week (Mondays), window 2024-10-01..2026-06-15.

Generated: 2026-06-12T01:49:53.328157+00:00

| column | description |
|---|---|
| `repo` | org/name |
| `week` | Monday of ISO week |
| `class` | repo class (manual override applied) |
| `treat_<i>` | 1 from adoption week onward |
| `cohort_<i>` | adoption week (NaN = never treated) |
| `event_time_<i>` | weeks since adoption (negative = pre) |
| `…` | outcome and covariate columns per source schemas |

## Provenance

Join of dependabot_weekly, sonar_weekly (+pr_checks), covariates_weekly, interventions. See missingness_report.md.
