# Use Apache APISIX as the ingress controller

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** 郭育郡
- **Design refs:** 01-gateway §5.6, §6.2, §8; 05-keycloak §5.4; 06-data-platform §8; assumption G‑04

## Context

The ingress controller terminates TLS for `shop.bookstore.example` (→ gateway) and `auth.bookstore.example` (→ Keycloak `/realms/`, `/resources/` only). It also has to:

- pass SSE on `/api/catalog/stream` without buffering, with a 1 h read timeout;
- set trusted `X-Forwarded-*` headers;
- enforce body limits (1 MB JSON, 6 MB multipart);
- provide [rate limiting at the edge](./261020-rate-limit-at-the-ingress.md).

The design assumed APISIX (G‑04) and noted ingress-nginx as an alternative. Upstream ingress-nginx reached end of maintenance in **March 2026** (no further releases or security fixes), so it is no longer an acceptable choice for a new system.

## Decision

We will use **Apache APISIX** (APISIX Ingress Controller) for both public hosts:

- Separate routes for `/api/catalog/stream` with timeouts `read: 3600, send: 60, connect: 5` s and no response-rewriting plugins. The upstream already sends `X-Accel-Buffering: no`.
- `client-control` / `max_body_size` limits per 00 §3.8.
- Rate limiting via the `limit-req` and `limit-count` plugins.
- Real client IP preserved (load balancer `externalTrafficPolicy: Local` or PROXY protocol) so per-IP limits and logs are correct.
- Route definitions live in the gateway and Keycloak charts, rendered per overlay.

## Consequences

### Positive

- Actively maintained Apache project with built-in plugins (rate limiting, body limits, real-IP) we'd otherwise build.
- Supports both Ingress/CRD routes and Gateway API, which leaves a migration path.

### Negative

- APISIX adds etcd (or the controller's standalone mode) to operate. Check which mode the platform team runs.
- Its CRDs and annotations differ from the ingress-nginx examples common in docs; the team needs some ramp-up.
- SSE behaviour must be verified on APISIX specifically (buffering, timeouts) in the kind e2e suite.

### Follow-ups

- Remove the ingress-nginx annotations from 01 §5.6 to avoid confusion.
- Add an e2e check: an SSE event reaches a browser through the ingress within 2 s; the stream stays open for over 5 min.
- Re-evaluate a move to Gateway API (Envoy Gateway or APISIX's Gateway API support) once the platform team standardises on it.

## Alternatives Considered

### ingress-nginx

- **Why rejected:** Upstream retired; no security fixes after March 2026.

### Gateway API with Envoy Gateway

- **Pros:** The Kubernetes-recommended successor API; portable `HTTPRoute`s.
- **Cons:** Rewriting all ingress manifests now; rate-limit setup needs its own rate-limit service.
- **Why rejected:** Not needed for v1; can be adopted later without app changes.

### Traefik

- **Pros:** Popular; Gateway API support.
- **Cons:** Not the platform's current controller.
- **Why rejected:** No reason to diverge from the existing APISIX setup.

## References

- [Kubernetes blog: Ingress NGINX retirement](https://kubernetes.io/blog/2025/11/11/ingress-nginx-retirement/)
- [Kubernetes Steering & SRC statement on Ingress NGINX (Jan 2026)](https://www.kubernetes.io/blog/2026/01/29/ingress-nginx-statement/)
- [APISIX limit-req plugin](https://apisix.apache.org/docs/apisix/3.0/plugins/limit-req/)
- [APISIX: protect API tutorial (limit-count)](https://apisix.apache.org/docs/apisix/tutorials/protect-api/)
