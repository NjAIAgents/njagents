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

## Visual vocabulary

Markdown has no color. Inline HTML color is stripped by most renderers, so it is not
used. Color comes from two portable mechanisms only: colored markers, which render
everywhere, and callout blocks, which render as colored boxes where supported and as
a labelled quote elsewhere.

**Every color is paired with text.** A reader who cannot see color, or a renderer that
drops it, must lose nothing. `🟠 P2`, never `🟠` alone.

### Markers

| Meaning | Marker | Written as |
| --- | --- | --- |
| Priority P1 | 🔴 | `🔴 P1` |
| Priority P2 | 🟠 | `🟠 P2` |
| Priority P3 | 🟡 | `🟡 P3` |
| Priority P4 | 🔵 | `🔵 P4` |
| Non-defect, no priority | ⚪ | `⚪ voice_of_customer` |
| Source live and ok | 🟢 | `🟢 live` |
| Source on fixture, or partial | 🟡 | `🟡 fixture` · `🟡 partial` |
| Source off | ⚫ | `⚫ off` |
| Source in error | 🔴 | `🔴 error` |
| Location evidence strong / moderate / weak | 🟢 🟡 🔴 | `🔴 weak evidence` |

Confidence uses a meter, not a color, so it cannot be mistaken for a priority:
`●●● high` · `●●○ medium` · `●○○ low`.

Markers are fixed. Do not introduce new ones per report; a reader learns the
vocabulary once. Yellow means two things (P3 and a degraded source) only because the
column always disambiguates it.

### Callouts

| Callout | Used for, and only for |
| --- | --- |
| `> [!WARNING]` | Demo data banner. Any source on fixtures. |
| `> [!CAUTION]` | A source in `error`, or **weak or moderate location evidence**. Placed above Recommendation. Both say the same thing: do not act on this blindly. |
| `> [!IMPORTANT]` | A priority gap against the tracker's current value. |
| `> [!TIP]` | The workaround. |
| `> [!NOTE]` | The closing reminder that nothing was written to the tracker. |

One callout per purpose per report. A report where everything is highlighted has
highlighted nothing.

### Labels

Dispositions, escalation classes and field names stay in code spans, `defect`,
`+1 release`, so they read as fixed vocabulary rather than prose. Bold is reserved for
the answer: the priority, the disposition, the route.

---

## 1. Chat summary

Lead with the answer. Detail goes in the report.

```markdown
### 🟠 P2 · BUG-4830 · Approval step fails silently for Northwind Co when submitted via API

| | |
| --- | --- |
| **Disposition** | `defect` · ●●● high |
| **Priority** | **🟠 P2** → "Critical" · currently "Minor" ⚠ gap |
| **Release** | 2026.09, 3 days before first error · file-level match |
| **Workaround** | Re-submit through the UI · support can do this |
| **Blast radius** | 1 account, 0 enterprise |
| **Team** | Approvals Team |

Base 🟡 P3 · `+1 release` · `+1 code` · capped at 🟠 P2. Never P1 by escalation.

Sources: 🟢 tracker · 🟢 releases · 🟢 metrics · 🟢 warehouse · 🟢 code
Report: `triage-reports/BUG-4830.md`
```

A non-defect leads with its disposition instead:

```markdown
### ⚪ BUG-4844 · `voice_of_customer` · no priority assigned
```

Rules:

- The heading carries the answer: priority marker and level for a defect, `⚪` and
  the disposition for anything else. Nothing above it except a callout.
- A non-defect shows **no priority row at all.** Not "n/a", not "none". Absent.
- One line of arithmetic, not the full derivation.
- ⚠ marks only two things: a priority gap against the tracker, and a source in
  `error`. Do not decorate anything else.
- If any source is on fixtures, the message opens with the demo banner:

  ```markdown
  > [!WARNING]
  > **Demo data.** tracker, metrics are on fixtures. Not live figures.
  ```

## 2. Report file

Written to `output.reports_dir`, default `triage-reports/`, as `<TICKET>.md`.
Overwritten on a re-run; the audit log keeps the history.

````markdown
# 🟠 P2 · BUG-4830 — Approval step fails silently for Northwind Co when submitted via API

Triaged 2026-09-21 14:22 UTC · team `demo` · agent 0.4.2

## Recommendation

| | |
| --- | --- |
| **Disposition** | `defect` |
| **Priority** | **🟠 P2** → tracker "Critical" |
| **Confidence** | ●●● high |
| **Evidence** | 🟢 strong · fault signal at `ApprovalReviewService.ts:89`, same file changed in 2026.09 |
| **Route to** | **Approvals Team** |
| **Fix brief** | `triage-reports/BUG-4830.fix-brief.md` |

