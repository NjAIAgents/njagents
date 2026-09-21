# Expected outcomes

A regression test for the demo. Run each command and compare. A divergence means the
fixtures drifted or a shared rule changed.

The arithmetic below is recomputed from `reference/priority-rubric.md`. If you change
the rubric, recompute these.

## `/triage BUG-4830 --team demo`

All five sources in fixture mode.

| Field | Expected |
| --- | --- |
| Disposition | `defect`, confidence high |
| Release | 2026.09, shipped 5 Sep, first error 8 Sep, 3 days. File-level overlap on `ApprovalReviewService.ts` via PR #4412. Correlation confidence high |
| Workaround | Re-submit through the UI rather than the API. Source: BUG-4701 resolution. Applies to: support |
| Base | P3. The ticket also matches P2 "core workflow blocked", but a practical customer workaround caps the base at P3 per the base-precedence rule |
| Escalations | `+1 release` confirmed regression (4.4x baseline, deploy 2026.09 in window), `+1 code` error swallowing at line 214 |
| Not counted | `history` (4 resolved in 90d, sprint collision) - cap reached |
| Final | **P2** -> Jira "Critical". Current "Minor", gap flagged |
| Confidence | high |
| Team | Approvals Team |
| Not P1 | The reviewer is a human acting through the API, so the automated-approval criterion does not apply |

Two levels from P3 reaches P1 arithmetically. The rule that P1 is never reached by
escalation holds it at P2. This is the cap doing its job.

## `/triage BUG-4844 --team demo`

| Field | Expected |
| --- | --- |
| Disposition | `voice_of_customer`, confidence high |
| Evidence | BUG-3120 closed works-as-designed, BUG-4402 open feature request for this exact behaviour |
| Alternative considered | `defect`, ruled out: the system does what it was designed to do, the customer wants a different design |
| Priority | **none assigned** |
| Stage 3 | never runs. Two source calls, not five |
| Routing | PRODUCT (`jira.voc_destination`) |

The key beat. A `Major` ticket from an unhappy customer that should never enter the
defect queue.

## `/triage BUG-4851 --team demo`

| Field | Expected |
| --- | --- |
| Disposition | `defect`, confidence medium |
| Release | 2026.08, shipped 4 Aug, first seen 18 Sep, 45 days. Component-level overlap only (`jira_fixversion` yields no file detail), timing beyond one cycle. Correlation confidence **low**, reported as "shipped in window, weak evidence it caused this" |
| Datadog | No spike. Absence of output produces no errors. Reported as a finding, not as evidence against a defect |
| Workaround | Engineer-run manual export. **Not a customer workaround**, so the impact escalation still applies |
| Floor | P2 (labels `at-risk`, `renewal` match `jira.at_risk_labels`) |
| Escalations | `+1 impact` no customer workaround. `blast` class not counted at all: the at-risk floor consumes the class, so enterprise tier adds nothing on top |
| Final | **P2** (escalation cannot reach P1) |
| Confidence | high. Five sources returned data and agree, and no question is unanswered. The absent spike is consistent with an absence-type failure, not a disagreement |

Demonstrates an honest negative on release correlation, and the customer-versus-engineer
workaround distinction.

## `/triage BUG-4858 --team demo`

| Field | Expected |
| --- | --- |
| Disposition | `duplicate` of BUG-4849, confidence high |
| Why | Same failure mode, header offset after the amount column was added. Not merely similar wording |
| Priority | none assigned. Parent may need review |
| Release | reported from Stage 1: 2026.09 touched `csvExport.ts`, consistent with the duplicate's cause. Pull-request numbers come from the `code` source in Stage 3, which never runs for a non-defect, so they are not cited here |

## `/triage BUG-4830 --team demo-gc`

Same ticket, same shared rubric, second team running Jira and releases only.

| Field | Expected |
| --- | --- |
| Disposition | `defect`, confidence medium |
| Unanswered | Q2 blast radius, Q4 regression, Q7 code signals, Q10 enterprise tier |
| Base | P3 |
| Escalations | `+1 history` recurring component and sprint collision, one escalation for the class. No `release` escalation: a regression needs Datadog, which is off |
| Final | **P2** -> Jira "**High**" (different priority name, identical rubric) |
| Confidence | medium, capped by the unanswered regression question |
| Team | Second Team Backend (`routing.approvals`) |
| Round-up | **not applied.** Symptoms are single-account, so switched-off connectors do not inflate priority |

The two runs reach the same level by different routes, with different confidence and
an explicit list of what could not be checked. That is the intended message: more
connectors buy **certainty**, not severity. The previous design would have rounded this
up for lack of data, which is what drove teams off it.

## Validator behaviour

Two exit paths, deliberately.

```
python3 scripts/validate_config.py --all             -> exit 0
  UNCONFIGURED reference-full.json: jira.cloud_id is a placeholder (REPLACE_WITH_CLOUD_ID). This config cannot go live until it is set.
  UNCONFIGURED reference-full.json: placeholder value at 'jira.site' (REPLACE_WITH_SITE.atlassian.net)
  UNCONFIGURED reference-full.json: placeholder value at 'release_correlation.github.org' (REPLACE_WITH_ORG)
  UNCONFIGURED bta.json: jira.cloud_id is a placeholder (REPLACE_WITH_CLOUD_ID). This config cannot go live until it is set.
  PASS (0 warning(s), 2 config(s) awaiting real values). Run the validator on a named config before going live with it.

python3 scripts/validate_config.py teams/demo.json  -> exit 0
python3 scripts/validate_config.py teams/bta.json   -> exit 1
  1 unset value(s). This config cannot go live yet.
```

The suite is green so it can gate CI, while a named config still refuses to certify a
placeholder. `/triage-doctor --team bta` runs the named form and therefore fails until
`cloud_id` is set. A validator that reports green on a placeholder is worse than no
validator; one that is permanently red is ignored.

## Not covered by fixtures

The P1 fast path. No fixture triggers it, deliberately: P1 detection is unchanged from
the existing design and does not need demo airtime. Verify it separately with a
hand-written outage ticket.
