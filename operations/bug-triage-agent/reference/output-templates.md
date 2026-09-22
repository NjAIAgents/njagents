# Output templates (shared, do not fork)

Three surfaces, because they have different readers and different constraints.

| Surface | Reader | Constraint |
| --- | --- | --- |
| **Chat summary** | the person who asked, right now | scannable in ten seconds, markdown |
| **Report file** | whoever picks the ticket up later | complete, evidence and arithmetic, markdown |
| **Tracker comment** | everyone on the ticket, forever | plain text, no markdown tables |

The tracker comment is plain on purpose. Trackers render their own markup and a
markdown table pasted into one becomes a wall of pipes.

---

## 1. Chat summary

Lead with the answer. Detail goes in the report.

```markdown
**BUG-4830** · Approval step fails silently for Northwind Co when submitted via API

| | |
| --- | --- |
| **Disposition** | `defect` · high confidence |
| **Priority** | **P2** → "Critical" · currently "Minor" ⚠ gap |
| **Release** | 2026.09, 3 days before first error · file-level match |
| **Workaround** | Re-submit through the UI · support can do this |
| **Blast radius** | 1 account, 0 enterprise |
| **Team** | Approvals Team |

Base P3, +1 regression, +1 error swallowing, capped. Never P1 by escalation.

Report: `triage-reports/BUG-4830.md` · Sources: tracker, releases, metrics,
warehouse, code — all live
```

Rules:

- The first line is the ticket and its summary. Nothing above it.
- A non-defect shows **no priority row at all.** Not "n/a", not "none". Absent.
- One line of arithmetic, not the full derivation.
- ⚠ marks only two things: a priority gap against the tracker, and a source in
  `error`. Do not decorate anything else.
- If any source is on fixtures, the first line of the whole message is
  `> **DEMO DATA** — tracker, metrics. Not live figures.`

## 2. Report file

Written to `output.reports_dir`, default `triage-reports/`, as `<TICKET>.md`.
Overwritten on a re-run; the audit log keeps the history.

````markdown
# BUG-4830 — Approval step fails silently for Northwind Co when submitted via API

> Triaged 2026-09-21 14:22 UTC · team `demo` · agent 0.2.1

## Recommendation

**Disposition `defect`** · confidence **high**
**Priority P2** → tracker "Critical" · currently "Minor" · **gap flagged**
**Route to** Approvals Team

Deciding factor: confirmed regression with error swallowing at the bug site.

## Why this is a defect

| Evidence | Source |
| --- | --- |
| API returns 200 while the request stays Pending Review | ticket description |
| BUG-4701, same failure mode, closed **Fixed** rather than as designed | tracker |

Considered `expected_behavior`; ruled out because no specification, release note or
prior works-as-designed closure describes this behaviour.

## How the priority was reached

| Step | Level | Because |
| --- | --- | --- |
| Base | P3 | A practical customer workaround exists, which caps the base |
| `+1 release` | P2 | Confirmed regression: 4.4× baseline, deploy 2026.09 52h before first error |
| `+1 code` | — | Error swallowing at `ApprovalReviewService.ts:89` |
| `history` | — | Not counted: 4 resolved in 90d and a sprint collision, but the cap binds |
| **Final** | **P2** | Two levels from P3 reaches P1 arithmetically; P1 is never reached by escalation |

## Release correlation

**2026.09**, shipped 2026-09-05. First error 2026-09-08, a gap of **3 days** against a
30-day cadence.

File-level overlap: `approvals-api/src/approvals/ApprovalReviewService.ts` appears in
both the release manifest and the candidate paths. Adapters: `tracker_fixversion`,
`wiki_release_notes`, `vcs_tag`. **Correlation confidence: high.**

## Workaround

> Re-submit the approval through the UI rather than the API.

**Who can do this:** support · **Cost:** a few clicks · **Source:** BUG-4701 resolution notes
**Does not cover:** bulk approvals submitted by integration.

## Evidence

```
ApprovalReviewService.ts:89
} catch (e) { logger.warn('approval not committed', e); return { ok: true }; }
```

## Coverage

| Source | Mode | Result |
| --- | --- | --- |
| tracker | live | ok |
| releases | live | ok |
| metrics | live | ok |
| warehouse | live | 1 account, 0 enterprise |
| code | live | ok |

All ten classification questions answered.

## Fields to update

```
priority  → Critical
labels    → component:approvals, severity:p2
assignee  → Approvals Team
```

Nothing has been written to the tracker. Confirm before posting.
````

### Report rules

- A non-defect report stops after **Why this is a `<disposition>`** and a **Route**
  section. No priority section, no correlation section unless one was gathered.
- **Unanswered** replaces **Coverage** rows where a source was `off`, and the report
  says which questions went unanswered and what they would have changed.
- A source in `error` gets its own section at the **top**, above Recommendation.
- Never include a section with nothing in it. Omit it.

## 3. Tracker comment

Plain text. Generated, never posted without per-ticket confirmation.

```
Triage: P2 (Critical) — confirmed regression, currently Minor

Disposition: defect (high confidence)
Why: API returns 200 while the request stays Pending Review. BUG-4701 is the
same failure mode and was fixed rather than closed as designed.

Release: 2026.09, shipped 5 Sep, 3 days before the first error. Touched
ApprovalReviewService.ts, which is also where the error is swallowed (line 89).

Workaround: re-submit through the UI. Support can do this. Source: BUG-4701.

Blast radius: 1 account, 0 enterprise.
Suggested team: Approvals Team.

Sources: tracker, releases, metrics, warehouse, code (all live).
Full report: triage-reports/BUG-4830.md
```

## Batch mode

One table, ordered by priority then by deciding factor. Non-defects in a separate
table below, never ranked among the defects.

```markdown
### Defects

| Ticket | Priority | Deciding factor | Confidence |
| --- | --- | --- | --- |
| BUG-4851 | **P2** → Critical | At-risk client, no customer workaround | high |
| BUG-4830 | **P2** → Critical ⚠ was Minor | Confirmed regression + error swallowing | high |

### Not defects

| Ticket | Disposition | Route | Why |
| --- | --- | --- | --- |
| BUG-4844 | `voice_of_customer` | PRODUCT | Working as designed per BUG-3120 |
| BUG-4858 | `duplicate` of BUG-4849 | link and close | Same failure mode |
```
