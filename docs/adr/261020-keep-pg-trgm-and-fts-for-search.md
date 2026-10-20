# Keep PostgreSQL pg_trgm plus simple full-text search for catalog search

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** 郭育郡
- **Design refs:** 02-inventory §5.3; 06-data-platform §3.1–3.2; assumption I‑04

## Context

Book titles and author names mix Traditional Chinese and English. PostgreSQL text search doesn't segment Chinese, so 02 §5.3 combines:

1. `to_tsvector('simple', …)` full-text search for English words and space-separated runs.
2. `pg_trgm` substring matching (`LIKE '%q%'` on `search_text`, GIN trigram index) for Chinese substrings and partial words.

Known limits found in review:

- Trigram indexes can't serve queries shorter than 3 characters. Many Chinese queries are 2 characters (e.g. `哈利`), so they fall back to a sequential scan on `book`.
- pg_trgm only indexes characters that the database's **`LC_CTYPE`** classifies as alphanumeric. Under the `C` ctype, CJK characters are ignored. ICU as the locale *provider* (06 §3.1: `localeProvider: icu`, `icuLocale: und`) controls collation, but initdb still sets a libc ctype.
- Scale: well under 100k books (I‑08). A sequential scan of that table is cheap.

## Decision

We will **keep pg_trgm + `simple` FTS** in PostgreSQL for v1 and not add pg_bigm or a search engine. To make the trigram part reliable:

- Set the libc ctype explicitly in the CNPG `initdb` bootstrap (`localeCType: en_US.UTF-8` or `C.UTF-8`, whichever the CNPG image supports with full Unicode classification), alongside the ICU settings.
- Run search test 6 (02 §11) against a database bootstrapped **exactly like CNPG**, not a default Testcontainers database, including `show lc_ctype` and `select show_trgm('哈利波特')`, which must return CJK trigrams.
- Add a load test with 2-character Chinese queries at the target catalog size. Track `bookstore.search.short_query` and search p95.

## Consequences

### Positive

- No new extension, image or system. `pg_trgm` is a trusted extension that ships with PostgreSQL.
- Search stays transactionally consistent with the catalog; no index sync.

### Negative

- 2-character Chinese queries do sequential scans. That's fine at today's size, but cost grows linearly with the catalog.
- Relevance is basic (`ts_rank` + `similarity`): no word segmentation, synonyms, or simplified/traditional folding.
- Getting `LC_CTYPE` wrong at initdb silently breaks CJK search, and fixing it means dump and restore.

### Follow-ups

- Revisit if search p95 exceeds 300 ms under load, the catalog nears 100k books, or the business asks for better relevance. The next step is **pg_bigm** (2-gram GIN, built for CJK; needs a custom CNPG image). After that, a dedicated engine fed by catalog events (ARCH §7).

## Alternatives Considered

### pg_bigm

- **Summary:** A 2-gram GIN index extension derived from pg_trgm, designed for CJK text and short keywords.
- **Pros:** Indexes 2-character queries; handles CJK without locale tricks.
- **Cons:** Not in the standard CNPG images (custom image or extension image needed). GIN-only. Version-dependent coexistence with pg_trgm (1.1+ can coexist). Slower index builds reported on large corpora.
- **Why rejected (for now):** Image and maintenance cost aren't justified below about 100k books. It's the first upgrade path.

### Dedicated search engine (OpenSearch, Meilisearch)

- **Pros:** CJK analyzers, typo tolerance, facets, better relevance.
- **Cons:** Another stateful cluster, plus indexing from catalog events, consistency lag and backups.
- **Why rejected:** Operational cost too high for v1 scale.

### PGroonga

- **Pros:** Fast CJK full-text search inside PostgreSQL.
- **Cons:** Not in standard images; less common in operations teams.
- **Why rejected:** Same image cost as pg_bigm, with a less familiar operational model.

## References

- [PostgreSQL pg_trgm](https://www.postgresql.org/docs/current/pgtrgm.html)
- [pg_bigm documentation](https://github.com/pgbigm/pg_bigm/blob/REL1_0_STABLE/docs/pg_bigm_en.md)
- [Vonng: fuzzy matching in PostgreSQL and LC_CTYPE for Chinese](https://vonng.com/en/pg/fuzzymatch/)
- [pgsql-general: pg_trgm and non-C locales](https://www.postgresql.org/message-id/1274983261.18581.14.camel%40vanquo.pezone.net)
- [PostgreSQL initdb (ICU provider still sets libc locale)](https://www.postgresql.org/docs/current/app-initdb.html)
- [PGroonga 1.0.0 announcement and benchmark](https://groonga.org/en/blog/2015/10/29/pgroonga-1.0.0.html)
