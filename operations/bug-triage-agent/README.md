# bug-triage-agent (BTA)

Bug triage agent. Disposition before priority, release correlation over a full release
cycle, workaround discovery, and a shared rubric that teams configure rather than fork.

## Why it is shaped this way

- **Disposition first.** A ticket is classified defect, expected behaviour, config or
  data, duplicate, or voice-of-customer *before* any priority is assigned. Scoring a
  non-defect is worse than not triaging it.
- **One rubric, many configs.** `skills/` and `reference/` are shared and versioned.
  Each team owns exactly one config file, kept in its own repo under `triage-teams/`.
  Forked rubrics were the reason the
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
| [Examples](docs/09-examples.md) | Worked runs to copy, with expected output |

## Quick start

Install to first triage in seven steps: see the
[Quick start](../../README.md#quick-start-bug-triage-agent) in the repository README.

## Install

Add the marketplace, install the plugin, authorize the connectors your team uses.
Credentials live in the MCP host, never in this repo.

**Where it runs:** Cowork and Claude Code, where the whole plugin is available to the
session. Not in a regular Chat: there a plugin syncs only its skill folders, so the
scripts, rubric and team configs are absent and the triage stops at its first step
rather than improvise.

## Configure

```
/triage-config <your-team>   # asks a few questions, writes triage-teams/<your-team>.json
/triage-doctor <your-team>   # checks every source is reachable and bound
```

The config is written to `triage-teams/` in your own repository, not into the plugin:
an installed plugin is read-only and is replaced on every update. Commit the file so
your team shares it. See [`docs/04-configuration.md`](docs/04-configuration.md) for the
lookup order and every key.

`teams/team-config.example.json` ships with placeholder values and will not certify
until those are filled in. `--all` reports them as `UNCONFIGURED` and still exits zero,
so the suite can gate CI; naming a config exits non-zero.

### Zero-setup tier

Leave every source except `tracker` and `releases` set to `off`. You still get related
tickets, duplicate detection, release correlation from fix versions, disposition, and
workaround discovery from resolved tickets. Add the metrics source, the warehouse and code search
later by flipping a mode. `/triage-doctor` lists which classification questions each
`off` source costs you.

### Going live from the demo

```bash
# in teams/<team>.json
"sources": { "tracker": {"mode":"live"}, "releases": {"mode":"live"},
             "metrics": {"mode":"live"}, "warehouse": {"mode":"live"},
             "code": {"mode":"live"} }
```

Then fill `tracker.instance_id`, `tool_bindings` for each non-tracker source,
`warehouse.queries`, `repos`, and the `release_correlation` adapters. Run
`/triage-doctor`. No skill file changes.

Tool names differ between MCP deployments, which is why they are configuration.
Read-only is enforced outside the prompt: a read-only account on each source, the
validator's SQL check, and per-ticket confirmation before any tracker write. The
subagents themselves run with all tools; an earlier allowlist enforced nothing.

## Release manifest adapters

`release_correlation.manifest_sources` is an ordered list. Match it to your ecosystem.

| Adapter | Needs | Gives |
| --- | --- | --- |
| `tracker_fixversion` | tracker only | Version, date, components, issue keys |
| `wiki_release_notes` | tracker only | Human-written "what changed", areas |
| `vcs_tag` / `vcs_pr` | GitHub | Files touched, merged pull requests |
| `manual_file` | Nothing | A team-maintained list, for orgs with no queryable release record |

tracker-and-wiki-heavy orgs should start with the first two, which need no connector beyond
the one tracker already requires.

## Use

Step-by-step runs with expected output: [`docs/09-examples.md`](docs/09-examples.md).

```
# live: the team is found from the ticket's project key
/triage ABC-12
/triage-doctor

# what still needs triage
/queue

# the fixture demo: recorded data, needs no connectors
/triage BUG-4830
/triage BUG-4830 BUG-4844 BUG-4851

# the live demo: synthetic Jira project DEMO
/queue demo-live
/triage DEMO-7
/triage DEMO-7 DEMO-8 DEMO-9
/release-impact DEMO-7
/triage-doctor demo-live
/triage-review DEMO-8 voice_of_customer "held balance release is by design"
```

## Layout

```
.claude-plugin/plugin.json    also plugin.json and .cursor-plugin/plugin.json, kept in step
commands/                     triage, queue, triage-log, triage-config, release-impact, triage-doctor, triage-review
skills/
  bug-triage/                 orchestrator
  data-sources/               source contract, adapters, degradation rules
  triage-disposition/         defect vs expected vs VoC vs config vs duplicate
  release-correlation/        which release touched this area
  workaround-finder/          what unblocks the customer today
  triage-priority/            P1-P4, escalation caps, confidence
  triage-config/              builds a team config by conversation
  triage-queue/               open bugs, what still needs triage
  triage-readiness/           behind /triage-doctor
  triage-history/             behind /triage-log
  triage-override/            behind /triage-review
agents/                       parallel enrichment, one per source
reference/                    SHARED: rubric, taxonomy, calibration, output templates
teams/                        the two demo configs, schema, example
fixtures/                     recorded envelopes and worked results: rubric test data, validated in CI
scripts/                      run_header, render_trace, render_queue, triage_log, validate_config

In your own folder, never in the plugin:
triage-teams/<team>.json      the only file a team edits
triage-reports/               reports and run traces
triage-logs/triage-log.jsonl  every recommendation and every human override
```

## Calibration

The taxonomy is v0, built from interviews with the people who triage today. See
`reference/taxonomy-calibration.md` for the interview guide, the calibration set, and
the monthly override review that improves it.

## Guardrails

- No automatic tracker writes. Posting a comment or changing a field needs explicit
  per-ticket confirmation.
- the warehouse queries are read-only and come from the team config. `validate_config.py`
  rejects any write verb.
- No credentials in this repo. `validate_config.py` fails on credential-shaped keys.
- Any output built on a fixture is banner-marked `DEMO DATA`.
- Live mode never silently falls back to fixtures.
