# Status

An honest account of what is built and what is not. Release notes for every version
are in [CHANGELOG.md](CHANGELOG.md).

## Built and verified

- Shared instruction layer: orchestrator, disposition taxonomy, priority rubric with
  escalation caps, release correlation, workaround finder, source contract and adapters.
- Two demo configs under `teams/` (`demo` on fixtures, `demo-live` on a real Jira
  project), one schema, one example. Team configs live in the team's own folder under
  `triage-teams/`.
- 14 fixtures, each a complete envelope validated against the live source contract, and
  four worked results.
- Deterministic renderers, so the model cannot drift or abbreviate them:
  `run_header.py` (header and team resolution), `render_trace.py` with `report_html.py`
  (the HTML report, the default), `html_theme.py` (inlines `assets/report-theme.css`
  and applies `output.theme`), `pages_html.py` (queue, batch and automatic-run pages), `brief_index.py` (the handoff index, briefs.json), `page_check.py` (page structure and link checks),
  `render_queue.py` (bug queue with overdue and stuck flags; `--html` writes the queue
  page), `render_fix_brief.py` (fix brief with evidence grading and `brief_version: 2`
  front matter), `render_report.py` (the markdown report, opt-in), `clusters.py`
  (groups in a batch, and the batch page), `links.py` (evidence links, including the
  `log_query` template), `timeline.py`, `story.py`, `summary.py`,
  `history.py` (what changed since the last triage), `dupes.py` (duplicate scoring),
  `comments.py`, `counterevidence.py`, `effort.py`, `fix_status.py`, `human_gate.py`,
  `next_action.py`, `risks.py`, `sla.py`,
  `verify_workaround.py`, `auto_triage.py`, and `triage_log.py` with `calibration.py`
  (audit log, overrides, accuracy report, calibration suggestions, dashboard).
- `scripts/validate_config.py`: config validation, contract validation, read-only SQL
  enforcement, credential-shaped key detection, placeholder detection, result files,
  command and skill front matter, `output.theme` colours, and fix brief front matter
  that parses and keeps its types.

## Added in 0.7.0

| Change |
| --- |
| The report is rendered by script from the result file, like the trace and the fix brief, and opens with verdict, why and do now; "Supported by" lists each independent source with its link; stale or expiring data is flagged |
| Timeline: deploy, error rise, ticket and triage with the gaps between them, drawn over the error counts in the trace and as a sparkline in the report |
| Since the last triage: earlier results are archived to `history/`, and a re-run shows what changed and why |
| Duplicate detection by failure mode: error text, symptom, stack, endpoint, file, area and release, scored by script; a title match alone is never a duplicate; a fixed candidate is a `recurrence` |
| Queue: triage-within limits per team, overdue bugs first, triaged P1 and P2 with no movement flagged as stuck |
| Automatic triage (`triage-auto`), off by default, set up in `triage-config`; never writes to the tracker, writes a review digest |
| Workaround verification, off by default, with an http, docker, ci or command runner; never production |
| Calibration suggestions from repeated overrides, and an accuracy dashboard with tabs |

## Added in 0.6.x

| Version | Change |
| --- | --- |
| 0.8.0 | HTML report is the default (markdown on request, agent mode for fix pipelines); story, risks, reproduction, fix complexity, groups, counter-evidence, SLA, human review, fixed set of next actions; already-fixed check; fix brief front matter v2 and briefs.json handoff index; queue, batch and automatic-run pages; theme file; working metrics query links; page checks in the validator |
| 0.7.1 | Reads the ticket's own comments: noise dropped by script, relevant comments categorised and quoted word for word, checked by the validator; shown in report, trace and fix brief |
| 0.6.0 | `/queue`, `/triage-log`, fix briefs graded strong, moderate or weak; team from the ticket's project key; `triage-config` stops on a skipped required answer; `+1 history` counts only fixed defects; hint when a connector is present but its source is off |
| 0.6.1 | Quoted command front matter. An unquoted hint starting with `[` made three commands disappear |
| 0.6.2 | Team or project as a plain word, because a leading `--flag` was rejected by the host; queue ages from Jira dates with colonless offsets |
| 0.6.7 | Evidence links: every cited item links to its source behind a short label (file:line pinned to a commit, release, commit, ticket, log query, deploy). URLs come from tool results or the config's `links` templates, never from the model; the validator checks templates and result URLs |
| 0.6.6 | Code source reads files under `key_paths` when search returns nothing; metrics can combine a log store with a hosting platform's deploys and runtime logs; the header warns when a live run uses the plugin's shipped config; demo-live runs on Jira, GitHub, Grafana Loki and Vercel |
| 0.6.5 | `triage-config <team> <section>` changes one section only, shown as a diff; a code-host name sets up code search and release tags together |
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
| Live event trigger | Since 0.7.0, `/triage-auto` runs on a schedule or a tracker event, off by default. It has run on fixtures only; no webhook or scheduled task has driven it against the live demo yet. |
| Validated taxonomy | The shipped disposition taxonomy is a construction, not any organization's actual judgment. Replace it via interviews plus a changelog-derived benchmark. |
| Live warehouse | Tracker, releases (GitHub), metrics (Grafana Loki, Vercel) and code (GitHub) are bound live for the demo. The warehouse has only run on fixtures. |

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
| `skills/` (12), one behind every command | yes | yes | yes |
| `reference/`, `teams/`, `fixtures/` | yes | yes | yes |
| MCP servers | yes | yes | yes |
| `commands/` (8) | yes | yes | **no** |
| `agents/` (4) | yes | yes | **no** |
| **Installed and run** | **yes** | **yes** (2026-09-22, queue on the demo team) | Installed; skills load since 0.6.4. A regular ChatGPT chat cannot run them (no tool, no shell). A Codex task with a folder is untested |

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
Production: still roughly half. Automatic triage and workaround verification exist
but have run only on fixtures and local tests, the taxonomy is unvalidated, and the
warehouse has never run against a live source.

## Do not

Rewrite the instruction layer before running it. It is a first draft to be corrected by
evidence, not a spec to reimplement.
