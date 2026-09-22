# Configuration

A team owns exactly one file: `teams/<team>.json`. Nothing else. The authoritative
list of allowed keys is [`teams/team-config.schema.json`](../teams/team-config.schema.json);
this page explains what each one is for and which ones bite.

## Getting started

```bash
cp teams/team-config.example.json teams/<your-team>.json
# set tracker project key and instance id, then:
python3 scripts/validate_config.py teams/<your-team>.json
```

`team.id` must match the filename. The validator enforces it, because the `--team`
argument resolves against `team.id`.

## Shipped configs

| File | Purpose |
| --- | --- |
| `team-config.example.json` | Copy-and-fill starting point |
| `team-config.schema.json` | The contract, not a config |
| `demo.json` | All five sources on fixtures. Needs no connectors |
| `demo-gc.json` | Second team, fewer sources, different priority names. The consistency proof |
| `bta.json` | Zero-setup tier example, tracker and releases only |
| `reference-full.json` | All five sources live, generic placeholders |

## Key reference

### `tracker`

| Key | Notes |
| --- | --- |
| `project_key` | Which project to query |
| `instance_id` | Instance id. **Blocks everything live until set** |
| `site`, `board_id` | Used by the readiness check |
| `priority_names` | Maps P1 to P4 onto this project's own values. This is how two teams share one rubric while their trackers call the levels different things |
| `at_risk_labels` | Labels triggering the P2 floor. Match your own conventions |
| `voc_destination` | Where voice-of-customer items route. **A disposition with nowhere to go is useless** |

### `sources`

One entry per source: `mode` of `live`, `fixture` or `off`, plus `fixture` naming a
path when in fixture mode. A directory path resolves to `<dir>/<TICKET-KEY>.json`; a
missing file resolves to `unavailable`, identical to a switched-off source.

`tracker` may not be `off`. It is the minimum viable source and the validator rejects it.

### `release_correlation`

| Key | Notes |
| --- | --- |
| `cadence_days` | Your release interval |
| `lookback_days` | How far back to look. **Default two cycles** |
| `manifest_sources` | Ordered adapter list, first wins per field, later ones enrich |
| `wiki`, `github` | Per-adapter settings |
| `manual_file_path` | Required if `manual_file` is in the adapter list |

Order the adapters to match your ecosystem. An tracker-and-wiki-heavy org starts with
`tracker_fixversion` then `wiki_release_notes`, neither of which needs a connector
beyond the tracker. Add `vcs_tag` when you want file-level resolution, which is
what upgrades area overlap from plausible to matched.

A lookback shorter than two cycles earns a warning. Under a monthly cadence, bugs
surface days or weeks after the release that caused them.

### `regression`

`baseline_days`, `baseline_method`, `spike_ratio`, `deploy_window_hours`.

The baseline is a **rolling median**, not the prior day. Prior-day baselines produce
false regressions every Monday. A `deploy_window_hours` shorter than one release cycle
earns a warning, because it will miss most regressions.

### `warehouse` / `warehouse`

`database`, `schema`, and `queries`: a map of named read-only templates. **All
product-specific SQL lives here**, never in a shared skill. The validator rejects any
query containing a write verb or not beginning with `SELECT` or `WITH`.

### `tool_bindings` / `tool_bindings`

Tool-name suffixes per non-tracker source. Tool names differ between MCP deployments,
so they are configuration rather than constants. A live non-tracker source without a
binding fails validation: the adapter cannot be bound and guessing tool names is worse
than stopping.

### `repos`, `routing`

Repositories to search with a note on when each is relevant, and a component-to-team
map used to suggest an assignee. A component with no routing entry produces a
recommendation with no team.

## Credentials

None, ever. The validator scans recursively for credential-shaped keys and fails on
them. Authentication lives in the MCP host.

## Going live from the demo

```json
"sources": { "tracker": {"mode":"live"}, "releases": {"mode":"live"},
             "metrics": {"mode":"live"}, "warehouse": {"mode":"live"},
             "code": {"mode":"live"} }
```

Then fill `instance_id`, the tool bindings, the query templates, `repos` and the release
adapters. **No skill file changes.** Run `/triage-doctor`.

## Two validator behaviours

```bash
python3 scripts/validate_config.py --all          # exit 0, placeholders reported as UNCONFIGURED
python3 scripts/validate_config.py teams/bta.json # exit 1 on any placeholder
```

The suite stays green so it can gate CI; a named config refuses to certify on an
unfilled value. A validator that reports green on a placeholder is worse than none;
one that is permanently red gets ignored.
