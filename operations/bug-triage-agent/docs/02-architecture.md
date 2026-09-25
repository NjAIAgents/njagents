# Architecture

Normative procedure lives in [`skills/bug-triage/SKILL.md`](../skills/bug-triage/SKILL.md).
This page explains the shape and the reasoning behind it.

## The pipeline

```mermaid
flowchart TD
  CMD["/triage TICKET"] --> SET
  SCH["Scheduler or tracker event<br/>(automation.enabled, off by default)"] --> AUTO["/triage-auto<br/>auto_triage.py plan: new, changed, overdue"]
  AUTO --> SET["Setup<br/>run_header.py prints every source and its mode"]
  CFG[("triage-teams/ID.json<br/>modes · bindings · queue ·<br/>automation · verification")] -. reads .-> SET
  SET --> G0{"Stage 0<br/>information gate"}
  G0 -- "missing repro, component or error" --> X0["Return to reporter"]
  G0 -- complete --> S1["Stage 1 · base enrichment, always<br/>enrich-tracker + release adapters"]
  TR[("Tracker connector<br/>the one required source")] -. reads .-> S1
  S1 -- "tracker absent" --> X1["Stop: no tracker, no triage"]
  S1 -- envelopes --> DUP["dupes.py<br/>score candidates by failure mode"]
  DUP --> D{"Stage 2<br/>disposition: is it a defect?"}
  D -- "no: expected_behavior · config_or_data ·<br/>duplicate · voice_of_customer" --> ND["Route and log<br/>no priority, Stage 3 never runs"]
  D -- "yes: defect" --> F(("parallel"))
  F --> M["enrich-metrics<br/>spike, deploys, error series"]
  F --> W["enrich-warehouse<br/>accounts via team SQL"]
  F --> K["enrich-code<br/>swallowed errors, stubs"]
  M --> J(("join"))
  W --> J
  K --> J
  J --> RW["release-correlation · workaround-finder"]
  RW --> VER["verify_workaround.py<br/>http · docker · ci · command<br/>never production"]
  RW -- evidence --> S4["Stage 4 · classify<br/>10 questions → base<br/>+1 per class, at most +2<br/>at-risk P2 floor · never P1 by escalation"]
  VER -. "failed: workaround not practical" .-> S4
  RB[("priority-rubric.md<br/>shared, never forked")] -. rules .-> S4
  S4 --> RES["Stage 5 · TICKET.result.json<br/>the one source of truth"]
  ND --> RES
  HIST[("history/<br/>earlier results")] -. "since the last triage" .-> RES
  RES --> O3["HTML report, the default<br/>TICKET-report.html<br/>render_trace.py + report_html.py"]
  RES -. "report_format md or both,<br/>or asked for in the run" .-> O2["markdown report<br/>TICKET.md · render_report.py"]
  RES --> O6["fix brief .md<br/>every defect, every mode<br/>render_fix_brief.py"]
  RES --> O1["chat summary"]
  RES --> PG["queue and batch pages<br/>queue-TEAM.html · batch-DATE.html<br/>pages_html.py"]
  THM[("assets/report-theme.css<br/>html_theme.py inlines it")] -. look .-> O3
  THM -. look .-> PG
  RES --> O5["audit log<br/>triage_log.py refuses a scored non-defect"]
  RES -. "only after a person says yes,<br/>never from /triage-auto" .-> O4["tracker comment"]
  RES -. "automatic runs" .-> DIG["review page<br/>auto/DATE-TEAM.html<br/>auto_triage.py digest"]
  O6 --> IDX["handoff index<br/>briefs.json: ready · held<br/>brief_index.py"]
  O5 -. "reviews release a hold" .-> IDX
  IDX --> FIX["fix agent<br/>picks up ready briefs only"]
  THM -. look .-> DIG
  PCHK["page_check.py<br/>structure · links · query URLs"] -. "validator gate" .-> O3
  DOC["/triage-doctor · /triage-config<br/>check and write the team config"] -. sets up .-> CFG

  classDef gate fill:#DCEFEA,stroke:#0B7A69,stroke-width:2px,color:#17201C
  classDef stop fill:#F7E5DC,stroke:#B4502A,color:#17201C
  classDef cond stroke-dasharray:5 4
  class D,G0 gate
  class X0,X1,ND,O4 stop
  class M,W,K,VER,AUTO,SCH,O2,PCHK cond
```

