---
description: Record a human override of a triage recommendation, for calibration
argument-hint: <TICKET-ID> <correct-disposition-or-priority> [reason]
---

Resolve `<plugin root>` and `<working folder>` as in `skills/bug-triage` Setup step 0,
then record the override for: $ARGUMENTS

    python3 <plugin root>/scripts/triage_log.py \
        --log <working folder>/triage-logs/triage-log.jsonl \
        override --ticket <KEY> [--disposition <d>] [--priority <P>] --reason "<why>"

Use the script; never edit the log file by hand. It sets the override fields and leaves
the original recommendation untouched: the gap between recommended and final is the
measurement.

Then report the running accuracy:

    python3 <plugin root>/scripts/triage_log.py \
        --log <working folder>/triage-logs/triage-log.jsonl report --days 30

It reports disposition agreement per class and priority agreement within one level,
separately. Unreviewed runs measure volume, not correctness.
