# Schema: cve_timeline.csv

Public CVE timeline for OpenMRS (keyword + CPE match, deduped).

Generated: 2026-06-11T22:57:38.914079+00:00

| column | description |
|---|---|
| `cve_id` | CVE |
| `published` | NVD publish ts |
| `last_modified` | NVD modified ts |
| `cvss_score` | base score |
| `cvss_version` | CVSS version of reported score |
| `status` | NVD vuln status |

## Provenance

NVD API 2.0 /cves. API key present: True.