Dashed boxes are conditional. Enrichment runs only when its source is not `off`; each
`live` source gets its own subagent, and `fixture` sources are read directly.
Verification and automatic triage run only when the team config turns them on. The
disposition diamond is the design: a non-defect leaves with no priority, and the audit
log refuses to record one that carries a priority.

Every output after Stage 5 is rendered by a script from the one result file, so the
HTML report, the markdown report, the fix brief and the digest cannot disagree. The HTML
report is the default; `output.report_format` decides whether a markdown report is also
written (`md`, `both`), or only the result file and the fix brief (`agent`). Every HTML
page inlines `assets/report-theme.css`, so each one is a single file that opens anywhere.
Before a re-run writes a new result, `history.py` archives the old one, and the report
opens with what changed.

A fix agent never reads the reports folder directly. After every run `brief_index.py`
writes `briefs.json`: the briefs that are `ready`, and the ones `held` because a person
must decide, a fix already exists, or the location evidence is weak. A review recorded
with `/triage-review` releases a human-review hold on the next run. `page_check.py`
runs in the validator on every page, so a broken tag or an old-shape query link fails
the build instead of reaching a reader.

## Commands

| Command | Group | What it does |
| --- | --- | --- |
| `/triage-config` | Set up | Writes or updates a team config by asking a few questions |
| `/triage-doctor` | Set up | Checks the config and that every source is reachable |
| `/triage` | Run | Triages one ticket or a batch, end to end |
| `/triage-auto` | Run | Unattended triage of new, changed and overdue bugs, when the config turns it on |
| `/release-impact` | Run | Which recent release most likely touched a bug's area |
| `/queue` | Review | Open bugs, what still needs triage, overdue and stuck ones |
| `/triage-log` | Review | Recent decisions, accuracy, calibration, dashboard |
| `/triage-review` | Review | Records a person's override, which the agent learns from |

## The feedback loop

```mermaid
flowchart LR
  Q["/queue<br/>overdue first, stuck flagged"] --> T["/triage or /triage-auto"]
  T --> LOG[("triage-logs/<br/>triage-log.jsonl")]
  T --> P["Person reads report or digest"]
  P -- "agrees or corrects" --> REV["/triage-review<br/>override with reason"]
  REV --> LOG
  LOG --> CAL["/triage-log calibrate<br/>repeated override patterns"]
  LOG --> DASH["/triage-log dashboard<br/>accuracy page with tabs"]
  CAL -. "suggests, never edits" .-> CHG["Team config change<br/>via /triage-config"]
  CAL -. "suggests, never edits" .-> RUB["Rubric or taxonomy change<br/>reviewed like code"]
  CHG --> T
  RUB --> T
  LOG -. "last triage per ticket" .-> Q
```

The gap between what the agent recommended and what a person decided is the only
measurement the system has. The loop turns that gap into proposed changes, and a person
decides which to make.

### Why the stages sit in that order

**Stage 1 must precede stage 2.** The disposition gate reasons from prior tickets
closed as works-as-designed, duplicate candidates and component history. All of those
come from the tracker. A gate that ran first would have nothing to reason from.

**Stage 3 must follow stage 2.** A non-defect costs two source calls instead of five,
because the expensive sources never run. That is a cost property, but the real reason
is correctness: scoring something that is not a defect is the failure this design
exists to prevent.

## Shared core versus per-team

| Shared, versioned, never forked | Per team, one file |
| --- | --- |
| Disposition taxonomy | Tracker project key and instance id |
| Priority rubric, escalation classes, caps | Priority name mapping |
| Confidence definition | Which sources are live, fixture or off |
| Output format | Warehouse query templates |
| Stage ordering, degradation rules | Repository list |
| Source contract | Component-to-team routing |
| | Release manifest adapters |
| | Tool-name bindings for non-tracker sources |

Nothing under `skills/` or `reference/` may name a product, schema, repository or
customer. That constraint is what lets one rubric serve two product lines running at
different quality bars. It is worth enforcing with a grep in CI rather than by
discipline.

