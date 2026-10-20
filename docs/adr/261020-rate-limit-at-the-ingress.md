# Rate-limit public traffic at the ingress

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** 郭育郡
- **Design refs:** 01-gateway §1 non-goals; 05-keycloak §3.1 (brute force); 06-data-platform §6; assumption G‑06 (amended)

## Context

v1 had no rate limiting (G‑06). The exposed surfaces are:

- public catalog reads and search (`/api/catalog/**`, including search queries that can fall back to sequential scans, see the [search decision](./261020-keep-pg-trgm-and-fts-for-search.md));
- SSE connections (5,000 per inventory pod);
- `/bff/login`;
- Keycloak login, registration and password-reset endpoints, which send email.

Keycloak's brute-force detection is per account. It doesn't stop password spraying or registration and reset-email abuse.

Rate limiting inside the gateway (`RequestRateLimiter`) needs a Redis. It must not share `redis-sessions` (`noeviction`, 512 MB), so a third instance would be needed.

## Decision

We will rate-limit **per client IP at the APISIX ingress** ([ADR](./261020-use-apisix-as-ingress-controller.md)). There are no app-level limiters in v1. Starting values (tune after load test):

| Host / path | Plugin | Limit |
| --- | --- | --- |
| shop `/api/**` (except stream) | `limit-req` | 20 r/s, burst 40 |
| shop `/api/catalog/stream` | `limit-conn` | 10 concurrent per IP |
| shop `/bff/login`, `POST /logout` | `limit-req` | 2 r/s, burst 10 |
| shop `POST /bff/csp-report` | `limit-req` | 1 r/s, burst 20 |
| auth `/realms/bookstore/login-actions/*` | `limit-count` | 30 / min |
| auth `/realms/bookstore/protocol/openid-connect/registrations`, reset-credentials | `limit-count` | 5 / 10 min |

- Rejections return **429** with `Retry-After`. The frontend treats a 429 like a 503 (retry later).
- Counters are local to each APISIX node (no shared Redis). Limits are approximate across replicas, which is accepted.
- SSR calls the gateway in-cluster, bypassing the ingress, so server-side rendering isn't throttled by one shared IP.
- Real client IP must be preserved (see the APISIX ADR). Otherwise all traffic shares the load balancer's IP.

## Consequences

### Positive

- Abusive traffic is stopped before it reaches the gateway, Keycloak or PostgreSQL.
- No app code and no extra Redis.
- Covers Keycloak, which an app-level limiter in the gateway couldn't.

### Negative

- Per-IP limits can hit many users behind one NAT (offices, mobile carriers). Limits must be generous, and the 429 rate watched.
- No per-user or per-session limits, so a distributed attack from many IPs isn't stopped.
- Per-node counters: the effective limit is roughly N × configured with N ingress replicas.

### Follow-ups

- Dashboard and alert on 429 rate by route.
- If per-user limits become necessary (e.g. API abuse by signed-in users), add gateway `RequestRateLimiter` backed by a **separate** Redis instance, and supersede this ADR.
- Consider a WAF or CDN in AWS phase 2.

## Alternatives Considered

### No rate limiting in v1 (G‑06 as written)

- **Why rejected:** Leaves login spraying, email abuse and search-driven DB load unbounded.

### Spring Cloud Gateway `RequestRateLimiter`

- **Pros:** Per-session/user keys; consistent across gateway replicas.
- **Cons:** Needs a third Redis; doesn't protect Keycloak's own endpoints.
- **Why rejected:** More infrastructure and a smaller coverage area for v1.

## References

- [APISIX limit-req](https://apisix.apache.org/docs/apisix/3.0/plugins/limit-req/)
- [APISIX rate limiting guide](https://docs.api7.ai/apisix/how-to-guide/traffic-management/rate-limiting)
- [Keycloak brute-force detection scope (Red Hat build of Keycloak 26.0)](https://docs.redhat.com/en/documentation/red_hat_build_of_keycloak/26.0/html/server_administration_guide/mitigating_security_threats)
