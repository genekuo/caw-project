# Platform versions

Platforms the bookstore depends on that need tracking for security patches and upgrades. This is the image, runtime, framework-BOM and operator level, not individual libraries.

- **Checked:** 2026-10-21
- **Derived from:** `docs/00-conventions.md` … `06-data-platform.md`, `architecture.md`, and the ADRs in `docs/adr/`
- **Source of truth:** the YAML block below. The other sections are summaries of it.

## How to use this file (for agents)

1. Parse the single fenced `yaml` block under **Inventory**. Each item in `platforms` is one component.
2. For each item, fetch `check.url` and read the latest version using `check.kind`:
   - `endoflife`: JSON from the endoflife.date v1 API. Find the release whose `name` matches `track_line`, and read its `latest.name` and `eolFrom`.
   - `github_release`: the GitHub releases API. Use a token, because unauthenticated calls are limited to 60 per hour. Skip prereleases, and apply `check.filter` if one is set.
   - `maven_metadata`: `maven-metadata.xml`. Take the highest `<version>` that matches `check.filter`, and ignore `-M`, `-RC`, `-rc`, `-alpha` and `-beta`.
   - `artifacthub`: read `app_version` (or `version` for the chart).
   - `docker_hub`: the Docker Hub tags API. Compare digests, not tag names.
   - `html`: a human page. Read it and extract the version.
3. Compare the fetched version with `latest.version` and with `track_line`, then flag the item if:
   - the line you track has a newer patch (the patch-update case), or
   - `support.line_eol` is within 90 days, or
   - a newer line exists that `design_pin` doesn't allow.
4. When you update an entry:
   - Edit only `latest`, `pinned_line_latest`, `support` and `notes`, and set `checked` to the date of your check.
   - Change `design_pin` only when a design doc or ADR changes. It mirrors the docs.
5. `owner: platform` means the component is installed and versioned by the platform team outside this repo (06 P‑01). Report it, but the change belongs to them.

## Needs attention (as of 2026-10-21)

| Item | Issue | Suggested action |
| --- | --- | --- |
| `rabbitmq` | The design pins **4.1** (P‑08). Community support for 4.1 ended on 2026‑01‑31, and 4.2's ended on 2026‑07‑31. Cluster Operator ≥ 2.22 needs RabbitMQ 4.2.4+ or 4.3+ for its startup probe. | Re-decide P‑08: target 4.3 or 4.4, and update 06 §5.1. |
| `kubernetes` | 1.34 reaches EOL on **2026‑10‑27**. The design doesn't state the cluster version. | Confirm the cluster version with the platform team. APISIX IC 2.2 needs ≥ 1.31. |
| `keycloak-config-cli` | The newest image is built against Keycloak 26.5.5. Keycloak is at 26.8.1, and only the latest Keycloak minor gets support. | Test 6.5.1‑26.5.5 against 26.8, or wait for a new build (05 K‑04). |
| `temurin` | The Oracle CPU came out on 2026‑10‑20, so a Temurin 25.0.5 build is expected within days. | Rebuild the images once `25.0.5` tags appear. |
| `nodejs` | 24 moved to Maintenance LTS on 2026‑10‑20. Node 26 becomes Active LTS on 2026‑10‑28. `node:24` on Docker Hub looked stale, and its digest didn't match 24.22.0. | Pin `node:24.22.0(-slim)`. Optionally plan a move to 26. |
| `cloudnative-pg` | Only 1.30.x is supported, until about 2026‑12. 1.31 is overdue. | Platform team: watch for 1.31. |
| `cnpg-postgresql-image` | The design uses the bare tag `postgresql:17`, which is deprecated and will be removed. | Use `17.11-standard-trixie` (or the dated tag) with the Barman Cloud plugin. |
| `helm` | Helm 4 is GA. Helm 3's end-of-support date was not verified. | Confirm on helm.sh and plan the CI move to Helm 4. |
| `maven` | 3.10.0 is now the recommended line. 3.9.x is still maintained. | Bump the Maven wrapper when convenient. |

## Inventory

