# Use Redis 8 under AGPLv3 for sessions and cache

- **Status:** Superseded by [Use Valkey 8 for sessions and cache](./261020-use-valkey-for-sessions-and-cache.md)
- **Date:** 2026-10-20
- **Deciders:** 郭育郡
- **Design refs:** 06-data-platform §6; 01-gateway §4; 02-inventory §5.4; assumptions P‑09, P‑10 (ARCH §6.3 legal check)

## Context

Two standalone Redis-protocol instances are needed:

- `redis-sessions`: Spring Session for the gateway, AOF persistence, `noeviction`.
- `redis-cache`: Spring Cache for inventory, no persistence, `allkeys-lru`.

Both use only core commands (hashes, sets, strings, `SCAN`), with ACL users and `-@dangerous`.

Since Redis 8, Redis is distributed under a choice of **RSALv2, SSPLv1 or AGPLv3**. AGPLv3 is OSI-approved. Its network clause (§13) requires offering source for *modified* versions used over a network. Some organisations ban AGPL software by policy. Valkey (BSD-3, Linux Foundation) is a protocol-compatible fork of Redis 7.2.4.

Redis 8 also folds JSON, time series, probabilistic structures and vector sets into core. We don't need those today.

## Decision

We will run the **official `redis:8` image, unmodified, under the AGPLv3 option**, for both `redis-sessions` and `redis-cache`, deployed from the in-repo `redis-standalone` chart (no third-party chart, P‑09).

- We don't patch or rebuild Redis. If we ever need to, the change goes through legal again.
- The chart and the apps stay image-agnostic. **Valkey 8 remains the drop-in fallback** (image swap only, no app change).
- Licence choice and conditions are recorded in `platform/charts/redis-standalone/README.md`.

## Consequences

### Positive

- Official upstream image and release cadence; Redis 8 features available if needed later.
- No app change either way, because Spring Data Redis talks to both.

### Negative

- Depends on **legal sign-off** for AGPLv3 use (ARCH §6.3). Until that's recorded, production can't go live on Redis 8.
- Single-vendor governance. The licence has changed twice (BSD → RSAL/SSPL in 2024 → +AGPL in 2025), so future changes are possible.
- AGPL obligations apply if anyone modifies Redis, which needs an explicit "no patches" rule.

### Follow-ups

- Get and file the legal review result before the first production deploy. If it's rejected, switch the image to `valkey/valkey:8` and supersede this ADR.
- Pin minor versions in overlays; watch Redis licence announcements on each upgrade.
- Redis HA (Sentinel or a managed service) stays a separate decision (ARCH §6.3).

## Alternatives Considered

### Valkey 8

- **Summary:** BSD-3 fork of Redis 7.2.4 governed by the Linux Foundation; protocol-compatible.
- **Pros:** Permissive licence removes the legal question; multi-vendor governance; already the default on several clouds.
- **Cons:** Diverging feature set from Redis 8 (modules are separate); not the "official Redis" image.
- **Why rejected:** The team prefers upstream Redis. Valkey stays the documented fallback.

### Redis 7.2.x (last BSD release)

- **Why rejected:** Out of upstream support; would freeze on an old version.

### Third-party Helm chart (e.g. Bitnami)

- **Why rejected:** Image distribution terms changed (P‑09). The in-repo chart is small and under our control.

## References

- [InfoQ: Redis returns to open source under AGPL](https://www.infoq.com/news/2025/05/redis-agpl-license)
- [Redis: What is Valkey](https://redis.io/blog/what-is-valkey/)
- [AWS: Compare Redis OSS and Valkey](https://aws.amazon.com/elasticache/redis/)
- [GNU AGPLv3 text (§13 Remote Network Interaction)](https://www.gnu.org/licenses/agpl-3.0.html)
