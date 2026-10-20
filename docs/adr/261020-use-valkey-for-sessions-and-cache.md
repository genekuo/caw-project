# Use Valkey 8 for sessions and cache

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** 郭育郡
- **Supersedes:** [Use Redis 8 under AGPLv3 for sessions and cache](./261020-use-redis-8-under-agplv3.md)
- **Design refs:** 06-data-platform §6; 01-gateway §4; 02-inventory §5.4; assumptions P‑09, P‑10 (ARCH §6.3 legal check)

## Context

The [earlier decision](./261020-use-redis-8-under-agplv3.md) chose Redis 8 under AGPLv3, on condition of legal sign-off before production, with Valkey 8 as the fallback. That decision is now reversed. We'd rather remove the licence question than carry an open legal item and an AGPL "no modifications" rule into the platform.

Nothing else has changed:

- Two standalone instances: `redis-sessions` (Spring Session, AOF, `noeviction`) and `redis-cache` (Spring Cache, no persistence, `allkeys-lru`).
- Both use only core commands (hashes, sets, strings, `SCAN`), with ACL users and `-@dangerous`.
- Valkey is a BSD-3 fork of Redis 7.2.4, governed by the Linux Foundation. It speaks the same RESP protocol and supports the same ACL, AOF and `maxmemory` configuration we use.

## Decision

We will run **Valkey 8** (official image `valkey/valkey:8`, minor version pinned in overlays) for both `redis-sessions` and `redis-cache`, deployed from the in-repo `redis-standalone` chart.

- Instance names, Service names, ACL users, key prefixes and the `REDIS_*` env vars stay unchanged. Spring Data Redis (Lettuce) connects to Valkey as it does to Redis, so the apps don't change.
- The config file keeps its directives (`appendonly`, `appendfsync`, `maxmemory`, `maxmemory-policy`, `aclfile`, `protected-mode`).
- The metrics sidecar stays `oliver006/redis_exporter`; confirm its metrics against Valkey in CI.
- Testcontainers integration tests use the same `valkey/valkey:8` image as production.

## Consequences

### Positive

- No legal review is needed. The permissive BSD-3 licence carries no network-copyleft obligations.
- Multi-vendor, foundation governance makes a licence change like Redis's in 2024 unlikely.
- Same operating model and app code as planned.

### Negative

- Not the "official Redis" image. Docs and tooling usually say Redis, and Valkey's feature set diverges from Redis 8's (JSON, time series, vector sets are separate modules in Valkey). We use none of them.
- Managed-service parity in AWS phase 2 depends on ElastiCache Valkey support, which AWS offers, but should be checked when that phase is planned.
- Compatibility of tools (exporter, `redis-cli`, dashboards) has to be checked on each Valkey major.

### Follow-ups

- Update 06 §6 (image, licensing note) and the chart README.
- The CI smoke test runs Spring Session and Spring Cache against `valkey/valkey:8`, including the ACL file and `-@dangerous` (`SCAN` allowed, `CONFIG` blocked).
- Redis HA (Sentinel or a managed service) remains a separate decision (ARCH §6.3); Valkey supports Sentinel and replication the same way.

## Alternatives Considered

### Redis 8 under AGPLv3 (the superseded decision)

- **Pros:** Official upstream image; Redis 8 features built in.
- **Cons:** Needs legal sign-off; AGPL obligations if anyone ever modifies it; single-vendor licence history (BSD → RSAL/SSPL → +AGPL).
- **Why rejected:** We'd rather not carry the licence risk and the open legal item for features we don't use.

### Redis 7.2.x (last BSD release)

- **Why rejected:** Out of upstream support; would freeze on an old version.

## References

- [Valkey project](https://valkey.io/)
- [Valkey official image (Docker Hub)](https://hub.docker.com/r/valkey/valkey)
- [Redis: What is Valkey](https://redis.io/blog/what-is-valkey/)
- [InfoQ: Redis returns to open source under AGPL](https://www.infoq.com/news/2025/05/redis-agpl-license)
- [AWS: Compare Redis OSS and Valkey](https://aws.amazon.com/elasticache/redis/)
