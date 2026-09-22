---
name: data-sources
description: Resolves every enrichment source (tracker, releases, the metrics source, the warehouse, code search) to live MCP calls, recorded fixtures, or a typed unavailable result. Load this before any enrichment. It defines the source contract that the rubric consumes, so live and fixture modes are indistinguishable downstream.
---

# Data sources

Every source returns the **same envelope** whether it came from a live MCP call or a
recorded fixture. Nothing downstream of this file knows or cares which. That is the
whole point: switching a team from demo to production is a change to
`team-config.json`, never a change to a skill.

## Envelope (mandatory, all sources)

```json
{
  "source": "tracker | releases | metrics | warehouse | code",
  "mode": "live | fixture | off",
  "status": "ok | partial | unavailable | error",
  "as_of": "2026-09-21T14:22:00Z",
  "latency_ms": 840,
  "data": {},
  "notes": []
}
```

Rules:

- `status: "unavailable"` means the source is switched off or not configured. This is
  a **normal** state, not a failure.
- `status: "error"` means it was configured and the call failed. Always surface the
  error text in `notes`. Never silently downgrade an error to unavailable.
- `data` must match the per-source shape below **exactly** in every mode. A fixture
  that does not validate against the shape is a bug in the fixture.
- Never invent a field you could not retrieve. Omit it and add a note.

## Mode resolution

Read `teams/<team>.json`. For each source:

1. `mode: "live"` -> call the adapter below. On failure, return `status: "error"`, do
   not fall back to fixtures. Silent fallback in production is how people end up
   trusting fake numbers.
2. `mode: "fixture"` -> resolve the recording from `sources.<name>.fixture`. When that
   path is a **directory**, the file is `<dir>/<TICKET-KEY>.json`; when it is a file,
   that file is the whole envelope. A ticket with no recording resolves to
   `status: "unavailable"`. Stamp `"mode": "fixture"` so it is visible in every output.
3. `mode: "off"` -> return `status: "unavailable"` immediately. No call, no cost.

If **any** source is in fixture mode, the final output must carry a banner:
`DEMO DATA - <list of fixture sources>`. Never present fixture numbers as live.

## Live adapters

`tool_bindings` records tool **suffixes**. The full identifier carries a server prefix
generated per session, so a bare suffix is not callable: discover the full identifier
with `ToolSearch` before the first call, and record in `notes` which server served it.
Where two servers expose the same tool set, either is fine.

### tracker

Tool suffixes come from `tool_bindings.tracker`, keyed `get_issue` and
`search_issues`. The tracker is configuration-driven like every other source; it is
not special-cased to one vendor.

What to retrieve, expressed as intent rather than one tracker's query language:

```
ticket             the issue itself
related            issues in the project matching the summary's distinctive nouns,
                   excluding this one, most recently updated first   (limit 10)
                   When more than the limit match, rank by how many distinctive nouns
                   overlap, and prefer a summary match over a description-only match.
                   State the ranking you applied in `notes`; it is a judgement call.
                   Include resolution_notes: the resolution text or closing
                   comment. Without it workaround discovery has nothing to read,
                   and will correctly but uselessly report none found.
duplicates         issues in the same component, created within 180 days, whose
                   summary is close to this one                      (limit 5)
component_history  count of issues in the component resolved in the last 90 days
open_in_component  count currently unresolved in the component

                   If the ticket has **no component set**, these counts cannot be
                   component-scoped. Compute them project-wide, set status to
                   `partial`, and say so in `notes`. Do not present a project-wide
                   count as a component count: the recurring-component escalation
                   would fire on project volume rather than on a hot area. A live run
                   on a project with no components configured produced 6 resolved and
                   30 open, which would have escalated every ticket in the project.
sprint_collision   whether the component has work in an open sprint  -> bool
```

An Atlassian tracker expresses those as JQL, for example
`project = {key} AND component = "{component}" AND resolved >= -90d` for
`component_history`, and `sprint in openSprints()` for `sprint_collision`. A tracker
without a sprint concept returns `false` for `sprint_collision` and notes it; the
rubric treats that as an unanswered question, not as an absent signal.

`data` shape:

```json
{
  "ticket": {"key":"", "summary":"", "description":"", "component":"", "priority":"",
             "labels":[], "reporter":"", "created":"", "fix_versions":[]},
  "related": [{"key":"", "summary":"", "status":"", "resolution":"", "resolved":""}],
  "duplicates": [{"key":"", "summary":"", "similarity":"high|medium|low", "why":""}],
  "component_history": {"resolved_90d": 0, "open": 0},
  "sprint_collision": false
}
```

### releases

Pluggable. `release_correlation.manifest_sources` is an **ordered list**; adapters run
in order, the first to supply a field wins, later ones enrich rather than overwrite.
Align the order with the org's ecosystem. An org that records releases in its
tracker and wiki uses `["tracker_fixversion", "wiki_release_notes", "vcs_tag"]`;
an org that records them in version control puts the vcs adapters first.

