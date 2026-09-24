# Run visibility

What the user sees while a triage runs, as opposed to what they read when it finishes.

The report explains the answer. This explains the run. They are different jobs: a
reader who sees "3 of 5 sources unavailable" before the priority reads a low-confidence
P3 as a known limitation. A reader who meets the same P3 cold reads it as a weak
answer and ignores the tool. Visibility is an adoption mechanism, not decoration.

Everything here is markdown and works in every client. The optional surfaces at the
end degrade to nothing without changing the triage.

**Never put the header or a stage line in a code block.** Chat renders a code block in
monospace with no colour, which strips the markers that carry the meaning. The markers
are the fixed vocabulary from `reference/output-templates.md`: 🟢 live or ok, 🟡
fixture or partial, ⚫ off or skipped, 🔴 error, 🔴🟠🟡🔵 P1-P4, ⚪ non-defect, and the
●●● confidence meter. A colour means the same thing in the header, the stage lines,
the report and the trace.

## The header

Printed once, after the team config resolves and before Stage 1 runs. Never after: a
header that arrives with the answer has told the reader nothing they could act on.

Produced by `scripts/run_header.py`, not composed by the model. A first live run showed
a model-written header collapsing to "All five sources are fixtures", which dropped
the count and the principle line, and arrived after four opaque file reads. Code
cannot abbreviate it. The orchestrator runs it with `--format md` and repeats the
output verbatim as message text, because hosts collapse command output.

**Bug triage · DEMO-7 · team `demo-live`**

| Source | Mode | |
| --- | --- | --- |
| tracker | 🟢 live | project DEMO |
| releases | 🟢 live | manual_file |
| metrics | ⚫ off | Metrics connector not provisioned yet |
| warehouse | ⚫ off | Warehouse not provisioned yet |
| code | ⚫ off | No code-search connector bound |

> **2 of 5 sources available.** Absent sources lower confidence and drop escalations. They never raise severity.
> Config: `…/teams/demo-live.json` (plugin) · Agent **0.5.3**

A live source whose bindings are missing or unfilled shows 🔴, not 🟢: it will fail,
and the header is where the reader should learn that.

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

One markdown line per stage, posted as its own message the moment the stage
completes, not when it starts. A line that appears before the work claims a result the
run does not yet have. Posted one at a time, they stream: the reader watches the run
advance.

**Stage 1 · ticket + releases** · 🟢 ok · 25.0s · tracker via `enrich-tracker`
**Stage 2 · disposition** · `defect`
**Stage 3 · enrichment** · 🟢 metrics 4.4× baseline · ⚫ warehouse off · 🟢 code swallowed error at `:89`
**Stage 4 · priority** · **🟠 P2** · ●●○ medium
**Stage 5 · output** · 🟢 report · 🟢 trace · 🟢 audit log

A non-defect reads:

**Stage 2 · disposition** · ⚪ `voice_of_customer`
**Stage 3 · enrichment** · ⚫ skipped, non-defect
**Stage 4 · priority** · ⚫ skipped, non-defect

The closing summary repeats all five as one table, so the finished run can be read in
one place:

| Stage | Result | |
| --- | --- | --- |
| 1 · ticket + releases | 🟢 ok | 25.0s · tracker via `enrich-tracker` |
| 2 · disposition | `defect` | |
| 3 · enrichment | ⚫ 0 of 3 sources | metrics, warehouse, code off |
| 4 · priority | **🟠 P2** | ●●○ medium |
| 5 · report + audit log | 🟢 written | |

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

## Live progress: the task list (optional)

A message cannot be rewritten once posted, so the stage lines stream but never update.
The one surface that updates **in place** is the host's task list, where the host has
one. Use it as the live view: it shows which stage is running now and fills in each
result as it lands.

Right after the header, create these tasks, all pending:

| Task title | Shown while running |
| --- | --- |
| `Stage 1 · ticket + releases` | Fetching the ticket and release history |
| `Stage 2 · disposition` | Deciding whether this is a defect |
| `Stage 3 · enrichment` | Querying metrics, warehouse and code |
| `Stage 4 · priority` | Scoring against the rubric |
| `Stage 5 · report + log` | Writing the report, trace and audit record |

Drive them as the run moves:

1. Mark a stage **in progress before** starting its work, never after.
2. When it finishes, **rewrite the title to carry the result**, using the same markers
   as the stage line, then mark it complete:
   `Stage 2 · disposition → defect`, `Stage 4 · priority → 🟠 P2 · ●●○ medium`,
   `Stage 3 · enrichment → ⚫ skipped, non-defect`.
3. A stage that stops the run (no tracker, information gate) is rewritten with the
   reason, e.g. `Stage 1 · ticket + releases → 🔴 tracker unavailable`, and the
   remaining tasks are marked complete as `→ not run`. Never leave a task spinning
   after the run has ended.

**Batch mode:** one task per ticket instead of per stage, or a batch of ten would be
fifty tasks. Show the current stage while running (`DEMO-7 · Stage 3 · enrichment`)
and rewrite the title to the outcome when done: `DEMO-7 → 🟠 P2 · ●●○`,
`DEMO-8 → ⚪ voice_of_customer`.

This surface is additive. The stage lines are the record; the task list is a live view
that some clients render and others do not. Never put information in the task list
that does not also appear in the stage lines, or the run becomes illegible in the
clients that lack it.

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

