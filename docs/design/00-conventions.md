# 00 — Conventions and shared contracts

| | |
| --- | --- |
| **Status** | Draft v0.2 — assumptions marked `A-xx` need confirmation. v0.2: offset paging with totals for catalog tables, `publishedDate`/`description` on books, `nationality` on authors, genre `SELF_HELP` (driven by the UI mock‑ups, 04 §3.5) |
| **Applies to** | Every component |
| **Source** | `architecture.md` (referred to below as ARCH) |

This document holds everything more than one component depends on: repository layout, API style, error format, event contracts, security wiring, configuration, observability and the Kubernetes workload shape. Component docs refer here instead of repeating it.

## How to use these docs

| Doc | Component | Build after |
| --- | --- | --- |
| `00-conventions.md` | Shared rules and contracts (this doc) | — |
| `06-data-platform.md` | PostgreSQL, MongoDB, RabbitMQ, Redis, object storage, NetworkPolicies, GitOps layout | 00 |
| `05-keycloak.md` | Realm, clients, roles, themes, realm-as-code | 06 |
| `02-inventory-service.md` | Books, authors, covers, search, outbox, SSE | 05, 06 |
| `03-user-service.md` | Profiles, admin user management via Keycloak | 05, 06 |
| `01-gateway.md` | BFF: login, sessions, CSRF, routing | 02, 03 (routes only need the services to exist) |
| `04-frontend.md` | Angular SSR app: public catalog, account, admin UI | 01, 02, 03 |

Rules for a coding agent working from these docs:

1. If a component doc and ARCH disagree, the component doc wins. Every such deviation is listed in that doc's **Assumptions to confirm** table.
2. If a component doc and this document disagree on a cross‑cutting rule, this document wins. Flag the conflict in the PR.
3. Where a doc is silent, choose the simplest option consistent with these docs and record the choice in the PR description under "Unspecified decisions". Do not invent new endpoints, events or fields that other components would depend on.
4. Never edit another component's contract (OpenAPI file, event schema) as part of a change to your component. Contract changes are their own PR.

### Common document template

Every component doc uses these sections, in this order. A section may say "Not applicable" but is never removed.

1. Purpose and scope (responsibilities, non‑goals)
2. Context (dependencies, diagram)
3. Interfaces (HTTP API, events, other)
4. Data model
5. Behaviour and flows
6. Security
7. Configuration
8. Deployment
9. Observability
10. Failure modes
11. Testing
12. Implementation plan (ordered milestones, each independently testable)
13. Assumptions to confirm

---

## 1. Repository layout

One monorepo (A‑01).

```
bookstore/
├── pom.xml                         # parent POM: bookstore-parent
├── libs/
│   ├── contracts/                  # shared Java types: Genre, event envelope + payload records
│   ├── security-common/            # Keycloak role converter, actor extraction, resource-server autoconfig
│   └── web-common/                 # ProblemDetail handlers, ETag helpers, cursor codec, audit types
├── services/
│   ├── gateway/
│   ├── inventory/
│   └── user/
├── frontend/                       # Angular workspace (app: bookstore-web)
├── identity/
│   └── keycloak/                   # realm config (keycloak-config-cli), login theme
├── platform/
│   ├── charts/                     # one Helm chart per deployable
│   ├── overlays/{onprem,aws}/      # Kustomize overlays
│   └── argocd/                     # Argo CD Applications
└── docs/
    ├── architecture.md
    └── design/                     # these documents
```

Each Java service contains its own committed `openapi.yaml` at `services/<name>/openapi.yaml` (see §3.9).

## 2. Build and toolchain

