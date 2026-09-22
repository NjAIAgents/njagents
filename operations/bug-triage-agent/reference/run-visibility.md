# Run visibility

What the user sees while a triage runs, as opposed to what they read when it finishes.

The report explains the answer. This explains the run. They are different jobs: a
reader who sees "3 of 5 sources unavailable" before the priority reads a low-confidence
P3 as a known limitation. A reader who meets the same P3 cold reads it as a weak
answer and ignores the tool. Visibility is an adoption mechanism, not decoration.

Everything here is plain text and works in every client. The two optional surfaces at
the end degrade to nothing without changing the triage.

## The header

Printed once, after the team config resolves and before Stage 1 runs. Never after: a
header that arrives with the answer has told the reader nothing they could act on.

```
Bug triage · DEMO-7 · team demo-live

  tracker     live      project DEMO
  releases    live      manual file, 2 releases
  metrics     off       not connected
  warehouse   off       not connected
  code        off       no code search bound

  1 of 5 sources available. Absent sources lower confidence and drop
  escalations. They never raise severity.
```

Rules:

- One row per source in the fixed order tracker, releases, metrics, warehouse, code.
  Fixed order so a reader scanning two runs side by side compares like with like.
- Column two is the mode exactly as the config states it: `live`, `fixture`, `off`.
  Never soften `off` to something that sounds optional.
- Column three says **why**, in the user's terms. For `live`, name what it binds to.
  For `fixture`, name the fixture path. For `off`, give the reason from the config
  comment if there is one, else `not configured`.
- The count line states availability before the run, so it cannot be read as a
  post-hoc excuse for a weak answer.
- The last sentence is fixed wording. It is the one-line statement of constitution
  principle III and must not be reworded per run.

## Stage lines

One line per stage as it completes, not when it starts. A line that appears before the
work claims a result the run does not yet have.

```
Stage 1  ticket + releases ........ ok          1.4s
Stage 2  disposition .............. defect      0.8s
Stage 3  enrichment, 1 of 4 sources available
           tracker ................ ok          1.2s
           metrics ................ skipped     off
           warehouse .............. skipped     off
           code ................... skipped     off
Stage 4  priority ................. P3          confidence low
Stage 5  report + audit log ....... written
```

Rules:

- Latency comes from the envelope's `latency_ms`. A `fixture` source prints `fixture`
  in the latency column, never `0.0s`: a zero implies a call that was never made.
- A `partial` envelope prints `partial` and the first line of its `notes`. Do not
  round `partial` up to `ok`; the whole point of the status is that the reader learns
  what was incomplete.
- A source that is `off` prints `skipped` with the mode, not an error. It was not
  tried, so it did not fail.
- A source that is `live` and failed prints `error` with the message. Distinguish this
  from `skipped`: one is a configuration choice, the other is a broken dependency, and
  the fixes differ.
- When Stage 2 returns a non-defect, Stage 3 never runs. Print
  `Stage 3  skipped, non-defect` rather than omitting it, so the reader sees the gate
  worked rather than wondering what happened to a stage.
- Stage 4 prints the priority and the confidence together. Never the priority alone.

## Subagent visibility

Stage 3 delegates one subagent per available source. Name each in the indented block
as it returns, in completion order. Two things must stay honest here:

- A client that cannot delegate runs the sources in turn. Print the same lines. The
  reader cares which sources answered, not how the work was scheduled.
- Never print a subagent line for a source that was `off`. A skipped source spawned
  no agent, and a line implying otherwise would misrepresent the run.

## Task list (optional)

Where the host offers task tools, create five tasks matching the five stages at the
start of the run and resolve each as it completes. Where the host does not, skip it
silently.

This surface is additive. The stage lines above are the record; the task list is a
convenience that some clients render and others do not. Never move information into
the task list that does not also appear in the stage lines, or the run becomes
illegible in the clients that lack it.

## Run trace (optional)

A single self-contained page showing the decision path: the gate, the disposition and
its basis, each source's contribution, the ten rubric questions marked answered or
unanswered, the escalation arithmetic, and the final priority with its confidence.

Controlled by `output.run_trace` in the team config:

| Value | Behaviour |
| --- | --- |
| `never` | No trace. |
| `file` | Written next to the report as `<TICKET>-trace.html`. **Default.** |
| `artifact` | Published as a hosted page, where the client can publish one. |

The default is `file` deliberately. A triage report carries customer names, account
counts and defect detail. Publishing that to a hosted URL is a disclosure decision,
so it is opt-in per team rather than something the tool does because it can. A team
whose tracker holds real customer tickets should leave the default alone.

Where `artifact` is set but the client cannot publish, fall back to `file` and say so
in one line. Never fail a triage because a presentation surface was unavailable.
