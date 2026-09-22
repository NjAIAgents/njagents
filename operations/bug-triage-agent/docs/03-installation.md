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

## MCP servers

`mcp.json` declares four servers. Only the tracker entry has a real URL; the other
three are literal `REPLACE_WITH_` placeholders you edit before enabling that source.

They are placeholders rather than variables on purpose: **no client expands
environment variables in a `url` field**, so a `${METRICS_MCP_URL}` there ships broken.
The validator now rejects that pattern.

Credentials never live in this repository. Each team authorizes with its own, held by
the MCP host.

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
/triage-doctor --team <your-team>
```

Then try the demo, which needs no connectors at all:

```
/triage BUG-4830 --team demo
```

Compare against [`fixtures/expected-outcomes.md`](../fixtures/expected-outcomes.md).
Note that file is a *prediction* derived from the rubric, not a recorded transcript.
