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

## Rough completeness

Demo: about 85 percent, the remainder being "run it and fix what breaks".
Production: closer to 40 percent.

## Do not

Rewrite the instruction layer before running it. It is a first draft to be corrected by
evidence, not a spec to reimplement.
