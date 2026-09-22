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

### Claude Code and Cowork

Add the marketplace, then install:

1. Customize, Browse plugins, Add marketplace
2. `github.com/NjAIAgents/njagents`
3. Sync, then install `bug-triage-agent`

### Cursor

Cursor reads `.cursor-plugin/plugin.json` and discovers `skills/`, `agents/`,
`commands/` and `mcp.json` by folder. Install from a team marketplace pointed at the
same repository, or drop the plugin directory in `~/.cursor/plugins/local/` to try it.

### Codex and ChatGPT

Codex reads the root `plugin.json`, which conforms to the Agent Plugins standard. It
loads `skills/` and MCP servers; `agents/` and `commands/` are not loaded there. See
[`STATUS.md`](../STATUS.md) for what that changes and what it does not.

**None of these three has actually been installed and run yet.** The compatibility is
reasoned from each client's manifest and discovery rules, not observed. Expect the
first install to surface something.

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

```bash
python3 scripts/validate_config.py teams/<your-team>.json   # named form, fails on placeholders
/triage-doctor <your-team>
```

Then try the demo, which needs no connectors at all:

```
/triage BUG-4830
```

Compare against [`fixtures/expected-outcomes.md`](../fixtures/expected-outcomes.md).
Note that file is a *prediction* derived from the rubric, not a recorded transcript.
