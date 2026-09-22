---
name: triage-override
description: "Record a human override of a bug triage recommendation, with the reason, so the agent's accuracy can be measured and the rubric calibrated. Use when the user disagrees with a triage result, says a ticket's disposition or priority should be something else, or wants to log a correction. Also use it when the request starts with review or override followed by a ticket."
---

# Record a triage override

The `/triage-review` command is a thin wrapper over this skill. Clients that load skills but
not commands reach it by name.

Resolve `<plugin root>` and `<working folder>` as in `skills/bug-triage` Setup step 0,
then record the override for: the user's request

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
