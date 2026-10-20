# Publish catalog events with a hand-written transactional outbox relay

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** 郭育郡
- **Design refs:** 02-inventory §5.1, §5.2, §9; 00-conventions §5; assumption I‑03

## Context

Every admin write in inventory has to produce catalog events (`book.*`, `author.*`) on RabbitMQ exchange `catalog.events`. The events must not be lost or published for rolled-back changes. The write and the event therefore have to commit atomically: a transactional outbox in PostgreSQL.

Specific requirements:

- A custom envelope (`eventId` = outbox row id, `aggregateVersion`, `schemaVersion`) and AMQP properties (00 §5.1–5.2).
- A price change writes **two** rows in one transaction (`book.updated` + `book.price-changed`).
- The W3C trace context is stored with the row and restored on publish, so one trace spans admin PUT → RabbitMQ → consumer.
- Publisher confirms; unroutable messages are counted but still marked published.
- Safe to run on every replica at once (2–6 pods) without leader election.

Spring Modulith offers an event publication registry (JDBC) with AMQP externalization, and from 2.1 requires RabbitMQ publisher confirms for outbox-based externalization.

## Decision

We will implement the **outbox relay ourselves** as described in 02 §5.2:

- An `outbox` table written in the same transaction as the change.
- A scheduled relay (every 500 ms, plus an in-process wake-up after commit) runs `SELECT … WHERE published_at IS NULL ORDER BY created_at LIMIT 100 FOR UPDATE SKIP LOCKED`.
- Publish via `RabbitTemplate.invoke` + `waitForConfirmsOrDie(5 s)`, with `mandatory: true` and a returns callback.
- Exponential backoff on failure (max 30 s). A daily cleanup of rows published more than 7 days ago, under `pg_try_advisory_lock`.
- Metrics: outbox lag, published, failures, unroutable.

## Consequences

### Positive

- The envelope, the two-row price rule and trace propagation are explicit code that is easy to test.
- No framework owns the table schema or retry semantics. Behaviour is fully visible in about 150 lines.
- `SKIP LOCKED` scales across replicas with no coordination.

### Negative

- We own the code: retries, backoff, cleanup and metrics have to be built and tested by us.
- Ordering across replicas isn't guaranteed. Consumers depend on `aggregateVersion` and `eventId` dedupe (00 §5.5).
- Polling adds up to 500 ms latency for events committed on another replica.

### Follow-ups

- Integration tests 1, 2 and 8 in 02 §11 cover publish, the two-row price rule and cross-instance delivery.
- Revisit Spring Modulith if more services need outboxes, so the code isn't duplicated.

## Alternatives Considered

### Spring Modulith event publication registry + AMQP externalization

- **Summary:** Domain events are stored in a JDBC publication table and externalized to RabbitMQ by Modulith.
- **Pros:** Less custom code; maintained by the Spring team; built-in republish of incomplete publications.
- **Cons:** Modulith's table, serialization and retry model would have to be bent to our envelope, the `eventId` = row id rule, stored trace context and the two-row price rule. Another framework to track across Boot 4.x releases.
- **Why rejected:** The custom envelope and tracing needs make the framework's abstractions more of an obstacle than a help for a single service.

### Change data capture (Debezium) from the outbox table

- **Pros:** No polling; log-based ordering.
- **Cons:** Kafka Connect or Debezium Server plus logical replication slots to operate.
- **Why rejected:** Too much infrastructure for one table and modest volume.

### Publish directly after commit (no outbox)

- **Why rejected:** Events are lost if the process dies between commit and publish.

## References

- [Spring Modulith reference: event publication registry and externalization](https://docs.spring.io/spring-modulith/reference/events.html)
- [Spring Modulith 2.1 API](https://docs.spring.io/spring-modulith/docs/current/api/)
- [microservices.io: Transactional outbox](https://microservices.io/patterns/data/transactional-outbox.html)
- [PostgreSQL: SELECT … FOR UPDATE SKIP LOCKED](https://www.postgresql.org/docs/current/sql-select.html#SQL-FOR-UPDATE-SHARE)
