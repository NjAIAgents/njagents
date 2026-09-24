# njagents

Agent plugins for engineering and delivery work. Each plugin packages the skills,
agents, commands and configuration needed to run a repeatable workflow.

Author: Navjyot Nishant

## Quick start: bug-triage-agent

From nothing to a triaged ticket in about five minutes. Full detail is in
[`operations/bug-triage-agent/docs/`](operations/bug-triage-agent/docs/README.md).

### 1. Install the plugin

**Cowork (Claude desktop app)**

1. Open **Customize**, then **Browse plugins**, then **Add marketplace**.
2. Enter `github.com/NjAIAgents/njagents` and sync.
3. Install **bug-triage-agent**.
4. Quit and reopen the app, so new sessions load the plugin's commands.

**Claude Code**

```
/plugin marketplace add NjAIAgents/njagents
/plugin install bug-triage-agent@njagents
```

Then restart Claude Code.

**Updating later:** sync the marketplace (Cowork) or run `/plugin marketplace update
njagents` (Claude Code), then start a new session. An open session keeps the version it
started with.

### 2. Start a session in the right place

- Use a **Cowork task** or **Claude Code**. A regular Chat only syncs the skill folders,
  so the scripts and team configs are missing and every command fails at its first step.
- In Cowork, **connect a folder** to the task. Reports, traces, fix briefs and the audit
  log are written there, never into the plugin.

### 3. Try it with no connectors

The plugin ships a `demo` team whose five sources are recorded fixtures:

```
/bug-triage-agent:triage BUG-4830
```

You should see a header with the team, the source modes and **Agent 0.7.1**, then a
live stage list, then a P2 defect with strong evidence. Three files land in
`triage-reports/` in your folder: the report, an HTML run trace, and a fix brief.

Two more to see the full range:

```
/bug-triage-agent:triage BUG-4830 BUG-4844 BUG-4851 BUG-4858    a defect, a request, a duplicate
/bug-triage-agent:queue                                          what still needs triage
```

### 4. Connect your tracker

Connect your issue tracker in your client's connector settings, the way you connect any
other tool. The plugin declares no connections of its own and
never asks for credentials. It uses the tools already in your session.

The tracker is the only required source. Metrics, warehouse and code search are
optional and only add confidence; leaving them off never raises a priority.

### 5. Create your team's config

```
/bug-triage-agent:triage-config payments
```

It asks a few questions (tracker, project key, how P1 to P4 map to your priority
names, which sources to use), proves each tool name against your session, and writes
`triage-teams/payments.json` in your folder. Commit that file so your team shares it.
If you skip a required answer, it stops and writes nothing.

### 6. Check, then triage

```
/bug-triage-agent:triage-doctor payments      every source reachable and bound
/bug-triage-agent:queue payments              open bugs, what still needs triage
/bug-triage-agent:triage PAY-123              one ticket, end to end
```

You do not name the team when triaging: `PAY-123` resolves to `payments` from its
project key. When a command takes a team, give it as a plain word (`payments`) or a
project key (`PAY`), not as a `--team` flag; some hosts reject a command whose first
argument is a flag.

### On Cursor, Codex or ChatGPT

