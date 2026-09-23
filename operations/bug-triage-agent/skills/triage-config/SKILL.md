---
name: triage-config
description: Create or update a team config for the bug triage agent by asking the user a short series of questions, discovering which connectors are available in the session, and writing a validated teams file into the team's own folder. Use when the user asks to set up triage for a team, configure the triage agent, onboard a new team, or when a triage run finds no config for the requested team.
---

# Triage config

Builds `<team-id>.json` by conversation instead of by hand. The result is the only
per-team file the agent reads; everything else is shared and is not asked about here.

The schema is [`teams/team-config.schema.json`](../../teams/team-config.schema.json).
Every key written must exist there. Do not invent keys, and do not copy rubric,
taxonomy or output rules into the file: those are shared on purpose.

Paths below marked `<plugin root>` and `<working folder>` are resolved exactly as in
`skills/bug-triage` Setup step 0. Resolve them first; never conclude the plugin's
scripts are missing because a relative path failed.

## Rules for the whole conversation

- **One topic per question.** Ask, wait, then move on. Where the host offers a
  structured question tool, use it with concrete options; otherwise ask in plain text
  and number the choices.
- **Discover before asking.** Anything that can be read from a connected tool (project
  keys, priority names, labels, components, tool names) is looked up first and offered
  as the default. Ask the user only to confirm or correct. People mistype identifiers;
  tools do not.
- **Never guess a tool name.** Bindings come only from tools found in this session. A
  source with no discoverable tool is written as `off` with a reason, never `live` with
  a guessed name. A wrong binding fails at triage time, far from the cause.
- **Never ask for credentials.** No tokens, passwords, keys or connection strings.
  Access comes from connectors the user has already authorised in the app. If a source
  needs one that is not connected, say which kind of connector to add and write the
  source as `off` until it is.
- **Read only.** Discovery calls read. Nothing is created, edited or commented on in
  any connected system while configuring.
- **Default to less.** An unknown answer becomes `off` or the schema default, not a
  plausible value. An `off` source lowers confidence honestly; a wrong one corrupts it.
- **Required answers are never defaulted. If the user skips one, stop.** Required:
  the team id, the tracker instance, the project key, the P1-P4 priority mapping, and
  where to write the file. For these, never offer "no preference", "you decide" or
  "skip" as an option. If the user gives one anyway, or declines, stop: say which
  answer is missing and why it cannot be guessed, write nothing, and tell them how to
  resume (`/bug-triage-agent:triage-config <team-id>`). Only optional answers
  (members, default flag, at-risk labels, routing, and whether a team has metrics,
  warehouse or code) may be skipped, and a skipped optional answer becomes `off` or is
  left out, never a guessed value.
- **Never derive an identity from unrelated signals.** Do not pick a team id, project
  or instance because something was "most recently updated", because it appears in a
  different tool (a chat workspace, another tracker, a design tool), or because it is
  the only one you happened to see. You may *suggest* a value discovered for the
  question being asked, such as the project the user just chose, but the user must
  confirm it.

## Changing one section

The arguments may name a section after the team id, for example
`triage-config demo-live code`. Then change only that section and leave every other
key exactly as it is:

| Word | Walks |
| --- | --- |
| `tracker` | Step 2 |
| `releases` | Step 3 |
| `metrics`, `warehouse`, `code` | That source in step 4 |
| `repo`, `vcs`, or the name of the user's code host or version-control product | Code in step 4 **and** the version-control adapters (`vcs_tag`, `vcs_pr`) in step 3, the two things a code host provides |
| `routing` | Step 5 |
| `output` | Step 6 |
| `members`, `default` | Those questions in step 1 |

Step 0 still runs first, to find the file. If the config exists only in the plugin,
copy it to the working folder as usual, then walk only the named section. Discover and
prove the tools for that section as in the full flow, then go to step 7: show the diff
of what changed, not the whole file, and write only on a yes. An unknown section word
stops with this list.

## Step 0: where the file goes, and whether it exists

Take the team id from the argument, else ask for it: lowercase, letters, digits and
hyphens. It is a name the user chooses, not something to infer, so ask it as an open
question. If they want a suggestion, offer the lowercase project key *after* step 2
picks the project, and wait for them to confirm. If they decline to name one, stop as
the rules above say. Then run:

    python3 <plugin root>/scripts/run_header.py --workdir <working folder> --team <id> --where

- **Found in the working folder or config dir:** this is an update. Load it, show a
  short summary of what it sets, and ask which sections to change. Only walk those.
- **Found only in the plugin:** it is a shipped example. Offer to copy it as the
  starting point for a team-owned file, never to edit it in place: the plugin's copy is
  read-only once installed and is replaced on every update.
- **Not found:** a new config.

Ask where to write, offering in this order:

1. `triage-teams/<id>.json` in the working folder. **Default.** Committed to the team's
   own repository, reviewed like code.
2. `$CLAUDE_TRIAGE_CONFIG_DIR/<id>.json`, when that variable is set.

Never offer the plugin's own `teams/` directory.

## Step 1: team

`team.id` (fixed from step 0) and `team.name`, a readable label.

Then two optional questions, both about choosing this team when nobody names it:

- **Members.** Who triages for this team? Offer to list exact addresses, a whole
  domain as `*@example.com`, or skip. Written to `team.members`. Only used when there
  is no ticket to read a project key from, such as the queue. Offer the signed-in
  user's own address as the first entry only if the host already shows it; never ask
  for an address just to fill this in.
