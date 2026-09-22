# Usage

## Invoking it

| Client | How |
| --- | --- |
| Claude, Cursor | `/triage BUG-4830 --team demo` |
| Codex, ChatGPT | Invoke the plugin or skill by name, then give it the ticket |

The commands are thin wrappers over the skills, so nothing is lost where they are not
loaded.

```
/triage BUG-4830 --team demo                      one ticket
/triage BUG-4830 BUG-4844 BUG-4851 --team demo    batch, returns a ranked table
/release-impact BUG-4830 --team demo              correlation only
/triage-doctor --team demo                        readiness check
/triage-review BUG-4844 voice_of_customer "..."   record a human override
```

## Reading the output

Full templates are in [`reference/output-templates.md`](../reference/output-templates.md).
Four parts are worth knowing how to read.

### The provenance line

```
Sources: tracker=live releases=live metrics=off warehouse=off code=error(timeout)
```

Appears on every output. A recommendation whose basis is invisible is not reviewable.
`off` is a choice; `error` is a failure and is never silently downgraded to `off`.

If any source is on fixtures, the whole output is prefixed `DEMO DATA`.

### The disposition block

Always carries evidence, and always names the runner-up:

```
Disposition: voice_of_customer (high)
  Evidence: BUG-3120 - closed works-as-designed
  Considered defect; ruled out because the system does what it was designed to do.
```

The runner-up line is what lets you correct the agent in one glance. A disposition with
an empty evidence list and a confidence above `low` is a bug in the agent.

**Non-defects get no priority at all.** If you see a priority on a
`voice_of_customer`, something has gone wrong.

### The arithmetic

```
Base: P3 (workaround exists, one account, blocks a task)
  +1 release: confirmed regression, v2026.09 matched
  +1 code:    error swallowing at ApprovalReviewService line 214
  (history signal present, not counted: cap reached)
Final: P2 -> tracker "Critical". Current: "Minor". Gap flagged.
```

Every escalation names its class. One escalation per class, capped at two levels, and
**P1 is never reached by escalation** — P1 requires meeting a P1 criterion directly.
If you cannot reconstruct the number from the output, report it.

### Unanswered questions

```
Unanswered: Q2 blast radius, Q4 regression, Q7 code signals, Q10 enterprise tier
Confidence: medium - capped by the unanswered regression question
```

This is the honest cost of switched-off sources. It lowers confidence. It does not
raise priority.

## What to do with the result

The agent produces text. **You apply it.** Nothing is written to the tracker without
per-ticket confirmation, and the field updates come as a checklist:

```
priority  -> Critical
labels    -> component:approvals, severity:p2
assignee  -> Approvals Team
```

## When you disagree

Use `/triage-review`. It records your correction **without altering the original
recommendation**, because the gap between the two is the entire measurement. Skipping
this costs you the only feedback loop the system has.

## When it refuses

| Output | Meaning |
| --- | --- |
| `insufficient_information` | Missing repro, component or error. It lists exactly what it needs |
| `P1 DETECTED` | A P1 criterion met directly. Enrichment skipped. Follow your incident process; the agent does not replace it |
| `no release in the window touched this area` | A real finding, not a failure. Points at data, config or a latent bug rather than a regression |
| `Workaround: none found. Searched: ...` | It looked and found nothing. Different from not looking |
