# GO / NO-GO memo — RQ3 causal design

_From panel.parquet — 44 repos × 89 weeks, O3 distribution scope. Window 2024-10-07 … 2026-06-15._

## 1. Treatment timing (identification within the window)

*within_window* adopters drive staggered DiD; *always_treated* (adopted before the window) carry no pre-period; *never_treated* are clean controls.

| intervention | total treated | within-window | always-treated | never | win-cohorts | win SD (wks) | staggered DiD? |
|---|---|---|---|---|---|---|---|
| sonarcloud | 29 | **29** | 0 | 15 | 3 | 5.8 | no |
| dependabot | 21 | **7** | 14 | 23 | 4 | 29.9 | YES |
| actions_archetype | 0 | **0** | 0 | 44 | 0 | 0.0 | no |
| sha256_release | 1 | **1** | 0 | 43 | 1 | 0.0 | no |
| quality_gates | 0 | **0** | 0 | 44 | 0 | 0.0 | no |
| playwright_bdd | 12 | **4** | 8 | 32 | 3 | 14.4 | no |

## 2. Weekly-count outcome density (why count-DiD is hard)

| outcome | mean/repo-week | % nonzero repo-weeks |
|---|---|---|
| `alerts_fixed` | 0.1210 | 2.5% |
| `alerts_created` | 0.2485 | 8.5% |
| `cs_fixed` | 0.0335 | 1.2% |
| `cs_created` | 0.0432 | 1.5% |

_Counts are very sparse (≈98% of repo-weeks are zero on the primary outcome) → weekly-count DiD/ITS is underpowered for moderate effects._

## 3. Minimal detectable effect — weekly `alerts_fixed` (Poisson DiD proxy, 200 sims)

| intervention | MDE (rate ratio) | result |
|---|---|---|
| sonarcloud | — | underpowered for weekly counts |
| dependabot | — | underpowered for weekly counts |
| actions_archetype | — | underpowered for weekly counts |
| sha256_release | — | underpowered for weekly counts |
| quality_gates | — | underpowered for weekly counts |
| playwright_bdd | — | underpowered for weekly counts |

## 4. The well-powered alternative: alert-level MTTR (survival)

Weekly counts are sparse, but resolution times are abundant at the alert level:

| source | resolved alerts (with fixed_at) |
|---|---|
| dependabot | 709 |
| code | 212 |

Cox time-varying MTTR (treatment status at alert time) is powered by these 921+ events — this is the right home for the Dependabot/code-scanning causal claim, not weekly-count DiD.

## 5. Recommendation

- **Primary causal estimand → alert-level MTTR survival** (Cox, time-varying treatment): well-powered (Dependabot 709 + code-scanning 212 resolved alerts).
- **Staggered DiD (counts):** `dependabot` — limited by sparse counts + mostly pre-window adoption; report as event-study with wide CIs, not the headline.
- **ITS (segmented):** SonarCloud (near-simultaneous) + the distro-level CVSS dashboard series (org-week) — the cleanest quantitative trend evidence.
- **Descriptive longitudinal:** the remaining interventions.

**Verdict: conditional GO** — RQ3 stands as a *longitudinal* causal study anchored on **MTTR survival + ITS**, with count-DiD as supportive/exploratory. This is the ULTRAPLAN §8 fallback, reached deliberately: the per-repo weekly-count DiD is underpowered, but MTTR and org-level ITS are not. The qualitative process model (RQ1/RQ2) carries the mechanism story. **Do NOT headline staggered-DiD-on-counts.**

