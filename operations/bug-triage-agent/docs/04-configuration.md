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

Tool-name suffixes per source, **including the tracker**, plus `verification` when the
`ci` runner dispatches a workflow. The plugin declares no MCP
servers, so this is the only thing connecting it to a real system. A live source
without a binding fails validation: the adapter cannot be bound, and guessing tool
names is worse than stopping.

The tools can come from anywhere already in the session. The plugin does not care
which provider supplied them.

### `repos`, `routing`

Repositories to search with a note on when each is relevant, and a component-to-team
map used to suggest an assignee. A component with no routing entry produces a
recommendation with no team.

### `queue`

How long a bug may wait for triage. Past its limit the queue marks it **⏰ overdue**
and lists it first, at-risk before the rest. A ticket triaged P1 or P2 with no tracker
activity for `stuck_after_days` is marked **🧊 stuck**.

```json
"queue": {"triage_within_hours": {"at_risk": 4, "default": 48, "by_priority": {"Highest": 8}},
          "stuck_after_days": 7}
```

`by_priority` uses the tracker's own priority values. The shortest limit that applies
wins. Without the section: 24 hours at-risk, 72 otherwise, 7 days.

### `automation` (off by default)

Automatic triage. When `enabled` is true, a scheduler or a tracker event runs
`/bug-triage-agent:triage-auto <team>`, which triages new, changed and overdue bugs
unattended and writes a review digest to `<reports_dir>/auto/`.

```json
"automation": {"enabled": false, "trigger": "schedule", "schedule": "0 * * * *",
               "lookback_hours": 72, "max_per_run": 10, "retriage_changed": true,
               "skip_labels": ["no-auto-triage"], "tracker_write": "none"}
```

| Key | Meaning |
| --- | --- |
| `trigger` | `schedule`: a scheduled task runs it on `schedule` (five-field cron). `event`: a tracker webhook or CI job runs it with the new ticket keys |
| `lookback_hours` | Only bugs created in this window, plus any that are overdue |
| `max_per_run` | Cap per run, 1 to 50. The rest wait for the next run |
| `retriage_changed` | Re-triage a ticket updated since its last triage |
| `skip_labels` | A ticket with one of these is never auto-triaged |
| `tracker_write` | Always `none`. Automatic triage never writes to the tracker; a person posts from the digest |

Set it up with `/bug-triage-agent:triage-config <team> automation`, which also offers to
create the schedule. A run checks `enabled` first, so turning it off stops a scheduled
task that is still in place.

### `verification` (off by default)

Checks that a workaround works before the report recommends it. The runner decides
where:

| Runner | Use when | Section |
| --- | --- | --- |
| `http` | You have a hosted preview or staging deployment | `http.base_url` (https), `allow_methods`, `headers_from_env` |
| `docker` | You run the app locally in containers | `docker.start`, `docker.stop`, `docker.base_url` (localhost), `cwd`, `wait_seconds` |
| `ci` | Your checks run in CI | `ci.workflow`, `ci.ref`, and `tool_bindings.verification.dispatch` |
| `command` | You have your own test command | `command.run` with `{scenario}` for the scenario file; exit 0 passes |

```json
"verification": {"enabled": true, "runner": "docker", "environment": "local",
  "docker": {"base_url": "http://localhost:3000", "start": "docker compose up -d",
             "stop": "docker compose down", "allow_methods": ["GET"]}}
```

Guards that no scenario can override: `environment` must be `preview`, `staging` or
`local`, never `production`; methods default to `GET`; a step can only reach the
configured base URL; commands come from this config, never from a ticket; header values
are read from environment variables named in `headers_from_env`, never stored.

The triage writes `<TICKET>.scenario.json` from the ticket's reproduction steps and the
workaround. Results: ✅ verified, ❌ did not work (the workaround then does not count as
practical for the rubric), ⚠️ bug not reproduced (proves nothing), 🔴 error.

### `comments`

The ticket's own comment thread is read, after a script drops the noise. Optional:

```json
"comments": {"bot_authors": ["Automation for Jira"], "staff": ["*@example.com"],
             "max_fetch": 50, "max_kept": 20}
```

`bot_authors` adds names to the built-in bot detection (names with bot, automation, CI
or noreply). `staff` marks whose comments are always kept, when the tracker does not say.

### `calibration`

`min_overrides` (default 3) and `min_rate` (default 0.3): how many overrides of the same
kind, and what share of the runs they apply to, before `triage-log calibrate` suggests a
change.

### `sources.<s>.provider`

A display name for the system behind each source, shown in the HTML report beside
the source (for example `tracker (Jira)`, `metrics (Grafana Loki · Vercel)`).
`triage-config` sets it from the connector it bound. Optional; without it the report
shows the source name alone.

