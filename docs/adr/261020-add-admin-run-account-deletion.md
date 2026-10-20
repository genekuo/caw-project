# Add admin-run account deletion on request

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** 郭育郡
- **Design refs:** 03-user-service §1 (non-goals), §3.3, §5.4; 04-frontend §5.8; 06-data-platform §3.3, §4 (backups); assumption U‑04 (amended)

## Context

v1 had no account deletion (U‑04), and "hard deletion of Keycloak users from the app" was a non-goal. Personal data about a customer lives in:

- Keycloak: email, first/last name, password hash, transient `reg_address_*` attributes, user events (30-day expiry), admin events (90-day expiry);
- MongoDB `profiles`: display name, phone, address, preferences;
- MongoDB `audit_log`: entries about the user (see the [audit PII decision](./261020-keep-pii-out-of-user-audit-records.md));
- backups: CNPG and PBM, 30-day retention.

Taiwan's Personal Data Protection Act (PDPA) Art. 11 requires a data controller to delete personal data, on its own initiative or on request, once the specific purpose of collection no longer exists, unless the data is needed for business duties or the person consented in writing. A customer closing their account ends the purpose. We need a defined, audited way to honour that, but self-service UI is more than v1 needs.

## Decision

We will add an **admin-run deletion** that support staff execute when a customer asks:

- New endpoint `DELETE /admin/users/{id}` (`hasRole('ADMIN')`), 204 on success. The user-service admin UI (04 §5.8) gets a 刪除帳戶 button with a typed-email confirmation.
- Guards (as in 03 §5.4): not self (409 `cannot-modify-self`), not the last enabled admin (409 `last-admin`).
- Sequence, using [pending-then-confirm audit](./261020-use-pending-then-confirm-user-audit.md):
  1. Insert a `PENDING` audit record `DELETE` (entity `USER`, `entityId` = sub, `changes: null`).
  2. `POST /admin/realms/bookstore/users/{id}/logout`, which ends sessions and triggers back-channel logout at the gateway.
  3. `DELETE /admin/realms/bookstore/users/{id}`. 404 counts as already deleted.
  4. Delete the Mongo `profiles` document.
  5. Insert the outcome record (`SUCCEEDED`, or `FAILED` with an error code).
- Steps 2–4 are idempotent, so a failed run can be repeated safely.
- Inventory holds no customer personal data (only admin `actorSub`/`actorUsername` in its audit), so no cross-service call is needed.
- Backups aren't edited. Deleted data ages out with the 30-day backup retention; this is stated in the privacy policy. A restore from backup must re-apply deletions made since the backup (run from the audit log `DELETE` records).

Request intake (email or form) and identity verification of the requester are a support process outside the app.

## Consequences

### Positive

- A defined, audited, repeatable way to meet PDPA deletion requests in v1.
- Small scope: one endpoint, one button; no customer-facing deletion flow or re-auth logic.

### Negative

- Customers can't delete their own account. Support handles each request manually.
- Deletion is irreversible; a wrong click by an admin loses the account (mitigated by typed confirmation and audit).
- Personal data stays in backups for up to 30 days, and Keycloak admin events (which include representations) for up to 90 days.
- Restore procedures gain a "re-apply deletions" step.

### Follow-ups

- Integration test: delete → Keycloak 404, profile gone, sessions invalidated at the gateway, PENDING + SUCCEEDED audit records present; repeat call → 204.
- Update the privacy policy page (`/privacy`) with the deletion request channel and backup retention.
- Re-evaluate self-service deletion if request volume exceeds a few per month.
- Confirm with legal whether 90-day Keycloak admin-event retention is acceptable, or shorten it.

## Alternatives Considered

### Self-service "delete my account"

- **Pros:** No support effort; best user experience.
- **Cons:** Needs re-authentication (fresh login or OTP), confirmation UX, and abuse protection; more gateway and frontend work.
- **Why rejected:** Not needed for v1 volume; the same backend flow can be exposed later.

### Defer (no deletion in v1)

- **Cons:** Manual steps across Keycloak console and Mongo shell, error-prone and unaudited.
- **Why rejected:** Doesn't give a reliable PDPA compliance path.

### Disable instead of delete

- **Why rejected:** Disabling keeps all personal data, which doesn't satisfy a deletion obligation once the purpose has ended.

## References

- [Taiwan PDPA (English translation, Eiger)](https://eiger.law/wp-content/uploads/2016/10/Eiger_Personal_Info_Protection_Act-Taiwan.pdf)
- [Winkler Partners: right to be forgotten in Taiwan (PDPA Art. 11)](https://winklerpartners.com/google-remembers-your-dark-past-can-i-claim-the-right-to-be-forgotten-in-taiwan)
- [Keycloak Admin REST API: users](https://www.keycloak.org/docs-api/latest/rest-api/index.html#_users)
