# Expected outcomes

**Recorded from real runs on 2026-09-21, not derived from the rubric.** An earlier
version of this file was a prediction, and five runs found nine divergences from it.
When you change a rule, re-run these and rewrite this file from what happened.

Every run below is `--team demo` unless stated.

## `/triage BUG-4830 --team demo`

| Field | Observed |
| --- | --- |
| Disposition | `defect`, high. Evidence: BUG-4701 same failure mode fixed as a defect; API returns 200 while state stays Pending Review |
| Alternative | `expected_behavior`, ruled out: no spec or works-as-designed closure describes it |
| Workaround | Re-submit through the UI. **Applies to: support**, and customers can be told. Source: BUG-4701 `resolution_notes` |
| Base | **P3**, because a practical customer workaround exists and caps it there |
| Escalations | `+1 release` confirmed regression (4.4x vs spike_ratio 3.0; deploy 2026.09 52.2h before first error, inside 720h), `+1 code` error swallowing at ApprovalReviewService.ts:89 |
| Not counted | `history` (4 resolved in 90d, sprint collision) — two-level cap reached |
| Final | **P2** → "Critical". Current "Minor", gap flagged |
| Release | 2026.09, shipped 5 Sep, first error 8 Sep, 3 days. File-level overlap via `vcs_tag`. Correlation **high** |
| Confidence | high |
| Team | Approvals Team |

Demonstrates the cap: P3 plus two levels reaches P1 arithmetically, and the
never-P1-by-escalation rule holds it at P2.

## `/triage BUG-4844 --team demo`

| Field | Observed |
| --- | --- |
| Disposition | `voice_of_customer`, high |
| Evidence | BUG-3120 closed **Works as designed**: held balance release is deliberately manual. BUG-4402 is an open feature request for this exact behaviour |
| Alternative | `defect`, ruled out: the system does what it was designed to do |
| Priority | **none assigned** |
| Stage 3 | never ran. Two source calls, not five |
| Routing | `tracker.voc_destination` |

The key case. A `Major` ticket from an unhappy customer that never enters the defect
queue. Note the ticket says "They call this a bug" and the gate disagrees, correctly.

## `/triage BUG-4851 --team demo`

| Field | Observed |
| --- | --- |
| Disposition | `defect`, high |
| Workaround | Engineer restarts the scheduler and backfills. **Applies to: engineer only.** Source: BUG-4790 `resolution_notes`. Not a customer workaround, so the P3 base cap does **not** apply |
| P1 stoppage test | Outcome = reconcile settlements. An engineer-assisted path exists, so **not** a stoppage. Stays below P1 |
| Base | **P2** (core workflow blocked, at-risk client) |
| Floor | P2 from labels `at-risk`, `renewal`. The floor consumes the blast class, so enterprise tier adds nothing |
| Escalations | `+1 impact` no customer workaround — absorbed by never-P1 |
| Final | **P2** → "Critical". Current "Critical", no gap |
| Release | 2026.08, shipped 4 Aug, first seen 18 Sep, **45 days against a 30-day cadence**. Component overlap only, no file detail. Correlation **low** |
| Metrics | No spike. An absent output produces no errors. Reported as a finding, not as evidence against a defect |
| Confidence | high |

Exercises three rules at once: the customer-versus-engineer workaround distinction, the
P1 stoppage test, and the correlation row for area overlap with stale timing.

## `/triage BUG-4858 --team demo`

| Field | Observed |
| --- | --- |
| Disposition | `duplicate` of BUG-4849, high |
| Why | Same **failure mode**, header offset after the amount column was added. Not wording similarity |
| Priority | none assigned |
| Release | from Stage 1: 2026.09 touched `csvExport.ts` |

## `/triage BUG-4830 --team demo-gc`

The consistency test. Same ticket, same shared rubric, second team with metrics,
warehouse and code `off`.

| Field | Observed |
| --- | --- |
| Disposition | `defect` |
| Unanswered | Q2 blast radius, Q4 regression, Q7 code signals, Q10 enterprise tier |
| Base | P3 (the workaround is still visible: it comes from the tracker, which is on) |
| Escalations | `+1 history` recurring component and sprint collision, one per class. **No release escalation**: confirming a regression needs metrics |
| Final | **P2** → "**High**". Different priority name, identical rubric |
| Confidence | **medium**, capped by the unanswered regression question |
| Round-up | **not applied.** Single-account symptoms, so switched-off sources do not inflate |
| Team | Second Team Backend |

Both teams reach P2 by different routes with different confidence. That is the intended
message: **more connectors buy certainty, not severity.**

## Validator behaviour

```
python3 scripts/validate_config.py --all           -> exit 0, placeholders as UNCONFIGURED
python3 scripts/validate_config.py teams/demo.json -> exit 0
python3 scripts/validate_config.py teams/bta.json  -> exit 1, placeholder instance_id
```

## Not covered

The P1 fast path. No fixture triggers it, deliberately. Verify separately with a
hand-written outage ticket.
