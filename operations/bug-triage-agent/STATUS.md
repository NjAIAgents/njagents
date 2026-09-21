# Status

An honest account of what is built and what is not.

## Built and verified

- Shared instruction layer: orchestrator, disposition taxonomy, priority rubric with
  escalation caps, release correlation, workaround finder, source contract and adapters.
- Four team configs under `teams/`, one schema, one worked example.
- 14 fixtures, each a complete envelope validated against the live source contract.
- `scripts/validate_config.py`: config validation, contract validation, read-only SQL
  enforcement, credential-shaped key detection, placeholder detection.

## Built but unexercised

Almost everything above is **instructions the model follows at runtime**, not code that
executes deterministically. It is written but has never been run.

`fixtures/expected-outcomes.md` is a specification derived from the rubric, **not a
transcript of a real run**. Expect the first execution to surface skipped stages or the
right answer reached by the wrong reasoning.

## Not built

| Missing | Why it matters |
| --- | --- |
| Event trigger | The agent runs when a person types a command. The requirement is that it acts when a ticket is submitted. Needs real code. |
| Log writer and accuracy report | `logs/` is empty. The format is specified; nothing writes it. Needs real code. |
| Validated taxonomy | The shipped disposition taxonomy is a construction, not any organization's actual judgment. Replace it via interviews plus a changelog-derived benchmark. |
| Live connection | No credentials have been used. Tool-name bindings for non-tracker sources are informed guesses. |

## Client compatibility

Three manifests ship, all agreeing on name and version. The skills are the portable
core and exist in one copy.

| Component | Claude | Cursor | Codex / ChatGPT |
| --- | --- | --- | --- |
| `skills/` (6) | yes | yes | yes |
| `reference/`, `teams/`, `fixtures/` | yes | yes | yes |
| MCP servers | yes | yes | yes |
| `commands/` (4) | yes | yes | **no** |
| `agents/` (4) | yes | yes | **no** |

### Degradations on Codex and ChatGPT

Both are consequences of Codex having no subagent concept. Neither is a correctness
problem, but both should be understood before promising parity.

**Enrichment runs sequentially.** Stage 3 dispatches four subagents in one batch on
Claude and Cursor. Without them the orchestrator queries each source in turn, so wall
time on the slowest path is roughly four times higher.

**The read-only guarantee loses a layer.** The four agent files carry tool allowlists
matching read-shaped verbs only, which is what makes "cannot write to the tracker or
run DDL" enforced rather than merely stated. Codex has no equivalent, so there the
guarantee rests on the read-only service account and the validator's SQL check alone.
Defence in depth minus one layer.

**Invocation differs.** `/triage BUG-4830` on Claude and Cursor; on Codex, invoke the
plugin or skill by name. The commands are thin wrappers over the skills, so no
capability is lost.

### MCP server urls are placeholders, not variables

An earlier version used `${DATADOG_MCP_URL}` style placeholders in `url` fields. No
client expands environment variables there, so those entries would have shipped
broken. They are now literal `REPLACE_WITH_` placeholders that the validator reports
as unconfigured. Only the tracker entry is needed for the zero-setup tier.

## Rough completeness

Demo: about 85 percent, the remainder being "run it and fix what breaks".
Production: closer to 40 percent.

## Do not

Rewrite the instruction layer before running it. It is a first draft to be corrected by
evidence, not a spec to reimplement.
