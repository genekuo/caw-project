# Architecture Decision Records

Decisions that shape the bookstore system. Each file is `{yymmdd}-{title}.md`, and accepted ADRs are never edited in substance. To change a decision, write a new ADR and mark the old one `Superseded by …`.

When an ADR decides an assumption from the design docs (`../design/`), the assumption's row in that doc's **Assumptions to confirm** table links to the ADR.

| # | Decision | Status | Date | Assumptions |
| --- | --- | --- | --- | --- |
| 0001 | [Use a WebFlux Spring Cloud Gateway as BFF with server-side tokens](./261020-use-bff-gateway-with-server-side-tokens.md) | Accepted | 2026-10-20 | G‑01, G‑02 |
| 0002 | [Use offset paging with totals for catalog tables](./261020-use-offset-paging-for-catalog-tables.md) | Accepted | 2026-10-20 | A‑11, F‑04 |
| 0003 | [Call the Keycloak Admin REST API with Spring RestClient](./261020-use-restclient-for-keycloak-admin-api.md) | Accepted | 2026-10-20 | U‑08 |
| 0004 | [Manage the Keycloak realm as code with keycloak-config-cli](./261020-manage-keycloak-realm-with-config-cli.md) | Accepted | 2026-10-20 | K‑04 |
| 0005 | [Host Keycloak on its own subdomain](./261020-host-keycloak-on-auth-subdomain.md) | Accepted | 2026-10-20 | K‑08 |
| 0006 | [Require OTP for users with the ADMIN role](./261020-require-otp-for-admin-users.md) | Accepted | 2026-10-20 | K‑05 (amended) |
| 0007 | [Publish catalog events with a hand-written transactional outbox relay](./261020-use-hand-written-outbox-relay.md) | Accepted | 2026-10-20 | I‑03 |
| 0008 | [Keep PostgreSQL pg_trgm plus simple full-text search for catalog search](./261020-keep-pg-trgm-and-fts-for-search.md) | Accepted | 2026-10-20 | I‑04 |
| 0009 | [Use Redis 8 under AGPLv3 for sessions and cache](./261020-use-redis-8-under-agplv3.md) | Superseded by 0017 | 2026-10-20 | P‑09, P‑10 |
| 0017 | [Use Valkey 8 for sessions and cache](./261020-use-valkey-for-sessions-and-cache.md) | Accepted | 2026-10-20 | P‑09, P‑10 (supersedes 0009) |
| 0010 | [Use Garage as the in-cluster S3-compatible object store](./261020-use-garage-for-object-storage.md) | Accepted | 2026-10-20 | P‑11 |
| 0011 | [Use Apache APISIX as the ingress controller](./261020-use-apisix-as-ingress-controller.md) | Accepted | 2026-10-20 | G‑04 |
| 0012 | [Rate-limit public traffic at the ingress](./261020-rate-limit-at-the-ingress.md) | Accepted | 2026-10-20 | G‑06 (amended) |
| 0013 | [Ship CSP in report-only mode, then enforce two weeks after launch](./261020-ship-csp-report-only-then-enforce.md) | Accepted | 2026-10-20 | G‑05 (amended) |
| 0014 | [Add admin-run account deletion on request](./261020-add-admin-run-account-deletion.md) | Accepted | 2026-10-20 | U‑04 (amended) |
| 0015 | [Keep customer PII out of user audit records](./261020-keep-pii-out-of-user-audit-records.md) | Accepted | 2026-10-20 | A‑07 (related) |
| 0016 | [Audit user-service admin actions with pending-then-confirm records](./261020-use-pending-then-confirm-user-audit.md) | Accepted | 2026-10-20 | U‑07 (amended) |

## Open items carried by these ADRs

- **0017:** CI smoke test of Spring Session / Spring Cache and `redis_exporter` against `valkey/valkey:8`.
- **0008:** Set `localeCType` explicitly in CNPG `initdb` and verify `show_trgm('哈利波特')` returns CJK trigrams on a CNPG-bootstrapped database.
- **0013:** Release ticket "Enforce CSP" at launch + 14 days.
- **0014:** Confirm with legal whether 90-day Keycloak admin-event retention is acceptable; update `/privacy`.

## Template

Each ADR has these sections: Title, Status, Date, Deciders, Context, Decision, Consequences (Positive / Negative / Follow-ups), Alternatives Considered, References.
