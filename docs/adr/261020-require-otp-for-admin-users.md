# Require OTP for users with the ADMIN role

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** 郭育郡
- **Design refs:** 05-keycloak §3.1, §5.3, §6; 03-user-service §5.4; assumption K‑05 (amended)

## Context

Shop administrators (realm role `ADMIN`) sign in through the same `bookstore` realm and the same login page as customers. With `ADMIN` they can change prices, delete books, create users, grant `ADMIN`, disable accounts and (per [admin-run deletion](./261020-add-admin-run-account-deletion.md)) delete accounts.

K‑05 put MFA out of scope for everyone in v1, leaving a stolen or phished admin password as the only barrier. Keycloak's brute-force detection is per user. It doesn't stop password spraying, and a reused password beats it.

Human Keycloak operators (`master` realm) already use MFA (K‑07). Only the shop admins are exposed.

## Decision

We will require **TOTP for every user who holds the `ADMIN` realm role**. Customers keep password-only login in v1.

- Copy the built-in `browser` flow to `bookstore browser`. After username/password, add a **conditional sub-flow**: `Condition – user role` = `ADMIN` → `OTP Form` (REQUIRED). Bind it as the realm's browser flow. Users without an OTP credential are sent through the `CONFIGURE_TOTP` required action on their next login.
- When the user service grants `ADMIN` (`PUT /admin/users/{id}/roles`), it also logs out that user's Keycloak sessions (`POST /users/{id}/logout`). The next login then enforces enrollment instead of the role arriving silently on the next token refresh.
- `POST /admin/users` with `ADMIN` in `roles` adds `CONFIGURE_TOTP` to the user's required actions.
- Theme the `login-otp.ftl` and `login-config-totp.ftl` pages in the `bookstore` login theme (zh‑TW).
- Lost device: another admin resets the user's OTP credential in the Keycloak admin console (VPN-only), and the action is audited by Keycloak admin events.

Scope: interactive browser login only. Service accounts (`bookstore-user-service`) are unaffected.

## Consequences

### Positive

- A leaked admin password alone no longer gives access to catalog or user administration.
- No change for customers, and no extra infrastructure. TOTP works with any authenticator app.

### Negative

- Admins need an authenticator app, and there is a recovery procedure to run.
- TOTP is phishable in real time (it is not WebAuthn). Accepted for v1.
- Custom flow config to maintain in realm YAML ([keycloak-config-cli](./261020-manage-keycloak-realm-with-config-cli.md)). Verify the authenticator and condition provider IDs on the Keycloak version we deploy.
- Promoting a user to `ADMIN` now ends their current sessions.

### Follow-ups

- Add a realm assertion test: a user with `ADMIN` and no OTP is prompted for TOTP setup; a `USER`-only account isn't.
- Consider WebAuthn/passkeys for admins in a later release, and OTP opt-in for customers (K‑05 still applies to them).

## Alternatives Considered

### No MFA in v1 (K‑05 as written)

- **Pros:** No extra setup.
- **Cons:** Admin compromise from a single credential; brute-force protection doesn't cover spraying.
- **Why rejected:** The risk is too high for privileged accounts.

### WebAuthn / passkeys for ADMIN

- **Pros:** Phishing-resistant.
- **Cons:** Every admin needs a platform authenticator or hardware key; recovery is harder; more theme work.
- **Why rejected:** Deferred to a later release; TOTP gives most of the benefit now.

### MFA for everyone

- **Why rejected:** Hurts customer conversion; out of v1 scope.

## References

- [Keycloak server admin guide: authentication flows and conditions](https://www.keycloak.org/docs/latest/server_admin/#_authentication-flows)
- [Keycloak ConditionalOtpFormAuthenticator Javadoc](https://www.keycloak.org/docs-api/26.4.7/javadocs/org/keycloak/authentication/authenticators/browser/ConditionalOtpFormAuthenticator.html)
- [Red Hat build of Keycloak 26.0: mitigating security threats (brute force scope)](https://docs.redhat.com/en/documentation/red_hat_build_of_keycloak/26.0/html/server_administration_guide/mitigating_security_threats)
