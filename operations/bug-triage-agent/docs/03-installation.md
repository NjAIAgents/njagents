# Installation

## Prerequisites

Only one thing is truly required: **a connection to your issue tracker**. Everything
else is additive. See the zero-setup tier below.

| Source | Needed for | Required? |
| --- | --- | --- |
| Tracker (tracker MCP) | Everything | Yes |
| Release manifest | Release correlation | Uses the tracker; no extra connector |
| Metrics | Regression detection | No |
| Warehouse | Blast radius, enterprise tier | No |
| Code search | Error swallowing and stub detection | No |

## Install per client

The plugin carries three manifests and one copy of everything else.

### Cowork

1. Customize, Browse plugins, Add marketplace
2. `github.com/NjAIAgents/njagents`
3. Sync, then install `bug-triage-agent`
4. Quit and reopen the app. New sessions then load the plugin's commands

Run it in a **Cowork task with a folder connected**, not a regular Chat. A Chat syncs
only the skill folders, so the scripts and configs are missing.

### Claude Code

```
/plugin marketplace add NjAIAgents/njagents
/plugin install bug-triage-agent@njagents
```

Restart Claude Code after installing.

### Updating

Sync the marketplace in Cowork, or `/plugin marketplace update njagents` in Claude
Code, then start a **new** session. A session keeps the plugin version it started
with; the run header's **Agent** line shows which one you have.

### Cursor

Cursor reads `.cursor-plugin/plugin.json` and discovers `skills/`, `agents/`,
`commands/` and `mcp.json` by folder. Install from a team marketplace pointed at the
same repository, or drop the plugin directory in `~/.cursor/plugins/local/` to try it.

### Codex and ChatGPT desktop

Add the marketplace from the same repository (`https://github.com/NjAIAgents/njagents.git`)
in the plugin settings, then install `bug-triage-agent`. They read
`.codex-plugin/plugin.json`, whose `skills` path is what makes the skills load: without
it the plugin installs and appears, but the model has nothing to call. `agents/` and
`commands/` are not loaded there; every command has a skill behind it, so nothing is
lost.

To update, refresh the marketplace first. The app keeps its own copy of the repository
and reinstalls from that copy, so reinstalling alone keeps the old version. See
[`STATUS.md`](../STATUS.md) for what that changes and what it does not.

**Cowork and Cursor are installed and run.** Claude Code uses Cowork's plugin format.
Codex and ChatGPT desktop install the plugin and load its skills since 0.6.4, but a run
has not been completed there. Codex needs a Codex task with a local folder; a regular ChatGPT chat shows the plugin but cannot run its skills.

## Connecting sources

**This plugin declares no MCP servers of its own.** It binds to tools already present
in your session, wherever they come from: an account-level connector, another plugin,
or a local server.

That means there is nothing to "connect" inside the plugin. You connect your providers
the way you normally would, then tell the plugin what their tools are called:

```json
"tool_bindings": {
  "tracker":   { "get_issue": "getJiraIssue", "search_issues": "searchJiraIssuesUsingJql" },
  "metrics":   { "logs_search": "search_logs", "metrics_query": "query_metrics" },
  "warehouse": { "query": "run_query" },
  "code":      { "search": "search_code" }
}
```

`/triage-doctor` checks whether those tool names actually resolve in your session and
names what is missing.

An earlier version declared four servers in an `mcp.json`. That was wrong: it made the
host ask you to create connections **owned by the plugin**, duplicating connectors you
already had, and it listed meaningless names like "warehouse" with a generic icon in
your connector list. Three of them could never connect at all, so every install opened
with failed connections.

`reference/mcp-servers.example.json` keeps those entries as a template if you genuinely
need a dedicated endpoint. Copy it into your own MCP configuration, not the plugin.

Credentials never live in this repository. Each team authorizes with its own.

## The zero-setup tier

The adoption path. Leave every source except `tracker` and `releases` set to `off`:

```json
"sources": {
  "tracker":      { "mode": "live" },
  "releases":  { "mode": "live" },
  "metrics":   { "mode": "off" },
  "warehouse": { "mode": "off" },
  "code":      { "mode": "off" }
}
```

You still get related tickets, duplicate detection, release correlation from fix
versions, disposition and workarounds from resolved tickets. Add connectors later by
flipping a mode.

Crucially, the switched-off sources **do not inflate your priorities**. They cost you
answered questions and some confidence. `/triage-doctor` lists exactly which of the ten
classification questions each `off` source leaves unanswered.

## Verify the install

Try the demo first, which needs no connectors at all:

```
/bug-triage-agent:triage BUG-4830
```

The header should end with **Agent** and the version you installed. Compare the result
with [Examples](09-examples.md) and [`fixtures/expected-outcomes.md`](../fixtures/expected-outcomes.md),
which is recorded from real runs.

Then check your own team:

```
/bug-triage-agent:triage-doctor <your-team>
```
