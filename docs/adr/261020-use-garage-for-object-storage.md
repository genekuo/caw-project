# Use Garage as the in-cluster S3-compatible object store

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** 郭育郡
- **Design refs:** 06-data-platform §7; 02-inventory §5.5; assumption P‑11

## Context

Inventory stores book cover images (≤ 5 MB each) in one private bucket, `bookstore-covers`, through a `CoverImageStore` interface over the S3 API (AWS SDK v2, `endpointOverride`, path-style). On-prem, we need an S3-compatible store. AWS phase 2 switches to Amazon S3 by configuration only.

Forces:

- Small data volume (thousands of objects, a few GB), a single bucket, low request rate. Reads are served through inventory and cached by browsers (`immutable`).
- The team has no existing Rook/Ceph cluster to reuse.
- MinIO's community edition went into maintenance mode in December 2025 (no new features or binaries), so it's no longer a sound default.
- Backups go off-cluster (P‑05) with `rclone`.

## Decision

We will run **Garage** in the `bookstore-data` namespace as a 3-node StatefulSet with replication factor 3 (PVC 20 Gi each), with:

- bucket `bookstore-covers` (private) and key `inventory-covers` scoped to it,
- `S3_PATH_STYLE=true` and `S3_REGION=garage`,
- a nightly `rclone sync` to the off-cluster backup bucket.

We use the upstream Garage binary unmodified. Garage is AGPLv3; inventory talks to it only over the S3 API.

## Consequences

### Positive

- Lightweight (single binary, low memory) and designed for small self-hosted clusters; replication without erasure-coding complexity.
- Pure S3 API, so the move to Amazon S3 is a config change.

### Negative

- Smaller community and ecosystem than Ceph. Fewer operators and tools; we write our own bootstrap Job (layout, bucket, key).
- Replication factor 3 means 3× raw storage for the data.
- AGPLv3: same "no modifications" rule as the [Redis decision](./261020-use-redis-8-under-agplv3.md); note it in the chart README.
- Not every S3 feature is implemented. We use only Put/Get/Delete/Head, which Garage supports.

### Follow-ups

- Integration test 10 (02 §11) runs against a Garage container, not just a generic S3 mock.
- If Rook/Ceph is introduced on the cluster later, switch to Ceph RGW and supersede this ADR.
- Add the orphaned-object cleanup job (02 §5.5 step 8) in a later release.

## Alternatives Considered

### Ceph RGW (via Rook)

- **Pros:** Very mature and feature-complete; ideal if Ceph already runs.
- **Cons:** Heavy to introduce just for one small bucket (MONs, OSDs, MGR).
- **Why rejected:** No existing Ceph; out of proportion to the need.

### SeaweedFS

- **Pros:** Apache-2.0; fast for small files; S3 gateway.
- **Cons:** More components (master, volume, filer, S3) to run and back up.
- **Why rejected:** More operational surface than Garage for the same result.

### MinIO

- **Why rejected:** The community edition is in maintenance mode or archived, with no published binaries; the admin console was removed from the community edition.

## References

- [Garage project](https://garagehq.deuxfleurs.fr/)
- [Garage repository (replication modes)](https://git.deuxfleurs.fr/Deuxfleurs/garage)
- [Garage licence discussion (AGPLv3), issue #840](https://git.deuxfleurs.fr/Deuxfleurs/garage/issues/840)
- [MinIO is in maintenance mode (Elestio)](https://blog.elest.io/minio-is-in-maintenance-mode-your-guide-to-s3-compatible-storage-alternatives/)