| Item | Choice |
| --- | --- |
| Java | 25, toolchain enforced by `maven-enforcer-plugin` |
| Build | Maven 3.9+ with the Maven wrapper (A‑02). Parent POM imports the Spring Boot 4.1.x BOM and the Spring Cloud BOM from the release train compatible with Boot 4.1 (check the Spring Cloud compatibility table; do not guess) |
| Spring Boot 4 specifics | Use Boot 4's modular starters (for example the dedicated Flyway starter). Jackson 3 is the default: its packages are `tools.jackson.*`, annotations remain `com.fasterxml.jackson.annotation.*`. Do not add Jackson 2 |
| Null safety | Annotate every package with JSpecify `@NullMarked` (`package-info.java`); mark nullable fields and parameters `@Nullable` |
| Formatting | Spotless with google‑java‑format; `mvn spotless:check` runs in CI |
| Base package | `com.bookstore.<service>` (A‑03 — replace with your company's namespace before the first commit) |
| Frontend | Node.js 24 LTS, npm, Angular CLI 22 |
| Images | Multi‑stage Dockerfile per service; runtime `eclipse-temurin:25-jre`; non‑root UID 10001; read‑only root filesystem; tag = git commit SHA |

### Internal service structure

Package by feature, not by layer:

```
com.bookstore.inventory
├── book/        # BookController, BookService, Book (entity), BookRepository, dto/
├── author/
├── cover/
├── search/
├── events/      # outbox, relay, SSE
├── audit/
└── config/
```

- Controllers are thin: validate, call one service method, map to DTO.
- `@Transactional` lives on service methods only.
- Entities never leave the service layer. API DTOs are Java `record`s.
- `spring.jpa.open-in-view=false`.

## 3. HTTP API conventions

### 3.1 Paths

The gateway strips the `/api` prefix (A‑04). Services never see `/api`.

| Browser path | Service path |
| --- | --- |
| `/api/catalog/books` | `/catalog/books` |
| `/api/admin/catalog/books/{id}` | `/admin/catalog/books/{id}` |
| `/api/users/me` | `/users/me` |
| `/api/admin/users` | `/admin/users` |

### 3.2 JSON

- `Content-Type: application/json`. Field names in camelCase.
- IDs are UUID strings. Keycloak user IDs (`sub`) are also UUID strings.
- Timestamps are ISO‑8601 UTC with `Z`, millisecond precision: `"2026-10-20T08:15:30.123Z"`. Stored as `timestamptz` (Postgres) or `Date` (Mongo).
- Calendar dates without a time (e.g. a book's `publishedDate`) are `yyyy-MM-dd` strings, Java `LocalDate`, Postgres `date`. No time‑zone conversion anywhere.
- Money is a **string** with exactly two decimal places plus a separate currency field: `"price": "450.00", "currency": "TWD"`. Single currency `TWD` in v1 (A‑05). Java type `BigDecimal`, scale 2, `RoundingMode.HALF_UP` on input.
- Enums are `UPPER_SNAKE_CASE` strings.
- Optional fields that have no value are serialized as `null`, not omitted, so response shapes are stable.
- Unknown request fields are rejected (`FAIL_ON_UNKNOWN_PROPERTIES` on) so typos surface as 400 instead of silently doing nothing.

### 3.3 Pagination

**Keyset (default).** Request: `?limit=20&cursor=<opaque>`. `limit` defaults to 20, max 100.

```json
{
  "items": [ ],
  "nextCursor": "eyJ2IjoxLCJzIjoiTkVXRVNUIiwiayI6WyIyMDI2LTEwLTIwVDA4OjE1OjMwLjEyM1oiLCI3YjQ..."
}
```

`nextCursor` is `null` on the last page. The cursor is base64url (no padding) of JSON:

```json
{ "v": 1, "s": "NEWEST", "k": ["2026-10-20T08:15:30.123Z", "7b4e…uuid"] }
```

- `v` — cursor format version.
- `s` — sort it was issued for. A cursor used with a different `sort` → 400 `invalid-cursor`.
- `k` — the sort key values and `id` of the last item returned.

Shared codec: `libs/web-common` → `CursorCodec`. Malformed cursors → 400 `invalid-cursor`. The cursor is not signed; it only contains values the client has already seen.

**Offset (exception).** Used where the backing system cannot do keyset (Keycloak user search) and for tables whose UI shows a total and page sizes (A‑11): the public and admin book lists and the admin author list. Request `?offset=0&limit=20`; response `{ "items": [], "offset": 0, "limit": 20, "total": 132 }`.

- `offset` max 10 000 (larger → 400 `validation-failed`); deep pages beyond that are reached by narrowing the search.
- `total` is an exact `COUNT(*)` with the same filters, computed in the same read transaction as the page.
- Offset paging can show a row twice or skip one if the data changes between page requests; accepted for these tables.
- Endpoints that use offset do not accept `cursor`, and vice versa. Audit logs stay keyset.

### 3.4 Optimistic concurrency

- Every single‑resource `GET` returns `ETag: "<version>"` (strong ETag, the entity's `version` number).
- Every `PUT`, `PATCH` and `DELETE` on a versioned resource **requires** `If-Match: "<version>"`.
  - Missing → 428 `precondition-required`.
  - Stale → 412 `version-conflict` with the current `version` in the problem body.
- Responses to successful writes carry the new `ETag`.
- JPA/Spring Data optimistic lock failures that slip past the header check map to 412 `version-conflict` as well.

### 3.5 Status codes

| Code | Use |
| --- | --- |
| 200 | Successful GET, PUT, PATCH |
| 201 | Successful POST that creates; `Location` header set |
| 204 | Successful DELETE |
| 400 | Validation failure, malformed JSON, bad cursor |
| 401 | Missing or invalid token |
| 403 | Authenticated but lacking role |
| 404 | Resource does not exist (or is soft‑deleted, for public endpoints) |
| 409 | State conflict that is not a version mismatch (duplicate ISBN, author still attached to books) |
| 412 | `If-Match` stale |
| 413 | Upload too large |
| 415 | Unsupported media type |
| 428 | `If-Match` missing |
| 502 / 503 | Downstream dependency (Keycloak, object storage) failed or unavailable |

### 3.6 Errors — RFC 9457 Problem Details

All errors are `application/problem+json`, produced through Spring's `ProblemDetail`. `libs/web-common` provides a `@RestControllerAdvice` that every service registers.

```json
{
  "type": "https://bookstore.example/problems/validation-failed",
  "title": "Request validation failed",
  "status": 400,
  "detail": "2 fields are invalid",
  "instance": "/admin/catalog/books",
  "code": "validation-failed",
  "traceId": "4bf92f3577b34da6a3ce929d0e0e4736",
  "errors": [
    { "field": "isbn", "code": "invalid-isbn", "message": "ISBN check digit is wrong" },
    { "field": "price", "code": "out-of-range", "message": "must be between 0.00 and 99999999.99" }
  ]
}
```

- `type` is `https://bookstore.example/problems/<code>`. The URL does not need to resolve.
- `code` duplicates the slug so clients can switch on it without parsing URLs.
- `traceId` is the current OpenTelemetry trace ID (from MDC `trace_id`).
- `errors` appears only for `validation-failed`.
- Stack traces and exception messages from libraries are never returned. Unexpected exceptions → 500 `internal-error` with a generic `detail`; the full exception is logged.

Shared codes: `validation-failed`, `malformed-request`, `invalid-cursor`, `not-found`, `unauthorized`, `forbidden`, `version-conflict`, `precondition-required`, `payload-too-large`, `unsupported-media-type`, `dependency-unavailable`, `internal-error`. Services add their own codes in their docs.

### 3.7 Validation

Jakarta Bean Validation on request records, plus explicit service‑level checks for cross‑field and database‑dependent rules. Strings are trimmed before validation; an all‑whitespace string counts as empty.

### 3.8 Request size

JSON bodies: 1 MB maximum. Multipart uploads: 6 MB per request (cover images, see 02). Both the ingress and the gateway enforce the same limits.

### 3.9 OpenAPI

- springdoc‑openapi (Boot 4‑compatible line), served at `/v3/api-docs` on the **management port only**. It is not routed through the gateway.
- Each service commits `openapi.yaml`. A test regenerates the spec and fails if it differs from the committed file, so contract changes show up in review.
- The frontend generates TypeScript types from these files (see 04).

## 4. Security conventions (services)

Both services are OAuth2 resource servers. They hold no sessions and use no cookies.

```yaml
# mapped from environment variables, see §7
spring.security.oauth2.resourceserver.jwt:
  issuer-uri: ${OIDC_ISSUER_URI}     # public URL, e.g. https://auth.bookstore.example/realms/bookstore
  jwk-set-uri: ${OIDC_JWK_SET_URI}   # in-cluster, e.g. http://keycloak-service.identity.svc:8080/realms/bookstore/protocol/openid-connect/certs
  audiences: [bookstore-api]
```

With both properties set, keys are fetched from `jwk-set-uri` and the `iss` claim is still validated against `issuer-uri`. Do not let the service call the issuer's discovery endpoint at startup (it would go out through the public URL).

`libs/security-common` provides:

```java
// Converts Keycloak realm roles to Spring authorities: realm_access.roles ["ADMIN"] -> ROLE_ADMIN
public final class KeycloakRealmRoleConverter implements Converter<Jwt, AbstractAuthenticationToken> {
  @Override
  public AbstractAuthenticationToken convert(Jwt jwt) {
    Map<String, Object> realmAccess = jwt.getClaimAsMap("realm_access");
    Collection<String> roles = realmAccess == null ? List.of()
        : (Collection<String>) realmAccess.getOrDefault("roles", List.of());
    List<GrantedAuthority> authorities = roles.stream()
        .filter(r -> r.equals("USER") || r.equals("ADMIN"))   // ignore Keycloak's default-roles-*, offline_access, …
        .map(r -> new SimpleGrantedAuthority("ROLE_" + r))
        .collect(Collectors.toUnmodifiableList());
    return new JwtAuthenticationToken(jwt, authorities, jwt.getSubject());
  }
}
```

and an auto‑configured `SecurityFilterChain` baseline:

- `SessionCreationPolicy.STATELESS`, CSRF disabled (no cookies reach services), CORS disabled (same origin via gateway).
- `@EnableMethodSecurity`; every controller method declares `@PreAuthorize` explicitly, including public ones (`@PreAuthorize("permitAll()")`). A test fails the build if a `@RequestMapping` method lacks `@PreAuthorize` (A‑06).
- `Actor` record (`sub`, `username`, `roles`) resolvable as a controller argument via `@CurrentActor`. `username` comes from the `preferred_username` claim.

## 5. Event contracts

Owned by the inventory service; consumed by inventory replicas (SSE fan‑out, cache eviction), the browser (via SSE) and future consumers. Java records live in `libs/contracts` under `com.bookstore.contracts.events`.

### 5.1 Envelope

```json
{
  "eventId": "0b0c7f6e-3e0a-4b3c-9a37-3a6f1a7f3e21",
  "eventType": "book.price-changed",
  "schemaVersion": 1,
  "occurredAt": "2026-10-20T08:15:30.123Z",
  "aggregateType": "book",
  "aggregateId": "7b4e…uuid",
  "aggregateVersion": 4,
  "payload": { }
}
```

- `eventId` is generated when the outbox row is written and is the outbox row's `id`.
- `aggregateVersion` is the entity's `version` after the change. Consumers use it to ignore events older than the state they hold.

### 5.2 AMQP transport

| Property | Value |
| --- | --- |
| Exchange | `catalog.events` (topic, durable) |
| Routing key | equals `eventType` |
| `message_id` | `eventId` |
| `type` | `eventType` |
| `content_type` | `application/json` |
| `delivery_mode` | 2 (persistent) |
| `timestamp` | `occurredAt` |
| Headers | `traceparent`, `tracestate` (W3C), `schema-version` |

### 5.3 Event types and payloads (schemaVersion 1)

`BookView` (public‑safe; also used by the public API):

```json
{
  "id": "uuid", "isbn": "9789573317241", "title": "…", "genre": "FANTASY",
  "price": "450.00", "currency": "TWD", "pageCount": 320, "inStock": true,
  "publishedDate": "2001-06-01", "description": "…",
  "coverUrl": "/api/catalog/covers/covers/7b4e…/c1a2….webp",
  "authors": [ { "id": "uuid", "name": "…" } ],
  "version": 4, "createdAt": "…", "updatedAt": "…"
}
```

| Event type | Payload |
| --- | --- |
| `book.created` | `{ "book": BookView }` |
| `book.updated` | `{ "book": BookView, "changedFields": ["title", "price", …] }` |
| `book.price-changed` | `{ "bookId", "oldPrice", "newPrice", "currency" }` |
| `book.deleted` | `{ "bookId" }` |
| `author.created` / `author.updated` | `{ "author": { "id", "name", "nationality", "bio", "version" } }` |
| `author.deleted` | `{ "authorId" }` |

Rules:

- A write that changes a book's price produces **two** outbox rows in the same transaction: `book.updated` (with `price` in `changedFields`) and `book.price-changed`. Any other book update produces only `book.updated`. This keeps `book.updated` sufficient for consumers that only want snapshots, while `book.price-changed` serves future consumers such as price alerts.
- Payloads never contain stock quantities, audit data or anything not shown on public pages, because they reach browsers.

### 5.4 Versioning

- Adding an optional field is not a version change. Consumers must ignore unknown fields.
- Removing or renaming a field, or changing its meaning, requires `schemaVersion` + 1 and a period where both versions are published.

### 5.5 Consumer rules

- Delivery is at‑least‑once. Deduplicate on `eventId`.
- Ordering across events is not guaranteed. Compare `aggregateVersion` with the version you hold and drop stale events.

## 6. Audit conventions

Every admin write (create, update, delete, cover change, role change, account creation) writes one audit record **in the same transaction as the change** (inventory: Postgres; user service: same Mongo write sequence, see 03).

| Field | Type | Notes |
| --- | --- | --- |
| `id` | UUID | |
| `occurredAt` | timestamp | |
| `actorSub` | string | JWT `sub` |
| `actorUsername` | string | JWT `preferred_username`, denormalised for display |
| `action` | enum | `CREATE`, `UPDATE`, `DELETE`, `COVER_UPLOAD`, `COVER_DELETE`, `ROLES_CHANGE`, `ENABLE`, `DISABLE`, `PASSWORD_RESET_SENT` |
| `entityType` | enum | `BOOK`, `AUTHOR`, `USER` |
| `entityId` | string | |
| `changes` | JSON | `{ "<field>": { "old": …, "new": … } }`; `null` values allowed; for `CREATE` all fields have `old: null` |
| `traceId` | string | |
| `outcome` | enum, optional | User service only: `PENDING`, `SUCCEEDED`, `FAILED` ([ADR 0016](../adr/261020-use-pending-then-confirm-user-audit.md)). Absent for inventory, whose audit shares the change's transaction |
| `correlationId` | UUID, optional | User service only: on outcome records, the `id` of the `PENDING` intent record |

Audit records are never updated or deleted by application code. Retention: indefinite in v1 (A‑07).

Records with `entityType = USER` never contain the subject user's personal data: `changes` is limited to an allow-list (`roles`, `enabled`, `sendInvite`, `inviteSent`, required-action names) and `entityId` is the Keycloak `sub` ([ADR 0015](../adr/261020-keep-pii-out-of-user-audit-records.md)). `actorUsername` (the acting admin) is kept.

## 7. Configuration conventions

- Every endpoint, credential, bucket name and tunable comes from an **environment variable**. Kubernetes injects them from ConfigMaps and Secrets (Secrets populated by External Secrets Operator).
- `application.yaml` maps env vars to Spring properties with safe defaults only for non‑environment values (timeouts, pool sizes). It contains no hostnames.
- No Spring profiles for environments. The only profile is `local`, used for developer conveniences that contain no URLs (for example, verbose SQL logging).
- Local development runs each service with Testcontainers through Spring Boot's test‑run support (`./mvnw spring-boot:test-run`): a `TestBookstoreApplication` class declares the containers with `@ServiceConnection`, so no connection strings are needed locally.
- Env var naming: `UPPER_SNAKE`, grouped by dependency prefix: `DB_*`, `MONGODB_*`, `RABBITMQ_*`, `REDIS_*`, `S3_*`, `OIDC_*`, `KEYCLOAK_*`. Each component doc lists its variables in a table with required/default columns.
- A service must fail fast at startup if a required variable is missing (`@ConfigurationProperties` + `@Validated`).

## 8. Observability conventions

**Tracing and logs — OpenTelemetry Java agent.**

- The agent jar is baked into each Java image at `/otel/opentelemetry-javaagent.jar` and enabled via `JAVA_TOOL_OPTIONS=-javaagent:/otel/opentelemetry-javaagent.jar`.
- Agent env: `OTEL_SERVICE_NAME=<service>`, `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector.observability.svc:4317`, `OTEL_EXPORTER_OTLP_PROTOCOL=grpc`, `OTEL_TRACES_EXPORTER=otlp`, `OTEL_LOGS_EXPORTER=otlp`, `OTEL_METRICS_EXPORTER=none` (metrics come from Micrometer/Prometheus), `OTEL_RESOURCE_ATTRIBUTES=deployment.environment=<env>,service.namespace=bookstore`.
- Do **not** add Micrometer Tracing or any Spring Boot tracing starter; the agent is the only tracer, to avoid double spans.
- Console logs are JSON using Spring Boot structured logging (`logging.structured.format.console=ecs`). The agent puts `trace_id` and `span_id` into MDC; include them.
- Never log tokens, cookies, `Authorization` headers, passwords, phone numbers or addresses. Log user IDs (`sub`), not emails.

**Metrics — Micrometer.**

- `/actuator/prometheus` on the management port, scraped by a `ServiceMonitor` in the chart.
- Common tags: `application`, `namespace`, `pod`.
- Custom metric names start with `bookstore.` (rendered as `bookstore_…` in Prometheus).

**Health.** `/actuator/health/liveness` and `/actuator/health/readiness` on the management port. Readiness includes the service's own database; it does **not** include optional dependencies (`redis-cache`) or Keycloak.

## 9. Kubernetes workload conventions

| Item | Rule |
| --- | --- |
| Ports | 8080 application (`http`), 8081 management (`management`). Only 8080 is in the Service used by other workloads; 8081 is in a separate `<name>-management` Service for Prometheus |
| Replicas | Minimum 2 in every environment except local; `PodDisruptionBudget` `minAvailable: 1` |
| Probes | liveness → `/actuator/health/liveness`, readiness → `/actuator/health/readiness`, startup probe with 60 s budget |
| Shutdown | `server.shutdown=graceful`, `spring.lifecycle.timeout-per-shutdown-phase=20s`, `preStop` sleep 5 s, `terminationGracePeriodSeconds: 30` |
| Security context | `runAsNonRoot`, UID 10001, `readOnlyRootFilesystem`, drop all capabilities, `seccompProfile: RuntimeDefault`; writable `emptyDir` at `/tmp` |
| Identity | One ServiceAccount per deployable, `automountServiceAccountToken: false` unless needed |
| JVM | `-XX:MaxRAMPercentage=75`, no `-Xmx` |
| Labels | `app.kubernetes.io/name`, `app.kubernetes.io/part-of: bookstore`, `app.kubernetes.io/component` |
| Network | Default‑deny NetworkPolicy per namespace; allow rules in 06 §8 |

## 10. Testing conventions

| Level | Tooling | Expectation |
| --- | --- | --- |
| Unit | JUnit 5, AssertJ, Mockito | Domain rules (ISBN validation, cursor codec, role converter, diff builder) |
| Slice | `@WebMvcTest`, `@DataJpaTest`, `@DataMongoTest` | Controllers incl. security rules and problem responses; repositories against real DB via Testcontainers |
| Integration | `@SpringBootTest` + Testcontainers (PostgreSQL, MongoDB, RabbitMQ, Redis, Keycloak, an S3‑compatible container) | Each flow in the component's §5 has at least one end‑to‑end test |
| Contract | Committed `openapi.yaml` diff test; event JSON schema tests against `libs/contracts` | No silent contract drift |
| Frontend | Vitest (unit), Playwright (e2e against a docker‑compose or kind environment) | See 04 |

Keycloak in integration tests imports the realm JSON exported from `identity/keycloak` (see 05 §11), so tests use the same clients and roles as production.

## 11. Definition of done (per component)

- All endpoints, events and behaviours in the component doc are implemented or explicitly deferred in the PR.
- `openapi.yaml` committed and matches the running service.
- Integration tests for every flow in §5 of the component doc pass in CI.
- Helm chart renders with the `onprem` overlay and passes `kubeconform`.
- Dashboard JSON and alert rules listed in the doc's §9 are committed.
- No `TODO` without a linked issue.

## 12. Shared reference data — `Genre`

Fixed list (A‑08), defined once in `libs/contracts` as a Java enum and mirrored in the frontend from the OpenAPI spec. Stored as `text` with a CHECK constraint in Postgres and as strings in Mongo.

| Value | zh‑TW label | en label |
| --- | --- | --- |
| `FICTION` | 文學小說 | Fiction |
| `FANTASY` | 奇幻 | Fantasy |
| `SCIENCE_FICTION` | 科幻 | Science fiction |
| `MYSTERY` | 推理懸疑 | Mystery |
| `ROMANCE` | 愛情 | Romance |
| `HISTORY` | 歷史 | History |
| `BIOGRAPHY` | 傳記 | Biography |
| `BUSINESS` | 商業理財 | Business |
| `SCIENCE` | 自然科普 | Science |
| `COMPUTING` | 電腦資訊 | Computing |
| `CHILDREN` | 童書 | Children |
| `COMICS` | 漫畫 | Comics |
| `SELF_HELP` | 心理勵志 | Self‑help |
| `OTHER` | 其他 | Other |

Adding a genre is a contract change: update the enum, the Flyway CHECK constraint (new migration) and the frontend labels in one PR.

---

## 13. Assumptions to confirm

| ID | Assumption | If wrong |
| --- | --- | --- |
| A‑01 | Monorepo | Split `libs/*` into a versioned internal artifact; everything else unchanged |
| A‑02 | Maven, not Gradle | Build files only |
| A‑03 | Base package `com.bookstore` | Rename before first commit |
| A‑04 | Gateway strips `/api`; services expose un‑prefixed paths | Change route filters and service mappings together |
| A‑05 | Single currency TWD, two decimals stored | Multi‑currency needs a `currency` column and pricing rules |
| A‑06 | Build fails on controller methods without `@PreAuthorize` | Drop the arch test |
| A‑07 | Audit retention indefinite | Add a retention job |
| A‑08 | Fixed genre list above | Replace list; if genres must be admin‑managed, they become an inventory entity with its own API |
| A‑09 | Design docs written in English, UI default language zh‑TW (see 04) | Translate docs; UI default changes in one config value |
| A‑10 | Public host `shop.bookstore.example`, identity host `auth.bookstore.example` | Placeholders; replace in overlays |
| A‑11 | **Decided 2026‑10‑20 — [ADR 0002](../adr/261020-use-offset-paging-for-catalog-tables.md).** Catalog tables use offset paging with totals (UI paginator); catalog stays well under 100k books (02 I‑08) | Return to keyset `nextCursor` only and drop totals from the UI |
