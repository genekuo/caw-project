# Use offset paging with totals for catalog tables

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** 郭育郡
- **Design refs:** 00-conventions §3.3; 02-inventory §3.1, §5.3; 04-frontend §5.2; assumptions A‑11, F‑04, I‑08

## Context

The API convention (00 §3.3) defaults to keyset pagination with an opaque `nextCursor`. Keyset pages stay stable when data changes, and they cost the same no matter how deep you page.

The UI mock-ups (`book-page-logged-in-and-anonymous-users.png`, `author-dialog.png`) show a Material paginator with a page-size selector and "1 – 10 of N". That needs a total count and random access to page *n*, which keyset can't provide. SEO and no-JS pages also link to `?page=n` (04 §5.1).

Expected scale: the catalog stays well under 100k books (I‑08), and the admin author list is smaller still.

## Decision

We will use **offset paging with an exact `total`** (`?offset=&limit=` → `{items, offset, limit, total}`) for:

- the public book list and search (`GET /catalog/books`),
- the admin book list,
- the admin author list,
- admin user search (Keycloak only offers offset).

Keyset stays the default everywhere else, including audit logs. Rules:

- `offset` is capped at 10,000.
- `total` is a `COUNT(*)` with the same filters, run in the same `REPEATABLE READ` read-only transaction as the page.
- Every sort has an `id` tie-breaker.
- An endpoint supports either `offset` or `cursor`, never both.

## Consequences

### Positive

- Matches the mock-ups: page numbers, page size and totals.
- Shareable and crawlable `?page=n` URLs.
- Simple SQL, so no cursor codec is needed on these endpoints.

### Negative

- Each list request runs two queries (page + count). The count is cached together with the page in `book-page` (TTL 2 min).
- Deep offsets get slower linearly. They're capped at 10,000, so very deep pages are reached by narrowing the search.
- Rows can appear twice or be skipped if data changes between page requests. This is accepted for these tables.

### Follow-ups

- Watch p95 latency of `GET /catalog/books` with `q` and large offsets. If the catalog approaches 100k books, revisit keyset with "next page" only (drop totals from the UI).

## Alternatives Considered

### Keyset only (the original convention)

- **Pros:** Stable under concurrent writes; cost independent of depth.
- **Cons:** No totals, no jump-to-page, no page-size selector; doesn't match the mock-ups.
- **Why rejected:** The UI design requires totals and page numbers.

### Keyset with an approximate total (e.g. `pg_class.reltuples` or a capped count)

- **Pros:** Cheaper count.
- **Cons:** Wrong numbers under filters and search; still no random page access.
- **Why rejected:** Inaccurate "of N" with filters, and the cost saving isn't needed at this scale.

## References

- [PostgreSQL: LIMIT and OFFSET](https://www.postgresql.org/docs/current/queries-limit.html)
- [Use The Index, Luke: Paging through results](https://use-the-index-luke.com/no-offset)