## Source modes

Every source is `live`, `fixture` or `off`.

- **live** calls the real system. On failure it returns an error status and **never**
  falls back to fixtures. Silent fallback is how people end up trusting fake numbers.
- **fixture** reads a recorded envelope. Fixtures are recordings of the live contract,
  not a parallel code path, which is what makes demo-to-production a config change.
- **off** returns `unavailable` immediately. A normal state, not a failure.

Any output built on a fixture carries a `DEMO DATA` banner.

## The source contract

Every source returns the same envelope regardless of mode, so nothing downstream knows
or cares where the data came from. Shapes and per-source fields are defined in
[`skills/data-sources/SKILL.md`](../skills/data-sources/SKILL.md).

```mermaid
flowchart LR
  CFG[("teams/ID.json<br/>sources.SOURCE.mode")] -- mode --> DS["data-sources skill<br/>resolve each source"]
  DS -- live --> L["Session connector (MCP)<br/>called via tool_bindings"]
  DS -- fixture --> FX["fixtures/SOURCE/<br/>recorded envelope"]
  DS -- off --> U["Unavailable<br/>typed result, not an error"]
  L --> E[["One envelope<br/>source · mode · status · as_of<br/>latency_ms · notes · data"]]
  FX --> E
  U --> E
  E -- feeds --> R["Rubric + skills<br/>cannot tell fixture from live"]
```

The plugin declares no connectors. Switching a source from `off` to live is a
`tool_bindings` entry, a query template where one applies, and a mode change.

The validator checks every fixture against the same shape a live adapter produces. If
the validator ever needs a special case for a fixture, demo and production have quietly
diverged and the contract is no longer enforced.

## Parallelism and the read-only guarantee

Stage 3 delegates one subagent per **live** source and waits for all of them. Fixture
sources are read directly: a subagent to read a local file adds latency and
parallelises nothing. The delegation is stated in the orchestrator skill rather than
relying on any single client's bundled agent files, so it holds across Claude, Cursor
and Codex.

The files in `agents/` declare `tools: ["*"]`. An earlier version used pattern
allowlists and this document claimed they enforced read-only. **They did not.** A live
test showed the patterns granted no MCP tools at all, and even working, a
`get`/`search`/`list` name filter is not semantic: `get_auth_token` mutates.

Read-only is an instruction to the agent. The enforcement lives elsewhere and applies
on every client equally: a read-only service account, the validator's SQL check, and
per-ticket confirmation before anything is written.

## Component map

| Directory | Holds | Loaded by |
| --- | --- | --- |
| `skills/` | Orchestrator, five component skills, triage-config setup, the queue, the log and override skills, readiness, and automatic triage | all three clients |
| `reference/` | Taxonomy, rubric, output templates, run visibility, calibration guide | read by the skills |
| `agents/` | One enrichment subagent per source, `tools: ["*"]` | Claude, Cursor |
| `commands/` | Thin wrappers: triage, queue, triage-log, triage-config, release-impact, doctor, review, triage-auto | Claude, Cursor |
| `teams/` | Shipped demo configs, schema and example. A team's own config lives in its repo under `triage-teams/`, found first | read by the skills |
| `fixtures/` | Recorded envelopes, and worked result files under `results/` | demo mode, tests |
| `assets/` | `report-theme.css`, the stylesheet every HTML page inlines | `html_theme.py` |
| `scripts/` | Header (`run_header.py`); renderers for the HTML report (`render_trace.py`, `report_html.py`), markdown report, fix brief, queue, and queue and batch pages (`pages_html.py`); `html_theme.py` for the look; shared `summary.py`, `links.py`, `timeline.py`, `history.py`; `dupes.py` duplicate scoring; `verify_workaround.py`; `auto_triage.py`; `triage_log.py` with `calibration.py`; `validate_config.py` build gate | runtime, CI, packaging |
| `logs/` | Unused at runtime. The audit log lives in the working folder, `triage-logs/`, because an installed plugin is read-only | none |

The header, the reports, the fix brief, the queue, the batch page and the digest are all
rendered by code, not written by the model. The header and the trace were first
model-written, and a real run showed the header abbreviated and the traces not produced
at all; the report followed in 0.7.0 for the same reason.
