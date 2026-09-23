---
name: bug-triage
description: "Triage a bug ticket end to end. Disposition first, then release correlation, workaround discovery and priority scoring, with an audit log entry. Use when the user asks to triage a ticket, prioritize bugs, analyse a tracker bug, or asks what priority a bug should be. Triggers include \"triage ABC-1234\", \"priorizá estos bugs\", \"qué prioridad tiene\", \"is this a bug or expected behavior\", \"which release broke this\". A bare ticket key is a request to triage it. A bare word routes to its skill without asking - queue to triage-queue, log to triage-history, doctor to triage-readiness, config to triage-config, review to triage-override, auto to triage-auto."
---

# Bug triage

Orchestrator. Loads the shared rubric, resolves the team config, runs the stages in
order.

## Commands and skills

Every command is a thin wrapper over a skill, so a client that loads skills but not
commands loses nothing. Where this plugin tells the user to run a command, name the
skill instead on such a client.

| Command | Skill |
| --- | --- |
| `/triage` | `bug-triage` |
| `/queue` | `triage-queue` |
| `/triage-config` | `triage-config` |
| `/triage-doctor` | `triage-readiness` |
| `/triage-log` | `triage-history` |
| `/triage-review` | `triage-override` |
| `/release-impact` | `release-correlation` |
| `/triage-auto` | `triage-auto` |

## Setup

0. **Find the plugin and the user's folder.** Every `scripts/…`, `reference/…`,
   `skills/…` and `teams/…` path in this plugin is relative to the plugin root, not to
   the shell's current directory. The base directory this skill was loaded from is
   often a host path the shell cannot see (a sandboxed shell mounts the plugin
   elsewhere), so resolve the root once with this, and never conclude the plugin's
   files are missing until it has run:

   ```bash
   for c in "${CLAUDE_PLUGIN_ROOT:-}" "${PLUGIN_ROOT:-}" "<this skill's base directory>/../.."; do
     [ -n "$c" ] && [ -f "$c/scripts/run_header.py" ] && { cd "$c" && pwd; exit 0; }
   done
   for d in /sessions "$HOME" /var/folders /tmp; do
     [ -d "$d" ] && find "$d" -maxdepth 9 -path '*/scripts/run_header.py' 2>/dev/null
   done | xargs grep -l 'Print the run header for a triage' 2>/dev/null \
        | grep -E '/(\.remote-plugins|claude-hostloop-plugins|\.claude/plugins|\.cursor/plugins|\.codex/plugins|\.agents/plugins)/' \
        | head -1 | sed 's#/scripts/run_header.py$##'
   ```

   The first line covers every client that tells the skill where it was loaded from.
   The search is the fallback, and knows the install folders of Cowork, Claude Code,
   Cursor and Codex. It prefers the installed plugin. If it prints nothing but a search without the
   final `grep -E` finds a copy in a source checkout, say so and ask before using it:
   a checkout may hold unreleased code.

   The **working folder** is the folder the user is working in: the one they opened or
   connected, not the shell's start directory. Reports, traces, the audit log and the
   team's own `triage-teams/` all live there. If you cannot tell, ask.

   Shell state may not persist between commands, so write both resolved paths out
   literally in every later command rather than relying on a variable.

