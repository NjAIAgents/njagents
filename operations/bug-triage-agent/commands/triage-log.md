---
description: Show recent triage decisions and how often people agreed with them
argument-hint: "[TICKET-ID] [--days N] [--team <id>] [--limit N] [--accuracy]"
---

Read-only. Show the audit log for: $ARGUMENTS

Resolve `<plugin root>` and `<working folder>` as in `skills/bug-triage` Setup step 0.
The log lives in the working folder, never in the plugin.

Recent decisions, newest first (a bare ticket id in the arguments becomes `--ticket`):

    python3 <plugin root>/scripts/triage_log.py \
        --log <working folder>/triage-logs/triage-log.jsonl \
        list [--ticket <KEY>] [--days N] [--team <id>] [--limit N]

With `--accuracy`, or when the user asks how accurate the agent has been, run
instead:

    python3 <plugin root>/scripts/triage_log.py \
        --log <working folder>/triage-logs/triage-log.jsonl report --days <N, default 30>

Print the output **verbatim, as markdown, not in a code block**: the table carries the
same colour markers as the triage output. Do not summarise it or add rows. If the log
does not exist yet, say so plainly: nothing has been triaged from this folder.

To record a correction, point the user at `/bug-triage-agent:triage-review`.
