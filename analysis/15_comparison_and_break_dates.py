"""Comparison repos, placebo start dates, and the start-date grid (paper, RQ3).

Produces the numbers behind Table V (per-repo rates, program vs comparison repos),
the pre-trend test, the two placebo start dates (2024-06-03, 2025-06-02), and the
start-date grid (every Monday 2025-11-03 .. 2026-03-02) in the start-date table.
This code was written for the SEIP revision; the specification below was fixed
before running and not tuned afterwards:

Data (June cache only; no network calls)
  - Program group: the 44 O3 repos, alerts from data/derived/dependabot_alerts.csv
    and code_scanning_alerts.csv (same inputs as analysis/12_its_models.py).
  - Comparison group: the 49 repos selected by the paper's rule (module or
    o3_frontend class, not archived, active_flag == 1, not in o3_sample.csv),
    Dependabot alerts from data/derived/comparison_dependabot_alerts.csv,
    exported from the June API cache. No code-scanning alerts were collected for
    these repos. 9 of the 49 have no alert data (comparison_repos.csv,
    has_alert_data = 0) and count as zero alerts (denominator stays 49).
  - Weeks: Mondays 2023-01-02 .. study end (study_config.WINDOW_END).
    A "found" alert counts in the week of created_at, a "fixed" alert in the
    week of fixed_at (dismissals are not fixes), as in 12_its_models.py.

Rates (Table V): mean weekly count / number of repos, pre (< 2026-01-05) vs post.

Group x time model (stacked two-group weekly series, negative binomial,
offset = log(number of repos), HAC-panel SEs with 4 lags):
    log E[y] = b0 + b1*g + b2*t + b3*post + b4*tp + b5*gsoc
                  + b6*g:t + b7*g:post + b8*g:tp + log(n_repos)
  g = 1 for program repos; t = years since 2023-01-02; post = week >= 2026-01-05;
  tp = years since the break (0 before); gsoc = June-September.
  Between-group test of the onset = b7 (difference in level shift).
  Pre-trend test: pre-period only, log E[y] = a0 + a1*g + a2*t + a3*gsoc + a4*g:t
  + offset; parallel pre-trends <=> a4 = 0.
  Run twice: (A) program all alerts vs comparison Dependabot, (B) Dependabot
  only for both groups. Outcomes: fixed (primary) and found.

Placebo and break-date grid: identical model to fit_break() in
analysis/12_its_models.py (segmented NB, HAC maxlags=4, program group, all
alerts, outcome = fixed), extended to also return the 95% CI. The script checks
that it reproduces fit_break() exactly before using it.

Outputs: analysis/15_comparison_and_break_dates.md,
         data/derived/break_grid.csv, data/derived/cohort_weekly.csv
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from study_config import WINDOW_END  # noqa: E402

DERIVED = ROOT / "data" / "derived"
OUT = Path(__file__).resolve().parent / "15_comparison_and_break_dates.md"
START = pd.Timestamp("2023-01-02")
END = pd.Timestamp(WINDOW_END)
BREAK = pd.Timestamp("2026-01-05")
N_PROGRAM, N_COMPARISON = 44, 49

# Reuse the original ITS module so the program series is built identically.
_spec = importlib.util.spec_from_file_location("its12", Path(__file__).parent / "12_its_models.py")
its12 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(its12)


# ---------------------------------------------------------------- data ----
def comparison_repos():
    r = pd.read_csv(DERIVED / "repos.csv")
    o3 = set(pd.read_csv(DERIVED / "o3_sample.csv").repo)
    sel = r[r["class"].isin(["module", "o3_frontend"]) & (r.archived == 0)
            & (r.active_flag == 1) & ~r.repo.isin(o3)]
    return sel.repo.tolist()




def weekly(created, fixed):
    weeks = pd.date_range(START, END, freq="7D")
    out = pd.DataFrame({"week": weeks})
    for s, name in [(created, "created"), (fixed, "fixed")]:
        out = out.merge(its12._wk(pd.Series(s)).value_counts().rename(name),
                        left_on="week", right_index=True, how="left")
    return out.fillna(0)


def build_series():
    dep = pd.read_csv(DERIVED / "dependabot_alerts.csv")
    cs = pd.read_csv(DERIVED / "code_scanning_alerts.csv")
    prog_all = weekly(pd.concat([dep.created_at, cs.created_at]),
                      pd.concat([dep.fixed_at, cs.fixed_at]))
    prog_dep = weekly(dep.created_at, dep.fixed_at)
    status = pd.read_csv(DERIVED / "comparison_repos.csv")
    assert set(status.repo) == set(comparison_repos()), "comparison_repos.csv does not match the selection rule"
    no_cache = status.loc[status.has_alert_data == 0, "repo"].tolist()
    cmp_alerts = pd.read_csv(DERIVED / "comparison_dependabot_alerts.csv")[["created_at", "fixed_at"]]
    comp_dep = weekly(cmp_alerts.created_at, cmp_alerts.fixed_at)
    return prog_all, prog_dep, comp_dep, cmp_alerts, no_cache


# -------------------------------------------------------------- models ----
def rates(df, n):
    pre, post = df[df.week < BREAK], df[df.week >= BREAK]
    r = {}
    for y in ["created", "fixed"]:
        a, b = pre[y].mean() / n, post[y].mean() / n
        r[y] = (a, b, b / a if a else np.nan)
    return r


def _design(prog, comp, pre_only=False):
    frames = []
    for g, df, n in [(1, prog, N_PROGRAM), (0, comp, N_COMPARISON)]:
        d = df.copy()
        d["g"], d["n"] = g, n
        d["tidx"] = np.arange(len(d))
        frames.append(d)
    d = pd.concat(frames, ignore_index=True)
    d["t"] = d["tidx"] / 52.0
    d["post"] = (d["week"] >= BREAK).astype(int)
    bidx = int(d.loc[d["post"] == 1, "tidx"].min())
    d["tp"] = ((d["tidx"] - bidx).clip(lower=0) * d["post"]) / 52.0
    m = d["week"].dt.month
    d["gsoc"] = ((m >= 6) & (m <= 9)).astype(int)
    d["g_t"], d["g_post"], d["g_tp"] = d.g * d.t, d.g * d.post, d.g * d.tp
    if pre_only:
        d = d[d.post == 0].copy()
    return d.sort_values(["g", "tidx"]).reset_index(drop=True)


def _fit(d, y, cols):
    X = sm.add_constant(d[cols])
    off = np.log(d["n"])
    kw = {"groups": d["g"].values, "time": d["tidx"].values, "maxlags": 4}
    try:
        m = sm.NegativeBinomial(d[y], X, offset=off).fit(
            disp=0, maxiter=500, cov_type="hac-panel", cov_kwds=kw)
        if not np.isfinite(m.bse).all():
            raise ValueError("non-finite SEs")
        return m, "NB"
    except Exception:
        m = sm.GLM(d[y], X, family=sm.families.Poisson(), offset=off).fit(
            cov_type="hac-panel", cov_kwds=kw)
        return m, "Poisson"


def group_time(prog, comp, y):
    d = _design(prog, comp)
    m, fam = _fit(d, y, ["g", "t", "post", "tp", "gsoc", "g_t", "g_post", "g_tp"])
    dp = _design(prog, comp, pre_only=True)
    mp, famp = _fit(dp, y, ["g", "t", "gsoc", "g_t"])
    ci = np.exp(m.conf_int().loc["g_post"])
    return {"fam": fam, "g_post": np.exp(m.params["g_post"]), "g_post_ci": tuple(ci),
            "g_post_p": m.pvalues["g_post"], "g_tp": np.exp(m.params["g_tp"]),
            "g_tp_p": m.pvalues["g_tp"], "pre_fam": famp,
            "pre_g_t": np.exp(mp.params["g_t"]), "pre_g_t_p": mp.pvalues["g_t"]}


def fit_break_ci(df, y, brk):
    """Same model as its12.fit_break(), but also returns the 95% CI."""
    d = df.copy()
    d["post"] = (d["week"] >= pd.Timestamp(brk)).astype(int)
    if d["post"].sum() < 4:
        return None
    bidx = int(d.loc[d["post"] == 1, "time"].min())
    d["t"] = d["time"] / 52.0
    d["tp"] = ((d["time"] - bidx).clip(lower=0) * d["post"]) / 52.0
    X = sm.add_constant(d[["t", "post", "tp", "gsoc"]])
    m = sm.NegativeBinomial(d[y], X).fit(disp=0, maxiter=300,
                                         cov_type="HAC", cov_kwds={"maxlags": 4})
    lo, hi = np.exp(m.conf_int().loc["post"])
    return np.exp(m.params["post"]), lo, hi, m.pvalues["post"], int(d["post"].sum())


# ---------------------------------------------------------------- main ----
def main():
    prog_all, prog_dep, comp_dep, cmp_alerts, no_cache = build_series()
    org, _ = its12.org_week_series()

    # Safety check: fit_break_ci() must reproduce fit_break() in 12_its_models.py.
    for brk in ["2025-12-15", "2026-01-05", "2026-01-15"]:
        a, b = its12.fit_break(org, "fixed", brk), fit_break_ci(org, "fixed", brk)
        assert abs(a[0] - b[0]) < 1e-9 and abs(a[1] - b[3]) < 1e-9, brk

    L = ["# Comparison repos, placebo start dates, start-date grid", "",
         "_Output of analysis/15_comparison_and_break_dates.py. June data. "
         "Weeks %s .. %s; onset 2026-01-05._" % (START.date(), END.date()), "",
         "Comparison repos: %d selected by the paper's rule; %d with no cached Dependabot "
         "data (counted as zero alerts): %s." % (len(comparison_repos()), len(no_cache),
                                                     ", ".join(r.split("/")[1] for r in no_cache)),
         "Comparison alerts: %d found, %d fixed; latest created_at %s." % (
             len(cmp_alerts), cmp_alerts.fixed_at.notna().sum(), cmp_alerts.created_at.max()), ""]

    L += ["## Per-repo weekly rates (pre → post 2026-01-05)", "",
          "| group | alert source | repos | found pre → post (×) | fixed pre → post (×) |",
          "|---|---|---|---|---|"]
    for name, src, df, n in [("program", "all (Dependabot + code scanning)", prog_all, N_PROGRAM),
                             ("program", "Dependabot only", prog_dep, N_PROGRAM),
                             ("comparison", "Dependabot only", comp_dep, N_COMPARISON)]:
        r = rates(df, n)
        L.append("| %s | %s | %d | %.3f → %.3f (×%.1f) | %.3f → %.3f (×%.1f) |" % (
            name, src, n, *r["created"], *r["fixed"]))

    L += ["", "## Group × time model (between-group test) and pre-trend test", "",
          "Ratio for g:post = how much larger the onset jump is in program repos than in "
          "comparison repos. Pre-trend ratio = difference in pre-onset yearly growth "
          "(1 = parallel).", "",
          "| comparison | outcome | model | g:post ratio [95% CI] | p | g:slope-after ratio | p "
          "| pre-trend g:t ratio | p |", "|---|---|---|---|---|---|---|---|---|"]
    results = {}
    for label, prog in [("A: program all vs comparison Dependabot", prog_all),
                        ("B: Dependabot only, both groups", prog_dep)]:
        for y, yname in [("fixed", "fixed"), ("created", "found")]:
            g = group_time(prog, comp_dep, y)
            results[(label, y)] = g
            L.append("| %s | %s | %s | %.2f [%.2f, %.2f] | %.3g | %.2f | %.3g | %.2f | %.3g |" % (
                label, yname, g["fam"], g["g_post"], *g["g_post_ci"], g["g_post_p"],
                g["g_tp"], g["g_tp_p"], g["pre_g_t"], g["pre_g_t_p"]))

    L += ["", "## In-time placebo (program, all alerts, fixed/wk; same model as Table IV)", "",
          "| break | post wks | ratio | 95% CI | p |", "|---|---|---|---|---|"]
    for brk in ["2024-06-03", "2025-06-02"]:
        r = fit_break_ci(org, "fixed", brk)
        L.append("| %s | %d | %.2f | %.2f–%.2f | %.3g |" % (brk, r[4], r[0], r[1], r[2], r[3]))

    L += ["", "## Break-date grid: every Monday 2025-11-03 .. 2026-03-02", "",
          "| break (Monday) | post wks | ratio | 95% CI | p |", "|---|---|---|---|---|"]
    grid = []
    for brk in pd.date_range("2025-11-03", "2026-03-02", freq="7D"):
        r = fit_break_ci(org, "fixed", brk)
        grid.append((brk.date(), *r))
        L.append("| %s | %d | %.2f | %.2f–%.2f | %.3g |" % (brk.date(), r[4], r[0], r[1], r[2], r[3]))
    pd.DataFrame(grid, columns=["break", "ratio", "ci_lo", "ci_hi", "p", "post_weeks"]).to_csv(
        DERIVED / "break_grid.csv", index=False)

    # weekly series for the SEIP figure
    fig = pd.DataFrame({"week": prog_all.week,
                        "program_all_found": prog_all.created / N_PROGRAM,
                        "program_all_fixed": prog_all.fixed / N_PROGRAM,
                        "program_dep_found": prog_dep.created / N_PROGRAM,
                        "program_dep_fixed": prog_dep.fixed / N_PROGRAM,
                        "comparison_dep_found": comp_dep.created / N_COMPARISON,
                        "comparison_dep_fixed": comp_dep.fixed / N_COMPARISON})
    fig.to_csv(DERIVED / "cohort_weekly.csv", index=False)

    OUT.write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    sys.exit(main() or 0)