The same plugin installs there from the same repository. Commands differ by client;
see [Invoking it](operations/bug-triage-agent/docs/05-usage.md#per-client). In Codex and
ChatGPT, invoke `@bug-triage-agent` and say what you want in a sentence, for example
"show the bug queue for demo-live". Cursor is tested. Codex is installed and loads the
skills but is not yet run end to end. Codex needs a Codex task with a local folder; a regular ChatGPT chat shows the plugin but cannot run its skills.

### 7. Use the output

| Output | Where | What to do with it |
| --- | --- | --- |
| Report | `triage-reports/<TICKET>.md` | Read the disposition, priority, evidence and workaround |
| Run trace | `triage-reports/<TICKET>-trace.html` | See every stage, source call and rule that fired |
| Fix brief | `triage-reports/<TICKET>.fix-brief.md` | Hand to a fix-bug agent. Weak evidence is flagged at the top |
| Tracker comment | offered in chat | Posted only after you confirm, per ticket |
| Audit log | `triage-logs/triage-log.jsonl` | `/bug-triage-agent:triage-log`, and `/bug-triage-agent:triage-review` to record where you disagreed |

More worked runs with expected output:
[`docs/09-examples.md`](operations/bug-triage-agent/docs/09-examples.md).

### If something goes wrong

| You see | Fix |
| --- | --- |
| "Unknown skill" | Update the plugin, restart the app, start a new Cowork task, not a Chat |
| "Unknown skill" only when you add arguments | Name the team as a plain word: `/bug-triage-agent:queue payments` |
| Header shows an older **Agent** version | That session started before the update. Start a new one |
| "Could not tell which team" | Name the team, or create one with `/bug-triage-agent:triage-config` |
| 🔴 next to a live source | `/bug-triage-agent:triage-doctor <team>` names the missing tool |

## How this repository is organized

Top-level directories name the **kind of work** a plugin serves, not the client, the
vendor or the technology. Find a plugin by asking what job you are doing.

| Directory | Work it serves | Plugins |
| --- | --- | --- |
| `development/` | Writing, reviewing and shipping code | none yet |
| `operations/` | Triage, incidents, releases, running systems | `bug-triage-agent` |
| `qa/` | Test strategy, coverage, defect analysis | none yet |
| `business-analyst/` | Requirements, process mapping, stakeholder analysis | none yet |
| `release/` | Release planning, notes, change management | none yet |

A new category is added when a genuinely new kind of work appears, not for a new
client or a new tool. A plugin named after a customer dates immediately; one named
after the work outlives it.

## Client compatibility

Plugins here target the portable [Agent Plugins](https://agent-plugins.org) standard
and carry client manifests alongside it, so one copy of the skills serves several
agents.

Four manifests, one copy of the skills:

| Manifest | Target | Loads |
| --- | --- | --- |
| `.claude-plugin/plugin.json` | Claude Code, Cowork | Skills, agents, commands, MCP |
| `.cursor-plugin/plugin.json` | Cursor | Skills, agents, commands, MCP, rules |
| `.codex-plugin/plugin.json` | Codex, ChatGPT desktop | Skills (via its `skills` path), MCP servers |
| `plugin.json` at plugin root | Other Agent Plugins clients | Skills, MCP servers |

The root manifest follows the vendor-neutral Agent Plugins specification, so other
conformant clients should load the skills as well. That is an inheritance from the
standard, not a tested claim. Cowork and Cursor are installed and run; Claude Code shares
Cowork's plugin format; Codex and ChatGPT desktop install the plugin and load its
skills, but a run has not been completed there yet.

Where a target cannot load a component, the difference is recorded in that plugin's
`STATUS.md`.

## Plugin index

| Plugin | What it includes | Status |
| --- | --- | --- |
| `operations/bug-triage-agent` | Disposition gate, release correlation, workaround discovery and priority scoring, a bug queue, fix briefs for a fix-bug agent, and an audit log, with a shared rubric and per-team configuration | 0.7.1. Run on recorded fixtures and a live Jira demo in Cowork |

### bug-triage-agent

Triage bug tickets with judgment, not just severity. The agent classifies a ticket as
defect, expected behaviour, config or data issue, duplicate, or voice-of-customer
**before** any priority is assigned, identifies which release touched the affected
area over a full release-cycle lookback, and surfaces a workaround the customer can
use today.

One shared rubric governs every team; a team owns exactly one configuration file. See
`operations/bug-triage-agent/README.md` for setup,
[`operations/bug-triage-agent/docs/09-examples.md`](operations/bug-triage-agent/docs/09-examples.md)
for worked examples you can run, and
`operations/bug-triage-agent/STATUS.md` for an honest account of what is built, what
has been exercised, and what does not exist yet.
[`operations/bug-triage-agent/CHANGELOG.md`](operations/bug-triage-agent/CHANGELOG.md)
summarises every release.

## Repository structure

```
njagents/
├── README.md
├── LICENSE
├── package-plugin.sh              packaging script
├── scripts/check_constitution.py  repository rules, run in CI
├── .claude-plugin/
│   └── marketplace.json           marketplace manifest
├── .specify/                      Spec Kit artifacts (repo root, never inside a plugin)
├── specs/                         feature specs
└── operations/
    └── bug-triage-agent/
        ├── README.md
        ├── STATUS.md
        ├── CHANGELOG.md
        ├── docs/                  full documentation, 01 to 09
        ├── plugin.json            Agent Plugins manifest (Codex, ChatGPT)
        ├── .claude-plugin/        Claude Code and Cowork manifest
        ├── .cursor-plugin/        Cursor manifest
        ├── commands/              triage, queue, triage-log, triage-config, triage-doctor, triage-review, triage-auto, release-impact
        ├── skills/                SHARED judgment, one folder per stage
        ├── agents/                one enrichment subagent per source
        ├── reference/             SHARED rubric, taxonomy, output templates
        ├── teams/                 the two demo configs, the schema, the example
        ├── fixtures/              recorded envelopes and worked results
        └── scripts/               header, trace, queue, fix brief, log, validator
```

A team's own config never goes in the plugin. It lives in the team's repository as
`triage-teams/<team>.json`.

Spec Kit lives at the repository root, not inside a plugin. A plugin ZIP must never
contain `.specify/` or `.claude/`; `package-plugin.sh` strips them defensively.

## Installing

See [Quick start](#quick-start-bug-triage-agent) for the marketplace install in Cowork
and Claude Code.

### Via ZIP

```bash
./package-plugin.sh operations/bug-triage-agent
```

The script runs the plugin's own validator first and refuses to package a plugin that
fails it. Upload the resulting ZIP via Customize, Browse plugins, Upload custom plugin.

## Spec-driven development

This repository uses [Spec Kit](https://github.com/github/spec-kit). Run the skills
from the repository root:

```
/speckit-constitution   once per repository
/speckit-specify        per feature
/speckit-plan
/speckit-tasks
/speckit-implement
/speckit-converge
```

## License

Apache-2.0. See LICENSE.
