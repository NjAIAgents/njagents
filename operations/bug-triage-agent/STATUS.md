# Status

An honest account of what is built and what is not.

## Built and verified

- Shared instruction layer: orchestrator, disposition taxonomy, priority rubric with
  escalation caps, release correlation, workaround finder, source contract and adapters.
- Four team configs under `teams/`, one schema, one worked example.
- 14 fixtures, each a complete envelope validated against the live source contract.
- `scripts/validate_config.py`: config validation, contract validation, read-only SQL
  enforcement, credential-shaped key detection, placeholder detection.

## Exercised, 2026-09-21

Five runs against fixtures: BUG-4830, BUG-4844, BUG-4851, BUG-4858 under `demo`, and
BUG-4830 again under `demo-gc`. `fixtures/expected-outcomes.md` is now **recorded from
those runs**, not predicted.

What held: the disposition gate (two non-defects received no priority), the
two-team consistency guarantee (same rubric, different priority names, no inflation
from switched-off sources), parallel subagent delegation, the escalation cap.

What the runs found, all since fixed: the tracker contract had no field for resolution
text so workaround discovery could never succeed; the expectations file assumed a base
level that the base-precedence rule contradicted; the correlation confidence table had
no row for area overlap with stale timing; the P1 stoppage criterion was ambiguous
enough that two readings of BUG-4851 were defensible; nothing wrote the audit log; and
`mcp.json` declared servers the plugin did not need.

Still true: this is instructions the model follows at runtime, not deterministic code.
Five runs is five runs.

## Not built

| Missing | Why it matters |
| --- | --- |
| Event trigger | The agent runs when a person types a command. The requirement is that it acts when a ticket is submitted. Needs real code. |
| Validated taxonomy | The shipped disposition taxonomy is a construction, not any organization's actual judgment. Replace it via interviews plus a changelog-derived benchmark. |
| Live connection | No credentials have been used. Tool-name bindings for non-tracker sources are informed guesses. |

## Connections

The plugin declares **no MCP servers**. It binds to tools already in the session via
`tool_bindings`, whatever provided them.

The first install proved why. Declaring servers named `metrics`, `warehouse` and `code`
made the host ask for connections **owned by the plugin**, duplicating connectors the
user already had, listing meaningless names in their connector list, and failing on
install because three had placeholder urls. Removed in 0.2.0.

## Client compatibility

Three manifests ship, all agreeing on name and version. The skills are the portable
core and exist in one copy.

| Component | Claude | Cursor | Codex / ChatGPT |
| --- | --- | --- | --- |
| `skills/` (6) | yes | yes | yes |
| `reference/`, `teams/`, `fixtures/` | yes | yes | yes |
| MCP servers | yes | yes | yes |
| `commands/` (4) | yes | yes | **no** |
| `agents/` (4) | yes | yes | **no** |

### What differs on Codex and ChatGPT

**Parallel enrichment still works.** Codex and ChatGPT Work run subagent workflows,
spawning agents in parallel and collecting results, enabled by default in current
local Codex releases. Their documentation states Codex delegates when project or
**skill** instructions request it, which is exactly how the orchestrator asks for
stage 3. Stage 3 is written as an explicit delegation instruction rather than relying
on any one client's bundled-agent mechanism, so it holds on all three.

**What is not loaded is the four agent definition files.** The Codex plugin format
carries skills and MCP servers only; Codex custom agents are configured locally rather
than shipped inside a plugin. The behaviour those files describe is in the skill, so
nothing is lost functionally.

**The read-only guarantee loses a layer.** This is the real difference. Each agent
file carries a tool allowlist matching read-shaped verbs only, which is what makes
"cannot write to the tracker or run DDL" enforced rather than merely stated. Without
those files loaded, the guarantee on Codex rests on the read-only service account and
the validator's SQL check alone. Defence in depth minus one layer. A Codex user who
wants the third layer defines equivalent custom agents locally.

**Invocation differs.** `/triage BUG-4830` on Claude and Cursor; on Codex, invoke the
plugin or skill by name. The commands are thin wrappers over the skills, so no
capability is lost.

### MCP server urls are placeholders, not variables

An earlier version used `${METRICS_MCP_URL}` style placeholders in `url` fields. No
client expands environment variables there, so those entries would have shipped
broken. They are now literal `REPLACE_WITH_` placeholders that the validator reports
as unconfigured. Only the tracker entry is needed for the zero-setup tier.

## Rough completeness

Demo: runs, with recorded expectations and an implemented audit log.
Production: still roughly half. The event trigger does not exist, the taxonomy is
unvalidated, and nothing has touched a live source.

## Do not

Rewrite the instruction layer before running it. It is a first draft to be corrected by
evidence, not a spec to reimplement.
