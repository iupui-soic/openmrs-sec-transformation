"""Phase 3.4 — Survival analysis for MTTR (ULTRAPLAN §5.4), the PRIMARY causal estimand
per the Jun-17 gate (counts too sparse for DiD; resolution times are abundant).

Two layers:
  (A) Per-alert resolution — pooled Dependabot + code-scanning alerts (full history
      2018→2026, NOT limited to the panel window). Cox PH: hazard of resolution ~
      proactive-era(at creation) + severity + tool + frontend/backend, clustered by repo.
      Kaplan–Meier by era → median MTTR pre/post (figure F3).
  (B) Org/core-level — JIRA security-issue resolution (2009→2026), same era split.

Era boundary = baseline-audit / proactive onset (2025-12-15; configurable).
Outputs: analysis/survival_results.md, data/derived/km_mttr_curve.csv.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from lifelines import CoxPHFitter, KaplanMeierFitter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from study_config import WINDOW_END as _STUDY_END  # noqa: E402

DERIVED = Path(__file__).resolve().parents[1] / "data" / "derived"
OUT = Path(__file__).resolve().parent / "survival_results.md"
WINDOW_END = pd.Timestamp(_STUDY_END, tz="UTC")
PROACTIVE_ONSET = pd.Timestamp("2025-12-15", tz="UTC")   # baseline audit delivery
ALT_ONSET = pd.Timestamp("2026-01-05", tz="UTC")         # sensitivity split (RQ3)
SEVRANK = {"low": 1, "medium": 2, "moderate": 2, "high": 3, "critical": 4}


def _dt(s):
    return pd.to_datetime(s, utc=True, errors="coerce")


def load_alerts():
    frames = []
    for f, src in [("dependabot_alerts.csv", "dependabot"),
                   ("code_scanning_alerts.csv", "code_scanning")]:
        d = pd.read_csv(DERIVED / f)
        d["source"] = src
        frames.append(d[["repo", "severity", "created_at", "fixed_at",
                         "dismissed_at", "source"]])
    a = pd.concat(frames, ignore_index=True)
    a["created"] = _dt(a["created_at"])
    a["fixed"] = _dt(a["fixed_at"])
    a["dismissed"] = _dt(a["dismissed_at"])
    a = a[a["created"].notna() & (a["created"] <= WINDOW_END)].copy()
    a["event"] = (a["fixed"].notna() & (a["fixed"] <= WINDOW_END)).astype(int)
    end = a["fixed"].where(a["event"] == 1,
                           a["dismissed"].fillna(WINDOW_END).clip(upper=WINDOW_END))
    a["duration"] = (end - a["created"]).dt.total_seconds() / 86400.0
    a = a[a["duration"] >= 0].copy()
    a["duration"] = a["duration"].clip(lower=0.5)
    o3 = pd.read_csv(DERIVED / "o3_sample.csv")
    fe = set(o3[(o3.in_inventory == 1) & (o3.source == "frontend_esm")]["repo"])
    a["proactive"] = (a["created"] >= PROACTIVE_ONSET).astype(int)
    a["sev_rank"] = a["severity"].str.lower().map(SEVRANK).fillna(2).astype(int)
    a["is_code_scanning"] = (a["source"] == "code_scanning").astype(int)
    a["is_frontend"] = a["repo"].isin(fe).astype(int)
    return a


def km_block(df, label, lines):
    kmf = KaplanMeierFitter()
    lines.append("\n**%s** (n=%d, %d resolved):" % (label, len(df), int(df["event"].sum())))
    lines.append("| era | n | resolved | median MTTR (days) |")
    lines.append("|---|---|---|---|")
    curve_rows = []
    for era, sub in [("pre (reactive)", df[df.proactive == 0]),
                     ("post (proactive)", df[df.proactive == 1])]:
        if len(sub) == 0:
            continue
        kmf.fit(sub["duration"], sub["event"], label=era)
        med = kmf.median_survival_time_
        lines.append("| %s | %d | %d | %s |" %
                     (era, len(sub), int(sub["event"].sum()),
                      "%.0f" % med if np.isfinite(med) else "not reached"))
        c = kmf.survival_function_.reset_index()
        c.columns = ["t_days", "survival"]
        c["era"] = era; c["stratum"] = label
        curve_rows.append(c)
    return curve_rows


def main():
    a = load_alerts()
    lines = ["# Survival analysis — MTTR (primary causal estimand)", "",
             "_Pooled Dependabot + code-scanning alerts, full history. Proactive onset = %s "
             "(baseline audit). Censoring at %s._" %
             (PROACTIVE_ONSET.date(), WINDOW_END.date()), ""]

    cols = ["duration", "event", "proactive", "sev_rank", "is_code_scanning", "is_frontend"]
    cph = CoxPHFitter()
    cph.fit(a[cols + ["repo"]], "duration", "event", cluster_col="repo")
    lines += ["## A. Cox PH — hazard of resolution (HR>1 = faster)", "",
              "| covariate | HR | 95% CI | p |", "|---|---|---|---|"]
    s = cph.summary
    for cov in s.index:
        lines.append("| %s | %.2f | %.2f–%.2f | %.3g |" % (
            cov, s.loc[cov, "exp(coef)"], s.loc[cov, "exp(coef) lower 95%"],
            s.loc[cov, "exp(coef) upper 95%"], s.loc[cov, "p"]))
    hr = s.loc["proactive", "exp(coef)"]
    lines += ["", "_Proactive-era HR = **%.2f** → resolution is %s in the proactive era "
              "(severity/tool/layer held fixed)._" %
              (hr, "%.0f%% faster" % ((hr - 1) * 100) if hr > 1
               else "%.0f%% slower" % ((1 - hr) * 100)), ""]

    # Sensitivity: split the eras at 2026-01-05 instead of the audit delivery date.
    alt = a.copy()
    alt["proactive"] = (alt["created"] >= ALT_ONSET).astype(int)
    cph2 = CoxPHFitter()
    cph2.fit(alt[cols + ["repo"]], "duration", "event", cluster_col="repo")
    s2 = cph2.summary
    lines += ["## A2. Same model, eras split at %s" % ALT_ONSET.date(), "",
              "| covariate | HR | 95% CI | p |", "|---|---|---|---|",
              "| proactive | %.2f | %.2f–%.2f | %.3g |" % (
                  s2.loc["proactive", "exp(coef)"], s2.loc["proactive", "exp(coef) lower 95%"],
                  s2.loc["proactive", "exp(coef) upper 95%"], s2.loc["proactive", "p"]), ""]

    lines += ["## B. Kaplan–Meier median MTTR by era"]
    curves = []
    curves += km_block(a, "all alerts", lines)
    curves += km_block(a[a.is_frontend == 0], "backend (mature)", lines)
    curves += km_block(a[a.is_frontend == 1], "frontend (new)", lines)

    j = pd.read_csv(DERIVED / "jira_security_issues.csv")
    j["created"] = _dt(j["created"]); j["resolved_dt"] = _dt(j["resolved"])
    j["event"] = (j["resolved_dt"].notna() & (j["resolved_dt"] <= WINDOW_END)).astype(int)
    jend = j["resolved_dt"].where(j["event"] == 1, WINDOW_END)
    j["duration"] = (jend - j["created"]).dt.total_seconds() / 86400.0
    j = j[j["duration"] >= 0].copy()
    j["proactive"] = (j["created"] >= PROACTIVE_ONSET).astype(int)
    lines += ["\n## C. JIRA security issues (org/core-level, 2009→2026)"]
    curves += km_block(j, "JIRA security issues", lines)

    if curves:
        pd.concat(curves, ignore_index=True).to_csv(DERIVED / "km_mttr_curve.csv", index=False)

    lines += ["", "## Notes / threats", "",
              "- Alert `created_at` reflects detection (a scanning *visibility* effect); "
              "resolution hazard conditions on the alert existing, so MTTR is less "
              "contaminated than raw counts (§4.1).",
              "- Post-era alerts have shorter follow-up → KM/Cox handle differential "
              "censoring; treat post medians as lower bounds.",
              "- Era split is calendar-based; per-repo time-varying treatment "
              "(CoxTimeVaryingFitter) is the robustness follow-up.", ""]
    OUT.write_text("\n".join(lines) + "\n")
    print("Cox proactive HR=%.2f (p=%.3g) | n=%d alerts, %d resolved" %
          (hr, s.loc["proactive", "p"], len(a), int(a["event"].sum())))
    print("-> wrote", OUT)


if __name__ == "__main__":
    sys.exit(main() or 0)
