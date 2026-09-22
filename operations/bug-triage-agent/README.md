# bug-triage-agent (BTA)

Bug triage agent. Disposition before priority, release correlation over a full release
cycle, workaround discovery, and a shared rubric that teams configure rather than fork.

## Why it is shaped this way

- **Disposition first.** A ticket is classified defect, expected behaviour, config or
  data, duplicate, or voice-of-customer *before* any priority is assigned. Scoring a
  non-defect is worse than not triaging it.
- **One rubric, many configs.** `skills/` and `reference/` are shared and versioned.
  Each team owns exactly one file in `teams/`. Forked rubrics were the reason the
  previous design could not deliver one quality bar.
- **Fixtures are recordings of the live contract.** Demo and production run the same
  code path. Switching over is a change to `sources.*.mode`, nothing else.
- **Missing connectors do not inflate priority.** Round-up is tied to evidence in the
  ticket, not to the absence of a data source.

## Documentation

Full documentation is in [`docs/`](docs/README.md). That index also states **where
each rule is defined**, so you never have to guess which file wins.

| | |
| --- | --- |
| [Overview](docs/01-overview.md) | The problem, what it does, why it is shaped this way |
| [Architecture](docs/02-architecture.md) | Stages, shared core, source contract |
| [Installation](docs/03-installation.md) | Per client, and the zero-setup tier |
| [Configuration](docs/04-configuration.md) | Every team config key |
| [Usage](docs/05-usage.md) | Commands, reading the output, overrides |
| [Operations](docs/06-operations.md) | Validator, packaging, logging, troubleshooting |
| [Extending](docs/07-extending.md) | Where a change belongs, adding sources and adapters |
| [Glossary](docs/08-glossary.md) | Terms that mean something specific here |

## Install

Add the marketplace, install the plugin, authorize the connectors your team uses.
Credentials live in the MCP host, never in this repo.

## Configure

```bash
cp teams/team-config.example.json teams/<your-team>.json
# set jira.project_key and jira.cloud_id, then:
python3 scripts/validate_config.py teams/<your-team>.json   # named form: fails on placeholders
/triage-doctor --team <your-team>
```

`teams/bta.json` and `teams/reference-full.json` ship with placeholder values and
will not certify until those are filled in. `--all` reports them as `UNCONFIGURED` and still
exits zero, so the suite can gate CI; naming a config exits non-zero.

### Zero-setup tier

Leave every source except `jira` and `releases` set to `off`. You still get related
tickets, duplicate detection, release correlation from fix versions, disposition, and
workaround discovery from resolved tickets. Add Datadog, Snowflake and code search
later by flipping a mode. `/triage-doctor` lists which classification questions each
`off` source costs you.

### Going live from the demo

```bash
# in teams/<team>.json
"sources": { "jira": {"mode":"live"}, "releases": {"mode":"live"},
             "datadog": {"mode":"live"}, "snowflake": {"mode":"live"},
             "code": {"mode":"live"} }
```

Then fill `jira.cloud_id`, `mcp_tools` for each non-Atlassian source,
`snowflake.queries`, `repos`, and the `release_correlation` adapters. Run
`/triage-doctor`. No skill file changes.

Tool names differ between MCP deployments, which is why they are configuration.
The subagent allowlists match read-shaped verb patterns rather than exact names, so
they do not need editing either.

## Release manifest adapters

`release_correlation.manifest_sources` is an ordered list. Match it to your ecosystem.

| Adapter | Needs | Gives |
| --- | --- | --- |
| `jira_fixversion` | Atlassian only | Version, date, components, issue keys |
| `confluence_release_notes` | Atlassian only | Human-written "what changed", areas |
| `github_tag` / `github_pr` | GitHub | Files touched, merged pull requests |
| `manual_file` | Nothing | A team-maintained list, for orgs with no queryable release record |

Atlassian-heavy orgs should start with the first two, which need no connector beyond
the one Jira already requires.

## Use

```
# live, zero-setup tier (Jira + releases only)
/triage ABC-12 --team <your-team>
/triage-doctor --team <your-team>

# demo, fixture data
/triage BUG-4830 --team demo
/triage BUG-4830 BUG-4844 BUG-4851 --team demo
/release-impact BUG-4830 --team demo
/triage-doctor --team demo
/triage-review BUG-4844 voice_of_customer "held balance release is by design"
```

## Layout

```
.claude-plugin/plugin.json
.mcp.json                     connector declarations, no secrets
commands/                     triage, release-impact, triage-doctor, triage-review
skills/
  bug-triage/                 orchestrator
  data-sources/               source contract, adapters, degradation rules
  triage-disposition/         defect vs expected vs VoC vs config vs duplicate
  release-correlation/        which release touched this area
  workaround-finder/          what unblocks the customer today
  triage-priority/            P1-P4, escalation caps, confidence
agents/                       parallel enrichment, one per source
reference/                    SHARED: rubric, taxonomy, calibration, output templates
teams/                        PER TEAM: the only file a team edits
fixtures/                     recorded envelopes, validated against the contract
scripts/validate_config.py    config and fixture validation
logs/triage-log.jsonl         every recommendation and every human override
```

## Calibration

The taxonomy is v0, built from interviews with the people who triage today. See
`reference/taxonomy-calibration.md` for the interview guide, the calibration set, and
the monthly override review that improves it.

## Guardrails

- No automatic Jira writes. Posting a comment or changing a field needs explicit
  per-ticket confirmation.
- Snowflake queries are read-only and come from the team config. `validate_config.py`
  rejects any write verb.
- No credentials in this repo. `validate_config.py` fails on credential-shaped keys.
- Any output built on a fixture is banner-marked `DEMO DATA`.
- Live mode never silently falls back to fixtures.
