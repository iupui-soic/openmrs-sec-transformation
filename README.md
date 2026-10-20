# OpenMRS security program: replication package

Data and code for the paper *From Reactive to Proactive: A Longitudinal Mixed-Methods
Study of Security Transformation in a Critical Open-Source Healthcare Ecosystem*
(ICSE 2027, Software Engineering in Practice track).

The study follows a funded security program in OpenMRS using two sources: coded
passages from the program's working group meetings (RQ1, RQ2), and GitHub security
alerts for 44 program repositories and 49 comparison repositories (RQ3).

## Reproduce the paper's numbers

All analyses run from the files in `data/derived/` and `qual/`. No API tokens or
network access are needed.

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt      # versions we used; Python 3.10+

python3 analysis/12_its_models.py               # jump in weekly alerts at Jan 5, 2026
python3 analysis/13_survival_mttr.py            # time to fix (Cox, Kaplan-Meier)
python3 analysis/15_comparison_and_break_dates.py  # comparison repos, start-date grid, placebo dates
python3 analysis/16_figures.py                  # both figures
python3 analysis/17_descriptives.py             # alert counts, repo descriptives, signing
python3 analysis/10_power_check.py              # share of repo-weeks with no fixes
python3 qual/agreement.py                       # coder agreement and the agreed RQ1/RQ2 sets
```

Each script writes a Markdown report next to itself (`analysis/*.md`).

## Where each result comes from

| Paper | Script | Output |
|---|---|---|
| Alert data for the 44 program repos (repos, alerts, fixed, by tool) | `analysis/17_descriptives.py` | `analysis/17_descriptives.md` |
| Share of repo-weeks with no fixes (97.5%) | `analysis/10_power_check.py` | `analysis/gate_memo.md` |
| Jump in weekly fixed and found alerts at Jan 5, 2026; Dependabot and code-scanning fixes | `analysis/12_its_models.py` | `analysis/its_results.md` |
| Jump for every start date Nov 3, 2025 to Mar 2, 2026, and the June 2024 / June 2025 checks | `analysis/15_comparison_and_break_dates.py` | `analysis/15_comparison_and_break_dates.md`, `data/derived/break_grid.csv` |
| Alerts per repo per week before and after Jan 5, program vs comparison repos; pre-trend test | `analysis/15_comparison_and_break_dates.py` | `analysis/15_comparison_and_break_dates.md` |
| Comparison repos: age, activity, and the February 2025 spike | `analysis/17_descriptives.py` | `analysis/17_descriptives.md` |
| Time to fix: hazard ratios (split at Dec 15, 2025 and at Jan 5, 2026), frontend vs backend, tool type | `analysis/13_survival_mttr.py` | `analysis/survival_results.md` |
| Issue-tracker security issues, Kaplan-Meier median (649 days) | `analysis/13_survival_mttr.py` | `analysis/survival_results.md` (section C) |
| Release signing (28 of 28 hosted backend modules) | `analysis/17_descriptives.py` | `analysis/17_descriptives.md` |
| Figure: alerts found and fixed per repo per week | `analysis/16_figures.py` | `figures/fig_alerts_per_repo.pdf` |
| Figure: share of alerts still open by days since found | `analysis/16_figures.py` | `figures/fig_time_to_fix.pdf` |
| Coder agreement (kappa), RQ1 and RQ2 passage sets and counts | `qual/agreement.py` | `qual/agreement_results.md`, `qual/agreed_rq1.csv`, `qual/agreed_rq2.csv` |

## Contents

```
analysis/       analysis scripts and their reports
data/derived/   repository data used by the analyses (each CSV has a *.schema.md where available)
figures/        the paper's figures
qual/           codebook, 120 coded passages, each coder's codes, agreement script
scripts/        the mining pipeline that built data/derived/ (needs API tokens; see below)
```

Key data files:

| File | Contents |
|---|---|
| `data/derived/o3_sample.csv` | The 44 program repos (O3 reference distribution) |
| `data/derived/comparison_repos.csv` | The 49 comparison repos and whether alert data exist for each |
| `data/derived/repos.csv` | All 360 public OpenMRS repos with the fields used to select both groups |
| `data/derived/dependabot_alerts.csv` | Dependabot alerts, program repos |
| `data/derived/code_scanning_alerts.csv` | Code-scanning alerts (CodeQL, OpenSSF Scorecard, SonarCloud), program repos |
| `data/derived/comparison_dependabot_alerts.csv` | Dependabot alerts, comparison repos |
| `data/derived/jira_security_issues.csv` | Security issues from the project's issue tracker |
| `data/derived/o3_backend_artifacts.csv` | Checksum and PGP-signature status of each backend release artifact |
| `data/derived/panel.parquet` | Repo x week panel (outcomes and covariates) |

## What is not included, and why

- **Alert details.** Alert files keep only repository, severity, state, ecosystem or
  tool, and dates. Package names, rule IDs, alert numbers, and advisory IDs are removed,
  because Dependabot and code-scanning alerts are visible only to people with security
  access to the repositories.
- **Security advisories.** No data on GitHub security advisories are included. Some
  advisories in these repositories were not published at the time of the study.
- **Meeting transcripts and notes.** They are confidential. `qual/passages.csv` holds
  the 120 coded passages with every person's name replaced by `[name]`.
- **Raw API cache** (`data/raw/`). It is large and can be rebuilt with the mining scripts.

## Re-running the mining pipeline

The scripts in `scripts/` rebuild `data/derived/` from the GitHub, SonarCloud, JIRA, and
NVD APIs. Copy `.env.example` to `.env` and add tokens. Dependabot and code-scanning
alerts need a GitHub token with security access to the OpenMRS repositories. The study
end date (June 15, 2026) is set in `pyproject.toml`. Alert states change over time, so a
fresh download will not match the June 2026 data exactly.

Run order: `01_inventory.py`, `01b_o3_sample.py`, `02_interventions.py`,
`03_outcomes_dependabot.py`, `03b_outcomes_code_scanning.py`, `04_outcomes_sonarcloud.py`,
`05_outcomes_dashboard.py`, `06_outcomes_jira_cve.py`, `07_covariates.py`,
`08_build_panel.py`. The comparison-repo alert file was exported from the same June 2026
API cache.

## License

Code: MIT (see `LICENSE`). Data in `data/derived/`, `figures/`, and `qual/`: CC BY 4.0.
