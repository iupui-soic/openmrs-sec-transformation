"""Phase 2.6 — Panel assembly (ULTRAPLAN §4.6).

Joins outcomes (4.1-4.4), covariates (4.5), and interventions.csv into the
repo x week analysis panel:

  data/derived/panel.parquet
  repo, week, class, outcomes…, covariates…,
  treat_<i> (0/1), cohort_<i> (adoption week), event_time_<i> (weeks since adoption)

Acceptance checks built in: no duplicate repo-weeks (hard fail), missingness report
(data/derived/missingness_report.md), treated/never-treated counts per intervention.
"""
from __future__ import annotations

import sys

import pandas as pd

from common import DERIVED, WINDOW_END, WINDOW_START, iso_week, log, o3_sample, write_schema

INTERVENTIONS = ["sonarcloud", "dependabot", "actions_archetype",
                 "sha256_release", "quality_gates", "playwright_bdd"]


def load_csv(name, **kw):
    p = DERIVED / name
    if not p.exists():
        log.warning("missing input %s — joining without it", name)
        return None
    df = pd.read_csv(p, **kw)
    log.info("%s: %d rows", name, len(df))
    return df


def main():
    repos = pd.read_csv(DERIVED / "repos.csv")
    repos["class_final"] = repos["class_override"].fillna("").replace("", pd.NA)
    repos["class_final"] = repos["class_final"].fillna(repos["class"])
    sample = repos[repos["repo"].isin(set(o3_sample()))]  # O3 distribution scope (01b)

    # spine: every active repo x every week in window
    weeks = [iso_week(str(d.date())) for d in
             pd.date_range(WINDOW_START, WINDOW_END, freq="W-MON")]
    weeks = sorted(set(weeks))
    spine = pd.MultiIndex.from_product(
        [sample["repo"], weeks], names=["repo", "week"]).to_frame(index=False)
    spine = spine.merge(sample[["repo", "class_final", "visibility"]], on="repo")
    spine = spine.rename(columns={"class_final": "class"})

    panel = spine
    dep = load_csv("dependabot_weekly.csv")
    if dep is not None:
        panel = panel.merge(dep, on=["repo", "week"], how="left")

    cs = load_csv("code_scanning_weekly.csv")
    if cs is not None:
        panel = panel.merge(cs, on=["repo", "week"], how="left")

    cov = load_csv("covariates_weekly.csv")
    if cov is not None:
        panel = panel.merge(cov.drop(columns=["primary_language"], errors="ignore"),
                            on=["repo", "week"], how="left")

    prc = load_csv("sonar_pr_checks.csv")
    if prc is not None:
        agg = (prc.groupby(["repo", "week"])
               .agg(pr_security_checked=("had_security_check", "sum"),
                    pr_stage_fixes=("failed_then_passed", "sum")).reset_index())
        panel = panel.merge(agg, on=["repo", "week"], how="left")

    son = load_csv("sonar_weekly.csv")
    if son is not None:
        # join via sonar_key -> repo mapping derived in 02 (sonarcloud rows)
        iv = load_csv("interventions.csv")
        key_map = {}
        if iv is not None:
            for r in iv[iv["intervention"] == "sonarcloud"].itertuples():
                url = str(r.signal_b_evidence_url)
                if "id=" in url:
                    key_map[url.split("id=")[-1]] = r.repo
        son["repo"] = son["sonar_key"].map(key_map)
        son = son.dropna(subset=["repo"])
        son = son.rename(columns={"vulnerabilities": "sonar_open_vulns",
                                  "security_hotspots": "sonar_hotspots",
                                  "security_rating": "sonar_security_rating",
                                  "new_vulnerabilities": "sonar_new_vulns",
                                  "alert_status": "sonar_quality_gate"})
        panel = panel.merge(son.drop(columns=["sonar_key"]),
                            on=["repo", "week"], how="left")
        log.info("sonar joined for %d projects", son["repo"].nunique())

    # treatment columns from interventions.csv
    iv = load_csv("interventions.csv")
    if iv is not None:
        adopt = (iv[iv["adoption_date"].notna() & (iv["adoption_date"] != "")]
                 .assign(adoption_week=lambda d: d["adoption_date"].map(iso_week))
                 .groupby(["repo", "intervention"])["adoption_week"].min()
                 .unstack())
        week_idx = {w: i for i, w in enumerate(weeks)}
        for i_name in INTERVENTIONS:
            col = adopt[i_name] if i_name in adopt.columns else pd.Series(dtype=str)
            panel["cohort_%s" % i_name] = panel["repo"].map(col)
            c = panel["cohort_%s" % i_name]
            panel["treat_%s" % i_name] = ((c.notna()) &
                                          (panel["week"] >= c)).astype(int)
            panel["event_time_%s" % i_name] = [
                (week_idx.get(w, -1) - week_idx.get(cw, -1))
                if pd.notna(cw) and cw in week_idx and w in week_idx else pd.NA
                for w, cw in zip(panel["week"], c)]

    # acceptance: duplicates are a hard failure
    dups = panel.duplicated(["repo", "week"]).sum()
    if dups:
        log.error("ACCEPTANCE FAIL: %d duplicate repo-weeks", dups)
        return 1

    count_cols = [c for c in panel.columns if panel[c].dtype.kind in "if"
                  and c.startswith(("alerts_", "cs_", "pr_", "commits", "loc_", "prs_"))]
    panel[count_cols] = panel[count_cols].fillna(0)

    out = DERIVED / "panel.parquet"
    panel.to_parquet(out, index=False)

    # missingness report + treated/never-treated descriptives
    lines = ["# Panel missingness & treatment descriptives", "",
             "Rows: %d (%d repos x %d weeks)" % (len(panel),
                                                 panel["repo"].nunique(), len(weeks)),
             "", "## Missingness by column", "", "| column | % missing |", "|---|---|"]
    for c in panel.columns:
        pct = 100 * panel[c].isna().mean()
        lines.append("| %s | %.1f%% |" % (c, pct))
    lines += ["", "## Treated / never-treated per intervention", "",
              "| intervention | treated repos | never-treated | distinct cohorts |",
              "|---|---|---|---|"]
    for i_name in INTERVENTIONS:
        cc = "cohort_%s" % i_name
        if cc in panel.columns:
            per_repo = panel.groupby("repo")[cc].first()
            lines.append("| %s | %d | %d | %d |" % (
                i_name, per_repo.notna().sum(), per_repo.isna().sum(),
                per_repo.dropna().nunique()))
    (DERIVED / "missingness_report.md").write_text("\n".join(lines) + "\n")

    write_schema(out, "Analysis panel, grain repo x ISO-week (Mondays), window %s..%s."
                 % (WINDOW_START, WINDOW_END),
                 {"repo": "org/name", "week": "Monday of ISO week",
                  "class": "repo class (manual override applied)",
                  "treat_<i>": "1 from adoption week onward",
                  "cohort_<i>": "adoption week (NaN = never treated)",
                  "event_time_<i>": "weeks since adoption (negative = pre)",
                  "…": "outcome and covariate columns per source schemas"},
                 "Join of dependabot_weekly, sonar_weekly (+pr_checks), "
                 "covariates_weekly, interventions. See missingness_report.md.")
    print("panel_rows=%d repos=%d weeks=%d -> %s" %
          (len(panel), panel["repo"].nunique(), len(weeks), out))


if __name__ == "__main__":
    sys.exit(main() or 0)
