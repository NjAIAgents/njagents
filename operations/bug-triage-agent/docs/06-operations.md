# Operations

Running this for one team, then several.

## The validator is a build gate

```bash
python3 scripts/validate_config.py --all            # CI form
python3 scripts/validate_config.py teams/<team>.json # pre-go-live form
```

It checks, and fails on:

- config against schema; every source declares a mode; `tracker` is not `off`
- **placeholders in a named config**, so a team cannot go live on `REPLACE_WITH_`
- every fixture against its source's data shape, **with no special cases**
- a release carrying file-level detail without a version-control adapter
- warehouse queries that are not read-only
- credential-shaped keys anywhere
- the three manifests agreeing on name and version
- `${VAR}` in an MCP url, which no client expands
- `mcp.json` and `.mcp.json` differing

It warns on a lookback under two release cycles, a deploy window under one cycle, and
a baseline under five days.

**If the validator ever needs a special case to let a fixture pass, stop.** That means
demo and production have diverged and the contract is no longer enforced.

## Packaging

```bash
cd <repo root>
./package-plugin.sh operations/bug-triage-agent
```

Runs the validator first and refuses to package a failing plugin. Strips `.specify/`,
`.claude/`, `.git`, runtime `.jsonl` logs, `local-*.json` team configs and OS noise.

Spec Kit lives at the repository root, never inside a plugin. An archive containing
`.specify/` is a packaging defect.

## The audit log

One JSON line per run to `logs/triage-log.jsonl`, written for **every** run including
those stopping at the information or disposition gate.

```json
{"ts":"","ticket":"","team":"","modes":{},"disposition":"","priority":null,
 "confidence":"","escalations":[],"unanswered":[],
 "human_override":null,"override_reason":null}
```

`human_override` is filled later by `/triage-review`. The gap between recommendation
and final decision is the measurement.

Implemented as `scripts/triage_log.py`:

```bash
triage_log.py append --ticket BUG-1 --team demo-live --disposition defect \
    --priority P2 --confidence high --modes tracker=live,metrics=off
triage_log.py override --ticket BUG-1 --priority P3 --reason "workaround exists"
triage_log.py report --days 30
```

`append` refuses a non-defect carrying a priority, so the disposition gate is enforced
in the log as well as in the pipeline. `override` records the human's call **without
altering the recommendation**, because the gap between them is the measurement.
`report` gives agreement per disposition class and priority-within-one-level,
separately.

## Weekly and monthly rhythm

**Weekly**: disposition accuracy and priority-within-one-level, reported *separately*.
An overall number hides the case that matters: a taxonomy 90 percent right overall but
wrong on every voice-of-customer item has not captured the judgment you wanted.

**Monthly**: review override patterns per
[`reference/taxonomy-calibration.md`](../reference/taxonomy-calibration.md).

| Pattern | Means | Do |
| --- | --- | --- |
| One disposition over-applied | Rule too loose | Require more evidence |
| One consistently missed | Evidence not being searched for | Add a search step |
| Overrides cluster in one component | Component knowledge missing | Add to team config, not the shared taxonomy |
| Overrides cluster on one reviewer | Two people disagree on policy | Escalate. A tool cannot resolve a policy disagreement |

That last row matters most. Where experts genuinely disagree, the agent should say so
and route to a person rather than pick a side confidently.

`triage_log.py calibrate` runs this review for you and prints each pattern it finds with
the change it suggests; `triage_log.py dashboard --out triage-reports/accuracy.html`
draws the same data as a page with tabs. Pass `--area` on `append` and `--reviewer` on
`override` so the last two rows can be detected. Both commands only suggest: rubric
and taxonomy changes go through review like code, config changes through
`triage-config`. A weekly trend that falls after a change means the change made things
worse; revert it.

## Automatic triage in operation

- It never writes to the tracker. The digest in `triage-reports/auto/` is the output.
- A run takes a lock (`triage-logs/auto-triage.lock`) and releases it when the digest is
  written; a second run within an hour skips. Delete a stale lock if a run crashed.
- Automatic runs are logged with the flag `auto`, so accuracy can be compared between
  automatic and manual triage.
- To stop it, set `automation.enabled` to false. A scheduled task left in place then
  does nothing.

## Onboarding a second team

1. Copy `team-config.example.json`, set `team.id` to match the filename
2. Start at the zero-setup tier: tracker and releases only
3. Validate the named config, run `/triage-doctor`
4. Run ten real tickets and review every one before anyone relies on it
5. Add connectors when the team wants the questions they answer

**Do not** copy the rubric, the taxonomy or the output format. If a team believes it
needs a different rubric, that is a conversation about the shared core, not a fork.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| Validator exits 1 on a named config | A `REPLACE_WITH_` placeholder. Intended |
| `--all` green but a team fails | Correct. `--all` treats placeholders as non-fatal so CI can pass |
| Live source returns `error` | Check the tool binding. Names differ between MCP deployments |
| Everything says `DEMO DATA` | A source is still in fixture mode |
| Priorities look too high | Check the escalation classes. One per class, capped at two, never P1 by escalation |
| Non-defect got a priority | A real bug. The disposition gate should stop before scoring |
| Release correlation always names a release | Suspicious. It should report honest negatives |
