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

Produced by `scripts/run_header.py`, not composed by the model. A first live run showed
a model-written header collapsing to "All five sources are fixtures", which dropped
the count and the principle line, and arrived after four opaque file reads. Code
cannot abbreviate it. The orchestrator repeats the output verbatim as message text,
because hosts collapse command output.

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

Every **live** source runs in a subagent, the tracker in Stage 1 included; fixture
sources are read directly. Besides parallelism this keeps connector output out of the
reader's view: some connectors render each result as a rich card, and a triage that
calls them inline shows a wall of ticket cards instead of its stage lines.
Name each source in the indented block as it returns, in completion order, whichever
way it was read. Two things must stay honest here:

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

### Rendered by code

`scripts/render_trace.py` turns a result file into the page. The orchestrator writes
the result; it never writes the HTML. A first test run showed why: with no renderer,
producing four traces meant hand-writing four pages, slow and different every time,
so none were produced at all.

The result file, `<TICKET>.result.json`:

```json
{
  "ticket": "BUG-4830", "summary": "…", "team": "demo",
  "triaged_at": "2026-09-22 10:14 UTC", "agent_version": "0.4.3",
  "sources": {
    "tracker":   {"mode": "fixture", "status": "ok", "note": ""},
    "releases":  {"mode": "fixture", "status": "ok"},
    "metrics":   {"mode": "fixture", "status": "ok", "note": "4.4× baseline"},
    "warehouse": {"mode": "off"},
    "code":      {"mode": "fixture", "status": "ok", "note": "error swallowing at :89"}
  },
  "disposition": "defect",
  "priority": "P2", "tracker_priority": "Critical", "current_priority": "Minor",
  "confidence": "high", "confidence_basis": "…", "route": "Approvals Team",
  "disposition_evidence": [{"text": "…", "source": "tracker"}],
  "alternative": "Considered expected_behavior; ruled out because …",
  "steps": [
    {"step": "Base",       "level": "P3", "because": "…"},
    {"step": "+1 release", "level": "P2", "because": "…"},
    {"step": "+1 code",    "level": "P2", "ghost": "P1", "because": "…"},
    {"step": "history",    "level": null, "because": "not counted: cap binds"},
    {"step": "Final",      "level": "P2", "because": "…"}
  ],
  "release": {"version": "2026.09", "shipped": "2026-09-05", "gap_days": 3,
              "confidence": "high", "basis": "…"},
  "workaround": {"text": "…", "who": "support", "source": "BUG-4701"},
  "unanswered": ["Q2 blast radius"]
}
```

Every source appears, including `off` ones: an absent key would hide exactly what the
trace exists to show. `level` is the level after that step; `null` means the step was
considered and not counted. `ghost` is where the arithmetic would have gone before a
rule held it, which the ladder draws as a crossed-out point. A non-defect has
`"priority": null` and no `steps`; the renderer refuses one that carries a priority.
Worked examples for all four demo tickets are in `fixtures/results/`.
