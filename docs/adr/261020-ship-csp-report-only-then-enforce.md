# Ship CSP in report-only mode, then enforce two weeks after launch

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** 郭育郡
- **Design refs:** 01-gateway §5.7; 04-frontend §6; assumption G‑05 (amended)

## Context

The gateway adds a Content-Security-Policy to every response on `shop.bookstore.example`. Angular SSR emits an inline event-replay script, which needs a per-request nonce (`ngCspNonce`). The Express SSR server generates the nonce and sets the CSP header for HTML responses itself (04 §6).

G‑05 started CSP as report-only with no end date. Two gaps:

- An unenforced CSP gives no XSS protection.
- The policy in 01 §5.7 has **no `report-to` / `report-uri`**, so report-only mode collects nothing.

## Decision

We will:

1. **Launch with `Content-Security-Policy-Report-Only`** using the policy in 01 §5.7 plus `'nonce-…'` in `script-src`, and add a reporting endpoint:
   - `Reporting-Endpoints: csp="/bff/csp-report"` and `report-to csp; report-uri /bff/csp-report` in the policy.
   - A new gateway local endpoint `POST /bff/csp-report` (CSRF-exempt, body ≤ 8 KB, rate-limited at the ingress) logs each report as a structured JSON line (`csp.violation`) and increments `bookstore.csp.violations{directive}`.
2. **Switch to the enforcing `Content-Security-Policy` header two weeks after go-live**, provided the violation dashboard shows no first-party violations in the last 7 days. Browser-extension noise (`chrome-extension:`, `moz-extension:` sources) is excluded.
3. Keep sending the report-only header alongside the enforcing one for later policy tightening.

Scope: the shop host only. Keycloak's pages on `auth.bookstore.example` keep Keycloak's own security headers.

## Consequences

### Positive

- Nonce or policy mistakes show up in reports instead of breaking the storefront on day one.
- A dated, measurable path to real XSS protection.

### Negative

- For two weeks after launch there is no CSP protection, only detection.
- A new public endpoint that accepts arbitrary JSON. It has to be size-limited, rate-limited and must never echo input.
- Somebody has to own the enforcement switch on the release calendar.

### Follow-ups

- Create the release ticket "Enforce CSP" dated launch + 14 days.
- Grafana panel and Loki query for `csp.violation`.
- Playwright check that every SSR page carries a nonce on the event-replay script.

## Alternatives Considered

### Enforce from day one

- **Pros:** Protection from launch.
- **Cons:** A missed nonce or third-party asset breaks pages for users with no early warning.
- **Why rejected:** Too risky without production telemetry on the nonce wiring.

### Report-only indefinitely (G‑05 as written)

- **Why rejected:** Provides no protection, and without a reporting endpoint, no information either.

## References

- [MDN: Content-Security-Policy-Report-Only](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy-Report-Only)
- [MDN: CSP report-to directive](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy/report-to)
- [Angular: Content security policy and nonces](https://angular.dev/best-practices/security#content-security-policy)