```yaml
schema_version: 1
checked: 2026-10-21
platforms:

  # ---------- JVM services (gateway, inventory, user service) ----------

  - id: temurin
    name: Eclipse Temurin (Java runtime)
    category: language-runtime
    owner: app
    used_by: [gateway, inventory, user-service]
    design_pin: "Java 25; runtime image eclipse-temurin:25-jre"
    design_ref: "00 §2"
    image: "eclipse-temurin:25-jre (pin e.g. 25.0.4.1_1-jre)"
    track_line: "25"
    latest: { version: "25.0.4.1+1", released: 2026-08-19 }
    newest_line: { version: "27", released: 2026-09-22, lts: false, eol: 2027-03-23 }
    support: { line_eol: 2031-09-30, lts: true }
    patch_cadence: "Quarterly CPU on the third Tuesday of Jan/Apr/Jul/Oct (next 2027-01-19); Oracle also ships security-only updates in other months (next 2026-11-17)"
    check: { kind: endoflife, url: "https://endoflife.date/api/v1/products/eclipse-temurin" }
    check_alt: "https://api.adoptium.net/v3/assets/latest/25/hotspot?architecture=x64&image_type=jre&os=linux"
    notes: "October 2026 CPU released 2026-10-20; Temurin 25.0.5 not yet published at check time."

  - id: maven
    name: Apache Maven
    category: build-tool
    owner: app
    used_by: [build]
    design_pin: "Maven 3.9+ via Maven wrapper"
    design_ref: "00 §2, A-02"
    track_line: "3.10"
    latest: { version: "3.10.0", released: 2026-09-27 }
    pinned_line_latest: { line: "3.9", version: "3.9.16", released: 2026-05-13 }
    support: { line_eol: null, note: "3.10 and 3.9 maintained; Maven 4 is RC only (4.0.0-rc-7)" }
    check: { kind: maven_metadata, url: "https://repo1.maven.org/maven2/org/apache/maven/maven-core/maven-metadata.xml", filter: "^3\\." }
    notes: "<release> in metadata reports 4.0.0-rc-7; filter it out."

  - id: spring-boot
    name: Spring Boot
    category: framework
    owner: app
    used_by: [gateway, inventory, user-service]
    design_pin: "4.1.x BOM"
    design_ref: "00 §2"
    track_line: "4.1"
    latest: { version: "4.1.1", released: 2026-08-20 }
    newest_line: { version: "4.2.0-M2", prerelease: true }
    support: { line_eol: 2027-07-31, commercial_eol: 2028-07-31 }
    check: { kind: endoflife, url: "https://endoflife.date/api/v1/products/spring-boot" }
    check_alt: "https://repo1.maven.org/maven2/org/springframework/boot/spring-boot-dependencies/maven-metadata.xml"
    notes: "Boot BOM manages Spring Framework, Spring Security, Spring Session, Spring Data, Jackson, Tomcat, Netty, Micrometer, Flyway. Bumping Boot is the normal way to pick up their patches."

  - id: spring-framework
    name: Spring Framework
    category: framework
    owner: app
    managed_by: spring-boot
    used_by: [gateway, inventory, user-service]
    design_pin: "managed by Boot 4.1.x"
    design_ref: "00 §2"
    track_line: "7.0"
    latest: { version: "7.0.9", released: 2026-08-20 }
    support: { line_eol: 2027-07-31 }
    check: { kind: endoflife, url: "https://endoflife.date/api/v1/products/spring-framework" }
    notes: "Boot 4.1.1 manages 7.0.9. Track for CVEs (spring.io/security); override the BOM property only for an urgent fix."

  - id: spring-security
    name: Spring Security
    category: framework
    owner: app
    managed_by: spring-boot
    used_by: [gateway, inventory, user-service]
    design_pin: "managed by Boot 4.1.x"
    design_ref: "00 §4, 01 §5"
    track_line: "7.1"
    latest: { version: "7.1.1", released: null }
    support: { line_eol: null }
    check: { kind: maven_metadata, url: "https://repo1.maven.org/maven2/org/springframework/security/spring-security-core/maven-metadata.xml", filter: "^7\\.1\\." }
    notes: "Version taken from the spring-boot-dependencies-4.1.1 POM; release date not verified. Security-critical (OAuth2 client/resource server, CSRF, OIDC logout)."

  - id: spring-cloud
    name: Spring Cloud release train (incl. Spring Cloud Gateway)
    category: framework
    owner: app
    used_by: [gateway]
    design_pin: "release train compatible with Boot 4.1"
    design_ref: "00 §2, 01 §3.1, ADR 0001"
    track_line: "2025.1"
    latest: { version: "2025.1.3", codename: "Oakwood", released: 2026-08-20, gateway_version: "5.0.3" }
    newest_line: { version: "2026.0.0-M1", prerelease: true }
    support: { line_eol: null, note: "Compatible with Boot 4.0.x and 4.1.x from 2025.1.2" }
    check: { kind: maven_metadata, url: "https://repo1.maven.org/maven2/org/springframework/cloud/spring-cloud-dependencies/maven-metadata.xml", filter: "^2025\\.1\\." }
    check_alt: "https://spring.io/projects/spring-cloud (compatibility table)"
    notes: "2025.1.3 fixed 17 CVEs, including in Gateway. The design uses the WebFlux Gateway server variant."

  - id: otel-java-agent
    name: OpenTelemetry Java agent
    category: observability-agent
    owner: app
    used_by: [gateway, inventory, user-service]
    design_pin: "baked into each Java image at /otel/opentelemetry-javaagent.jar"
    design_ref: "00 §8"
    track_line: "2.x"
    latest: { version: "2.32.0", released: 2026-10-03 }
    check: { kind: github_release, url: "https://api.github.com/repos/open-telemetry/opentelemetry-java-instrumentation/releases/latest" }
    check_alt: "https://repo1.maven.org/maven2/io/opentelemetry/javaagent/opentelemetry-javaagent/maven-metadata.xml"

  # ---------- Frontend ----------

  - id: nodejs
    name: Node.js
    category: language-runtime
    owner: app
    used_by: [frontend-ssr, frontend-build]
    design_pin: "Node.js 24 LTS; build node:24, runtime node:24-slim"
    design_ref: "00 §2, 04 §8"
    image: "node:24-slim (pin e.g. node:24.22.0-slim)"
    track_line: "24"
    latest: { version: "24.22.0", released: 2026-10-14 }
    newest_line: { version: "26.12.0", released: 2026-10-14, active_lts_from: 2026-10-28, eol: 2029-04-30 }
    support: { line_eol: 2028-04-30, phase: "maintenance LTS since 2026-10-20" }
    check: { kind: endoflife, url: "https://endoflife.date/api/v1/products/nodejs" }
    check_alt: "https://nodejs.org/dist/index.json"
    notes: "At check time the Docker Hub tag node:24 did not match the 24.22.0 digest, while node:24-slim did. Pin full versions."

  - id: angular
    name: Angular (framework + CLI + @angular/ssr)
    category: framework
    owner: app
    used_by: [frontend]
    design_pin: "Angular 22, Angular CLI 22"
    design_ref: "00 §2, 04 §3.1"
    track_line: "22"
    latest: { version: "22.2.3", released: 2026-10-14 }
    newest_line: { version: "23", released: null, expected: "~2027-06" }
    support: { active_until: 2027-06-30, line_eol: 2028-06-30 }
    check: { kind: endoflife, url: "https://endoflife.date/api/v1/products/angular" }
    notes: "Includes Angular Material/CDK, released in lockstep. From v22 there is one major per 12 months."

  # ---------- Identity ----------

  - id: keycloak
    name: Keycloak (server, custom image) + Keycloak Operator
    category: identity
    owner: app   # the operator itself is owner: platform (06 §2)
    used_by: [identity]
    design_pin: null
    design_ref: "05 §5.1, 06 §2"
    image: "quay.io/keycloak/keycloak:<ver> (base of bookstore-keycloak); quay.io/keycloak/keycloak-operator:<ver>"
    track_line: "26"
    latest: { version: "26.8.1", released: 2026-10-13, operator_version: "26.8.1" }
    support: { line_eol: null, note: "Only the latest minor is supported; 26.7 went EOL 2026-10-01" }
    check: { kind: endoflife, url: "https://endoflife.date/api/v1/products/keycloak" }
    check_alt: "https://www.keycloak.org/downloads"
    notes: "Keep the operator version equal to the server version. Take a CNPG backup before a major upgrade (05 §6)."

  - id: keycloak-config-cli
    name: keycloak-config-cli (adorsys)
    category: identity-tooling
    owner: app
    used_by: [identity]
    design_pin: "image pinned to match the Keycloak major"
    design_ref: "05 §5.2, ADR 0004"
    image: "adorsys/keycloak-config-cli:<cli>-<keycloak>"
    track_line: "6"
    latest: { version: "6.5.1", released: 2026-05-22, newest_kc26_tag: "6.5.1-26.5.5" }
    check: { kind: github_release, url: "https://api.github.com/repos/adorsys/keycloak-config-cli/releases/latest" }
    check_alt: "https://hub.docker.com/v2/repositories/adorsys/keycloak-config-cli/tags?page_size=50&name=-26"
    notes: "No build for Keycloak 26.8 yet. The floating tag 6.5.1-26 resolves to 26.1.0, so pin the full tag."

  # ---------- Data platform ----------

  - id: postgresql
    name: PostgreSQL
    category: database
    owner: app
    used_by: [inventory, keycloak]
    design_pin: "17"
    design_ref: "06 §3, P-03"
    track_line: "17"
    latest: { version: "17.11", released: 2026-08-10 }
    newest_line: { version: "18.6", released: 2026-08-11, eol: 2030-11-14 }
    support: { line_eol: 2029-11-08 }
    patch_cadence: "Quarterly minors; next 2026-11-12, then 2027-02-11"
    check: { kind: endoflife, url: "https://endoflife.date/api/v1/products/postgresql" }
    notes: "PostgreSQL 19 RC1 came out 2026-10-15. A major upgrade must keep the explicit LC_CTYPE (ADR 0008)."

  - id: cnpg-postgresql-image
    name: CloudNativePG PostgreSQL operand image
    category: database-image
    owner: app
    used_by: [inventory, keycloak]
    design_pin: "ghcr.io/cloudnative-pg/postgresql:17"
    design_ref: "06 §3.1"
    image: "ghcr.io/cloudnative-pg/postgresql:17.11-standard-trixie"
    track_line: "17"
    latest: { version: "17.11-202609210816-standard-trixie", released: 2026-09-21 }
    check: { kind: html, url: "https://raw.githubusercontent.com/cloudnative-pg/artifacts/main/image-catalogs/catalog-standard-trixie.yaml" }
    notes: "Bare MM / MM.mm tags and the 'system' type are deprecated. Use MM.mm-standard-<os> plus the Barman Cloud plugin, or pin by digest."

  - id: cloudnative-pg
    name: CloudNativePG operator
    category: operator
    owner: platform
    used_by: [postgresql]
    design_pin: null
    design_ref: "06 §2, P-01"
    track_line: "1.30"
    latest: { version: "1.30.0", released: 2026-06-29 }
    support: { line_eol: "~2026-12", note: "1.29 EOL 2026-09-29; 1.31 overdue" }
    check: { kind: github_release, url: "https://api.github.com/repos/cloudnative-pg/cloudnative-pg/releases/latest" }
    check_alt: "https://cloudnative-pg.io/docs/devel/supported_releases"

  - id: cnpg-barman-cloud-plugin
    name: CNPG Barman Cloud plugin
    category: operator-plugin
    owner: platform
    used_by: [postgresql-backups]
    design_pin: null
    design_ref: "06 §2, §3.3"
    track_line: "0.x"
    latest: { version: "0.15.1", released: 2026-09-30 }
    check: { kind: github_release, url: "https://api.github.com/repos/cloudnative-pg/plugin-barman-cloud/releases/latest" }

  - id: percona-server-mongodb
    name: Percona Server for MongoDB
    category: database
    owner: app
    used_by: [user-service]
    design_pin: null
    design_ref: "06 §4, P-02"
    image: "percona/percona-server-mongodb:<ver>"
    track_line: "8.0"
    latest: { version: "8.0.32-14", released: 2026-09-23 }
    support: { line_eol: 2029-10-31, note: "upstream MongoDB 8.0 EOL; 7.0 EOL 2027-08-31" }
    check: { kind: html, url: "https://docs.percona.com/percona-server-for-mongodb/8.0/release_notes/index.html" }
    check_alt: "https://endoflife.date/api/v1/products/mongodb"
    notes: "Upstream MongoDB is at 8.0.34. Percona lags upstream by a few patches. 8.0 is the operator default since 1.21."

  - id: percona-operator-mongodb
    name: Percona Operator for MongoDB
    category: operator
    owner: platform
    used_by: [percona-server-mongodb]
    design_pin: null
    design_ref: "06 §2, P-02"
    track_line: "1.x"
    latest: { version: "1.23.1", released: 2026-10-05, tested_with: { psmdb: "8.0.32-14", pbm: "2.15.0" } }
    check: { kind: html, url: "https://docs.percona.com/percona-operator-for-mongodb/latest/RN/index.html" }
    check_alt: "https://api.github.com/repos/percona/percona-server-mongodb-operator/releases/latest"
    notes: "The GitHub 'latest' release lags the docs (it showed 1.23.0), so prefer the docs page."

  - id: percona-backup-mongodb
    name: Percona Backup for MongoDB (PBM)
    category: backup
    owner: platform
    used_by: [percona-server-mongodb]
    design_pin: null
    design_ref: "06 §2, §4"
    track_line: "2.x"
    latest: { version: "2.16.0", released: 2026-09-24 }
    check: { kind: github_release, url: "https://api.github.com/repos/percona/percona-backup-mongodb/releases/latest" }
    notes: "Use the PBM version the operator release is tested with (2.15.0 for 1.23.1). 2.16 drops GCS HMAC auth."

  - id: rabbitmq
    name: RabbitMQ
    category: message-broker
    owner: app
    used_by: [inventory]
    design_pin: "rabbitmq:4.1-management"
    design_ref: "06 §5.1, P-08"
    image: "rabbitmq:<ver>-management"
    track_line: "4.1"
    latest: { version: "4.4.0", released: 2026-10-20 }
    pinned_line_latest: { line: "4.1", version: "4.1.8", released: 2026-01-22 }
    lines:
      - { line: "4.4", latest: "4.4.0", community_eol: 2027-07-31 }
      - { line: "4.3", latest: "4.3.6", community_eol: 2027-01-31 }
      - { line: "4.2", latest: "4.2.11", community_eol: 2026-07-31 }
      - { line: "4.1", latest: "4.1.8", community_eol: 2026-01-31 }
    support: { line_eol: 2026-01-31, status: "pinned line out of community support" }
    check: { kind: html, url: "https://www.rabbitmq.com/release-information" }
    check_alt: "https://api.github.com/repos/rabbitmq/rabbitmq-server/releases/latest"
    notes: "endoflife.date lags here (it was missing 4.2.11 and 4.4). P-08 allows any 4.x."

  - id: rabbitmq-cluster-operator
    name: RabbitMQ Cluster Operator
    category: operator
    owner: platform
    used_by: [rabbitmq]
    design_pin: null
    design_ref: "06 §2"
    track_line: "2.x"
    latest: { version: "2.23.0", released: 2026-09-09 }
    check: { kind: github_release, url: "https://api.github.com/repos/rabbitmq/cluster-operator/releases/latest" }
    notes: "Since 2.22 the HTTP startup probe requires RabbitMQ 4.2.4+ or 4.3+. The default image is 4.3.4."

  - id: rabbitmq-topology-operator
    name: RabbitMQ Messaging Topology Operator
    category: operator
    owner: platform
    used_by: [rabbitmq]
    design_pin: null
    design_ref: "06 §2, §5.2"
    track_line: "1.x"
    latest: { version: "1.20.3", released: 2026-09-09 }
    check: { kind: github_release, url: "https://api.github.com/repos/rabbitmq/messaging-topology-operator/releases/latest" }
    notes: "Since 1.20, user-provided Secrets need the label rabbitmq.com/topology-operator: \"true\"."

  - id: valkey
    name: Valkey (redis-sessions, redis-cache)
    category: key-value-store
    owner: app
    used_by: [gateway, inventory]
    design_pin: "valkey/valkey:8 (minor pinned in overlays)"
    design_ref: "06 §6, P-10, ADR 0017"
    image: "valkey/valkey:8.1.10"
    track_line: "8"
    latest: { version: "9.1.2", released: 2026-08-31 }
    pinned_line_latest: { line: "8.1", version: "8.1.10", released: 2026-08-31 }
    lines:
      - { line: "9.1", latest: "9.1.2", maintenance_eol: 2029-05-19, security_eol: 2031-05-19 }
      - { line: "9.0", latest: "9.0.6", maintenance_eol: 2028-10-21 }
      - { line: "8.1", latest: "8.1.10", maintenance_eol: 2028-03-31, security_eol: 2030-03-31 }
      - { line: "8.0", latest: "8.0.11", maintenance_eol: 2027-09-15 }
    support: { line_eol: 2030-03-31 }
    check: { kind: endoflife, url: "https://endoflife.date/api/v1/products/valkey" }
    notes: "The tag valkey/valkey:8 points to 8.1."

  - id: redis-exporter
    name: redis_exporter (sidecar)
    category: observability-exporter
    owner: app
    used_by: [valkey]
    design_pin: "oliver006/redis_exporter"
    design_ref: "06 §6"
    image: "oliver006/redis_exporter:v<ver>"
    track_line: "1.x"
    latest: { version: "1.92.1", released: 2026-09-28 }
    check: { kind: github_release, url: "https://api.github.com/repos/oliver006/redis_exporter/releases/latest" }

  - id: garage
    name: Garage (S3-compatible object store)
    category: object-storage
    owner: app
    used_by: [inventory]
    design_pin: null
    design_ref: "06 §7, P-11, ADR 0010"
    image: "dxflrs/garage:v2.4.1"
    track_line: "2.x"
    latest: { version: "2.4.1", released: 2026-09-08 }
    check: { kind: html, url: "https://garagehq.deuxfleurs.fr/_releases.html" }
    check_alt: "https://hub.docker.com/v2/repositories/dxflrs/garage/tags?page_size=25"
    notes: "The Forgejo forge has a bot check. Docker Hub tags that look like commit hashes are dev builds; ignore them."

  # ---------- Cluster platform (platform team) ----------

  - id: kubernetes
    name: Kubernetes (on-prem; EKS in phase 2)
    category: orchestrator
    owner: platform
    used_by: [all]
    design_pin: null
    design_ref: "ARCH §6.1"
    track_line: null   # set to the cluster's minor once confirmed
    latest: { version: "1.37.1", released: 2026-09-23 }
    lines:
      - { line: "1.37", latest: "1.37.1", eol: 2027-10-28, eks_standard_eol: 2027-12-01 }
      - { line: "1.36", latest: "1.36.5", eol: 2027-06-28, eks_standard_eol: 2027-08-02 }
      - { line: "1.35", latest: "1.35.9", eol: 2027-02-28, eks_standard_eol: 2027-03-27 }
      - { line: "1.34", latest: "1.34.12", eol: 2026-10-27, eks_standard_eol: 2026-12-02 }
    check: { kind: endoflife, url: "https://endoflife.date/api/v1/products/kubernetes" }
    check_alt: "https://endoflife.date/api/v1/products/amazon-eks"

  - id: apisix
    name: Apache APISIX + APISIX Ingress Controller
    category: ingress
    owner: platform
    used_by: [ingress]
    design_pin: null
    design_ref: "01 §5.6, ADR 0011, ADR 0012"
    track_line: "3.x"
    latest: { version: "3.18.0", released: 2026-08-20, ingress_controller: "2.2.0" }
    support: { line_eol: null, note: "Only the newest minor is supported; no current LTS (3.2 LTS EOL 2024-11-13)" }
    check: { kind: github_release, url: "https://api.github.com/repos/apache/apisix/releases/latest" }
    check_alt: "https://api.github.com/repos/apache/apisix-ingress-controller/releases/latest"
    notes: "IC 2.2.0 requires Kubernetes ≥ 1.31 and Gateway API 1.6.0 CRDs (server-side apply)."

  - id: argo-cd
    name: Argo CD
    category: gitops
    owner: platform
    used_by: [delivery]
    design_pin: null
    design_ref: "06 §10, ARCH §6.1"
    track_line: "3.5"
    latest: { version: "3.5.4", released: 2026-10-06 }
    support: { note: "Newest three minors supported (3.5, 3.4, 3.3)" }
    check: { kind: endoflife, url: "https://endoflife.date/api/v1/products/argo-cd" }

  - id: external-secrets
    name: External Secrets Operator
    category: secrets
    owner: platform
    used_by: [all]
    design_pin: null
    design_ref: "06 §9"
    track_line: "2.x"
    latest: { version: "2.13.0", released: 2026-10-16 }
    check: { kind: artifacthub, url: "https://artifacthub.io/api/v1/packages/helm/external-secrets-operator/external-secrets" }
    notes: "GitHub releases/latest points at a chart tag, not the app version."

  - id: vault
    name: HashiCorp Vault
    category: secrets
    owner: platform
    used_by: [external-secrets]
    design_pin: null
    design_ref: "ARCH §6.1, 05 §5.2"
    track_line: "2.1"
    latest: { version: "2.1.2", released: 2026-10-06 }
    check: { kind: endoflife, url: "https://endoflife.date/api/v1/products/hashicorp-vault" }

  - id: helm
    name: Helm (CI + Argo CD rendering)
    category: delivery-tooling
    owner: platform
    used_by: [ci, delivery]
    design_pin: null
    design_ref: "06 §10–11"
    track_line: "3.x"
    latest: { version: "4.3.1", released: 2026-10-15 }
    pinned_line_latest: { line: "3", version: "3.22.1", released: 2026-10-15 }
    support: { line_eol: null, note: "Helm 3 end-of-support date not verified" }
    check: { kind: github_release, url: "https://api.github.com/repos/helm/helm/releases?per_page=10", filter: "^v[34]\\." }

  - id: kube-prometheus-stack
    name: kube-prometheus-stack (Prometheus, Alertmanager, Grafana, Prometheus Operator)
    category: observability
    owner: platform
    used_by: [observability]
    design_pin: null
    design_ref: "06 §2, §12, ARCH §6.4"
    track_line: null
    latest:
      chart: "92.11.0"
      prometheus_operator: "0.94.1"
      prometheus: { version: "3.15.0", released: 2026-09-25, eol: 2026-11-06 }
      prometheus_lts: { version: "3.13.4", released: 2026-09-29, eol: 2027-07-31 }
      grafana: { version: "13.2.4", released: 2026-10-13, eol: 2027-05-18 }
      alertmanager: { version: "0.34.0", released: 2026-08-16 }
    check: { kind: artifacthub, url: "https://artifacthub.io/api/v1/packages/helm/prometheus-community/kube-prometheus-stack" }
    check_alt: ["https://endoflife.date/api/v1/products/prometheus", "https://endoflife.date/api/v1/products/grafana"]

  - id: loki
    name: Grafana Loki
    category: observability
    owner: platform
    used_by: [observability]
    design_pin: null
    design_ref: "06 §2, ARCH §6.4"
    track_line: "3.7"
    latest: { version: "3.7.8", released: 2026-09-17 }
    check: { kind: endoflife, url: "https://endoflife.date/api/v1/products/grafana-loki" }

  - id: tempo
    name: Grafana Tempo
    category: observability
    owner: platform
    used_by: [observability]
    design_pin: null
    design_ref: "06 §2, ARCH §6.4"
    track_line: "3.x"
    latest: { version: "3.1.0", released: 2026-09-29 }
    check: { kind: github_release, url: "https://api.github.com/repos/grafana/tempo/releases/latest" }

  - id: otel-collector
    name: OpenTelemetry Collector (contrib)
    category: observability
    owner: platform
    used_by: [observability]
    design_pin: null
    design_ref: "00 §8, 06 §2"
    track_line: "0.x"
    latest: { version: "0.163.1", released: 2026-10-16 }
    check: { kind: github_release, url: "https://api.github.com/repos/open-telemetry/opentelemetry-collector-releases/releases/latest" }

  - id: reloader
    name: Stakater Reloader
    category: delivery-tooling
    owner: platform
    used_by: [all]
    design_pin: "Reloader or equivalent"
    design_ref: "06 §9, P-12"
    track_line: "1.x"
    latest: { version: "1.4.22", chart: "2.2.18", released: 2026-09-30 }
    check: { kind: artifacthub, url: "https://artifacthub.io/api/v1/packages/helm/stakater/reloader" }
    notes: "Reloader v2 is still beta. GitHub releases/latest points at a chart tag."

  - id: cert-manager
    name: cert-manager (optional, only if P-07 changes)
    category: certificates
    owner: platform
    used_by: [percona-server-mongodb]
    design_pin: null
    design_ref: "06 P-07"
    optional: true
    track_line: "1.21"
    latest: { version: "1.21.2", released: 2026-09-10 }
    support: { note: "1.21 and 1.20 supported" }
    check: { kind: endoflife, url: "https://endoflife.date/api/v1/products/cert-manager" }
```

## Out of scope

The following are library-level dependencies, so this file doesn't track them: springdoc-openapi, the AWS SDK v2, TwelveMonkeys, Testcontainers, Playwright, Vitest, openapi-typescript, prom-client and the OpenTelemetry Node SDK. Track them with Dependabot or Renovate, which can also bump the image tags above once they are pinned to full versions.
