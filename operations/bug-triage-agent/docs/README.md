# bug-triage-agent documentation

Start here. This index says what each document covers and, more importantly, **where
the authoritative version of each rule lives**.

## Reading paths

| If you are | Read |
| --- | --- |
| Deciding whether to adopt this | [Overview](01-overview.md), then [Status](../STATUS.md) |
| Installing it for your team | [Installation](03-installation.md), [Configuration](04-configuration.md) |
| Using it day to day | [Usage](05-usage.md) |
| Running it for several teams | [Operations](06-operations.md) |
| Building or changing it | [Architecture](02-architecture.md), [Extending](07-extending.md) |
| Lost in the vocabulary | [Glossary](08-glossary.md) |

## Source of truth

These documents **explain**. They do not define. Where a rule is stated normatively,
that file wins and these pages link to it. If you find a rule restated here, that is a
bug: file it or delete it.

| Rule | Defined in |
| --- | --- |
| What counts as a defect, expected behaviour, duplicate, voice-of-customer | [`reference/disposition-taxonomy.md`](../reference/disposition-taxonomy.md) |
| P1 to P4 criteria, the ten questions, escalation classes, caps, confidence | [`reference/priority-rubric.md`](../reference/priority-rubric.md) |
| What every output looks like | [`reference/output-templates.md`](../reference/output-templates.md) |
| How to replace the taxonomy with your organization's real judgment | [`reference/taxonomy-calibration.md`](../reference/taxonomy-calibration.md) |
| Stage ordering and the end-to-end procedure | [`skills/bug-triage/SKILL.md`](../skills/bug-triage/SKILL.md) |
| Source envelope, adapters, modes, degradation | [`skills/data-sources/SKILL.md`](../skills/data-sources/SKILL.md) |
| Per-component procedure | the matching `skills/*/SKILL.md` |
| What a team config may contain | [`teams/team-config.schema.json`](../teams/team-config.schema.json) |
| What is built, unexercised, or missing | [`STATUS.md`](../STATUS.md) |
| Principles governing the whole repository | [`.specify/memory/constitution.md`](../../../.specify/memory/constitution.md) |

## A caution before you rely on any of this

Most of this plugin is instructions an agent follows at runtime, not code that
executes deterministically. At the time of writing **none of it has been run**.
[`STATUS.md`](../STATUS.md) separates what is verified from what is merely written.
Read it before promising anything to anyone.
