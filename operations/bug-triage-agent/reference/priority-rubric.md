# Priority rubric (shared, do not fork)

Applies only to tickets dispositioned `defect`. Identical for every team. Teams map
P1 to P4 onto their own tracker priority names in `tracker.priority_names`; they do not
change the criteria.

| Level | SLA | Criteria (any) |
| --- | --- | --- |
| P1 | 45 min | Full outage, data loss, security breach, complete workflow stoppage for an at-risk client, or a fully automated approval workflow blocked. |
| P2 | 72 hours | Multiple accounts affected, core workflow blocked, or an at-risk client affected. |
| P3 | 15 business days | Workaround exists, limited accounts, erodes confidence without blocking. |
| P4 | No SLA | Cosmetic or minor display issue, no workflow impact. |

**Automated approval test.** "Automated approval workflow blocked" means a workflow
that completes with **no human in the loop** cannot proceed. A human approver acting
through an API is not an automated workflow: the human is the loop, and their failure
to act is an ordinary workflow impact. Without this test the criterion swallows every
API-submitted approval bug.

**Stoppage test (P1).** "Complete workflow stoppage for an at-risk client" means the
client cannot complete a **business outcome** the product exists to deliver, with no
path around it. One broken workflow among several they use is a blocked workflow, not
a stoppage.

Apply it in two steps:

1. Name the outcome the client cannot reach.
2. Ask whether any other path reaches it, including a manual or engineer-assisted one.
   If a path exists, however inconvenient, this is not a stoppage.

**When the answer is genuinely arguable, do not pick.** Emit the recommendation at the
lower level, flag it as a P1 boundary case, name both readings, and route to a human.
A wrong P1 burns the 45-minute SLA and the on-call's trust; a wrong P2 on something
that was P1 is caught by the person the flag went to. The asymmetry is deliberate.

**Base precedence.** The criteria are "any of", so a ticket can match several. Two
rules resolve it:

1. A practical **customer** workaround caps the base at P3, whatever the workflow
   impact. A blocked workflow the customer can route around is not a blocked workflow.
2. Otherwise take the highest matching level.

Escalations then apply on top. Without rule 1 the base is ambiguous and two reviewers
reading the same rubric get different answers.

Confirmed regression, recurring component and roadmap collision are **escalation signals only**, never base criteria. Listing a signal in both places double-counts it, which is the flaw this rubric replaces.

**P3 and P4 are separated by workflow impact, not by account count.** A single-account
bug that blocks a task is P3. A multi-account cosmetic issue is P4.

## Classification questions

Answer in order. Skip any question whose source is unavailable and record it as
unanswered rather than guessing.

1. Does this meet any P1 criterion? If yes, stop and emit the fast path.
2. How many accounts are affected? (`warehouse`)
3. Is any affected account at risk? Match the ticket's labels against `tracker.at_risk_labels` from the team config, then check the ticket text.
4. Is this a confirmed regression? (`metrics` + `releases`)
5. Is there a practical workaround? (workaround-finder)
6. What is the workflow impact: blocks, degrades, or cosmetic?
7. Is there error swallowing or a stub at the bug site? (`code`)
8. Is this a recurring component? (`tracker`, 3 or more resolved in 90 days)
9. Is there active sprint work in the same component? (`tracker`)
10. Is any affected account enterprise tier? (`warehouse`)

## Escalation signals

Each adds one level. **Total escalation is capped at two levels**, and a ticket can
never reach P1 by escalation alone. P1 requires meeting a P1 criterion directly.

| Signal | Class | Source |
| --- | --- | --- |
| Confirmed regression | release | metrics + releases |
| Error swallowing at bug site | code | code |
| Stub or suppressed type error at bug site | code | code |
| Recurring component, 3 or more in 90 days | history | tracker |
| Roadmap collision, active sprint work | history | tracker |
| No practical workaround | impact | workaround-finder |
| Enterprise tier account affected | blast | warehouse |
| At-risk client | blast | tracker labels matching `tracker.at_risk_labels`, or stated in the ticket |
| Automated approval workflow involved | impact | ticket |

**One escalation per class.** Two code signals at the same site count once. This stops
a single observation being counted three ways, which is how the original design turned
cosmetic bugs into P1s.

At-risk client remains a P2 floor, applied before the cap.

**The at-risk floor consumes the blast class.** When the floor is applied, no
blast-class escalation is counted, including enterprise tier. The floor already
encodes who the customer is; counting it again as an escalation is the same
double-count the class rule exists to prevent.

## Confidence

| Confidence | Condition |
| --- | --- |
| high | Two or more independent sources returned data, they agree, **and** no unanswered question could change the level. |
| medium | Sources agree but an unanswered question could change the level, or only one source returned data. |
| low | No enrichment source returned data, a source errored, or sources disagree on the deciding factor. |

An unanswered question that could change the level caps confidence at medium however
many sources agree. Otherwise a team running two sources would report the same
confidence as a team running five, which is false and would discourage adding
connectors.

State the confidence basis in one line. Never emit a bare label.
