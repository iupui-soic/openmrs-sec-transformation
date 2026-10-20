"""Figures for the paper: alerts per repo per week (Fig. 1) and time to fix (Fig. 2).

Fig. 1  figures/fig_alerts_per_repo.pdf (+ .png preview), 7.0 x 2.4 in
        Two panels side by side: alerts found (left), alerts fixed (right),
        per repo per week, 4-week centred mean, 2023-01-02 .. 2026-06-15.
        Program repos: all alerts and Dependabot only; comparison repos:
        Dependabot only (the only source cached for them).
        Dashed line at 2026-01-05; dotted line at 2025-12-15 (audit).
        Grey bands = June-September, the GSoC indicator used by the ITS model
        (12_its_models.py: gsoc = month 6..9).
        Input: data/derived/cohort_weekly.csv
               (written by 15_comparison_and_break_dates.py).
Fig. 2  figures/fig_time_to_fix.pdf (+ .png preview), 3.4 x 2.2 in
        Kaplan-Meier share of alerts still open, alerts found before vs on/after
        2025-12-15 (all alerts). x-axis shown to 730 days (display only; the
        model uses all follow-up). Input: data/derived/km_mttr_curve.csv
        (written by 13_survival_mttr.py).
Colours: dark blue #1c5cab, orange #eb6834 (validated pair: worst colour-blind
separation dE 24.4, normal-vision dE 35.7, both >= 3:1 contrast).
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived"
OUTDIR = ROOT / "figures"

BLUE, ORANGE = "#1c5cab", "#eb6834"
INK, MUTED, GRID, BAND = "#222222", "#666666", "#e3e3e3", "#efefef"
START, END = pd.Timestamp("2023-01-02"), pd.Timestamp("2026-06-15")
JAN5, AUDIT = pd.Timestamp("2026-01-05"), pd.Timestamp("2025-12-15")
GSOC_MONTHS = (6, 9)          # June..September, as in the ITS model
DOTTED = (0, (1, 1.5))        # dotted line pattern (on 1, off 1.5, in line widths)
DASHED = (0, (4, 3))

plt.rcParams.update({
    "font.size": 8, "axes.labelsize": 8, "xtick.labelsize": 8, "ytick.labelsize": 8,
    "legend.fontsize": 8, "font.family": "DejaVu Sans", "pdf.fonttype": 42,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
    "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
})

SERIES = [  # (column prefix, label, colour, linewidth, linestyle)
    ("program_all", "Program repos, all alerts", BLUE, 1.6, "solid"),
    ("program_dep", "Program repos, Dependabot only", BLUE, 1.0, DOTTED),
    ("comparison_dep", "Comparison repos, Dependabot only", ORANGE, 1.4, "solid"),
]


def _gsoc_bands(ax):
    for y in range(START.year, END.year + 1):
        a = max(pd.Timestamp(y, GSOC_MONTHS[0], 1), START)
        b = min(pd.Timestamp(y, GSOC_MONTHS[1], 30), END)
        if a < b:
            ax.axvspan(a, b, color=BAND, linewidth=0, zorder=0)


def fig_alerts():
    d = pd.read_csv(DERIVED / "cohort_weekly.csv", parse_dates=["week"])
    s = lambda c: d[c].rolling(4, min_periods=1, center=True).mean()  # noqa: E731
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.4), sharex=True)
    for ax, kind, tag in [(axes[0], "found", "Alerts found"), (axes[1], "fixed", "Alerts fixed")]:
        _gsoc_bands(ax)
        for col, lab, colour, lw, ls in SERIES:
            ax.plot(d.week, s("%s_%s" % (col, kind)), color=colour, linewidth=lw,
                    linestyle=ls, label=lab, zorder=3)
        ax.axvline(AUDIT, color=INK, linestyle=":", linewidth=0.7, zorder=2)
        ax.axvline(JAN5, color=INK, linestyle=DASHED, linewidth=0.9, zorder=2)
        ax.grid(axis="y", color=GRID, linewidth=0.5)
        ax.set_axisbelow(True)
        ax.set_ylim(bottom=0)
        ax.set_xlim(START, END)
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=[4, 7, 10]))
        ax.text(0.015, 0.97, tag, transform=ax.transAxes, ha="left", va="top",
                fontsize=8, fontweight="bold", color=INK)
        ax.annotate("Audit", xy=(AUDIT, 0.80), xycoords=("data", "axes fraction"),
                    xytext=(-3, 0), textcoords="offset points", ha="right", va="center",
                    fontsize=7, color=MUTED)
    axes[0].set_ylabel("Per repo per week (4-wk avg.)")
    ax = axes[1]
    ax.annotate("Jan 5, 2026", xy=(JAN5, 0.97), xycoords=("data", "axes fraction"),
                xytext=(-3, 0), textcoords="offset points", ha="right", va="top",
                fontsize=7, color=INK, zorder=4,
                bbox=dict(boxstyle="square,pad=0.1", facecolor="white", edgecolor="none"))
    # note next to the comparison-repo spike (peak of the smoothed series, early 2025)
    sp = s("comparison_dep_fixed")
    win = d.week.between("2025-01-01", "2025-03-31")
    i = sp[win].idxmax()
    ax.annotate("one repo, 74 fixes", xy=(d.week[i], sp[i]), xytext=(-6, 0),
                textcoords="offset points", ha="right", va="center", fontsize=7, color=INK)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False,
               bbox_to_anchor=(0.5, 1.0), handlelength=2.2, columnspacing=1.4,
               handletextpad=0.5)
    fig.tight_layout(rect=(0, 0, 1, 0.9), w_pad=1.5)
    for ext in ("pdf", "png"):
        fig.savefig(OUTDIR / ("fig_alerts_per_repo." + ext), dpi=300)
    plt.close(fig)


def fig_time_to_fix():
    k = pd.read_csv(DERIVED / "km_mttr_curve.csv")
    k = k[k.stratum == "all alerts"]
    fig, ax = plt.subplots(figsize=(3.4, 2.2))
    xmax = 730
    for era, colour, lab in [("pre (reactive)", BLUE, "Found before\nDec 15, 2025"),
                             ("post (proactive)", ORANGE, "Found on or after\nDec 15, 2025")]:
        g = k[k.era == era].sort_values("t_days")
        g = g[g.t_days <= xmax]
        ax.step(g.t_days, g.survival, where="post", color=colour, linewidth=1.4)
        below = era.startswith("post")   # keep the shorter curve's label clear of the other
        ax.annotate(lab, xy=(g.t_days.iloc[-1], g.survival.iloc[-1]),
                    xytext=(-20, -16) if below else (4, 0), textcoords="offset points",
                    ha="left", va="top" if below else "center", fontsize=7, color=INK)
    ax.set_xlabel("Days since found")
    ax.set_ylabel("Share still open")
    ax.set_xlim(0, xmax)
    ax.set_ylim(0, 1)
    ax.set_xticks([0, 180, 365, 545, 730])
    ax.grid(axis="y", color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(OUTDIR / ("fig_time_to_fix." + ext), dpi=300)
    plt.close(fig)


def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    fig_alerts()
    fig_time_to_fix()
    print("-> wrote", OUTDIR / "fig_alerts_per_repo.{pdf,png}", "and",
          OUTDIR / "fig_time_to_fix.{pdf,png}")


if __name__ == "__main__":
    main()
