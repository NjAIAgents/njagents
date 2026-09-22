# Architecture

Normative procedure lives in [`skills/bug-triage/SKILL.md`](../skills/bug-triage/SKILL.md).
This page explains the shape and the reasoning behind it.

## The pipeline

```mermaid
flowchart TD
  CMD["/triage TICKET --team id"] --> SET["Setup<br/>run_header.py prints every source and its mode"]
  CFG[("teams/ID.json<br/>modes · bindings · SQL")] -. reads .-> SET
  SET --> G0{"Stage 0<br/>information gate"}
  G0 -- "missing repro, component or error" --> X0["Return to reporter"]
  G0 -- complete --> S1["Stage 1 · base enrichment, always<br/>enrich-tracker + release adapters"]
  TR[("Tracker connector<br/>the one required source")] -. reads .-> S1
  S1 -- "tracker absent" --> X1["Stop: no tracker, no triage"]
  S1 -- envelopes --> D{"Stage 2<br/>disposition: is it a defect?"}
  D -- "no: expected_behavior · config_or_data ·<br/>duplicate · voice_of_customer" --> ND["Route and log<br/>no priority, Stage 3 never runs"]
  D -- "yes: defect" --> F(("parallel"))
  F --> M["enrich-metrics<br/>spike vs rolling median"]
  F --> W["enrich-warehouse<br/>accounts via team SQL"]
  F --> K["enrich-code<br/>swallowed errors, stubs"]
  M --> J(("join"))
  W --> J
  K --> J
  J --> RW["release-correlation · workaround-finder"]
  RW -- evidence --> S4["Stage 4 · classify<br/>10 questions → base<br/>+1 per class, at most +2<br/>at-risk P2 floor · never P1 by escalation"]
  RB[("priority-rubric.md<br/>shared, never forked")] -. rules .-> S4
  S4 --> OUT["Stage 5 · output + log"]
  ND --> OUT
  OUT --> O1["chat summary"]
  OUT --> O2["report .md"]
  OUT --> O3["run trace<br/>render_trace.py"]
  OUT -. "only after a person says yes" .-> O4["tracker comment"]
  OUT --> O5["audit log<br/>triage_log.py refuses a scored non-defect"]

  classDef gate fill:#DCEFEA,stroke:#0B7A69,stroke-width:2px,color:#17201C
  classDef stop fill:#F7E5DC,stroke:#B4502A,color:#17201C
  classDef cond stroke-dasharray:5 4
  class D,G0 gate
  class X0,X1,ND,O4 stop
  class M,W,K cond
```

Dashed enrichment boxes run only when their source is not `off`; each `live` source
gets its own subagent, and `fixture` sources are read directly. The disposition
diamond is the design: a non-defect leaves with no priority, and the audit log refuses
to record one that carries a priority.

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
| `skills/` | Orchestrator, five component skills, and triage-config setup | all three clients |
| `reference/` | Taxonomy, rubric, output templates, run visibility, calibration guide | read by the skills |
| `agents/` | One enrichment subagent per source, `tools: ["*"]` | Claude, Cursor |
| `commands/` | Thin wrappers: triage, triage-config, release-impact, doctor, review | Claude, Cursor |
| `teams/` | Shipped demo configs, schema and example. A team's own config lives in its repo under `triage-teams/`, found first | read by the skills |
| `fixtures/` | Recorded envelopes, and worked result files under `results/` | demo mode, tests |
| `scripts/` | `run_header.py` header, `render_trace.py` trace, `triage_log.py` audit, `validate_config.py` build gate | runtime, CI, packaging |
| `logs/` | Audit log destination | runtime |

The header and the trace are rendered by code, not written by the model. Both were
first model-written, and a real run showed the header abbreviated and the traces not
produced at all.
