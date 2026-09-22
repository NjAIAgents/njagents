# Configuration

A team owns exactly one file: `<team>.json`. Nothing else. The authoritative list of
allowed keys is [`teams/team-config.schema.json`](../teams/team-config.schema.json);
this page explains what each one is for and which ones bite.

## Getting started

Run the setup command and answer the questions:

```
/bug-triage-agent:triage-config <your-team>
```

It finds the connectors already in your session, reads project keys, priority names
and labels from them rather than asking you to type them, proposes each value, shows
the whole file before writing, and runs the validator on it. It never asks for
credentials: access comes from the connectors you have authorised in the app.

A triage run that finds no config for its team offers this command instead of
stopping.

### Changing one section

Name the section after the team to change only that part. Everything else stays as it
is, and you see a diff before anything is written:

```
/bug-triage-agent:triage-config demo-live github      code search + release tags from your code host
/bug-triage-agent:triage-config demo-live code        code search only
/bug-triage-agent:triage-config demo-live releases
/bug-triage-agent:triage-config payments metrics
```

Sections: `tracker`, `releases`, `metrics`, `warehouse`, `code`, `routing`, `output`,
`members`, `default`. `repo`, `vcs` or the name of your code host (GitHub, GitLab,
Bitbucket) sets up code search and the release-tag adapters together. If the team's
config exists only in the plugin, it is copied to your folder first.

## Which team a run uses

`--team` is optional. The run header states which rule chose the team:

| Order | Rule | Notes |
| --- | --- | --- |
| 1 | `--team <id>` | Always wins |
| 2 | `$CLAUDE_TRIAGE_TEAM` | |
| 3 | **The tickets' project key** matched against `tracker.project_key` | The normal case. `DEMO-7` picks the team whose project is `DEMO`. Tickets from two projects in one run are refused |
| 4 | The signed-in user's email against `team.members` | Only without a ticket, e.g. the queue. An exact address beats a `*@domain` entry. Matched locally, never stored |
| 5 | `team.default: true` in your folder, else the only config in your folder | Your folder always outranks the plugin |
| 6 | The plugin's `demo` config, marked `team.default` | Only when nothing above decides, so a first run works with no setup |

If none of these decides, the run stops and asks.

Configs still holding placeholder values are never picked implicitly.

### Connectors you have but the team does not use

A triage only reads the sources the team config binds. If a matching connector is
connected in your session but that source is `off` (say a metrics connector while
metrics is off), the run prints one **Available but off** line under the header and
`triage-doctor` lists it, both pointing at `/bug-triage-agent:triage-config <team>`.
Nothing is enabled automatically: which systems a team's triage reads is the team's
decision, and the same ticket should triage the same way whoever runs it. When two
candidates tie at the same rule, the run stops and asks rather than guessing.

A project shared by two teams, split by component, is a tie at rule 3 today. Pass
`--team` for those until component-level matching exists.

## Where the file lives

The plugin looks for a team in this order, first match on `team.id` wins:

| Order | Location | Use it for |
| --- | --- | --- |
| 1 | `$CLAUDE_TRIAGE_CONFIG_DIR` | A shared config folder outside any one repo. **Claude Code only**; Cowork's shell does not see it |
| 2 | `triage-teams/` in the working folder, or one or two levels below it | **The default.** Committed to the team's own repository and reviewed like code. The deeper look covers sandboxed shells that start above the user's folder |
| 3 | `teams/` inside the plugin | The two demo configs and the example only |

### Setting it up per client

**Cowork.** Put the file at `triage-teams/<team>.json` inside a folder you connect to the
session. It is found at the top of that folder or one or two levels below it, so both
of these work when you connect `~/workspace`:

```
~/workspace/triage-teams/whodunit.json             top level
~/workspace/whodunit/triage-teams/whodunit.json    inside the repo, one level down
```

The second is usually best: the file lives in the team's repo, is reviewed and shared
through git, and you can still connect the parent workspace and triage for several
teams from one place.