**Deciding factor:** confirmed regression with error swallowing at the bug site.

> [!IMPORTANT]
> **Priority gap.** The tracker has this at "Minor". Recommended "Critical".

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
| Base | 🟡 P3 | A practical customer workaround exists, which caps the base |
| `+1 release` | 🟠 P2 | Confirmed regression: 4.4× baseline, deploy 2026.09 52h before first error |
| `+1 code` | — | Error swallowing at `ApprovalReviewService.ts:89` |
| `history` | — | Not counted: 4 resolved in 90d and a sprint collision, but the cap binds |
| **Final** | **🟠 P2** | Two levels from P3 reaches P1 arithmetically; P1 is never reached by escalation |

## Release correlation

**2026.09**, shipped 2026-09-05. First error 2026-09-08, a gap of **3 days** against a
30-day cadence.

File-level overlap: `approvals-api/src/approvals/ApprovalReviewService.ts` appears in
both the release manifest and the candidate paths. Adapters: `tracker_fixversion`,
`wiki_release_notes`, `vcs_tag`. **Correlation confidence: high.**

## Workaround

> [!TIP]
> **Re-submit the approval through the UI rather than the API.**
>
> **Who can do this:** support · **Cost:** a few clicks · **Source:** BUG-4701 resolution notes
> **Does not cover:** bulk approvals submitted by integration.

## Evidence

```
ApprovalReviewService.ts:89
} catch (e) { logger.warn('approval not committed', e); return { ok: true }; }
```

## Coverage

| Source | Mode | Result |
| --- | --- | --- |
| tracker | 🟢 live | ok |
| releases | 🟢 live | ok |
| metrics | 🟢 live | 4.4× baseline |
| warehouse | 🟢 live | 1 account, 0 enterprise |
| code | 🟢 live | error swallowing found |

All ten classification questions answered.

## Fields to update

```
priority  → Critical
labels    → component:approvals, severity:p2
assignee  → Approvals Team
```

> [!NOTE]
> Nothing has been written to the tracker. Confirm before posting.
````

### Report rules

- A non-defect report stops after **Why this is a `<disposition>`** and a **Route**
  section. No priority section, no correlation section unless one was gathered.
- **Unanswered** replaces **Coverage** rows where a source was `off`, and the report
  says which questions went unanswered and what they would have changed.
- A source in `error` gets a `> [!CAUTION]` callout at the **top**, above
  Recommendation, naming the source and the error.
- When the evidence is not strong, the callout reads, for example:

  ```markdown
  > [!CAUTION]
  > Evidence for where this bug lives is **weak**. Confirm the location before changing
  > code. If it cannot be confirmed, report back rather than opening a pull request
  > against a guess.
  > - code search was off, so no file or line was checked for a fault signal
  > - the only link to approvals-api/src/approvals/ApprovalReviewService.ts is a release
  >   record, which ties it by area, not by a fault found in the code
  ```
- **Evidence.** For every defect, run
  `python3 <plugin root>/scripts/render_fix_brief.py --assess <result.json>` and add an
  `Evidence` row to the Recommendation table with its marker and level. When the level
  is not `strong`, place its `caution` text and `missing` list verbatim in a
  `> [!CAUTION]` callout above Recommendation. Never soften, reword or omit it: the
  report, the trace and the fix brief must show the same verdict, and a fixer or
  reviewer reading any one of them must learn that the location is unconfirmed.
  Priority confidence and location evidence are separate: a confident P2 can still
  have weak evidence about which file to change.
- Never include a section with nothing in it. Omit it.

## 3. Tracker comment

Plain text. Generated, never posted without per-ticket confirmation.

No markers and no callouts here. Callout syntax appears literally in a tracker, and
the comment outlives any viewer's rendering. Priority is written as words.

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
| BUG-4851 | **🟠 P2** → Critical | At-risk client, no customer workaround | ●●● high |
| BUG-4830 | **🟠 P2** → Critical ⚠ was Minor | Confirmed regression + error swallowing | ●●● high |

### Not defects

| Ticket | Disposition | Route | Why |
| --- | --- | --- | --- |
| BUG-4844 | ⚪ `voice_of_customer` | PRODUCT | Working as designed per BUG-3120 |
| BUG-4858 | ⚪ `duplicate` of BUG-4849 | link and close | Same failure mode |
```
