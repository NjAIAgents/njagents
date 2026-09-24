---
name: triage-disposition
description: Decide whether a ticket is a defect, expected behavior, a config or data issue, a duplicate, or a voice-of-customer request, before any priority is assigned. Use when triaging a bug, or when asked whether something is really a bug.
---

# Disposition

Read `<plugin root>/reference/disposition-taxonomy.md` for the definitions and output shape. This
file is the procedure.

## Procedure

1. **State the claimed deviation.** In one sentence: what the reporter expected, what
   happened. If you cannot write that sentence from the ticket, the disposition is
   `insufficient_information`.

2. **Find the intended behaviour.** Read the kept comments first (see
   `skills/bug-triage` Stage 2): a staff comment saying "by design" or "config on their
   side" is evidence to weigh, and a later comment that retracts it wins. Then search, in order:
   - prior tickets in the same component closed as works-as-designed (`tracker` source,
     JQL on resolution and component)
   - release notes for the component
   - the code path, if the `code` source is live: an explicit conditional or guard
     that produces the reported behaviour deliberately is strong evidence of
     `expected_behavior`
   Record what you searched even when you find nothing. "Searched, found nothing" is a
   different statement from "did not search".

3. **Duplicate check.** Open tickets in the same component with the same failure mode.
   Same wording with a different failure mode is not a duplicate. Same failure mode
   with different wording is. The comparison is done by `scripts/dupes.py` (see
   `skills/bug-triage` Stage 2), which scores each candidate on the same error text, the
   same symptom in the description, shared stack frames, the same endpoint or file, the
   same area and the same release, and caps a title-only match at `related`. Accept
   `duplicate` only from a candidate it scored `duplicate`, and name the matched signals
   in the evidence. A candidate scored `recurrence` was already fixed: the ticket is a
   defect, and that fix goes into `prior_fixes`.

4. **Config or data test.** Would the behaviour be correct if a specific setting or
   record had a particular value? If yes and you can name the setting, it is
   `config_or_data`.

5. **The VoC test.** Is the system doing what it was built to do? If yes, and the
   reporter wants different behaviour, it is `voice_of_customer`. Apply this test
   even when the ticket is angry, escalated, or filed by a large account. Commercial
   pressure changes routing urgency, not disposition.

6. **Default.** No evidence for any of the above, and a plausible deviation exists:
   `defect`, confidence `low`. Wrongly closing a real bug costs more than wrongly
   scoring a non-bug.

## Always report the runner-up

Emit `alternative_considered` and `why_not` on every call. This is what lets a human
reviewer correct the agent quickly, and what makes the log useful for calibration.

## Anti-patterns

- Inferring `expected_behavior` from the absence of similar reports. Absence of reports
  is not documentation.
- Marking `duplicate` on summary-text similarity alone, or overriding the script's
  `related` or `different` because two titles look alike.
- Treating a support escalation as evidence of defect.
- Emitting a disposition with an empty `evidence` array and a confidence above `low`.
