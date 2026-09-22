---
name: bug-triage
description: Triage a bug ticket end to end. Disposition first, then release correlation, workaround discovery and priority scoring, with an audit log entry. Use when the user asks to triage a ticket, prioritize bugs, analyse a tracker bug, or asks what priority a bug should be. Triggers include "triage ABC-1234", "priorizá estos bugs", "qué prioridad tiene", "is this a bug or expected behavior", "which release broke this".
---

# Bug triage

Orchestrator. Loads the shared rubric, resolves the team config, runs the stages in
order.

## Setup

0. **Find the plugin and the user's folder.** Every `scripts/…`, `reference/…`,
   `skills/…` and `teams/…` path in this plugin is relative to the plugin root, not to
   the shell's current directory. The base directory this skill was loaded from is
   often a host path the shell cannot see (a sandboxed shell mounts the plugin
   elsewhere), so resolve the root once with this, and never conclude the plugin's
   files are missing until it has run:

   ```bash
   for c in "${CLAUDE_PLUGIN_ROOT:-}" "<this skill's base directory>/../.."; do
     [ -n "$c" ] && [ -f "$c/scripts/run_header.py" ] && { cd "$c" && pwd; exit 0; }
   done
   for d in /sessions "$HOME" /var/folders /tmp; do
     [ -d "$d" ] && find "$d" -maxdepth 9 -path '*/scripts/run_header.py' 2>/dev/null
   done | xargs grep -l 'Print the run header for a triage' 2>/dev/null \
        | grep -E '/(\.remote-plugins|claude-hostloop-plugins|\.claude/plugins)/' \
        | head -1 | sed 's#/scripts/run_header.py$##'
   ```

   It prefers the installed plugin. If it prints nothing but a search without the
   final `grep -E` finds a copy in a source checkout, say so and ask before using it:
   a checkout may hold unreleased code.

   The **working folder** is the folder the user is working in: the one they opened or
   connected, not the shell's start directory. Reports, traces, the audit log and the
   team's own `triage-teams/` all live there. If you cannot tell, ask.

   Shell state may not persist between commands, so write both resolved paths out
   literally in every later command rather than relying on a variable.

1. **Header first, before reading anything else.** Take the team from `--team`, else
   `CLAUDE_TRIAGE_TEAM`, then run:

       python3 <plugin root>/scripts/run_header.py --workdir <working folder> \
           --team <id> <TICKET> [<TICKET>...]

   Print its output **verbatim** as your first message text, in a code block. Do not
   paraphrase, shorten or summarise it: the host collapses command output, so a reader
   sees the header only if you repeat it.

   The script looks for the team in the config dir, then `triage-teams/` in the
   working folder (and one or two levels below it), then the configs shipped in the
   plugin. The header names the config file it loaded and the agent version and root
   it ran from, so a stale install or a wrong copy is visible on the first line.

   **Exit code 2 means no config for that team.** Show what it printed, then offer two
   choices: run `skills/triage-config` to create one now, or use one of the listed ids.
   Never pick one silently, and never improvise a config inline: an untested config
   produces an untested triage. If the user creates one, resume this triage with the
   same tickets without asking for them again.

   Exit code 3 means a ticket has no fixture in fixture mode: say which, and triage
   only the rest. If no team was given at all, run the script with any id to get the
   available list, and ask.
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

**When the tracker is `live`, run it as the `enrich-tracker` subagent. Never call a
tracker tool from this orchestrator.** A live run showed why: called inline, every
issue fetch and search rendered in the user's chat as a full ticket card, one per
related ticket, burying the stage lines under noise. Inside a subagent those calls
stay in its collapsed block and only the envelope comes back. It also keeps raw ticket
bodies out of this context, which the rest of the run does not need. The same holds for
every `live` source in Stage 3. `fixture` sources are local files and are read directly.

Where a client cannot delegate, make the calls in turn and say in one line that tool
output may appear in the conversation; correctness does not depend on the delegation.

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
2. **Report file.** Written to `<working folder>/<output.reports_dir>/<TICKET>.md`
   when `output.write_report` allows. Never inside the plugin, which is read-only once
   installed. Say where you wrote it.
3. **Tracker comment.** Generated as plain text. Never posted without explicit
   per-ticket confirmation in the conversation.
4. **Run trace.** Unless `output.run_trace` is `never`, write the structured result to
   `<working folder>/<reports_dir>/<TICKET>.result.json` in the shape defined in
   [`reference/run-visibility.md`](../../reference/run-visibility.md), then run:

       python3 <plugin root>/scripts/render_trace.py --out <working folder>/<reports_dir> \
           <working folder>/<reports_dir>/<TICKET>.result.json

   **Never hand-write the trace HTML.** The script renders it identically every run and
   refuses a non-defect that carries a priority. If it refuses, the result file is
   wrong: fix the result, not the script. With `artifact`, publish the rendered file
   where the client can publish; otherwise keep the file and say so. Default is `file`,
   because a trace carries customer names and account counts and publishing it is a
   disclosure decision. Never fail a triage over a presentation surface. In batch mode,
   render all tickets in one call.

Then append the audit record:

    python3 <plugin root>/scripts/triage_log.py \
        --log <working folder>/triage-logs/triage-log.jsonl \
        append --ticket <KEY> --team <team> \
        --disposition <d> [--priority <P>] --confidence <c> --modes <src=mode,...> \
        [--escalations ...] [--unanswered ...] [--source-errors ...] [--flags ...]

`append` refuses a non-defect carrying a priority. If it refuses, the pipeline made a
mistake: a disposition other than `defect` must never have reached scoring.

## Batch mode

Several ticket IDs: run each through the full pipeline, then emit one ranked table
ordered by priority then by deciding factor. Non-defects are listed in a separate
section with their disposition, not ranked among the defects.