The result file, `<TICKET>.result.json`. Any evidence item may carry a `url`, taken
from a tool result; renderers show it behind a short label and validate it is a plain
https URL. Add `introduced_by.sha` when the changing commit is known, and a top-level
`links` list for evidence that has no other home, such as a log query or a deployment:
`{"label": "Logs", "kind": "spike", "text": "…", "source": "metrics", "url": "https://…"}`.

Fields the report, trace and brief use for their opening summary and data-age checks,
all optional:

| Field | Use |
| --- | --- |
| `deciding_factor` | One sentence: the reason that decided the verdict. Becomes the summary's **Why** |
| `headline`, `do_now` | Override the computed verdict line or next action |
| `sources.<s>.as_of` | When the source was read. Live data read more than 24h before triage is flagged |
| `sources.<s>.data_from`, `retention_days` | Oldest data point used, and how long the source keeps data. Evidence within 2 days of ageing out is flagged, because it cannot be re-checked later |
| `blast_radius` | `{"accounts": 1, "enterprise": 0, "url": "…"}` from the warehouse |
| `locations[].snippet` | The offending line or two, shown under Evidence |
| `fields_to_update` | Tracker fields to propose, e.g. `{"priority": "Critical"}` |
| `route_note` | One line after the route for a non-defect |
| `timeline` | Dated events from the sources: `[{"at": "2026-09-05 17:00 UTC", "kind": "deploy", "label": "2026.09", "url": "…"}]`. Kinds: `release`, `deploy`, `spike`, `first_error`, `ticket`, `triage`, `fix` |
| `series` | The metrics counts behind the spike: `{"label": "…", "unit": "per 3h", "baseline": 36, "points": [["2026-09-03 00:00 UTC", 35], …]}`. Drawn as a chart in the trace and a sparkline in the report |
| `duplicate_check` | Output of `scripts/dupes.py`: `{"searched": 4, "candidates": [{"key", "summary", "status", "score", "verdict", "signals", "url"}]}`. Verdicts `duplicate`, `recurrence`, `related`, `different`. A result with disposition `duplicate` must have a candidate scored `duplicate` |
| `workaround.verified` | Written by `scripts/verify_workaround.py`: `{"status": "passed|failed|not_reproduced|error|pending", "runner", "environment", "target", "at", "steps", "url"}`. Never `production` |
| `comment_review` | The ticket's own comments: `{"read": 10, "used": [{"id", "author_type", "created", "url", "category", "quote"}], "not_used": {"bot": 1, "chaser": 2, "status": 1, "repeat": 0, "no_signal": 1, "not_relevant": 0}}`. Categories: `detail`, `workaround_tried`, `disposition`, `impact`, `link`, `superseded`. Every quote must appear word for word in its comment (`scripts/comments.py check`) |
| `why_changed` | One sentence, when a re-triage changed the verdict: what made the difference |
| `previous` | Optional embedded snapshot of the last triage. Normally the renderers read it from `<reports_dir>/history/`, where `scripts/history.py archive` keeps each earlier result |

**Since the last triage** is computed, not written: disposition, priority,
confidence, evidence, release, route, workaround state, the number of supporting
sources and each source's mode, compared with the latest archived result for the
ticket. Nothing appears on a first triage.

**Supported by** is computed, not written: one entry per independent source whose
finding supports the verdict. Code counts only for a fault signal
(`error_swallowing`, `stub`, `suppressed_type_error`), never for a candidate file.

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

**Fix fields**, defects only, read by `scripts/render_fix_brief.py`:

```json
{
  "repo": {"name": "approvals-api", "base_branch": "main"},
  "repro": {"steps": ["…"], "expected": "…", "actual": "…"},
  "locations": [
    {"path": "approvals-api/src/approvals/ApprovalReviewService.ts", "line": 89,
     "signal": "error_swallowing", "evidence": "…", "source": "code"},
    {"path": "approvals-api/src/approvals/ApprovalReviewService.ts",
     "signal": "release_touched", "evidence": "…", "source": "releases"},
    {"area": "settlements", "signal": "area_only", "evidence": "…", "source": "releases"}
  ],
  "hypothesis": {"statement": "…", "confirm_by": "…", "refute_by": "…"},
  "introduced_by": {"release": "2026.09", "pr": "#4412"},
  "prior_fixes": [{"key": "BUG-4701", "summary": "…", "note": "…"}]
}
```

`signal` is one of `error_swallowing`, `stub`, `suppressed_type_error` (found in code),
`release_touched`, `prior_fix_file` (a file named by a release or a prior fix),
`candidate` (a path search suggested, no signal), or `area_only`. The evidence verdict
is computed from these and only counts signals that agree on the **same file**:
**strong** needs a code signal at a known line plus a release or prior fix on that
file; **moderate** is a code signal alone, or both a release and a prior fix on one
file; anything less is **weak**.

Every source appears, including `off` ones: an absent key would hide exactly what the
trace exists to show. `level` is the level after that step; `null` means the step was
considered and not counted. `ghost` is where the arithmetic would have gone before a
rule held it, which the ladder draws as a crossed-out point. A non-defect has
`"priority": null` and no `steps`; the renderer refuses one that carries a priority.
Worked examples for all four demo tickets are in `fixtures/results/`.
