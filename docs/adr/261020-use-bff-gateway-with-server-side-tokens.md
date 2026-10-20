# Use a WebFlux Spring Cloud Gateway as BFF with server-side tokens

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** 郭育郡
- **Design refs:** 01-gateway §1, §3.1, §4, §5.1–5.6; assumptions G‑01, G‑02

## Context

The browser runs an Angular SSR app on `shop.bookstore.example`. It calls two resource-server services (inventory, user) that validate Keycloak JWTs. We have to decide where OAuth2 tokens live and what the gateway runs on.

Forces:

- Tokens in browser storage are exposed to XSS. The OAuth 2.0 for Browser-Based Apps BCP recommends a backend-for-frontend (BFF) that keeps tokens on the server.
- SSR has to make authenticated API calls on the user's behalf. The browser's cookie can travel with those calls, but a bearer token in browser storage can't.
- The gateway mostly holds long-lived, idle SSE connections (`/api/catalog/stream`, up to 10,000 per inventory upstream) and relays bytes.
- There are at least 2 gateway replicas. Sessions, authorized clients and the OIDC back-channel logout registry therefore have to be shared.
- Spring Cloud Gateway comes in a reactive (WebFlux) and a servlet (Server MVC) variant. `TokenRelay` and reactive Spring Session Redis have been available longest on WebFlux.

## Decision

We will run the gateway as a **Spring Cloud Gateway Server (WebFlux) OAuth2 client in the BFF pattern**:

- Authorization code + PKCE (S256) against Keycloak, as a confidential client.
- Access and refresh tokens are kept only in the server-side session (`OAuth2AuthorizedClient` in `redis-sessions`). The browser holds only an HttpOnly `SESSION` cookie plus the `XSRF-TOKEN` CSRF cookie.
- `TokenRelay` adds the bearer token to requests going to the services, refreshing it transparently.
- Sessions are serialized as **JSON** (Spring Security Jackson modules), not with JDK serialization.
- The OIDC session registry is backed by Redis and back-channel logout deletes sessions directly, so logout works on every replica.

Scope: browser and SSR traffic to the services. Service-to-service calls are out of scope; v1 has none apart from user service → Keycloak, which uses client credentials.

## Consequences

### Positive

- No tokens in the browser. XSS can't exfiltrate them, and CSRF is handled in one place.
- SSR forwards the cookie and gets the same authorization as the browser.
- The reactive stack holds thousands of idle SSE streams on a small thread pool.
- JSON session format survives library upgrades without logging every user out.

### Negative

- The gateway is stateful and depends on `redis-sessions`. That Redis is a single instance in v1 (06 §6), so losing it logs everyone out.
- The team needs reactive (Reactor) skills for gateway filters and custom security components.
- We maintain custom code: the Redis OIDC session registry, the back-channel logout handler, and the CSRF cookie-subscribing filter.
- Concurrent token refreshes on two replicas rely on Keycloak refresh-token rotation staying **off** (05 §3.4).

### Follow-ups

- If refresh-token rotation is ever enabled, add a per-session refresh lock first.
- Revisit Redis HA (Sentinel or a managed service) once session loss becomes unacceptable.
- Revisit the MVC variant only if the reactive code becomes a maintenance burden; SSE thread sizing would then need care.

## Alternatives Considered

### Tokens in the browser (public SPA client)

- **Summary:** Angular obtains tokens itself (PKCE public client) and sends `Authorization: Bearer`.
- **Pros:** Stateless gateway; simpler infrastructure.
- **Cons:** Tokens reachable by XSS. SSR can't call APIs as the user. Refresh-token handling moves into the browser.
- **Why rejected:** Conflicts with SSR and with keeping tokens out of the browser.

### Spring Cloud Gateway Server MVC

- **Summary:** Servlet-based gateway with virtual threads.
- **Pros:** Imperative code, familiar to the team; virtual threads reduce the cost of blocking.
- **Cons:** Session and token-relay support is newer. Long-lived SSE needs careful connector and thread sizing.
- **Why rejected:** The workload is dominated by idle streaming connections, which the reactive variant handles natively.

### Separate API gateway product plus an auth proxy (e.g. oauth2-proxy)

- **Pros:** Off-the-shelf components.
- **Cons:** Two components to configure, weaker integration with Spring Security's back-channel logout and CSRF, and still a session store.
- **Why rejected:** More moving parts for the same result.

## References

- [OAuth 2.0 for Browser-Based Applications (IETF draft)](https://datatracker.ietf.org/doc/draft-ietf-oauth-browser-based-apps/)
- [Spring Cloud Gateway reference](https://docs.spring.io/spring-cloud-gateway/reference/)
- [Spring Security OIDC back-channel logout](https://docs.spring.io/spring-security/reference/reactive/oauth2/login/logout.html)
