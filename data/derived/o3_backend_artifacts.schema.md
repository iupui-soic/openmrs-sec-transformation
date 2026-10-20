# Schema: o3_backend_artifacts.csv

Backend Maven artifacts bundled in the OpenMRS 3.x Reference Application distribution,
with the distro-pinned version and the **release-integrity** status of each artifact.
Hand-extracted from `backend-dependency-report.pdf` (team-supplied, 2026-06-11), which
verified every signature/checksum locally against the OpenMRS code-signing key
(fingerprint CA12 619F DE8C D6A9 3FAF E458 A6F9 608D CC73 473F).

| column | description |
|---|---|
| `module` | OMOD/war artifact id (e.g. fhir2, webservices.rest) |
| `version` | exact version pinned in the 3.x distro (distro.properties had only placeholders) |
| `repo` | source GitHub repo (3 are external: Mekom/Bahmni) |
| `maven_hosted` | 1 if published on the OpenMRS Maven/Artifactory repo |
| `sha256_published` | 1 if a verified `.sha256` sidecar exists on the Maven repo |
| `pgp_signed` | 1 if a valid `.asc` PGP signature (OpenMRS code-signing key) exists |

## Provenance

backend-dependency-report.pdf (Maven/Artifactory, OpenMRS 3.x RefApp). 28/28 OpenMRS-hosted
artifacts passed both checksum and signature verification; the 3 externally-hosted modules
(initializer=Mekomsolutions, appointments+teleconsultation=Bahmni) carry no OpenMRS sidecars.
This captures the SHA-256/PGP **release-integrity** intervention at the Maven publishing layer,
which the per-repo GitHub-release-asset detector (interventions.csv `sha256_release`) misses.
