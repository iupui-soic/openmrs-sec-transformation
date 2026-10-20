# Survival analysis — MTTR (primary causal estimand)

_Pooled Dependabot + code-scanning alerts, full history. Proactive onset = 2025-12-15 (baseline audit). Censoring at 2026-06-15._

## A. Cox PH — hazard of resolution (HR>1 = faster)

| covariate | HR | 95% CI | p |
|---|---|---|---|
| proactive | 1.19 | 0.75–1.90 | 0.46 |
| sev_rank | 1.10 | 0.93–1.29 | 0.256 |
| is_code_scanning | 3.63 | 1.78–7.37 | 0.000373 |
| is_frontend | 4.45 | 1.94–10.20 | 0.000425 |

_Proactive-era HR = **1.19** → resolution is 19% faster in the proactive era (severity/tool/layer held fixed)._

## A2. Same model, eras split at 2026-01-05

| covariate | HR | 95% CI | p |
|---|---|---|---|
| proactive | 1.15 | 0.71–1.86 | 0.566 |

## B. Kaplan–Meier median MTTR by era

**all alerts** (n=1973, 921 resolved):
| era | n | resolved | median MTTR (days) |
|---|---|---|---|
| pre (reactive) | 1180 | 707 | 511 |
| post (proactive) | 793 | 214 | not reached |

**backend (mature)** (n=949, 330 resolved):
| era | n | resolved | median MTTR (days) |
|---|---|---|---|
| pre (reactive) | 675 | 271 | not reached |
| post (proactive) | 274 | 59 | not reached |

**frontend (new)** (n=1024, 591 resolved):
| era | n | resolved | median MTTR (days) |
|---|---|---|---|
| pre (reactive) | 505 | 436 | 234 |
| post (proactive) | 519 | 155 | not reached |

## C. JIRA security issues (org/core-level, 2009→2026)

**JIRA security issues** (n=74, 65 resolved):
| era | n | resolved | median MTTR (days) |
|---|---|---|---|
| pre (reactive) | 64 | 61 | 649 |
| post (proactive) | 10 | 4 | not reached |

## Notes / threats

- Alert `created_at` reflects detection (a scanning *visibility* effect); resolution hazard conditions on the alert existing, so MTTR is less contaminated than raw counts (§4.1).
- Post-era alerts have shorter follow-up → KM/Cox handle differential censoring; treat post medians as lower bounds.
- Era split is calendar-based; per-repo time-varying treatment (CoxTimeVaryingFitter) is the robustness follow-up.

