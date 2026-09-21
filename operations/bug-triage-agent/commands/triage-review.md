---
description: Record a human override of a triage recommendation, for calibration
argument-hint: <TICKET-ID> <correct-disposition-or-priority> [reason]
---

Update the matching line in `logs/triage-log.jsonl` for: $ARGUMENTS

Set `human_override` and `override_reason`. Do not alter the original recommendation
fields: the gap between recommended and final is the measurement.

Then report the running accuracy over the last 30 days: disposition accuracy and
priority accuracy within one level, counted separately.
