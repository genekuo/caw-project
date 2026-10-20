# Keep customer PII out of user audit records

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** 郭育郡
- **Design refs:** 00-conventions §6; 03-user-service §5.3, §5.4; 04-frontend §5.9; assumption A‑07

## Context

Audit records are append-only and kept indefinitely (00 §6, A‑07). The app's Mongo role has no `update` or `remove` on `audit_log`.

In 03 §5.3 the `CREATE` audit for a user stores `changes = { email, firstName, lastName, roles, sendInvite }`. After an [account deletion](./261020-add-admin-run-account-deletion.md), that customer's email and name would then live on forever in a log that by design can't be changed. That conflicts with the PDPA obligation to delete data whose purpose has ended.

Audit records also carry `actorUsername` (`preferred_username`, which is the email because the realm uses email as username). That identifies the **admin** who acted, not the customer.

## Decision

Audit records with `entityType = USER` will **not contain the subject user's personal data**:

- `entityId` is the Keycloak `sub` (a random UUID), which is pseudonymous once the Keycloak user is deleted.
- `changes` may contain only non-identifying fields: `roles`, `enabled`, `sendInvite`, `inviteSent`, required-action names. **No** `email`, `firstName`, `lastName`, phone or address, old or new.
- `CREATE` records `{ roles, sendInvite }` only.
- The audit viewer (04 §5.9) shows the user's current email and name by looking up `entityId` live via `GET /admin/users/{id}`. A deleted user shows as 已刪除的使用者.
- `actorUsername` (the acting admin) is kept: accountability for privileged actions is a business duty. When a staff account is deleted, its audit entries keep the admin's username.
- Inventory audit (`BOOK`, `AUTHOR`) is unaffected; it contains no customer data.

A unit test on the user-service diff builder enforces an allow-list of fields.

## Consequences

### Positive

- The audit log stays strictly append-only and immutable, with no redaction job.
- Deleting a customer leaves only a pseudonymous UUID behind.

### Negative

- The audit log alone can't show *who* (by email) a deleted user was. Support must keep the deletion ticket for that.
- The audit viewer makes one Keycloak lookup per distinct user row shown (cache for the page).
- Retained admin usernames are still personal data of staff; this is covered under the business-duty exception and stated in the internal privacy notice.

### Follow-ups

- Update 03 §5.3 step 6 and the 00 §6 field notes.
- If audit retention changes from indefinite (A‑07), revisit whether pseudonymous UUIDs need expiry too.

## Alternatives Considered

### Keep PII in audit under the business-duty exception

- **Pros:** Self-contained audit history.
- **Cons:** Customer PII retained forever after deletion; hard to justify for customers (unlike staff).
- **Why rejected:** Weak legal footing and unnecessary for the audit's purpose.

### Redaction job for deleted users

- **Pros:** Rich history until deletion.
- **Cons:** Needs a privileged role with `update` on `audit_log`, so the log is no longer immutable; more code and more risk.
- **Why rejected:** Undermines the integrity guarantee the audit log exists for.

### Encrypt PII per user and delete the key ("crypto-shredding")

- **Pros:** Immutable log and erasable PII.
- **Cons:** Key management per user, which is overkill for a few fields.
- **Why rejected:** Complexity out of proportion for v1.

## References

- [Taiwan PDPA (English translation, Eiger)](https://eiger.law/wp-content/uploads/2016/10/Eiger_Personal_Info_Protection_Act-Taiwan.pdf)
- [Winkler Partners: PDPA Art. 11 deletion and its exceptions](https://winklerpartners.com/google-remembers-your-dark-past-can-i-claim-the-right-to-be-forgotten-in-taiwan)
