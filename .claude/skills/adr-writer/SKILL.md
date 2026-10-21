---
name: "adr-writer"
description: "Write an Architecture Decision Record (ADR) from a one-line decision the user gives, e.g. \"use Redis Streams instead of Kafka for async jobs because Kafka is too heavy to operate\". Researches the options, asks the user to clarify gaps, and saves docs/adr/{yymmdd}-{title}.md with Title, Status, Context, Decision, Consequences and Alternatives Considered. Use when the user says \"write an ADR\", \"record this decision\", \"document why we chose X over Y\", or runs /adr-writer."
---

# ADR Writer

Turns a short decision statement into a complete Architecture Decision Record saved at `docs/adr/{yymmdd}-{title}.md`.

## Input

A decision statement from the user, usually in the shape "use X instead of Y for Z because R". Example:

> use Redis Streams instead of Kafka for async jobs because Kafka is too heavy to operate

## Workflow

### 1. Parse the statement

Pull out:

- **Chosen option** (X), e.g. Redis Streams
- **Rejected option(s)** (Y), e.g. Kafka
- **Scope / problem** (Z), e.g. async job processing
- **Stated rationale** (R), e.g. operational weight

Record which of these are missing or vague.

### 2. Look at the project

If a repo or docs folder is available:

- Locate the project root, meaning the folder that holds `docs/` or the VCS root. If `docs/adr/` doesn't exist, create it.
- List existing ADRs in `docs/adr/`. Read any that touch the same area, so you can reference, supersede or avoid contradicting them.
- Skim README, build files (pom.xml, package.json, build.gradle, docker-compose, k8s manifests) and config to learn the stack and what is already deployed. If Redis is already running for caching, that is relevant context.

### 3. Research

Use web search to back the ADR with facts, not just the user's opinion:

- What each option is and how it works, at the level relevant to the decision
- Operational cost: infra footprint, managed-service options, monitoring, upgrades
- Capabilities that matter for the scope: delivery guarantees, ordering, retention, replay, consumer groups, throughput limits, persistence and durability, ecosystem and client libraries for the project's language
- Known limits or failure modes of the chosen option, which feed Consequences
- One or two other credible alternatives the user didn't mention (e.g. RabbitMQ, a DB-backed queue, a cloud queue service)

Prefer official docs and well-known engineering sources. Keep claims accurate and avoid invented benchmark numbers. If a number can't be verified, describe it qualitatively.

### 4. Ask for clarification only when needed

Ask the user (use the AskUserQuestion tool if available, at most 1–4 focused questions in a single round) when a gap would change the ADR's substance. Typical gaps:

- Expected scale (jobs/sec, payload size, retention needs)
- Delivery requirements (at-least-once ok? ordering needed? replay needed?)
- Status: Proposed (default) or Accepted?
- Whether this supersedes an existing ADR
- Deciders/owners, if the team wants them listed

Don't ask about anything you can infer from the repo or research. If the user isn't available, use sensible defaults and mark assumptions explicitly in Context.

### 5. Build the filename

- `yymmdd` = today's date (e.g. 2026-10-20 → `261020`). Get it from the system (`date +%y%m%d`), never guess.
- `title` = a short kebab-case slug of the decision: lowercase ASCII, words joined by `-`, no punctuation, about 3–7 words. Example: `use-redis-streams-for-async-jobs`.
- Full path: `docs/adr/261020-use-redis-streams-for-async-jobs.md`
- If the file already exists, ask before overwriting, or append `-2`.

### 6. Write the ADR

Use exactly this structure:

```markdown
# {Title — imperative, human readable, e.g. "Use Redis Streams for asynchronous job processing"}

- **Status:** {Proposed | Accepted | Deprecated | Superseded by [ADR](./file.md)}
- **Date:** {YYYY-MM-DD}
- **Deciders:** {names/roles, or omit line if unknown}

## Context

{The problem and forces at play, written neutrally. What needs to be done and why now.
Relevant constraints: team size and ops capacity, existing stack, scale, delivery/ordering needs.
Facts from research that frame the choice. List any assumptions explicitly.
Link related ADRs.}

## Decision

{One clear statement in active voice: "We will use X for Z."
Then the key reasons, tied back to the forces in Context.
Include scope boundaries: what this decision covers and what it does not.}

## Consequences

### Positive
- {benefits that follow}

### Negative
- {costs, limits, risks the team is accepting, e.g. memory-bound retention, weaker replay than Kafka}

### Follow-ups
- {mitigations, monitoring, conditions that would make us revisit this decision (e.g. throughput > N, need for long-term event replay)}

## Alternatives Considered

### {Rejected option from the user, e.g. Apache Kafka}
- **Summary:** {what it is}
- **Pros:** {…}
- **Cons:** {…}
- **Why rejected:** {tie to Context}

### {Other researched alternative, e.g. RabbitMQ}
- **Summary / Pros / Cons / Why rejected** as above

## References
- {links to docs/articles used in research}
```

Writing rules:

- Be concrete and specific to this project, not a generic comparison article.
- Be fair to the rejected options. The ADR should stay credible a year later, when someone asks "why didn't we use Kafka?"
- Name the downsides of the chosen option honestly in Negative consequences.
- Keep it to roughly one to two pages. Bullets are fine; avoid filler.
- Write in the language the user wrote the decision in, unless they ask otherwise.

### 7. Finish

Save the file, show the user the path, and give a 2–3 line summary: the decision, the main trade-off accepted, and any assumptions they should confirm. Offer to change the status to Accepted or to link it from an ADR index (`docs/adr/README.md`) if one exists.

