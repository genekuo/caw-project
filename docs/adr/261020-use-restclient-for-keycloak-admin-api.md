# Call the Keycloak Admin REST API with Spring RestClient

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** 郭育郡
- **Design refs:** 03-user-service §5.3–5.5; assumption U‑08 (deviation from ARCH §3.1)

## Context

The user service manages Keycloak users: search, create, role mapping, enable/disable, action emails and (per [admin-run deletion](./261020-add-admin-run-account-deletion.md)) delete. That is about a dozen Admin REST API calls, made with a `client_credentials` service account.

The architecture doc suggested the official `keycloak-admin-client` library. The stack is Spring Boot 4.1, which uses Jackson 3 (`tools.jackson.*`) by default, on a Jakarta EE 11 baseline (00 §2).

The official admin client is built on RESTEasy and uses a Jackson 2 `com.fasterxml.jackson.databind.ObjectMapper` (Keycloak docs). Adding it would bring a second JSON stack and a JAX-RS client into a Boot 4 app.

## Decision

We will call the Admin REST API with **Spring's `RestClient` and `OAuth2ClientHttpRequestInterceptor`**, using a `client_credentials` registration (`keycloak-admin`) against the in-cluster Keycloak URL, instead of `keycloak-admin-client`.

- Hand-written DTOs cover only the `UserRepresentation` and `RoleRepresentation` fields we use, and ignore unknown fields.
- Timeouts: connect 2 s, read 5 s. GETs are retried once on connect failure or 5xx; writes are never retried.
- Error mapping per 03 §5.5 (404 → `user-not-found`, 409 → `user-exists`, 401/403 → `keycloak-error`, connect failure/5xx → `keycloak-unavailable`).

## Consequences

### Positive

- A single HTTP and JSON stack (Spring + Jackson 3). No RESTEasy, no Jackson 2 on the classpath.
- Token acquisition and caching are handled by Spring Security's OAuth2 client.
- Tracing via the OTel agent works the same as for every other `RestClient` call.

### Negative

- We maintain the DTOs and endpoint paths ourselves and track Admin API changes between Keycloak majors.
- No typed convenience API. Call sequences such as reading the `Location` header for the new user ID are coded by hand.

### Follow-ups

- The integration tests (Testcontainers Keycloak with the exported realm) cover every call, so a Keycloak upgrade that changes the API fails in CI.
- Revisit if Keycloak ships an admin client without RESTEasy and Jackson 2 dependencies.

## Alternatives Considered

### `keycloak-admin-client` (official library)

- **Summary:** Typed Java client for the Admin REST API.
- **Pros:** Full API coverage, maintained by the Keycloak team, aims to be compatible with several server versions.
- **Cons:** Pulls in RESTEasy and a Jackson 2 `ObjectMapper`, which is likely to conflict with or duplicate Boot 4's Jackson 3 setup. A heavy dependency for about 12 calls.
- **Why rejected:** Dependency risk outweighs the convenience at this call volume.

### Generated client from Keycloak's OpenAPI description

- **Pros:** Typed, generated, no RESTEasy.
- **Cons:** Large generated surface, and the generator's Jackson version has to be tuned for Jackson 3.
- **Why rejected:** More code than we need. Can be reconsidered if the call count grows a lot.

## References

- [Keycloak admin client guide](https://www.keycloak.org/securing-apps/admin-client)
- [Keycloak Admin REST API](https://www.keycloak.org/docs-api/latest/rest-api/index.html)
- [Introducing Jackson 3 support in Spring](https://spring.io/blog/2025/10/07/introducing-jackson-3-support-in-spring/)
