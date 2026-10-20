# Manage the Keycloak realm as code with keycloak-config-cli

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** 郭育郡
- **Design refs:** 05-keycloak §5.2, §11; 06-data-platform §10 (sync wave 1); assumption K‑04

## Context

The `bookstore` realm holds clients, roles, client scopes, mappers, the user profile, authentication flows (now including [conditional OTP for admins](./261020-require-otp-for-admin-users.md)), themes and SMTP. It has to be reproducible across dev, staging and prod, and reviewed in Git. Argo CD has to apply it.

Forces:

- The Keycloak Operator's `KeycloakRealmImport` **only creates** a realm that doesn't exist yet; it doesn't update one. That makes it unsuitable for ongoing changes.
- Secrets (client secrets, SMTP password) come from Vault via ESO and must not be committed.
- Integration tests import the same realm as production (00 §10, 05 §11).

## Decision

We will manage the realm with **adorsys keycloak-config-cli**, run as an Argo CD `PostSync` hook Job after Keycloak is ready:

- The source is `identity/keycloak/realm/bookstore.yaml` plus per-environment overlays, with `$(env:…)` substitution for hosts and secrets.
- `import.managed.*` is set to `full` for clients, roles, client scopes and mappers; users are `no-delete`. With remote state enabled, config-cli deletes only objects it created.
- The image version is pinned to match the Keycloak major version.
- CI applies the YAML to a throwaway Keycloak, exports `export/bookstore-realm.json`, and fails if it differs from the committed export. Testcontainers tests import that file.

## Consequences

### Positive

- Every realm change is reviewed in a PR and applied the same way in every environment.
- Removing something from YAML removes it from Keycloak, so the realm doesn't drift.
- One source of truth for production and tests.

### Negative

- A third-party tool whose version must track Keycloak majors; upgrades need a compatibility check.
- Changes made by hand in the admin console to managed objects are overwritten on the next sync. Admins have to be told.
- Full-management semantics need care: renaming a client or role is a delete plus a create.

### Follow-ups

- Document "do not edit managed objects in the console" in the ops runbook.
- Test config-cli upgrades on staging first (its changelog warns about managed-resource behaviour changes).

## Alternatives Considered

### KeycloakRealmImport CR (Keycloak Operator)

- **Pros:** Native to the operator; no extra tool.
- **Cons:** Create-only; later changes are ignored.
- **Why rejected:** Can't evolve an existing realm.

### Terraform Keycloak provider

- **Summary:** Realm objects as Terraform resources with state.
- **Pros:** Mature plan/apply workflow; precise diffs.
- **Cons:** Separate Terraform state and pipeline outside Argo CD. HCL rather than realm-export-shaped YAML. Harder to produce the JSON export the tests need.
- **Why rejected:** Doesn't fit the GitOps-only delivery (06 §10). Kept as the fallback if config-cli stops tracking Keycloak releases.

### Manual configuration plus a periodic export

- **Why rejected:** Not reproducible and not reviewable.

## References

- [keycloak-config-cli (GitHub)](https://github.com/adorsys/keycloak-config-cli)
- [keycloak-config-cli changelog v4.1.0 (managed defaults)](https://github.com/adorsys/keycloak-config-cli/blob/v4.1.0/CHANGELOG.md)
- [Keycloak Operator realm import](https://www.keycloak.org/operator/realm-import)
