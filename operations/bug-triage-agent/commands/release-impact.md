---
description: Show which recent release most likely touched a bug's affected area
argument-hint: "<TICKET-ID> | <component> [--team <id>]"
---

Load `skills/data-sources/SKILL.md` and `skills/release-correlation/SKILL.md`.

Report the candidate releases for: $ARGUMENTS

Report honest negatives. If no release in the lookback window touched the area, say so
rather than naming the nearest release by date.
