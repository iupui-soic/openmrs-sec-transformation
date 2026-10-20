# Schema: interventions.csv

First-adoption timestamps per repo x intervention, two independent signals (A = config introduction commit, B = first runtime evidence). adoption_date = min(A, B). ULTRAPLAN §3.2.

Generated: 2026-06-11T23:13:33.312958+00:00

| column | description |
|---|---|
| `repo` | org/name |
| `intervention` | sonarcloud|dependabot|actions_archetype|sha256_release|quality_gates|playwright_bdd|ERROR |
| `signal_a_date` | config-introduction commit date (ISO) |
| `signal_a_evidence_url` | commit URL |
| `signal_b_date` | first runtime evidence date (ISO) |
| `signal_b_evidence_url` | PR/run/release/analysis URL |
| `adoption_date` | min of available signals |
| `detection_method` | how signals were obtained |
| `verified_by` | filled during manual 20% verification |
| `notes` | caveats incl. quality_gates history limitation |

## Provenance

GitHub REST (trees/commits/contents/search/actions/releases/branch-protection) + SonarCloud public API (project_analyses). Archetype filename patterns: ['security*.yml', '*security-archetype*.yml'] (TODO confirm with team/transcripts). 93 rows; verification sample: 12 rows in interventions_verify_sample.csv (seed=42).