### `sla`

```json
"sla": {"fix_within": {"P1": "1d", "P2": "5d", "P3": "30d", "P4": "90d"},
        "clock": "created", "business_days": false}
```

Off unless `fix_within` is set. Each defect gets a fix-by date: when the clock starts
(`created`, the ticket, or `triaged`) plus its priority's time, in hours or days, with
weekends skipped when `business_days` is true. The report, trace, fix brief and batch
table show it as on track, due soon (a quarter of the time left), breached, or met (a
fix deployed in time); the queue flags triaged bugs that are due soon or breached. It
never changes the priority. The `demo` config sets example values.

### `risks`

```json
"risks": {"terms": {"payment": ["escrow", "held balance"]}, "off": ["performance"]}
```

Defects are tagged with named risks (security, payment, data integrity, compliance,
availability, silent failure, customer communication, performance) by
`scripts/risks.py`. `terms` adds this team's own words to a type; `off` stops a type
from being tagged. Risks never change the priority by themselves.

### `human_review`

```json
"human_review": {"enabled": false, "risk_types": ["security", "payment"],
                 "min_level": "reported", "reviewers": ["Priya (security)", "*@fin.example.com"]}
```

**Off by default.** Every tracker post already needs a person's yes. Turn this on to
go further for chosen risks: a defect tagged with one of `risk_types` (at `min_level`
or surer) is held for a person's *decision*. Its report, trace and fix brief open
with who must decide and why, automatic triage lists it under "Needs a person", the
queue shows 👤 until it is reviewed, and nothing is posted or handed to a fix agent
until a reviewer confirms by name. `reviewers` is shown in the report; empty means any
person. Change it with `triage-config <team> review`.

### `links`

```json
"links": {"code": "https://code.example.com/{owner}/{repo}/blob/{ref}/{path}#L{line}",
          "ticket": "https://tracker.example.com/browse/{key}",
          "log_query": "https://metrics.example.com/explore?q={query}&from={from}&to={to}"}
```

URL templates for evidence links, used when a tool returns no URL. Kinds and
placeholders: `code` {owner} {repo} {ref} {path} {line}; `commit` {owner} {repo} {sha};
`release` {owner} {repo} {version}; `pr` {owner} {repo} {number}; `ticket` {key};
`log_query` {query} {from} {to}.

`log_query` opens a metrics or log query in the metrics tool over the evidence window.
`{query}` is filled JSON-escaped and URL-encoded, so it can sit inside an encoded JSON
parameter; `{from}` and `{to}` are epoch milliseconds. A result link that carries a
`query` (with `from` and `to` as ISO times) is always rebuilt from this template, even
when a tool returned a URL: deep-link tools can emit an older URL shape that opens an
empty query. `python3 scripts/links.py --check <config>` fills every template with sample
values. The `demo-live` config carries a working `log_query`.

### `output`

```json
"output": { "reports_dir": "triage-reports", "write_report": "always",
            "report_format": "html", "run_trace": "file",
            "theme": { "accent": "#0F766E", "accent_dark": "#7DD3C4" } }
```

`report_format` picks the report files: `html` (default) writes only
`<TICKET>-report.html`, `md` only `<TICKET>.md`, `both` writes the two, and `agent`
writes no report for people: only the result file and, for defects, the fix brief,
whose YAML front matter a fix agent reads (`fault`, `hypothesis`, `acceptance`,
`fix_status`, the branch). Use `agent` for a pipeline that feeds a fix agent. Markdown is
useful to paste into a PR, a chat thread or a repo, or to hand to another agent; ask
for it in a single run ("markdown too") without changing the config. The fix brief is
always markdown. `run_trace: never` turns the HTML off, so the markdown is written
instead. The fix brief is written for every defect in every mode.

The batch page follows the same setting: `batch-<date>.html` for `html` and `both`,
`batch-<date>.md` for `md` and `both`, and only `clusters.json` for `agent`.

Every run, in every mode, refreshes `<reports_dir>/briefs.json`, the handoff index
(`scripts/brief_index.py`). A fix agent reads it instead of the folder: `ready` lists
the briefs it may pick up, in priority then fix-by order, with the branch and the fault
line; `held` lists the rest with a reason (`human_review` until someone records a
review, `already_fixed`, `locate_first` for weak location evidence, `no_brief`).

`theme` is optional. `accent` sets the accent colour in light mode and `accent_dark` in
dark mode (it defaults to `accent`). Both are `#RRGGBB`; the validator rejects any other
key or value. Everything else about the look lives in `assets/report-theme.css`, which
every HTML page inlines. Edit that file to change the look for every team.

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