- **Default.** Should this be the default team in this folder? Written as
  `team.default: true`. Only one config per folder should say so.

A ticket's project key always decides first. These only matter without one.

## Step 2: tracker (required)

The tracker is the one source that cannot be `off`. Without it there is no triage, so
if no tracker connector is available, stop here and say which kind to connect.

1. Find tracker tools in the session: search for tools that fetch an issue and that
   search issues. Record the exact suffixes for `tool_bindings.tracker.get_issue` and
   `tool_bindings.tracker.search_issues`. If more than one server offers them, ask
   which one this team uses.
2. Use the connector's own listing to find the instance: its identifier becomes
   `tracker.instance_id`, its hostname `tracker.host`. If several are accessible, ask.
3. List the projects visible there and ask which one. That is `tracker.project_key`.
4. **Prove it:** fetch one issue from that project. If the fetch fails, say why and
   fix the answer before going further. A config that cannot read one ticket is not a
   config.
5. Read the project's priority values and propose the `P1`…`P4` mapping, highest
   first. Ask the user to confirm; teams sometimes skip or reserve a level.
6. Ask whether the project uses components. If it does not, ask what the team uses
   instead. When it is a label prefix, offer the prefix seen on recent issues (e.g.
   `component-`) and write it as `tracker.component_label_prefix`, so history and
   duplicate searches stay area-scoped rather than project-wide, and the queue can
   show each bug's area.
7. `tracker.at_risk_labels`: offer the labels actually present on recent issues and
   ask which mark an at-risk or renewal account. These trigger the P2 floor, so an
   over-broad label inflates priorities.
8. `tracker.voc_destination`: where voice-of-customer items go. A project key, a
   board, or `none`. Explain in one line that a disposition with nowhere to go is
   useless.

Set `sources.tracker.mode` to `live`.

## Step 3: releases

Ask how this team records what shipped, and offer only the adapters that can work
with what is connected:

| Adapter | Needs |
| --- | --- |
| `tracker_fixversion` | Fix versions on tickets. Uses the tracker binding |
| `wiki_release_notes` | A wiki connector, a space key, a page label, a title pattern |
| `vcs_tag`, `vcs_pr` | A version-control connector, the org, the repos, a tag pattern. The only adapters with file-level detail |
| `manual_file` | A releases file maintained by hand, for teams with no queryable record |

Write `release_correlation.manifest_sources` in the order the user ranks them. Ask
the release cadence in days (default 30) and set `lookback_days` to at least twice
that; the validator warns below two cycles.

## Step 4: metrics, warehouse, code (each optional)

For each, one question first: does this team have it? If not, write `off` with a
reason in `//` and move on without further questions.

If yes, search the session for matching tools and propose bindings:

| Source | Binding keys | Then ask |
| --- | --- | --- |
| metrics | `metrics_query`, `logs_search`, `deploy_events`, optional `runtime_logs` | The log store's data source and the queries to use (error rate, deploys, expected heartbeats), and optionally a hosting platform for deploys and runtime logs (`sources.metrics.deploys`). Keys may be served by different providers |
| warehouse | `query` | Database and schema, then the query template (below) |
| code | `search`, plus `get_file` (and `list_files` if offered) when the host can read files | Which repos, what each holds, `key_paths` to narrow search and to bound the file-read fallback |

If a binding cannot be found, the source is `off` and the reason says which connector
to add. Do not write a partial binding.

**Prove code search against the team's own repo.** Search for a string you have just
read from a file in `key_paths`. If search returns nothing but `get_file` reads the
file, bind both and say that triage will use the file-read fallback until search
works. If neither works, write code as `off`.

**Warehouse query template.** Ask what table records account activity and how an
affected account and an enterprise account are identified. Draft one template named
`affected_accounts_core` from the answers, show it, and ask the user to confirm or
edit. It must start with `SELECT` or `WITH` and contain no write verb; the validator
enforces both. Never run it against the warehouse during setup beyond one
`LIMIT 1` probe, and only after the user confirms the text.

## Step 5: routing

Ask which team owns each component or area label found in step 2. Write
`routing.<component>: <team>`. Unknown owners are left out, not guessed.

## Step 6: output

- `output.reports_dir`: default `triage-reports`.
- `output.write_report`: default `always`.
- `output.run_trace`: default `file`. Offer `artifact` only after saying plainly that
  a trace contains customer names and account counts, and that `artifact` publishes it
  to a hosted page. Recommend `file` for any tracker with real customer tickets.

## Step 7: preview, write, validate

1. Show the complete file in a code block, and a one-line summary: sources live, off,
   and why.
2. Ask for confirmation before writing. This writes into the user's folder, so it gets
   the same yes-first treatment as anything else the agent writes.
3. Write it to the path chosen in step 0.
4. Run `python3 <plugin root>/scripts/validate_config.py <path>`. On an error, explain it in plain
   words, fix the answer that caused it, and re-run until it passes. Do not hand back
   a file that fails validation.
5. Run `python3 <plugin root>/scripts/run_header.py --workdir <working folder> --team <id> --where` to confirm the triage agent
   now resolves this file and not another one of the same id.

Finish by suggesting the next two commands:

    /bug-triage-agent:triage-doctor <id>
    /bug-triage-agent:triage <TICKET> --team <id>

and remind the user to commit `triage-teams/<id>.json` so the rest of the team gets it.

## When triage calls this

A triage run that cannot resolve its team offers this skill instead of stopping cold.
Run it, then return to the triage the user asked for with the new config, without
asking them to repeat the ticket ids.
