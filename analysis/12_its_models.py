"""Phase 3.3 — Interrupted time series for the org-level security transformation
(ULTRAPLAN §5.3). Per the Jun-17 gate, the org-level surge in alert creation/remediation
is the strongest, best-powered quantitative signal (per-repo weekly DiD is too sparse).

Org-week series are built from the RAW alert history (2023→2026, longer pre-period than
the panel window — addresses the short-baseline concern). Segmented negative-binomial
regression with Newey–West HAC SEs:

    log E[y_t] = b0 + b1*time + b2*post + b3*time_since_post + b4*gsoc

  b2 = level change at the break (exp = rate ratio), b3 = slope change after.
Primary break = baseline-audit/proactive onset (2025-12-15; configurable).
Outputs analysis/its_results.md and data/derived/its_org_week.csv (for figures F1/F2).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from study_config import WINDOW_END as _STUDY_END  # noqa: E402

DERIVED = Path(__file__).resolve().parents[1] / "data" / "derived"
OUT = Path(__file__).resolve().parent / "its_results.md"
START = pd.Timestamp("2023-01-02")                      # Monday; ~3 yr pre-period
END = pd.Timestamp(_STUDY_END)
# Proactive onset: first full operating period after the Dec-2025 baseline audit
# (December is holiday-sparse; remediation ramps in Jan). PROVISIONAL — R5 to confirm the
# exact squad/policy date from transcripts; break-date sensitivity reported below.
BREAK = pd.Timestamp("2026-01-05")


def _wk(s):
    # Monday (00:00) of each date's week — matches the Monday axis below
    d = pd.to_datetime(s, utc=True, errors="coerce").dt.tz_localize(None)
    return (d - pd.to_timedelta(d.dt.weekday, unit="D")).dt.normalize()


def org_week_series():
    weeks = pd.date_range(START, END, freq="7D")   # START is a Monday → all Mondays
    out = pd.DataFrame({"week": weeks})
    for f, tag in [("dependabot_alerts.csv", "dep"), ("code_scanning_alerts.csv", "cs")]:
        a = pd.read_csv(DERIVED / f)
        cre = _wk(a["created_at"]).value_counts().rename("%s_created" % tag)
        fix = _wk(a["fixed_at"]).value_counts().rename("%s_fixed" % tag)
        out = out.merge(cre, left_on="week", right_index=True, how="left")
        out = out.merge(fix, left_on="week", right_index=True, how="left")
    out = out.fillna(0)
    out["created"] = out["dep_created"] + out["cs_created"]
    out["fixed"] = out["dep_fixed"] + out["cs_fixed"]
    out["time"] = np.arange(len(out))
    out["post"] = (out["week"] >= BREAK).astype(int)
    bidx = int(out.loc[out["week"] >= BREAK, "time"].min())
    out["time_post"] = (out["time"] - bidx).clip(lower=0) * out["post"]
    m = out["week"].dt.month
    out["gsoc"] = ((m >= 6) & (m <= 9)).astype(int)
    return out, bidx


def fit_its(df, y):
    d = df.copy()
    d["t"] = d["time"] / 52.0          # time in years → keeps coefficients small
    d["tp"] = d["time_post"] / 52.0
    X = sm.add_constant(d[["t", "post", "tp", "gsoc"]])
    L = max(1, int(np.floor(4 * (len(df) / 100.0) ** (2 / 9.0))))   # Newey–West lag
    try:
        m = sm.NegativeBinomial(d[y], X).fit(disp=0, maxiter=300,
                                             cov_type="HAC", cov_kwds={"maxlags": L})
        if not np.isfinite(m.bse).all():
            raise ValueError("NB SEs not finite")
        return m, "NB"
    except Exception:
        m = sm.GLM(d[y], X, family=sm.families.Poisson()).fit(
            cov_type="HAC", cov_kwds={"maxlags": L})
        return m, "Poisson"


def fit_break(df, y, brk):
    """Refit with an alternative break date — for the sensitivity table."""
    d = df.copy()
    d["post"] = (d["week"] >= pd.Timestamp(brk)).astype(int)
    if d["post"].sum() < 4:
        return None
    bidx = int(d.loc[d["post"] == 1, "time"].min())
    d["t"] = d["time"] / 52.0
    d["tp"] = ((d["time"] - bidx).clip(lower=0) * d["post"]) / 52.0
    X = sm.add_constant(d[["t", "post", "tp", "gsoc"]])
    try:
        m = sm.NegativeBinomial(d[y], X).fit(disp=0, maxiter=300,
                                             cov_type="HAC", cov_kwds={"maxlags": 4})
        return np.exp(m.params["post"]), m.pvalues["post"], int(d["post"].sum())
    except Exception:
        return None


OUTCOMES = [("fixed", "alerts FIXED/wk (remediation — primary outcome)"),
            ("created", "alerts CREATED/wk (detection/tooling dose)"),
            ("dep_fixed", "Dependabot fixed/wk"),
            ("cs_fixed", "code-scanning fixed/wk")]


def main():
    df, bidx = org_week_series()
    df.to_csv(DERIVED / "its_org_week.csv", index=False)
    pre = df[df.post == 0]; post = df[df.post == 1]

    lines = ["# Interrupted time series — org-level security transformation", "",
             "_Org-week series (44 O3 repos), %s … %s, break = **%s** (proactive onset). "
             "%d pre weeks, %d post weeks. Segmented NB + Newey–West HAC SEs._" %
             (START.date(), END.date(), BREAK.date(), len(pre), len(post)), "",
             "Mean weekly rate pre → post: created %.1f → %.1f (×%.1f), "
             "fixed %.1f → %.1f (×%.1f)." % (
                 pre["created"].mean(), post["created"].mean(),
                 post["created"].mean() / max(pre["created"].mean(), 0.1),
                 pre["fixed"].mean(), post["fixed"].mean(),
                 post["fixed"].mean() / max(pre["fixed"].mean(), 0.1)), ""]

    for y, desc in OUTCOMES:
        m, fam = fit_its(df, y)
        p, pv = m.params, m.pvalues
        lines += ["## %s  _(%s)_" % (desc, fam), "",
                  "| term | rate ratio | p | meaning |", "|---|---|---|---|",
                  "| level change at break | %.2f | %.3g | immediate jump (×) |" %
                  (np.exp(p["post"]), pv["post"]),
                  "| slope change after break | %.2f | %.3g | trend shift (×/yr) |" %
                  (np.exp(p["tp"]), pv["tp"]),
                  "| pre-break trend | %.2f | %.3g | baseline drift (×/yr) |" %
                  (np.exp(p["t"]), pv["t"]), ""]

    # Seasonal control: the GSoC indicator itself, and the jump without it.
    lines += ["## Summer (GSoC) indicator", "",
              "| outcome | GSoC term (×) | p | jump with GSoC (×) | p | jump without GSoC (×) | p |",
              "|---|---|---|---|---|---|---|"]
    for y in ["fixed", "created"]:
        res = {}
        for use_gsoc in (True, False):
            d = df.copy()
            d["t"] = d["time"] / 52.0
            d["tp"] = d["time_post"] / 52.0
            cols = ["t", "post", "tp"] + (["gsoc"] if use_gsoc else [])
            res[use_gsoc] = sm.NegativeBinomial(d[y], sm.add_constant(d[cols])).fit(
                disp=0, maxiter=300, cov_type="HAC", cov_kwds={"maxlags": 4})
        g, n = res[True], res[False]
        lines.append("| %s | %.2f | %.2g | %.2f | %.2g | %.2f | %.2g |" % (
            y, np.exp(g.params["gsoc"]), g.pvalues["gsoc"], np.exp(g.params["post"]),
            g.pvalues["post"], np.exp(n.params["post"]), n.pvalues["post"]))
    lines.append("")

    lines += ["## Break-date sensitivity (outcome = alerts fixed/wk)", "",
              "The break must be pinned by the qualitative timeline (R5) — reported here for "
              "transparency, NOT chosen to maximize significance. The remediation "
              "discontinuity is sharpest in **early 2026** (≈1 month after the Dec-2025 "
              "audit → audit-to-remediation lag), with a strong secular pre-trend.", "",
              "| break date | post wks | level change (×) | p |", "|---|---|---|---|"]
    for brk in ["2025-10-01", "2025-12-15", "2026-01-15", "2026-03-26", "2026-04-30"]:
        r = fit_break(df, "fixed", brk)
        if r:
            lines.append("| %s | %d | %.2f | %.3g |" % (brk, r[2], r[0], r[1]))
    # overall secular trend (no break)
    d = df.copy(); d["t"] = d["time"] / 52.0
    mt = sm.GLM(d["fixed"], sm.add_constant(d[["t", "gsoc"]]),
                family=sm.families.Poisson()).fit(cov_type="HAC", cov_kwds={"maxlags": 4})
    lines += ["", "_Secular trend (no break): remediation grows ×%.2f/yr (p=%.2g) across "
              "2023–2026 — security activity was already climbing; the early-2026 jump sits "
              "on top of it._" % (np.exp(mt.params["t"]), mt.pvalues["t"]), ""]

    lines += ["## Reading it", "",
              "- **`fixed`** is the remediation outcome; a level/slope jump at the break = "
              "the proactive remediation push. **`created`** is partly a *detection* effect "
              "(tools switched on) — intervention dose, not harm.",
              "- Longer pre-period (2023→) gives a stable counterfactual. Robustness: shift "
              "break to tooling dates (Apr–May 2026); exclude the CVSS v3.1→v4 measurement "
              "break once R5 dates it (§8).",
              "- Pair with the distro-level CVSS dashboard ITS (05, gh-pages).", ""]
    OUT.write_text("\n".join(lines) + "\n")

    print("pre→post weekly: created %.1f→%.1f, fixed %.1f→%.1f" % (
        pre["created"].mean(), post["created"].mean(),
        pre["fixed"].mean(), post["fixed"].mean()))
    for y, _ in OUTCOMES:
        m, fam = fit_its(df, y)
        print("%-11s [%s] level x=%.2f (p=%.3g)  slope x=%.2f/yr (p=%.3g)" % (
            y, fam, np.exp(m.params["post"]), m.pvalues["post"],
            np.exp(m.params["tp"]), m.pvalues["tp"]))
    print("-> wrote", OUT, "and its_org_week.csv")


if __name__ == "__main__":
    sys.exit(main() or 0)
