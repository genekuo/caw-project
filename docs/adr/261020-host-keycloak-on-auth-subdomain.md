# Host Keycloak on its own subdomain

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** 郭育郡
- **Design refs:** 05-keycloak §5.1, §5.4; 01-gateway §5.7 (CSP `form-action`); 00-conventions A‑10; assumption K‑08

## Context

Customers see Keycloak's themed sign-in and registration pages, and the browser is redirected there during login. Keycloak can be exposed either on its own host or under a path on the shop host (`/auth`).

Forces:

- The `iss` claim must be one stable public URL that every service validates (00 §4).
- The shop's `SESSION` cookie must never reach Keycloak, and Keycloak's cookies must never reach the shop.
- Each host should have a self-contained CSP. The shop's CSP should only need `form-action https://auth.…`, not Keycloak's script and style needs.
- Only `/realms/` and `/resources/` may be public. `/admin/` must not be.

## Decision

We will expose Keycloak at **`https://auth.bookstore.example`**, a separate host from `https://shop.bookstore.example`:

- Keycloak `hostname` is the full public URL. `backchannelDynamic: true` lets in-cluster callers use the internal Service URL while tokens keep the public `iss`.
- The ingress for the auth host routes only `/realms/` and `/resources/`. `/admin/` is reachable only via port-forward or a VPN-only host (K‑06).
- The shop's cookies stay host-only (no `Domain` attribute), so they are never sent to the auth host.

## Consequences

### Positive

- Clean cookie separation and independent security headers per host.
- Keycloak can be scaled, upgraded or moved (e.g. to a managed IdP) without changing shop routes.
- Simple ingress rules. Theme assets come from the auth host, so the shop's CSP stays tight.

### Negative

- A second DNS name and TLS certificate (or a wildcard) per environment.
- The hosts are *same-site* (same registrable domain), so `SameSite` cookies don't isolate them from each other. Separation relies on host-only cookies.
- The shop's CSP has to allow `form-action https://auth.bookstore.example` (logout form posts redirect there).

### Follow-ups

- Keep `A‑10` hostnames as overlay values; replace the placeholders before the first non-dev deploy.
- HSTS `includeSubDomains` on the shop host also covers `auth.` — make sure every subdomain serves HTTPS.

## Alternatives Considered

### Path-based (`https://shop.bookstore.example/auth`)

- **Pros:** One host and certificate; same-origin.
- **Cons:** Shop and Keycloak cookies share a host, so cookie path scoping becomes the only barrier. A single CSP has to cover both apps. Ingress path rules interleave with the gateway catch-all. Keycloak `hostname` and the CSP have to change.
- **Why rejected:** Weaker isolation and more coupling for a small saving.

## References

- [Keycloak hostname configuration](https://www.keycloak.org/server/hostname)
- [MDN: Set-Cookie Domain attribute](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie#domaindomain-value)
