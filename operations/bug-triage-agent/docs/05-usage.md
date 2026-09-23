# Usage

## Invoking it

| Client | How |
| --- | --- |
| Claude, Cursor | `/triage BUG-4830` (fixture demo) or `/triage DEMO-7` (live demo) |
| Codex, ChatGPT | Invoke the plugin, then say what you want in a sentence |

### Per client

| Want | Cowork, Claude Code | Cursor | Codex, ChatGPT desktop |
| --- | --- | --- | --- |
| Triage | `/bug-triage-agent:triage BUG-4830` | `/triage BUG-4830` | `@bug-triage-agent triage BUG-4830` |
| Bug queue | `/bug-triage-agent:queue demo-live` | `/queue demo-live` | `@bug-triage-agent show the bug queue for demo-live` |
| Set up a team | `/bug-triage-agent:triage-config payments` | `/triage-config payments` | `@bug-triage-agent set up triage for team payments` |
| Readiness check | `/bug-triage-agent:triage-doctor payments` | `/triage-doctor payments` | `@bug-triage-agent check the triage setup for payments` |
| Log and accuracy | `/bug-triage-agent:triage-log accuracy` | `/triage-log accuracy` | `@bug-triage-agent show the triage log` |
| Automatic triage (config must enable it) | `/bug-triage-agent:triage-auto demo-live` | `/triage-auto demo-live` | `@bug-triage-agent run automatic triage for demo-live` |
| Record an override | `/bug-triage-agent:triage-review DEMO-8 voice_of_customer "reason"` | `/triage-review …` | `@bug-triage-agent record an override for DEMO-8: voice_of_customer, because …` |

Where commands are not loaded (Codex, ChatGPT), every command has a skill behind it
(`bug-triage`, `triage-queue`, `triage-config`, `triage-readiness`, `triage-history`,
`triage-override`, `release-correlation`), so nothing is lost. Say what you want in a
sentence rather than a single word: "show the bug queue for demo-live" is routed
reliably, a bare "queue" may get a clarifying question back.

The plugin runs Python scripts for the header, queue, trace, fix brief and log, so the
client needs a shell. Cowork, Claude Code and Cursor have one and are tested. Codex needs
a Codex task with a local folder, not a regular ChatGPT chat, and is not yet run end to
end. If a client cannot run scripts, the run stops at its first step rather
than improvising the output.

The commands are thin wrappers over the skills, so nothing is lost where they are not
loaded.

```
/triage BUG-4830                                  fixture demo, needs no connectors
/triage DEMO-7                                    one ticket; team found from the project key
/triage DEMO-7 DEMO-8 DEMO-9                      batch, returns a ranked table
/release-impact DEMO-7                            correlation only
/queue demo-live                                  open bugs, what still needs triage
/triage-config payments                           create or update a team config
/triage-doctor demo-live                          readiness check
/triage-review DEMO-8 voice_of_customer "..."     record a human override
/triage-log                                       recent decisions, newest first
/triage-log DEMO-7                                one ticket's history
/triage-log accuracy                              how often people agreed, per class
/triage-log calibrate                             repeated overrides and what to change
/triage-log dashboard                             accuracy page with tabs
/triage-auto demo-live                            automatic triage, when the config turns it on
```

## Three outputs, not one

| Surface | When | Where |
| --- | --- | --- |
| Chat summary | always | in the conversation |
| Report file | per `output.write_report` | `triage-reports/<TICKET>.md` |
| Tracker comment | generated, never posted | shown for you to paste |

The report is the one to share. It carries the evidence, the priority arithmetic step
by step, the release correlation with its confidence, and a coverage table. The chat
summary is deliberately thin so you can scan a batch.

The tracker comment is plain text rather than markdown, because trackers render their
own markup and a pasted markdown table becomes a wall of pipes.

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
  +1 code:    error swallowing at ApprovalReviewService line 89
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

## What else the report shows

| Section | When | What it tells you |
| --- | --- | --- |
| **Since the last triage** | The ticket was triaged before | What changed: priority, evidence, sources, workaround state, and why |
| **Duplicate check** | Always, when candidates were found | Each candidate scored on error text, symptom, stack, endpoint, file, area and release. A title match alone is never a duplicate. `recurrence` means the same failure came back after a fix |
| **Timeline** | A release, deploy or error rise has a timestamp | Deploy, error rise, ticket, triage in order with the gaps between them; a chart in the trace, a sparkline in the report |
| **Workaround verified** | The team turned on verification | Whether the workaround worked in preview, staging or local, and where |

## Automatic triage

Off unless the team config turns it on. When on:

```
/bug-triage-agent:triage-auto demo-live
```

picks new, changed and overdue bugs (up to `max_per_run`), triages them without asking
anything, and writes `triage-reports/auto/<date>-<team>.md`: one row per ticket with the
verdict and what to do. **Nothing is written to the tracker.** Read the digest, post what
you agree with, and record what you do not with `/triage-review`. A scheduled task runs
the same command; so can a CI job or webhook handler with the new ticket keys.

## When you disagree

Use `/triage-review`. It records your correction **without altering the original
recommendation**, because the gap between the two is the entire measurement. Skipping
this costs you the only feedback loop the system has.

The loop closes with two commands:

| Command | Shows |
| --- | --- |
| `/triage-log calibrate` | Repeated override patterns and the change each suggests: a disposition over-applied or missed, an escalation that keeps being lowered (with the config key to look at), overrides clustering in one area or on one reviewer |
| `/triage-log dashboard` | `triage-reports/accuracy.html`, one page with tabs: overview, dispositions (agent against person), priority, weekly trend, calibration, runs |

Both suggest; neither edits the rubric or a config.

## When it refuses

| Output | Meaning |
| --- | --- |
| `insufficient_information` | Missing repro, component or error. It lists exactly what it needs |
| `P1 DETECTED` | A P1 criterion met directly. Enrichment skipped. Follow your incident process; the agent does not replace it |
| `no release in the window touched this area` | A real finding, not a failure. Points at data, config or a latent bug rather than a regression |
| `Workaround: none found. Searched: ...` | It looked and found nothing. Different from not looking |
