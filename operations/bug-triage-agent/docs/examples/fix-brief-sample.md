---
brief_version: 2
ticket: "DEMO-7"
ticket_url: "https://nishantnavjyot.atlassian.net/browse/DEMO-7"
title: Approval step fails silently when submitted through the API
team: "demo-live"
repo: "njagents-demo-app"
base_branch: main
branch: "fix/demo-7-approval-step-fails-silently-when"
priority: P2
priority_confidence: high
evidence: strong
location_confirmed: true
reproduction: seen_in_production
complexity: low
human_review_required: false
next_action: fix_now
fix_due: null
risks:
  - data_integrity
  - compliance
  - silent_failure
candidate_files:
  - "approvals-api/src/approvals/ApprovalReviewService.ts:89"
  - "api/approve.js:25"
fault:
  file: "approvals-api/src/approvals/ApprovalReviewService.ts"
  line: 89
  signal: error_swallowing
  url: "https://github.com/NjAIAgents/njagents-demo-app/blob/main/approvals-api/src/approvals/ApprovalReviewService.ts#L89"
introduced_by: "2026.09"
fix_status: open
already_fixed: false
hypothesis:
  statement: "A failed commit is caught at ApprovalReviewService.ts:89 and turned into a success response, so the API reports an approval that was never stored; api/approve.js repeats the same pattern in production."
  confirm_by: "A test that forces store.approvals.commit to throw gets 200 { ok: true } and an unchanged request"
  refute_by: "With the commit forced to fail, the endpoint already returns an error and the request state is reported correctly"
alternatives:
  - "The approval commits, but the read-back hits a replica that has not caught up, so the request only looks unchanged."
  - "assertReviewer accepts the caller without checking the request, so a non-reviewer's decision is silently dropped."
acceptance:
  - "A test that reproduces the failure above, failing before the change"
  - The same test passing after the change
  - The existing test suite passing
route_to: Approvals Team
generated_by: "bug-triage-agent 0.7.1"
---

# Fix brief · [DEMO-7](https://nishantnavjyot.atlassian.net/browse/DEMO-7) · Approval step fails silently when submitted through the API

