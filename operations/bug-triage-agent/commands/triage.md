---
description: Triage one or more bug tickets end to end
argument-hint: "<TICKET-ID> [TICKET-ID...] [--team <id>]  (team is found from the ticket's project when omitted)"
---

Load `skills/bug-triage/SKILL.md` and run the full pipeline for: $ARGUMENTS

Resolve the team first (from `--team`, else the tickets' project key, else the fallbacks
in the skill) and state which sources are live, fixture or off before producing any
recommendation.
