---
name: triage-priority
description: Assign P1 to P4 with escalation caps and a stated confidence basis, for tickets already dispositioned as defects. Use after the disposition gate, never before it.
---

# Priority

Read `<plugin root>/reference/priority-rubric.md`. That file holds the criteria, the ten questions,
the escalation table, the class rule, the cap, and the confidence table. It is shared
and must not be edited per team.

This file is the procedure.

1. Confirm the disposition is `defect`. If not, stop and return to the orchestrator.
2. Check the P1 criteria directly. P1 is never reached by escalation.
3. Answer the ten questions in order using the enrichment envelopes. Mark unanswered
   any question whose source returned `unavailable` or `error`.
4. Set a base level from the criteria table.
5. Collect escalation signals. Group by class. **One escalation per class.** Total cap
   is two levels. Apply the at-risk P2 floor before the cap.
6. Compute confidence from the table. Write the basis in one line.
7. Map to the team's tracker priority name via `tracker.priority_names`. Compare against the
   ticket's current priority and flag a gap if they differ.
8. Route via `routing[component]`.

## Report the arithmetic

Show base level, each escalation with its class, the cap if it bound, and the final
level. A reviewer who cannot reconstruct the number will not trust the next one.

```
Base: P3 (workaround exists, single account, blocks a task)
  +1 release: confirmed regression, v2026.09 matched
  +1 code:    error swallowing at ApprovalReviewService line 89
  (history signal present, not counted: cap reached)
Final: P2 -> tracker "Critical". Current: "Minor". Gap flagged.
```
