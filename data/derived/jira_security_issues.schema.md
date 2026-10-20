# Schema: jira_security_issues.csv

Security-labeled/component JIRA issues with resolution time.

Generated: 2026-06-11T22:57:38.911609+00:00

| column | description |
|---|---|
| `issue_key` | issue_key |
| `project` | project |
| `type` | type |
| `priority` | priority |
| `labels` | labels |
| `created` | created |
| `resolved` | resolved |
| `resolution_days` | resolution_days |
| `created_week` | created_week |

## Provenance

https://openmrs.atlassian.net/rest/api/3/search/jql, JQL: labels in (security) OR component = "Security" ORDER BY created ASC
