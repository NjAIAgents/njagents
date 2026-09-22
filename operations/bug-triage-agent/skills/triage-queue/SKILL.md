---
name: triage-queue
description: "List the open bugs in the team's connected tracker, show which the triage agent has already handled and what it decided, flag priority gaps and tickets that changed since their last triage, and suggest what to triage next. Use when the user asks for the bug queue, the backlog of untriaged bugs, what is pending, what needs triage, or what to look at next. Also use it when the whole request is just the word queue, as in invoking the bug-triage-agent plugin with queue. Show the queue straight away for the resolved team; do not ask what the user wants to do with it."
---

# Triage queue

When invoked, run it. A request that is only the word "queue", with or without a
team or project, means show the queue now. Do not reply with a menu of options.

Answers "what should I triage next", where triage answers "what is this ticket".
Read-only: it never triages, comments on, or changes a ticket. It suggests the next
command and stops.

## Setup

Resolve `<plugin root>` and `<working folder>` exactly as in `skills/bug-triage`
Setup step 0. The team is optional, and may be given as a plain word: a team id
(`demo-live`) or a project key (`DEMO`). `--team <id>` also works. Pass the word
straight through to both scripts. Without one, with no ticket to read a project key from, the team
comes from `CLAUDE_TRIAGE_TEAM`, the signed-in user's email against `team.members`
(pass `--user-email` only if the host already tells you who is signed in), a default
or lone config in the working folder. If none decides, it stops and asks. Confirm it resolves:

    python3 <plugin root>/scripts/run_header.py --workdir <working folder> [<team or project>] \
        [--user-email <email>] --where

If it exits 2, it could not choose a team: show why and offer `/bug-triage-agent:triage-config <id>` and
stop. Never list bugs from a project the user did not configure.

## Fetch the open bugs

**Fixture tracker:** skip this step. The renderer reads the recorded tickets itself.

**Live tracker:** fetch the list in the `enrich-tracker` subagent, never from this
skill directly. Called inline, the tracker connector renders every result as a ticket
card, and a queue of twenty bugs becomes twenty cards. Ask the subagent for the
`open_bugs` retrieval defined in `skills/data-sources/SKILL.md` and to return **only**
a JSON list, no prose:

```json
[{"key": "", "summary": "", "status": "", "priority": "", "component": "",
  "labels": [], "created": "", "updated": ""}]
```

Write it to a file in the working folder, e.g. `<working folder>/triage-reports/queue.json`.

## Render

    python3 <plugin root>/scripts/render_queue.py --workdir <working folder> \
        [<team or project>] [--user-email <email>] [--issues <working folder>/triage-reports/queue.json] \
        [--limit N] [--untriaged-only]

Print its output **verbatim**. Do not re-sort, summarise or annotate the table: the
order is the recommendation (untriaged first, at-risk first within that, then oldest),
and the script produces it identically every time.

It cross-references the audit log in `<working folder>/triage-logs/`, so a ticket
shows as triaged only if this agent actually triaged it and logged the result. A
ticket triaged by hand, or by a run whose log was lost, shows as not triaged. That is
the honest reading: the queue reports what the agent knows, not what it assumes.

## After the table

Stop. Offer the suggested triage command the script printed, and let the user run it.
Do not start a triage on your own, and do not post anything to the tracker.

Arguments: `--team <id>`, `--limit N` (default 25), `--untriaged-only`.
