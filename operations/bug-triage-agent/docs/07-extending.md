# Extending

## Where a change belongs

Ask what kind of thing you are changing. This decides everything.

| Change | Goes in | Who approves |
| --- | --- | --- |
| A team's project key, tables, repos, routing | `teams/<team>.json` | That team |
| Which sources a team runs | `teams/<team>.json` | That team |
| Release adapters and their order | `teams/<team>.json` | That team |
| A new disposition, or changed evidence rules | `reference/disposition-taxonomy.md` | Shared-core owner |
| Priority criteria, escalation classes, caps | `reference/priority-rubric.md` | Shared-core owner |
| Output format | `reference/output-templates.md` | Shared-core owner |
| Stage ordering | `skills/bug-triage/SKILL.md` | Shared-core owner |
| A new source type | Contract in `skills/data-sources/`, plus an agent and validator shape | Shared-core owner |

The line: **if it names a product, schema, repository or customer, it is team
config.** If it is judgment, it is shared and changes once for everyone.

## Adding a release adapter

Release manifests are pluggable because organizations record releases differently.

1. Define its `data` contribution in `skills/data-sources/SKILL.md` under `releases`.
   It must produce the same release object shape.
2. Add the adapter name to the schema's allowed list.
3. Add any settings the adapter needs under `release_correlation`.
4. Teach the validator any invariant it introduces. Precedent: only version-control
   adapters may yield `files_touched`, and the validator rejects a release carrying
   file detail without one. **That rule caught a bad fixture.**
5. Record which adapters contributed in each release's `sources`, so a reader can tell
   a correlation resting on a release-note page from one resting on merged pull
   requests.

## Adding a source

Heavier. Five places:

1. **Contract** in `skills/data-sources/SKILL.md`: envelope shape, live adapter, what
   `unavailable` means for it.
2. **Agent** in `agents/`, with a read-verb tool allowlist and instructions to return
   the envelope and nothing else.
3. **Validator**: add the shape to `SHAPES` so fixtures are checked.
4. **Fixtures**: one per demo ticket, validated against the same shape.
5. **Rubric**: if it answers a classification question, say which. If it does not
   answer one, ask why you are adding it.

Then confirm the degradation rule: with the source `off`, which questions go
unanswered, and does anything inappropriately change priority? The answer must be no.

## Changing the rubric

The cap, the one-escalation-per-class rule and never-P1-by-escalation exist because
their absence turned cosmetic bugs into P1s in a predecessor. Before relaxing one:

1. Recompute every worked example in
   [`fixtures/expected-outcomes.md`](../fixtures/expected-outcomes.md) by hand.
2. Re-run the benchmark, if one exists by then, and compare per class.
3. Write down which real ticket motivated the change.

A rubric change that nobody can trace to a real misclassification is a guess.

## Adding a plugin to this repository

Repository structure names the **kind of work**: `development/`, `operations/`, `qa/`,
`business-analyst/`, `release/`. Put the plugin in the matching one, give it three
manifests, and add one entry to the root `marketplace.json`. Nothing else at the root
changes.

Add a category only when a genuinely new kind of work appears, never for a new client
or technology. See
[`.specify/memory/constitution.md`](../../../.specify/memory/constitution.md).

## Spec-driven changes

This repository uses Spec Kit. For anything beyond a config edit, run the skills from
the **repository root**:

```
/speckit-specify    what and why
/speckit-plan       how
/speckit-tasks      break it down
/speckit-implement
/speckit-converge
```

The constitution is already written and applies to every plan. Read it first: several
of its principles will reject an otherwise reasonable design.