1. **Header first, before reading anything else.** `--team` is optional. Run:

       python3 <plugin root>/scripts/run_header.py --format md --workdir <working folder> \
           [--team <id>] [--user-email <signed-in user's email>] <TICKET> [<TICKET>...]

   Pass `--team` only if the user gave one. Pass `--user-email` only if the host already
   tells you who is signed in; never ask the user for it just for this, and never write
   it into a report, trace or log. The script chooses the team in this order and the
   header says which rule decided: `--team`; `CLAUDE_TRIAGE_TEAM`; **the tickets'
   project key**, matched against `tracker.project_key`; the email against
   `team.members`; a default or lone config in the working folder; the plugin's `demo` default. If none decides, it stops.
   Configs still holding placeholder values are never chosen implicitly.

   Print its output **verbatim as markdown, not inside a code block**, as your first
   message text. A code block renders in monospace with no colour, which strips the
   source markers the header exists to show. Do not paraphrase, shorten or summarise
   it: the host collapses command output, so a reader sees the header only if you
   repeat it. (Use `--format text` only where the output is a terminal, not a chat.)

   **The header is the first thing the reader sees.** Before it, only the two commands
   that produce it: the locator in step 0 and this one. No narration ("delegating
   to…"), no subagent, no other tool call, no published page. A header that arrives
   after the work has started has told the reader nothing they could act on.

   The script looks for the team in the config dir, then `triage-teams/` in the
   working folder (and one or two levels below it), then the configs shipped in the
   plugin. The header names the config file it loaded and the agent version and root
   it ran from, so a stale install or a wrong copy is visible on the first line.

   **Exit code 2 means it could not choose a team safely**: no config for the project,
   tickets from two projects, or two equally good candidates. Show what it printed,
   then offer two choices: run `skills/triage-config` to create one now, or name one of
   the listed ids with `--team`.
   Never pick one silently, and never improvise a config inline: an untested config
   produces an untested triage. If the user creates one, resume this triage with the
   same tickets without asking for them again.

   Exit code 3 means a ticket has no fixture in fixture mode: say which, and triage
   only the rest.

   **Connected but off.** Right after printing the header, for each source the header
   shows as `off`, look in the session for tools that could serve it: for metrics, log
   or metric query tools; for warehouse, SQL query tools; for code, code or repository
   search tools. If any exist, add **one line** under the header naming the connector
   and the source, for example:

   > **Available but off:** a metrics connector is connected in this session, but
   > metrics is off for team `demo-live`. To use it: `/bug-triage-agent:triage-config demo-live`.

   This is a suggestion only. **Never use a connector the team config does not bind**,
   not even for this run: the config is the team's decision about what its triage
   reads, and results must not change with whoever happens to be signed in. Do not
   guess tool names for it either; binding happens in `triage-config`, which proves
   each one. Skip the check when nothing is `off`, and never delay the header for it.
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
6. **Live progress.** Where the host offers task tools, create the stage tasks right
   after the header, exactly as `reference/run-visibility.md` lists them, then drive
   them as the run moves: mark a stage in progress *before* starting it, and when it
   finishes rewrite its title to carry the result (`Stage 4 · priority → 🟠 P2 ·
   ●●○ medium`) and mark it complete. This is the one surface that updates in place,
   so the reader sees where the run is without scrolling. Where the host has no task
   tools, skip this: the stage lines are the record in every client.

## Narrating the run

The host draws every command as a bare row with no explanation, and long thinking
gaps show only a timer. A reader watching that learns nothing. So:

- **Read reference and fixture files with the file-read tool, not a shell command.**
  A file read shows the file name; `cat` in a shell shows only "Bash".
- **Where the shell tool accepts a description, give every command one** in plain
  words: "Validating team config", not the command itself.
- **Write the stage line as message text between tool calls**, the moment the stage
  completes, in the markdown format from `reference/run-visibility.md`, with its
  colour markers and never in a code block. Text between calls is what the reader
  sees; tool output is collapsed.
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

Run `skills/triage-disposition` against the Stage 1 envelopes. Its duplicate check is
scored by script, not by eye: write the tracker envelope to
`<working folder>/<reports_dir>/<TICKET>.tracker.json` and run

    python3 <plugin root>/scripts/dupes.py --tracker <that file> --links-config <resolved team config>

Put its output in the result file as `duplicate_check`. Call a ticket `duplicate` only
when a candidate scored `duplicate`; a `recurrence` is the same failure coming back
after a fix, which is a defect with a prior fix, not a duplicate to close.

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

**Workaround verification**, only when the team config has `verification.enabled:
true` and a workaround was found. Write `<reports_dir>/<TICKET>.scenario.json` from the
ticket's reproduction steps and the workaround (shape in `scripts/verify_workaround.py`),
using only paths and values the ticket or the evidence states. Then:

    python3 <plugin root>/scripts/verify_workaround.py run --team-config <resolved team config> \
        --scenario <scenario file> --result <result file, once written in Stage 5>

For the `ci` runner, dispatch the workflow through `tool_bindings.verification.dispatch`
in a subagent, wait for its outcome, and record it with `verify_workaround.py record`.
A workaround that fails verification is reported as not working, and does not count as
practical for the rubric. `not_reproduced` proves nothing either way: say so. When
verification is off, say nothing about it.

**Timeline.** From the envelopes already gathered, keep the events with timestamps: the
release or deploy, the error rise and first error from metrics, the ticket's creation.
Record them as `timeline`, and the metrics envelope's bucketed counts as `series`
(shapes in `reference/run-visibility.md`). Only what a source returned; never
interpolate a point or an event.

## Stage 4: classify



Apply `reference/priority-rubric.md`. Answer the ten questions in order. Mark any
question whose source was unavailable as unanswered; do not infer it.

Apply escalation signals with the one-per-class rule and the two-level cap. Apply the
at-risk P2 floor before the cap. Compute confidence from the stated table.

Apply the degradation rules in the data-sources skill. Round up only when the ticket
itself reports multi-account or systemic symptoms, never merely because a connector is
switched off.

## Stage 5: output and log

These surfaces, all defined in [`reference/output-templates.md`](../../reference/output-templates.md).
**If a result file for this ticket already exists, archive it first,** so the report
can say what changed since the last triage:

    python3 <plugin root>/scripts/history.py archive <working folder>/<reports_dir>/<TICKET>.result.json

When the verdict changed, set `why_changed` in the new result to one sentence saying
what made the difference (a source that came online, new evidence, an override).

**Write the result file first:** `<working folder>/<reports_dir>/<TICKET>.result.json`,
in the shape defined in [`reference/run-visibility.md`](../../reference/run-visibility.md).
The report, the trace and the fix brief are all rendered from it by scripts, so they
agree. Record for each source when it was read (`as_of`), and for metrics the oldest
data point used (`data_from`) and how long the source keeps data (`retention_days`),
so stale evidence is flagged. Set `deciding_factor` to the one reason that decided the
verdict, in a sentence.

1. **Chat summary.** Always. Start with the same three lines the report opens with
   (verdict, why, do now), then the "Supported by" line with its links, one line of
   arithmetic, and a pointer to the report. Ten seconds to read.
2. **Report file.** When `output.write_report` allows, render it:

       python3 <plugin root>/scripts/render_report.py --out <working folder>/<reports_dir> \
           --team-config <resolved team config> <working folder>/<reports_dir>/<TICKET>.result.json

   **Never hand-write the report.** It is written to `<reports_dir>/<TICKET>.md`, never
   inside the plugin. Say where you wrote it.
3. **Tracker comment.** Generated as plain text. Never posted without explicit
   per-ticket confirmation in the conversation.
4. **Run trace.** Unless `output.run_trace` is `never`, render it from the result file:

       python3 <plugin root>/scripts/render_trace.py --out <working folder>/<reports_dir> \
           --team-config <resolved team config> <working folder>/<reports_dir>/<TICKET>.result.json

   **Evidence links.** Put the URL a tool returned beside each piece of evidence in the
   result (`url` on `locations`, `disposition_evidence`, `prior_fixes`, `release`;
   `sha` on `introduced_by`; a top-level `links` list of `{label, kind, text, source,
   url}` for things like a log query or a deployment). Take URLs only from tool
   results: a ticket's web URL, a commit's or release's html URL, a deployment's page,
   a log store's deep link. `--team-config` fills the rest from the config's `links`
   templates. Never construct or guess a URL yourself.

   **Never hand-write the trace HTML.** The script renders it identically every run and
   refuses a non-defect that carries a priority. If it refuses, the result file is
   wrong: fix the result, not the script. With `artifact`, publish the rendered file
   where the client can publish; otherwise keep the file and say so. Default is `file`,
   because a trace carries customer names and account counts and publishing it is a
   disclosure decision. Never fail a triage over a presentation surface. In batch mode,
   render all tickets in one call.

5. **Fix brief (defects only).** Add the fix fields to the result file (`repo`,
   `repro`, `locations`, `hypothesis`, `introduced_by`, `prior_fixes`, shapes in
   [`reference/run-visibility.md`](../../reference/run-visibility.md)), then run:

       python3 <plugin root>/scripts/render_fix_brief.py --out <working folder>/<reports_dir> \
           --team-config <resolved team config> <working folder>/<reports_dir>/<TICKET>.result.json

   It writes `<TICKET>.fix-brief.md`, a hand-off a coding agent can act on, and refuses
   a non-defect. Fill `locations` only with what the run actually found, each with its
   `signal` and `source`: a file seen in a release record but not in code search is
   `release_touched`, never `error_swallowing`. The evidence verdict is computed from
   these, so an inflated location becomes an inflated verdict. `repo.base_branch` comes
   from `repos[].default_branch` in the team config, else `main`.

   Never open a branch, write code or raise a pull request from this skill. The brief
   is the hand-off; fixing is another agent's job.

Then append the audit record:

    python3 <plugin root>/scripts/triage_log.py \
        --log <working folder>/triage-logs/triage-log.jsonl \
        append --ticket <KEY> --team <team> \
        --disposition <d> [--priority <P>] --confidence <c> --modes <src=mode,...> \
        [--escalations ...] [--unanswered ...] [--source-errors ...] [--flags ...] \
        [--area <component>]

Pass `--area` whenever the ticket has a component: calibration uses it to see whether
overrides cluster in one area.

`append` refuses a non-defect carrying a priority. If it refuses, the pipeline made a
mistake: a disposition other than `defect` must never have reached scoring.

## Batch mode

Several ticket IDs: run each through the full pipeline, then emit one ranked table
ordered by priority then by deciding factor. Non-defects are listed in a separate
section with their disposition, not ranked among the defects.
