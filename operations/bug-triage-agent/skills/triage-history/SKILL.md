---
name: triage-history
description: "Show the bug triage agent's audit log: recent triage decisions, one ticket's triage history, and how often people agreed with the agent. Use when the user asks what was triaged, the triage log or history, what the agent decided for a ticket, or how accurate the triage agent has been. Also use it when the whole request is just log, history or accuracy. Show it straight away."
---

# Show triage history and accuracy

The `/triage-log` command is a thin wrapper over this skill. Clients that load skills but
not commands reach it by name.

Read-only. Show the audit log for: the user's request

Resolve `<plugin root>` and `<working folder>` as in `skills/bug-triage` Setup step 0.
The log lives in the working folder, never in the plugin.

Arguments may be plain words, because some hosts reject a command whose first argument
is a flag: a ticket id becomes `--ticket`, a team id becomes `--team`, and the word
`accuracy` means the same as `--accuracy`, `calibrate` runs the calibration review and
`dashboard` writes the accuracy page.

Recent decisions, newest first:

    python3 <plugin root>/scripts/triage_log.py \
        --log <working folder>/triage-logs/triage-log.jsonl \
        list [--ticket <KEY>] [--days N] [--team <id>] [--limit N]

With `accuracy` or `--accuracy`, or when the user asks how accurate the agent has been, run
instead:

    python3 <plugin root>/scripts/triage_log.py \
        --log <working folder>/triage-logs/triage-log.jsonl report --days <N, default 30>

With `calibrate`, or when the user asks what to change or why the agent keeps getting
something wrong:

    python3 <plugin root>/scripts/triage_log.py \
        --log <working folder>/triage-logs/triage-log.jsonl calibrate --days <N, default 90> \
        [--team <id>] [--min-overrides <calibration.min_overrides>] [--min-rate <calibration.min_rate>]

It lists repeated override patterns with the change each suggests. Suggestions only:
never edit the rubric, the taxonomy or a config from here. Offer the config ones through
`/bug-triage-agent:triage-config`, and the rubric ones as a proposed change for review.

With `dashboard`, or when the log holds more than a screen of runs and the user wants
the accuracy picture, write the tabbed page (overview, dispositions, priority, trend,
calibration, runs):

    python3 <plugin root>/scripts/triage_log.py \
        --log <working folder>/triage-logs/triage-log.jsonl dashboard \
        --out <working folder>/triage-reports/accuracy.html [--days N] [--team <id>]

Say where it was written. It carries ticket keys and reviewers' override reasons, so
publish it only if the user asks.

Print the output **verbatim, as markdown, not in a code block**: the table carries the
same colour markers as the triage output. Do not summarise it or add rows. If the log
does not exist yet, say so plainly: nothing has been triaged from this folder.

To record a correction, use the `triage-override` skill (`/triage-review` where the
client loads commands).
