---
name: triage-auto
description: "Automatic, unattended triage for a team whose config turns it on (automation.enabled). Picks new, changed and overdue bugs, triages them without asking questions, and writes a review digest. Never writes to the tracker. Use when a scheduled task or a tracker event runs triage-auto, or when the user asks to run automatic triage now. Off by default: if the config does not enable it, say so and stop."
---

# Automatic triage

Runs the same pipeline as `skills/bug-triage`, for several tickets, with nobody
watching. Everything that makes a manual triage safe still holds, and two things are
stricter:

- **Nothing is written to the tracker.** No comment, no field change, no transition,
  not even with a confirmation step, because there is nobody to confirm. The output is
  a digest a person reviews.
- **Nothing is asked.** Where a manual run would stop and ask (which team, a missing
  ticket field, an ambiguous config), this run skips that ticket, records why, and
  moves on.

## 1. Is it on?

Resolve `<plugin root>` and `<working folder>` as in `skills/bug-triage` Setup step 0.
The first argument is the team or project; any further arguments are ticket keys (an
event-triggered run names the new tickets).

    python3 <plugin root>/scripts/auto_triage.py plan --dry-run --workdir <working folder> <team> [KEY ...]

- **Exit 3: automation is off for this team.** Print its message and stop. Do not
  triage anything, do not offer to triage manually instead. A scheduled job that
  outlived the config must do nothing.
- **Exit 4:** another automatic run holds the lock. Print the message and stop.
- **Exit 2:** the team could not be resolved. Stop; an unattended run never guesses.

## 2. What to triage

With a fixture tracker, or when ticket keys were given, run `plan` without
`--dry-run`. With a live tracker and no keys, first fetch the open bugs through the
`enrich-tracker` subagent exactly as `skills/triage-queue` does (the `open_bugs`
retrieval), write them to `<working folder>/<reports_dir>/auto/open.json`, then:

    python3 <plugin root>/scripts/auto_triage.py plan --workdir <working folder> <team> \
        --issues <working folder>/<reports_dir>/auto/open.json

It prints the tickets to triage and why each other one was skipped: already triaged and
unchanged, a skip label, outside the look-back window, or over `max_per_run`. Overdue
tickets (the queue's triage-within limits) come first. Print the chosen list in one
line and start.

## 3. Triage each ticket

Follow `skills/bug-triage` for each chosen ticket, as a batch: header once, then the
stages per ticket, the result file, the reports the team's `output.report_format`
asks for (HTML by default; markdown only when asked; nothing but the fix brief with
`agent`, for a pipeline that hands defects to a fix agent), the fix brief, and the
audit log entry. Add `--flags auto` to the `triage_log.py append` call, so the log separates
automatic runs from manual ones.

Differences from a manual run:

- Skip the tracker comment step entirely. Do not draft it into the chat either.
- If a stage would stop to ask, stop that ticket only and note `KEY=<reason>`.
- If workaround verification is enabled for the team, run it as the triage skill says.
  It points only at preview, staging or local, never production.

## 4. Digest

    python3 <plugin root>/scripts/auto_triage.py digest --workdir <working folder> <team> \
        --results <working folder>/<reports_dir>/<KEY>.result.json ... \
        [--failed KEY=<reason> ...]

It writes `<reports_dir>/auto/<date>-<team>.html`, the review page in the report's
look (plus `.md` when `report_format` is `md` or `both`; only `.md` for `md`), and
releases the lock. Agent mode still gets the page: an unattended run always leaves
something a person reviews. Print the markdown it outputs verbatim and point to the
page. That is the whole output of the run.

Before the digest, refresh the handoff index as `skills/bug-triage` describes
(`scripts/brief_index.py`). With `report_format: agent` this is how a fix pipeline
finds new work: it reads `<reports_dir>/briefs.json` and picks up only `ready` entries.
A ticket held for `human_review` stays held until a person records a review with
`triage-review`.

## Setting it up

Automation is switched on in the team config, never here:
`/bug-triage-agent:triage-config <team> automation`. That step also offers to create
the schedule where the host has a scheduler, or prints the command a CI job or
webhook handler runs.
