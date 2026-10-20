# Schema: dashboard_series.csv

Long-format longitudinal CVSS scan series reconstructed from the dashboard repo's git history (each Actions push = one snapshot).

Generated: 2026-06-11T22:58:06.514959+00:00

| column | description |
|---|---|
| `commit` | commit |
| `commit_date` | commit_date |
| `week` | week |
| `file` | file |
| `module` | module |
| `severity` | severity |
| `metric` | metric |
| `value` | value |

## Provenance

git history of openmrs/openmrs-contrib-cvss-scanning, result globs ['*.json', '*.csv']. CVSS v3.1->v4 measurement break must be modeled/truncated downstream using events.csv. Unparsed files this run: 2.
