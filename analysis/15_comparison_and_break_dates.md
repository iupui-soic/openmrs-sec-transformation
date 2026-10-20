# Comparison repos, placebo start dates, start-date grid

_Output of analysis/15_comparison_and_break_dates.py. June data. Weeks 2023-01-02 .. 2026-06-15; onset 2026-01-05._

Comparison repos: 49 selected by the paper's rule; 9 with no cached Dependabot data (counted as zero alerts): openmrs-module-dhisconnector, openmrs-module-oauth2login, openmrs-esm-template-app, openmrs-module-authenticationui, openmrs-esm-form-engine-lib, openmrs-esm-patient-communications, openmrs-module-drools, openmrs-module-patientqueueui, openmrs-esm-patient-growth-chart-app.
Comparison alerts: 584 found, 154 fixed; latest created_at 2026-06-10T19:54:08Z.

## Per-repo weekly rates (pre → post 2026-01-05)

| group | alert source | repos | found pre → post (×) | fixed pre → post (×) |
|---|---|---|---|---|
| program | all (Dependabot + code scanning) | 44 | 0.121 → 0.742 (×6.1) | 0.071 → 0.372 (×5.2) |
| program | Dependabot only | 44 | 0.095 → 0.661 (×6.9) | 0.051 → 0.302 (×5.9) |
| comparison | Dependabot only | 49 | 0.038 → 0.179 (×4.7) | 0.018 → 0.010 (×0.6) |

## Group × time model (between-group test) and pre-trend test

Ratio for g:post = how much larger the onset jump is in program repos than in comparison repos. Pre-trend ratio = difference in pre-onset yearly growth (1 = parallel).

| comparison | outcome | model | g:post ratio [95% CI] | p | g:slope-after ratio | p | pre-trend g:t ratio | p |
|---|---|---|---|---|---|---|---|---|
| A: program all vs comparison Dependabot | fixed | NB | 188.26 [1.60, 22091.89] | 0.0312 | 0.00 | 0.344 | 0.46 | 0.284 |
| A: program all vs comparison Dependabot | found | NB | 4.34 [0.35, 54.21] | 0.254 | 0.01 | 0.273 | 0.99 | 0.983 |
| B: Dependabot only, both groups | fixed | NB | 452.65 [2.38, 86223.29] | 0.0224 | 0.00 | 0.294 | 0.39 | 0.228 |
| B: Dependabot only, both groups | found | NB | 5.47 [0.38, 77.69] | 0.21 | 0.01 | 0.294 | 0.94 | 0.855 |

## In-time placebo (program, all alerts, fixed/wk; same model as Table IV)

| break | post wks | ratio | 95% CI | p |
|---|---|---|---|---|
| 2024-06-03 | 107 | 0.28 | 0.08–0.91 | 0.0351 |
| 2025-06-02 | 55 | 0.41 | 0.11–1.52 | 0.181 |

## Break-date grid: every Monday 2025-11-03 .. 2026-03-02

| break (Monday) | post wks | ratio | 95% CI | p |
|---|---|---|---|---|
| 2025-11-03 | 33 | 0.65 | 0.11–3.79 | 0.631 |
| 2025-11-10 | 32 | 0.86 | 0.15–5.00 | 0.871 |
| 2025-11-17 | 31 | 1.10 | 0.18–6.64 | 0.916 |
| 2025-11-24 | 30 | 1.16 | 0.16–8.48 | 0.886 |
| 2025-12-01 | 29 | 1.36 | 0.17–10.57 | 0.769 |
| 2025-12-08 | 28 | 1.75 | 0.25–12.04 | 0.57 |
| 2025-12-15 | 27 | 1.88 | 0.25–14.27 | 0.541 |
| 2025-12-22 | 26 | 2.40 | 0.42–13.68 | 0.324 |
| 2025-12-29 | 25 | 3.07 | 0.75–12.47 | 0.118 |
| 2026-01-05 | 24 | 3.84 | 1.28–11.52 | 0.0166 |
| 2026-01-12 | 23 | 4.64 | 1.83–11.72 | 0.00119 |
| 2026-01-19 | 22 | 5.59 | 2.25–13.88 | 0.000206 |
| 2026-01-26 | 21 | 6.45 | 2.36–17.62 | 0.000279 |
| 2026-02-02 | 20 | 4.54 | 1.84–11.24 | 0.00105 |
| 2026-02-09 | 19 | 2.20 | 0.65–7.42 | 0.205 |
| 2026-02-16 | 18 | 2.07 | 0.57–7.49 | 0.266 |
| 2026-02-23 | 17 | 2.00 | 0.52–7.72 | 0.316 |
| 2026-03-02 | 16 | 2.32 | 0.74–7.26 | 0.15 |
