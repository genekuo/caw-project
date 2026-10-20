# Audit user-service admin actions with pending-then-confirm records

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** 郭育郡
- **Design refs:** 00-conventions §6; 03-user-service §4 (`audit_log`), §5.3, §5.4; 06-data-platform §4 (Mongo role); assumption U‑07 (amended)

## Context

Every admin write must be audited (00 §6). In inventory, the audit row and the change share one PostgreSQL transaction. In the user service, the change happens in **Keycloak** (create user, roles, enable/disable, password reset, [delete](./261020-add-admin-run-account-deletion.md)), and the audit record goes to **MongoDB**. No transaction spans both.

The design wrote the audit after the Keycloak call and accepted losing it if Mongo failed in between (U‑07). That leaves privileged actions, including granting `ADMIN`, with no trace.

Constraint: `audit_log` is append-only. The app role has `insert` and `find` only (06 §4), and records are never updated (00 §6). A status field can't be updated in place.

## Decision

Each user-service admin action writes **two append-only audit records**:

1. **Before** calling Keycloak, insert the intent record: the normal 00 §6 fields plus `outcome: "PENDING"`. If this insert fails, abort with 503 `dependency-unavailable`. No Keycloak call happens without an audit trail.
2. **After** Keycloak responds, insert an outcome record: `outcome: "SUCCEEDED"` or `"FAILED"` (with `errorCode`), `correlationId` = the intent record's `id`, and the same `action` / `entityType` / `entityId`. `changes` holds the final values, e.g. the new user's `sub` for `CREATE`.
3. If step 2 fails, log ERROR and count `bookstore.user.audit.unconfirmed`; the API response is unaffected. The intent record remains and is shown as 結果未確認 (unconfirmed).

Supporting changes:

- New audit fields `outcome` (`PENDING` | `SUCCEEDED` | `FAILED`) and `correlationId`, optional for inventory and absent there. Index `{ correlationId: 1 }`.
- The audit viewer pairs records by `correlationId` and shows one row per action with its outcome.
- A `PrometheusRule` alerts when an intent record is older than 5 minutes without an outcome. A scheduled check computes this with a `$lookup` every minute.

## Consequences

### Positive

- No privileged Keycloak change happens without at least an intent record, which closes the U‑07 gap.
- Failed attempts (e.g. Keycloak 409) are audited too, which helps support.
- The audit log stays strictly append-only; the Mongo role is unchanged.

### Negative

- Two inserts per admin action, plus pairing logic in the viewer and API.
- A crash between Keycloak success and the outcome insert leaves the action "unconfirmed". An operator must check Keycloak admin events (90-day retention) to settle it.
- Admin actions now fail (503) when Mongo is down, where before they would have succeeded unaudited.

### Follow-ups

- Integration tests: Mongo down → no Keycloak call and 503; Keycloak 409 → PENDING + FAILED; outcome insert failure → PENDING only, metric incremented.
- Update the 00 §6 field table and 03 §4 indexes.

## Alternatives Considered

### Accept rare audit loss (U‑07 as written)

- **Why rejected:** A missing trace of an `ADMIN` grant or account deletion is exactly what audit must prevent.

### Single record with status updated in place

- **Pros:** One document per action; simpler viewer.
- **Cons:** Requires `update` on `audit_log`, which breaks the immutability rule (00 §6, 06 §4).
- **Why rejected:** Weakens audit integrity.

### Rely on Keycloak admin events only

- **Pros:** Keycloak records every Admin API change.
- **Cons:** 90-day expiry; shows the service account, not the human admin; not in the app's audit viewer.
- **Why rejected:** Useful as a cross-check, not as the system of record.

## References

- [MongoDB built-in and custom roles (privilege actions)](https://www.mongodb.com/docs/manual/reference/privilege-actions/)
- [Keycloak server admin guide: auditing and events](https://www.keycloak.org/docs/latest/server_admin/#auditing-and-events)
