# Status

An honest account of what is built and what is not.

## Built and verified

- Shared instruction layer: orchestrator, disposition taxonomy, priority rubric with
  escalation caps, release correlation, workaround finder, source contract and adapters.
- Two demo configs under `teams/` (`demo` on fixtures, `demo-live` on a real Jira
  project), one schema, one example. Team configs live in the team's own folder under
  `triage-teams/`.
- 14 fixtures, each a complete envelope validated against the live source contract, and
  four worked results.
- Deterministic renderers, so the model cannot drift or abbreviate them:
  `run_header.py` (header and team resolution), `render_trace.py` (HTML run trace),
  `render_queue.py` (bug queue), `render_fix_brief.py` (fix brief with evidence
  grading), `triage_log.py` (audit log, overrides, accuracy report).
- `scripts/validate_config.py`: config validation, contract validation, read-only SQL
  enforcement, credential-shaped key detection, placeholder detection, result files,
  and command and skill front matter.

## Added in 0.6.x

| Version | Change |
| --- | --- |
| 0.6.0 | `/queue`, `/triage-log`, fix briefs graded strong, moderate or weak; team from the ticket's project key; `triage-config` stops on a skipped required answer; `+1 history` counts only fixed defects; hint when a connector is present but its source is off |
| 0.6.1 | Quoted command front matter. An unquoted hint starting with `[` made three commands disappear |
| 0.6.2 | Team or project as a plain word, because a leading `--flag` was rejected by the host; queue ages from Jira dates with colonless offsets |
| 0.6.4 | Added `.codex-plugin/plugin.json`. Codex and ChatGPT installed the plugin but loaded no skills without it, so `@bug-triage-agent` had nothing to call. The validator now checks its `skills` path |
| 0.6.3 | Every command is a wrapper over a skill (new `triage-readiness`, `triage-history`, `triage-override`), so Codex and ChatGPT reach every feature; bare words like `queue` route without a clarifying question; plugin-root search knows Cursor and Codex install folders; per-client invocation table |

## Exercised, 2026-09-21

Five runs against fixtures: BUG-4830, BUG-4844, BUG-4851, BUG-4858 under `demo`, and
BUG-4830 again under `demo-gc` (a second team config, removed in 0.6.0). `fixtures/expected-outcomes.md` is now **recorded from
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
| Live connection beyond the tracker | The tracker has run live against a Jira demo project. Metrics, warehouse and code have only run on fixtures; their tool-name bindings are informed guesses until a team binds them with `triage-config`. |

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

| Component | Claude (Cowork, Claude Code) | Cursor | Codex / ChatGPT |
| --- | --- | --- | --- |
| `skills/` (11), one behind every command | yes | yes | yes |
| `reference/`, `teams/`, `fixtures/` | yes | yes | yes |
| MCP servers | yes | yes | yes |
| `commands/` (7) | yes | yes | **no** |
| `agents/` (4) | yes | yes | **no** |
| **Installed and run** | **yes** | not yet | ChatGPT desktop: installed, loads; asked a clarifying question for a bare `queue` (0.6.3 routes it). Codex: not yet |

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

**The read-only guarantee was never enforced by the agent files.** Earlier versions
of this document claimed the tool allowlists in `agents/` enforced it on Claude and
Cursor. A live test on 2026-09-21 disproved that: the pattern allowlists granted no
MCP tools at all, and a name-prefix filter would not have been a semantic control
anyway. The agents now declare `tools: ["*"]` and read-only is an **instruction**.

What actually constrains writes, on every client equally: the read-only service
account, the validator's SQL check, and the rule that nothing reaches the tracker
without per-ticket confirmation.

**Invocation differs.** `/triage BUG-4830` on Claude and Cursor; on Codex and ChatGPT,
invoke the plugin and say what you want. Since 0.6.3 every command is a thin wrapper
over a skill (`validate_config.py` enforces it), so no capability is lost where
commands are not loaded. Before 0.6.3, the log, override and readiness check existed
only as commands and could not be reached there.

**Scripts need a shell.** The header, queue, trace, fix brief and log are rendered by
Python scripts. A client that cannot run them stops at the first step.

### MCP server urls are placeholders, not variables

An earlier version used `${METRICS_MCP_URL}` style placeholders in `url` fields. No
client expands environment variables there, so those entries would have shipped
broken. They are now literal `REPLACE_WITH_` placeholders that the validator reports
as unconfigured. Only the tracker entry is needed for the zero-setup tier.

## Rough completeness

Demo: runs on fixtures and on a live Jira project, with recorded expectations, a
queue, fix briefs and an audit log.
Production: still roughly half. The event trigger does not exist, the taxonomy is
unvalidated, and only the tracker has run against a live source.

## Do not

Rewrite the instruction layer before running it. It is a first draft to be corrected by
evidence, not a spec to reimplement.