`CLAUDE_TRIAGE_CONFIG_DIR` does **not** work in Cowork. The triage scripts run in an
isolated shell that does not inherit your Mac's environment, and it cannot see a folder
you have not connected, so a variable pointing at `~/triage-configs` would neither be
read nor lead anywhere visible.

Three things to watch:

- Connect the same folder every time. A different folder means the config is not found.
- A file loose in a workspace root is not in git: only you have it, and nobody reviews
  changes to it.
- Never rely on a session's `outputs` folder. It belongs to that session, not to a
  folder you will reconnect.

**Claude Code (terminal).** Either the same `triage-teams/` folder in the repo you run
from, or a dedicated folder named by `CLAUDE_TRIAGE_CONFIG_DIR`, set in your shell
profile:

```bash
echo 'export CLAUDE_TRIAGE_CONFIG_DIR="$HOME/triage-configs"' >> ~/.zshrc
source ~/.zshrc
```

or only for Claude, in `~/.claude/settings.json`:

```json
{ "env": { "CLAUDE_TRIAGE_CONFIG_DIR": "/Users/<you>/triage-configs" } }
```

Files in that folder sit directly in it, `~/triage-configs/whodunit.json`, with **no**
`triage-teams/` subfolder.

**Either way, check it.** `/bug-triage-agent:triage-doctor <team>` and every run
header print the config file that was loaded and which rule chose the team.

Reports go to `<working folder>/triage-reports/` and the audit log to
`<working folder>/triage-logs/triage-log.jsonl` (or `$CLAUDE_TRIAGE_LOG`). Nothing the
agent writes goes inside the plugin.

Do not put a team's config in the plugin's `teams/`. An installed plugin is read-only
and is replaced on every update, so a file there is lost at the next release. The run
header and `triage-doctor` both print which file was loaded, so a local copy
shadowing a shipped one is never a surprise.

To edit by hand instead:

```bash
mkdir -p triage-teams
cp <plugin>/teams/team-config.example.json triage-teams/<your-team>.json
python3 <plugin>/scripts/validate_config.py triage-teams/<your-team>.json
```

`team.id` must match the filename. The validator enforces it, because the `--team`
argument resolves against `team.id`.

## Shipped configs

| File | Purpose |
| --- | --- |
| `team-config.example.json` | Copy-and-fill starting point |
| `team-config.schema.json` | The contract, not a config |
| `demo.json` | All five sources on recorded fixtures. Needs no connectors. The plugin's default team, and `BUG-*` tickets resolve to it by project key |
| `demo-live.json` | The live demo: the synthetic `DEMO` Jira project, metrics bound once seeded. `DEMO-*` tickets resolve to it by project key |

A team's own config never goes here. It lives in the team's repo under `triage-teams/`.

## Key reference

### `tracker`

| Key | Notes |
| --- | --- |
| `project_key` | Which project to query |
| `instance_id` | Instance id. **Blocks everything live until set** |
| `host`, `board_id` | Used by the readiness check |
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
| `wiki`, `vcs` | Per-adapter settings |
| `manual_file_path` | Required if `manual_file` is in the adapter list |

Order the adapters to match your ecosystem. A tracker-and-wiki-heavy org starts with
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

### `warehouse`

`database`, `schema`, and `queries`: a map of named read-only templates. **All
product-specific SQL lives here**, never in a shared skill. The validator rejects any
query containing a write verb or not beginning with `SELECT` or `WITH`.

### `tool_bindings`

Tool-name suffixes per source, **including the tracker**. The plugin declares no MCP
servers, so this is the only thing connecting it to a real system. A live source
without a binding fails validation: the adapter cannot be bound, and guessing tool
names is worse than stopping.

The tools can come from anywhere already in the session. The plugin does not care
which provider supplied them.

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
python3 scripts/validate_config.py teams/team-config.example.json  # exit 1: placeholders unset
```

The suite stays green so it can gate CI; a named config refuses to certify on an
unfilled value. A validator that reports green on a placeholder is worse than none;
one that is permanently red gets ignored.