**Supported by:** code [ApprovalReviewService.ts:89](https://github.com/NjAIAgents/njagents-demo-app/blob/main/approvals-api/src/approvals/ApprovalReviewService.ts#L89) · releases [2026.09](https://github.com/NjAIAgents/njagents-demo-app/releases/tag/2026.09) · metrics [4.4× baseline](https://fondlizard977.grafana.net/explore?schemaVersion=1&orgId=1&panes=%7B%22a%22%3A%7B%22datasource%22%3A%22grafanacloud-logs%22%2C%22queries%22%3A%5B%7B%22refId%22%3A%22A%22%2C%22expr%22%3A%22sum%28count_over_time%28%7Bapp%3D%5C%22njagents-demo%5C%22%2Cservice%3D%5C%22approvals-api%5C%22%7D%20%7C%3D%20%5C%22approval%20not%20committed%5C%22%20%5B1h%5D%29%29%22%2C%22queryType%22%3A%22range%22%2C%22datasource%22%3A%7B%22type%22%3A%22loki%22%2C%22uid%22%3A%22grafanacloud-logs%22%7D%2C%22editorMode%22%3A%22code%22%7D%5D%2C%22range%22%3A%7B%22from%22%3A%221789560000000%22%2C%22to%22%3A%221790136000000%22%7D%7D%7D) · tracker [DEMO-1](https://nishantnavjyot.atlassian.net/browse/DEMO-1)

> ⚠️ **Stale data.** metrics: read 44h before triage. Re-check before acting.

This brief was produced by triage, not by reading the fix. Treat every location and cause below as a lead to verify, not a finding.

## Problem

- **Expected:** The response reflects the outcome and the request leaves Pending once the decision commits, or the call returns an error
- **Actual:** Response is 200 {"ok": true}; the request stays Pending; the log shows 'approval not committed, continuing' at ApprovalReviewService.ts:89

## Reproduce

**Status:** 🟢 seen in production · metrics: 4.4× baseline from 2026-09-19; baseline 24/h over 62h of history, not the configured 7 days; retention not confirmed

1. Create a request that needs two reviewers
2. POST an approval decision through the API (demo service: GET /api/approve?account=northwind)
3. Read the response, then read the request state

From the ticket's comments:

- Detail: “Repro against the service: GET /api/approve?account=northwind returns {"ok": true} but the request is not approved.”

**Fix complexity:** 🟢 low (2/5) · 2 files located (+1)

## Where to look

| # | Location | Signal | Evidence | From |
| --- | --- | --- | --- | --- |
| 1 | [`ApprovalReviewService.ts:89`](https://github.com/NjAIAgents/njagents-demo-app/blob/main/approvals-api/src/approvals/ApprovalReviewService.ts#L89) | `error_swallowing` | catch wraps commit, save, audit and notify; logs 'approval not committed' at warn and returns { ok: true } | code |
| 2 | [`ApprovalReviewService.ts`](https://github.com/NjAIAgents/njagents-demo-app/commit/834adf496fc73ae60d77af67f2485f61d60f583a) | `release_touched` | changed in 2026.09 by #4412 (reviewer decision flow), the only commit on the file | releases |
| 3 | [`approve.js:25`](https://github.com/NjAIAgents/njagents-demo-app/blob/main/api/approve.js#L25) | `error_swallowing` | the deployed Vercel slice repeats the same catch: console.warn then 200 { ok: true }; its comment says it mirrors ApprovalReviewService.ts:89 | code |

Likely introduced by release **[2026.09](https://github.com/NjAIAgents/njagents-demo-app/releases/tag/2026.09)**, PR [#4412](https://github.com/NjAIAgents/njagents-demo-app/commit/834adf496fc73ae60d77af67f2485f61d60f583a). Read that diff first.

Evidence: [4.4× baseline](https://fondlizard977.grafana.net/explore?schemaVersion=1&orgId=1&panes=%7B%22a%22%3A%7B%22datasource%22%3A%22grafanacloud-logs%22%2C%22queries%22%3A%5B%7B%22refId%22%3A%22A%22%2C%22expr%22%3A%22sum%28count_over_time%28%7Bapp%3D%5C%22njagents-demo%5C%22%2Cservice%3D%5C%22approvals-api%5C%22%7D%20%7C%3D%20%5C%22approval%20not%20committed%5C%22%20%5B1h%5D%29%29%22%2C%22queryType%22%3A%22range%22%2C%22datasource%22%3A%7B%22type%22%3A%22loki%22%2C%22uid%22%3A%22grafanacloud-logs%22%7D%2C%22editorMode%22%3A%22code%22%7D%5D%2C%22range%22%3A%7B%22from%22%3A%221789560000000%22%2C%22to%22%3A%221790136000000%22%7D%7D%7D) · [deploy 2026.09](https://vercel.com/navjyot-s-lab/njagents-demo-app/7NrEumyk89SwBXtzY8uvW4KCiZFe)

## Timeline

```
▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▄█▇███████▇█████▇▇███▇█████▇█▇
  1                2                     3
approval not committed (per hour) · baseline 24 · peak 121
```

| # | When (UTC) | Event | Gap |
| --- | --- | --- | --- |
| 1 | 2026-09-16 21:00 | Deploy: [2026.09](https://vercel.com/navjyot-s-lab/njagents-demo-app/7NrEumyk89SwBXtzY8uvW4KCiZFe) |  |
| 2 | 2026-09-19 04:00 | Errors rise: 4.4× baseline | +55h |
| 3 | 2026-09-22 04:38 | Ticket filed: [DEMO-7](https://nishantnavjyot.atlassian.net/browse/DEMO-7) | +3d |
| 4 | 2026-09-25 00:20 | Triaged: this run | +68h |

## Prior fixes in this area

- **[DEMO-1](https://nishantnavjyot.atlassian.net/browse/DEMO-1)**: Approval not persisted on retry. Fixed in 2026.08: the commit path swallowed the write failure and returned ok. Same symptom, so check whether #4412 undid that fix; the file's only commit on main is #4412

A regression of an earlier fix usually means that fix's test did not cover this path. Check it.

## Risks to test against

- 💾 **data integrity** (evidenced): a failed write is caught and reported as done. Check records already written wrong; a code fix alone may not repair them.
- 📜 **compliance** (suspected): “audit” in the code notes. Keep the audit trail intact.
- 🔇 **silent failure** (evidenced): error swallowing at ApprovalReviewService.ts:89. The failure must now surface as an error the caller sees.

## Hypothesis to test

**A failed commit is caught at ApprovalReviewService.ts:89 and turned into a success response, so the API reports an approval that was never stored; api/approve.js repeats the same pattern in production.**

- Confirmed if: A test that forces store.approvals.commit to throw gets 200 { ok: true } and an unchanged request
- Refuted if: With the commit forced to fail, the endpoint already returns an error and the request state is reported correctly

Evidence against this hypothesis:

- ⚖️ The 2026.09 tag commit is dated 2026-08-30, before the 2026-09-16 deploy the correlation rests on (releases, against the hypothesis). Addressed: the release body and the deployer log both record the approvals-api deploy on 2026-09-16; commit dates in this repo are out of order (the tag's parent is dated later than the tag).
- ⚖️ The error rise came 55h after the deploy, not at it (metrics, against the hypothesis). Addressed: the fault only fires when a commit fails; traffic that triggers it started on 09-19, and the log names the line the release changed.

If the test refutes it, test these next, in order:

1. The approval commits, but the read-back hits a replica that has not caught up, so the request only looks unchanged. Confirmed if: Reading the request from the primary right after the call shows it approved
2. assertReviewer accepts the caller without checking the request, so a non-reviewer's decision is silently dropped. Confirmed if: The failing calls come from users who are not reviewers on that request

These are hypotheses. If every one is refuted, stop and report what you found instead of fixing somewhere else.

## Definition of done

- [ ] A test that reproduces the failure above, failing before the change
- [ ] The same test passing after the change
- [ ] The existing test suite passing
- [ ] The path the workaround relies on still works: Approver re-submits the same decision through the UI rather than the API; the UI takes a different code branch that persists correctly

## Constraints

- Keep the change to the fault. No drive-by refactors in the same PR.
- Do not change a public API contract or response shape without calling it out in the PR description.
- Do not comment on, transition or edit the ticket. The PR links to it; a person updates the tracker.
- Branch from `main` as `fix/demo-7-approval-step-fails-silently-when`.

## Not checked by triage

- unanswered: Q2 accounts affected (warehouse off)
- unanswered: Q10 enterprise tier (warehouse off)

## Pull request

**Title:** `DEMO-7: Approval step fails silently when submitted through the API`

**Body:**

```markdown
Fixes DEMO-7.

## Cause
<what the fault was, and how you confirmed it>

## Change
<what changed and why this is the minimal fix>

## Tests
<the test that failed before and passes now>

Triage: P2 · evidence strong · generated by bug-triage-agent 0.7.1
```
