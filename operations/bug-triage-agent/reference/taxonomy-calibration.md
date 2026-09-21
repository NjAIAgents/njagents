# Calibrating the disposition taxonomy

The taxonomy in `disposition-taxonomy.md` is **v0, built from interviews**. There is no
historical record of triage decisions to train it on, so the first version encodes what
the two or three people who currently make these calls actually do, and the override
log corrects it from there.

Treat v0 as a hypothesis with a measurement attached, not as a finished rulebook.

## Step 1: interview, before the pilot

Two or three sessions, 45 minutes each, with the people who currently triage. Work
through **real recent tickets**, not hypotheticals. Abstract questions produce
abstract rules that do not survive contact with a real queue.

For each ticket, ask:

1. What did you call this, and what did you nearly call it instead?
2. What made you sure? Name the document, ticket, config value, or person.
3. What would have changed your mind?
4. How long did it take, and what was slow?
5. Has this exact shape come up before? How often?

Then, across the set:

- Which disposition do people disagree about most? That is where the taxonomy needs
  the sharpest test, and it is usually the defect versus voice-of-customer line.
- What do you check first, and why that?
- What does a ticket look like when you know instantly it is not a defect?
- Which tickets do you route to a person rather than decide yourself, and what is the
  trigger for that?

## Step 2: encode

Turn each recurring rule into a row or a test in the taxonomy. A rule earns its place
only if you can state the evidence it depends on. "You just know" is a signal to keep
digging, not a rule.

Record the interview set as a **calibration set**: 15 to 25 real tickets with the
disposition the expert gave and their stated reason. Store it outside this repo if the
tickets carry customer detail.

## Step 3: measure

Run the agent against the calibration set before the pilot. Report agreement per
disposition, not just overall. A taxonomy that is 90 percent right overall but wrong on
every voice-of-customer item has not captured the judgment that matters.

Target for go-live: no disposition class below 70 percent agreement, and every
disagreement explainable.

## Step 4: improve from overrides

Every human correction goes in through `/triage-review`, which writes
`human_override` to `logs/triage-log.jsonl`. Review monthly:

| Pattern in overrides | What it means | Action |
| --- | --- | --- |
| One disposition consistently over-applied | The rule is too loose | Add a required piece of evidence |
| One consistently missed | The evidence is not being searched for | Add a search step to the procedure |
| Overrides cluster in one component | Component-specific knowledge is missing | Add it to the team config, not the shared taxonomy |
| Overrides cluster on one reviewer | Two people disagree about policy | Escalate. The tool cannot resolve a policy disagreement. |

The last row matters. Where experts genuinely disagree, the agent should say so and
route to a person rather than pick a side and appear confident.
