---
name: bug-triage
description: Triage a bug ticket end to end. Disposition first, then release correlation, workaround discovery and priority scoring, with an audit log entry. Use when the user asks to triage a ticket, prioritize bugs, analyse a tracker bug, or asks what priority a bug should be. Triggers include "triage ABC-1234", "priorizá estos bugs", "qué prioridad tiene", "is this a bug or expected behavior", "which release broke this".
---

# Bug triage

Orchestrator. Loads the shared rubric, resolves the team config, runs the stages in
order.

## Setup

1. **Header first, before reading anything else.** Take the team from `--team`, else
   `CLAUDE_TRIAGE_TEAM`, then run:

       python3 scripts/run_header.py --team <id> <TICKET> [<TICKET>...]

   Print its output **verbatim** as your first message text, in a code block. Do not
   paraphrase, shorten or summarise it: the host collapses command output, so a reader
   sees the header only if you repeat it. Exit code 2 means no such team: show the
   available ids it lists and ask. Never pick one silently. Exit code 3 means a ticket
   has no fixture in fixture mode: say which, and triage only the rest.
   If no team was given at all, list the ids under `teams/` and ask.
2. Load `skills/data-sources/SKILL.md`. Do not call any MCP tool before this.
   For every source in `live` mode other than the tracker, read its tool-name suffixes
   from `tool_bindings` in the team config. A live source with no `tool_bindings` entry is a
   configuration error: report it, do not guess tool names.
3. Read `reference/disposition-taxonomy.md` and `reference/priority-rubric.md`.
4. Note which sources are `live`, `fixture`, `off`. This drives the provenance line and
   which classification questions can be answered.
5. Read [`reference/run-visibility.md`](../../reference/run-visibility.md) for the stage
   line format. The header is already printed; from here, emit one stage line per
   stage as each completes.
6. Where the host offers task tools, create the five stage tasks and resolve each as it
   completes. Where it does not, skip this and carry on: the stage lines are the record.

## Narrating the run

The host draws every command as a bare row with no explanation, and long thinking
gaps show only a timer. A reader watching that learns nothing. So:

- **Read reference and fixture files with the file-read tool, not a shell command.**
  A file read shows the file name; `cat` in a shell shows only "Bash".
- **Where the shell tool accepts a description, give every command one** in plain
  words: "Validating team config", not the command itself.
- **Write the stage line as message text between tool calls**, the moment the stage
  completes. Text between calls is what the reader sees; tool output is collapsed.
- **In batch mode, open each ticket with a marker** such as `Ticket 2 of 4 · BUG-4844`
  before its Stage 1, so the reader knows which ticket the next lines belong to.
- Never narrate intent ("now I will read the rubric"). Narrate results. A line that
  says what is about to happen tells the reader nothing they can act on.

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
five. Print `Stage 3  skipped, non-defect` rather than omitting the stage, so the
reader sees the gate fire instead of wondering where a stage went.

This ordering is the point of the whole tool. Scoring a non-defect is worse than not
triaging it.

## Stage 3: deep enrichment (defects only, in parallel)

**Delegate live sources to parallel subagents and wait for all of them before
continuing.** One per source, for whichever of `metrics`, `warehouse` and `code` are in
`live` mode. Skip sources that are `off`.

Read `fixture` sources directly, without a subagent. A fixture is a local envelope
file; a subagent to read it adds latency and parallelises nothing worth parallelising.
Delegation exists for network calls that are slow and independent. The envelope is the
same either way, so nothing downstream can tell the difference.

State the delegation explicitly rather than relying on any one client's bundled-agent
files: Claude and Cursor load the definitions in `agents/`, and Codex delegates when a
skill instruction asks it to. Where a client cannot delegate at all, query the sources
in turn and note the added latency; correctness does not depend on the parallelism.

Each subagent returns exactly the envelope defined in `skills/data-sources/SKILL.md`,
and nothing else. Do not reshape it.

Each must use read operations only: no writes to the tracker, no non-template SQL, no
repository modification. **This is an instruction, not an enforced boundary.** A live
test showed that per-agent tool allowlists granted no MCP tools at all rather than a
read-only subset, so the agents now declare `tools: ["*"]` and the allowlist guarantees
that earlier versions of this file claimed never existed. What does enforce it is
outside the prompt: a read-only service account on each source, the validator's SQL
check, and per-ticket confirmation before any tracker comment is posted.

Name each subagent in the stage-line block as it returns, per
[`reference/run-visibility.md`](../../reference/run-visibility.md). Never print a line
for a source that was `off`: no agent was spawned for it.

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

Three surfaces, all defined in [`reference/output-templates.md`](../../reference/output-templates.md):

1. **Chat summary.** Always. Lead with the answer, one line of arithmetic, a pointer
   to the report. Ten seconds to read.
2. **Report file.** Written to `output.reports_dir` as `<TICKET>.md` when
   `output.write_report` allows. The path is relative to the **working directory**,
   not the plugin, which may be installed somewhere temporary. Say where you wrote it.
3. **Tracker comment.** Generated as plain text. Never posted without explicit
   per-ticket confirmation in the conversation.
4. **Run trace.** Unless `output.run_trace` is `never`, write the structured result to
   `<reports_dir>/<TICKET>.result.json` in the shape defined in
   [`reference/run-visibility.md`](../../reference/run-visibility.md), then run:

       python3 scripts/render_trace.py --out <reports_dir> <reports_dir>/<TICKET>.result.json

   **Never hand-write the trace HTML.** The script renders it identically every run and
   refuses a non-defect that carries a priority. If it refuses, the result file is
   wrong: fix the result, not the script. With `artifact`, publish the rendered file
   where the client can publish; otherwise keep the file and say so. Default is `file`,
   because a trace carries customer names and account counts and publishing it is a
   disclosure decision. Never fail a triage over a presentation surface. In batch mode,
   render all tickets in one call.

Then append the audit record:

    python3 scripts/triage_log.py append --ticket <KEY> --team <team> \
        --disposition <d> [--priority <P>] --confidence <c> --modes <src=mode,...> \
        [--escalations ...] [--unanswered ...] [--source-errors ...] [--flags ...]

`append` refuses a non-defect carrying a priority. If it refuses, the pipeline made a
mistake: a disposition other than `defect` must never have reached scoring.

## Batch mode

Several ticket IDs: run each through the full pipeline, then emit one ranked table
ordered by priority then by deciding factor. Non-defects are listed in a separate
section with their disposition, not ranked among the defects.