Every release object carries `sources[]` naming which adapters contributed, so a
reviewer can see whether a correlation rests on a fix version, a release-note page, or
a git tag.

**`tracker_fixversion`** (baseline, needs nothing but the tracker)
: project versions released inside the lookback window, plus
the tracker's `search_issues`, filtered to each release version (on Atlassian,
`project = {key} AND fixVersion = "{version}"`).
Components come from those issues. Always available when tracker is live, which is what
makes the zero-setup tier work.

**`wiki_release_notes`** (wiki, no extra connector)
: pages in `release_correlation.wiki.space_key` carrying `page_label`. Extract
the version with `title_pattern`, the release date from the page date or a stated
field, and the components and areas from the page body. Use
the suffixes named in `tool_bindings.wiki`, keyed `list_pages` and `get_page`.
Best source for human-written "what changed" text, which often names an area no fix
version records.

**`vcs_tag`** / **`vcs_pr`** (highest resolution)
: release tags matching `tag_pattern` in `release_correlation.vcs.repos`, and the
pull requests merged between consecutive tags. This is the only adapter that yields
`files_touched`, which is what turns area overlap from a guess into a match.

**`manual_file`** (fallback)
: the envelope at `release_correlation.manual_file_path`. For orgs with no queryable
release record, and for the demo. The path is configuration; never hardcode it.

Merge rule: match releases across adapters on the normalized version string. Conflicting
release dates are a note, not an error, and the earliest date wins.

```json
{
  "releases": [
    {"version": "", "released_on": "", "components": [], "issue_keys": [],
     "files_touched": [], "notes_url": null, "sources": ["tracker_fixversion"]}
  ],
  "lookback_days": 60,
  "adapters_run": ["tracker_fixversion", "wiki_release_notes"],
  "adapters_failed": []
}
```

An adapter that fails goes in `adapters_failed` with its error. The envelope status is
`partial`, not `error`, as long as one adapter succeeded.

### metrics

Tool suffixes come from `tool_bindings.metrics` in the team config, keyed
`logs_search`, `metrics_query`, `deploy_events`. Tool names differ between metrics MCP
deployments, so they are configuration, not a constant in this file.

```json
{
  "baseline": {"window_days": 7, "method": "rolling_median", "value": 0},
  "current": {"value": 0, "ratio_to_baseline": 0.0},
  "spike": {"detected": false, "first_seen": null},
  "deploys_in_window": [{"version":"", "at":"", "service":""}],
  "sample_errors": []
}
```

Baseline uses `regression.baseline_method` over `regression.baseline_days`, defaulting
to a rolling median, not the prior day.
Prior-day baselines produce false regressions across weekends.

### warehouse

Read-only. Query templates live in `teams/<team>.json` under `warehouse.queries`, so
no product-specific SQL sits in this shared skill. The tool suffix comes from
`tool_bindings.warehouse.query`.

```json
{
  "affected_accounts": 0,
  "enterprise_accounts": 0,
  "account_names": [],
  "first_seen": null,
  "query_template": "",
  "query_used": ""
}
```

Echo both the template name and the **executed SQL** in `query_used`, so a reviewer
can check exactly what was counted.

### code

A code-search service across repos listed in `repos` in the team config,
restricted to `repos[].key_paths` when that is set. The tool suffix comes from
`tool_bindings.code.search`.

```json
{
  "candidate_paths": [],
  "error_swallowing": [{"path":"", "line":0, "snippet":""}],
  "stubs": [{"path":"", "line":0, "marker":"return true | @ts-ignore | TODO", "snippet":""}],
  "recent_changes": [{"path":"", "pr":"", "merged":"", "release":""}]
}
```

## Degradation rules

This replaces the original "unknown blast radius -> round up" rule, which punished
teams for incomplete setup and drove them off the tool.

| Situation | Behaviour |
| --- | --- |
| Source `off` by config | Skip the questions that depend on it. Do **not** adjust priority. State in the output which questions could not be answered. |
| Source `error` | Same as off, plus surface the error and mark confidence `low`. |
| Blast radius unknown **and** the ticket reports multi-account or systemic symptoms | Round up one level, flag it explicitly. |
| Blast radius unknown and symptoms are single-account | Do **not** round up. Ask the reporter for scope. |

Rounding up is now tied to evidence in the ticket, not to the absence of a connector.

## Audit log

After every run append one JSON line to `logs/triage-log.jsonl`:

```json
{"ts":"","ticket":"","team":"","modes":{"tracker":"live","metrics":"off"},
 "disposition":"","priority":"","confidence":"","escalations":[],
 "human_override":null,"override_reason":null}
```

`human_override` is filled in later when someone changes the call. The weekly accuracy
number comes from this file and is the adoption argument. Do not skip it.
