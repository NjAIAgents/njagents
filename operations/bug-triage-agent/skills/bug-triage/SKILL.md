---
name: bug-triage
description: Triage a bug ticket end to end. Disposition first, then release correlation, workaround discovery and priority scoring, with an audit log entry. Use when the user asks to triage a ticket, prioritize bugs, analyse a tracker bug, or asks what priority a bug should be. Triggers include "triage ABC-1234", "priorizá estos bugs", "qué prioridad tiene", "is this a bug or expected behavior", "which release broke this".
---

# Bug triage

Orchestrator. Loads the shared rubric, resolves the team config, runs the stages in
order.

## Setup

1. Resolve the team config: the `--team` argument matched against `team.id` in each
   file under `teams/`, else `CLAUDE_TRIAGE_TEAM`. If neither is given, list the
   available team ids and ask. Never pick one silently when several exist.
2. Load `skills/data-sources/SKILL.md`. Do not call any MCP tool before this.
   For every source in `live` mode other than the tracker, read its tool-name suffixes
   from `tool_bindings` in the team config. A live source with no `tool_bindings` entry is a
   configuration error: report it, do not guess tool names.
3. Read `reference/disposition-taxonomy.md` and `reference/priority-rubric.md`.
4. Note which sources are `live`, `fixture`, `off`. This drives the provenance line and
   which classification questions can be answered.

## Stage 0: information gate

Minimum: a description of the problem, an affected component or feature area, and one
of a reproduction step or an error message.

Missing any of them, stop. Return the specific missing items. Do not guess a
disposition from a one-line ticket.

## Stage 1: base enrichment (always)

Dispatch `enrich-tracker` and the release adapters. These two are the minimum viable
sources and the disposition gate depends on them: prior tickets, duplicates and
component history all come from the tracker envelope.

Skip nothing here. If `tracker` is unavailable, stop: without it there is no triage.

## Stage 2: disposition

Run `skills/triage-disposition` against the Stage 1 envelopes.

If the result is anything other than `defect`, emit the disposition output with the
release context already gathered, route per the taxonomy, log, and stop. No priority
is assigned and Stage 3 never runs, so a non-defect costs two source calls rather than
five.

This ordering is the point of the whole tool. Scoring a non-defect is worse than not
triaging it.

## Stage 3: deep enrichment (defects only, in parallel)

**Delegate these to parallel subagents and wait for all of them before continuing.**
One per source, for whichever of `metrics`, `warehouse` and `code` are in `live` or
`fixture` mode. Skip sources that are `off`.

State the delegation explicitly rather than relying on any one client's bundled-agent
files: Claude and Cursor load the definitions in `agents/`, and Codex delegates when a
skill instruction asks it to. Where a client cannot delegate at all, query the sources
in turn and note the added latency; correctness does not depend on the parallelism.

Each subagent returns exactly the envelope defined in `skills/data-sources/SKILL.md`,
and nothing else. Do not reshape it.

Each must use read operations only: no writes to the tracker, no non-template SQL, no
repository modification. On Claude and Cursor this is enforced by the tool allowlists
in `agents/`. Elsewhere it is enforced by the read-only service account and the
validator's SQL check, and must be honoured as an instruction.

Run `skills/release-correlation` and `skills/workaround-finder` across everything
gathered in Stages 1 and 3.

## Stage 4: classify



Apply `reference/priority-rubric.md`. Answer the ten questions in order. Mark any
question whose source was unavailable as unanswered; do not infer it.

Apply escalation signals with the one-per-class rule and the two-level cap. Apply the
at-risk P2 floor before the cap. Compute confidence from the stated table.

Apply the degradation rules in the data-sources skill. Round up only when the ticket
itself reports multi-account or systemic symptoms, never merely because a connector is
switched off.

## Stage 5: output and log

Render per `reference/output-templates.md`, including the provenance line. Append the
audit record to `logs/triage-log.jsonl`.

Never post to tracker without explicit per-ticket confirmation in the conversation.

## Batch mode

Several ticket IDs: run each through the full pipeline, then emit one ranked table
ordered by priority then by deciding factor. Non-defects are listed in a separate
section with their disposition, not ranked among the defects.
