# Interrupted time series — org-level security transformation

_Org-week series (44 O3 repos), 2023-01-02 … 2026-06-15, break = **2026-01-05** (proactive onset). 157 pre weeks, 24 post weeks. Segmented NB + Newey–West HAC SEs._

Mean weekly rate pre → post: created 5.3 → 32.7 (×6.1), fixed 3.1 → 16.4 (×5.2).

## alerts FIXED/wk (remediation — primary outcome)  _(NB)_

| term | rate ratio | p | meaning |
|---|---|---|---|
| level change at break | 3.84 | 0.0166 | immediate jump (×) |
| slope change after break | 0.11 | 0.214 | trend shift (×/yr) |
| pre-break trend | 1.56 | 0.0718 | baseline drift (×/yr) |

## alerts CREATED/wk (detection/tooling dose)  _(NB)_

| term | rate ratio | p | meaning |
|---|---|---|---|
| level change at break | 4.85 | 0.000344 | immediate jump (×) |
| slope change after break | 0.39 | 0.525 | trend shift (×/yr) |
| pre-break trend | 1.31 | 0.0096 | baseline drift (×/yr) |

## Dependabot fixed/wk  _(NB)_

| term | rate ratio | p | meaning |
|---|---|---|---|
| level change at break | 6.22 | 0.00728 | immediate jump (×) |
| slope change after break | 0.04 | 0.2 | trend shift (×/yr) |
| pre-break trend | 1.49 | 0.204 | baseline drift (×/yr) |

## code-scanning fixed/wk  _(NB)_

| term | rate ratio | p | meaning |
|---|---|---|---|
| level change at break | 0.68 | 0.629 | immediate jump (×) |
| slope change after break | 5.22 | 0.4 | trend shift (×/yr) |
| pre-break trend | 2.03 | 0.0119 | baseline drift (×/yr) |

## Break-date sensitivity (outcome = alerts fixed/wk)

The break must be pinned by the qualitative timeline (R5) — reported here for transparency, NOT chosen to maximize significance. The remediation discontinuity is sharpest in **early 2026** (≈1 month after the Dec-2025 audit → audit-to-remediation lag), with a strong secular pre-trend.

| break date | post wks | level change (×) | p |
|---|---|---|---|
| 2025-10-01 | 37 | 0.40 | 0.2 |
| 2025-12-15 | 27 | 1.88 | 0.541 |
| 2026-01-15 | 22 | 5.59 | 0.000206 |
| 2026-03-26 | 12 | 2.39 | 0.0375 |
| 2026-04-30 | 7 | 1.70 | 0.264 |

_Secular trend (no break): remediation grows ×1.97/yr (p=1.9e-05) across 2023–2026 — security activity was already climbing; the early-2026 jump sits on top of it._

## Reading it

- **`fixed`** is the remediation outcome; a level/slope jump at the break = the proactive remediation push. **`created`** is partly a *detection* effect (tools switched on) — intervention dose, not harm.
- Longer pre-period (2023→) gives a stable counterfactual. Robustness: shift break to tooling dates (Apr–May 2026); exclude the CVSS v3.1→v4 measurement break once R5 dates it (§8).
- Pair with the distro-level CVSS dashboard ITS (05, gh-pages).

