# Output templates (shared, do not fork)

Several surfaces, because they have different readers and different constraints.

| Surface | Reader | Constraint |
| --- | --- | --- |
| **Chat summary** | the person who asked, right now | scannable in ten seconds, markdown |
| **HTML report** (default) | whoever picks the ticket up later | complete, evidence and arithmetic, one self-contained page |
| **Markdown report** (opt-in) | a PR, a chat thread, a repo, another agent | the same facts, markdown, written only when asked |
| **Fix brief** | the person or agent who fixes it | every defect, every mode; front matter a fix agent parses |
| **Tracker comment** | everyone on the ticket, forever | plain text, no markdown tables |

`output.report_format` decides the report files: `html` (default), `md`, `both`, or
`agent`, which writes only the result file and, for defects, the fix brief. A user can
ask for markdown in one run; the HTML header then links it. `output.run_trace: never`
turns the HTML off, so the markdown report is written instead.

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

Callouts are quote blocks led by an icon, so they render the same in every markdown
viewer. The `> [!WARNING]` alert syntax is not used: most viewers show it as a
literal tag. Scripts produce them through `links.callout()`.

| Callout | Used for, and only for |
| --- | --- |
| `> ⚠️ …` | Demo data banner. Any source on fixtures. |
| `> 🛑 …` | A source in `error`, or **weak or moderate location evidence**. Placed above the at-a-glance table. Both say the same thing: do not act on this blindly. |
| `> ❗ …` | A priority gap against the tracker's current value. |
| `> 💡 …` | The workaround. |
| `> ℹ️ …` | The closing reminder that nothing was written to the tracker. |

One callout per purpose per report. A report where everything is highlighted has
highlighted nothing.

### Links

Evidence carries its link behind a short label, never as a bare URL:
[`ApprovalReviewService.ts:89`](#), [2026.09](#), [#4412](#), [DEMO-1](#), [Logs](#),
[Deploy 2026.09](#). A label is at most 40 characters. The URL comes from a tool result
or the team config's `links` templates, never from the model. Evidence with no real URL
shows its label as plain text. The chat summary links the two or three items that
decided the priority; the report, trace and fix brief link every item.

### Labels

Dispositions, escalation classes and field names stay in code spans, `defect`,
`+1 release`, so they read as fixed vocabulary rather than prose. Bold is reserved for
the answer: the priority, the disposition, the route.

---

Every surface opens with the same three lines, computed by `scripts/summary.py` from
the result file: the **verdict**, **why** (the deciding factor), and **do now** (the
workaround and who can do it, or the route). Then **Supported by**: the independent
sources that back the verdict, each linked, as "N of M sources". Stale data gets a
warning callout above everything.

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
Report: `triage-reports/BUG-4830-report.html`
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
  > ⚠️ **Demo data.** tracker, metrics are on fixtures. Not live figures.
  ```

## 2. HTML report (the default)

Rendered by `scripts/render_trace.py`, which calls `scripts/report_html.py`, from
`<TICKET>.result.json`, never written by hand, to `output.reports_dir` as
`<TICKET>-report.html`. The stylesheet is `assets/report-theme.css`, inlined by
`scripts/html_theme.py`, so the page is one file that opens anywhere. A team may change
only the accent colour, with `output.theme`. Top to bottom:

1. **Sticky header.** The ticket key and title; chips for priority, regression or
   defect, the tracker gap and confidence; a meta row with the owner, when it was
   triaged and the team; icon buttons to open the ticket in the tracker, to the markdown
   report (only when one was written) and to the fix brief (defects only); one theme
   button that cycles light, dark and system. Light is the default, and the choice is
   remembered per browser.
2. **Notes.** Demo data, stale data, weak evidence.
3. **Brief.** The story, then three action boxes: "Do now · support" (with the
   workaround's source and what it does not cover), "Fix · owner", and "Set in tracker ·
   on your yes". A side column shows the priority large, and the confidence.
4. **Why this verdict**, and the fix status.
5. **Since the last triage**, as a table, on a re-triaged ticket.
6. **Numbers** as tiles, from the metrics series.
7. **Risks** as tiles, each linking to its evidence.
8. **Timeline** track and the error chart.
9. **Priority ladder.**
10. **Evidence and coverage** meters.
11. **Where it is.** Locations, code (collapsed past 12 lines, with a copy button) and the
    hypothesis.
12. **Sources and coverage** table, naming each provider from `sources.<s>.provider`.
13. **Duplicate check.** One line when nothing matches; otherwise bars for the matches
    only (at most 3) and a line saying how many others were checked.
14. **Comments**, the evidence against, and other causes.
15. **How this was produced.** The stage flow, with a branch for each deep source.

Every ticket key, file, line, release, commit, PR, log query and deploy links behind a
short label. The fields to update are in the "Set in tracker" box; the markdown report
keeps its own "Fields to update" section.

## 3. Markdown report (opt-in)

Rendered by `scripts/render_report.py` from `<TICKET>.result.json`, never written by
hand, to `output.reports_dir` (default `triage-reports/`) as `<TICKET>.md`. Written only
when `output.report_format` is `md` or `both`, when `output.run_trace` is `never`, or
when the user asks for markdown in that run. Overwritten
on a re-run; the earlier result is archived to `history/` first and the audit log keeps
the history. The layout below is what the script produces, with these additions, each
shown only when its data exists:

- the summary block (verdict, why, do now) right after the title
- **Since the last triage**, after the summary, on a re-triaged ticket
- a **Supported by** row in the at-a-glance table
- **Duplicate check**, after the disposition evidence
- **Timeline**: a sparkline over the error counts with numbered event markers, and a
  table of events with the gaps between them. The release correlation is one line at
  its top, not a section of its own
- a verification line in the Workaround callout, when the team verifies workarounds
- **Coverage** as one line: each source and whether it answered, ⚠ stale when its data
  aged out. What each source found is already in the evidence

````markdown
# 🟠 P2 · BUG-4830 · Approval step fails silently for Northwind Co when submitted via API

*Triaged 2026-09-21 14:22 UTC · team `demo` · agent 0.4.2*

`regression` `since 2026.09` `priority gap` `customer workaround`

> ### P2 regression in 2026.09
>
> **Why** · error swallowing at ApprovalReviewService.ts:89; 2026.09 changed ApprovalReviewService.ts.
>
> **Next** · **🔧 Fix now** · Approvals Team. Meanwhile: re-submit the approval through the UI rather than the API. Who: support.

**What happened** · The call returns 200 with no error and the request stays in Pending Review. 2026.09 shipped on 2026-09-05 and changed ApprovalReviewService.ts (#4412); errors rose 4.4× after it. The code at ApprovalReviewService.ts:89 swallows the error and carries on. The same failure was fixed before in BUG-4701. Affected: 1 account, 0 enterprise.

| | |
| --- | --- |
| **Disposition** | `defect` |
| **Priority** | **🟠 P2** · ❗ tracker has "Minor", set it to "Critical" |
| **Next action** | `fix_now` · 🔧 Fix now |
| **Confidence** | ●●● high |
| **Supported by** | 🟢 strong evidence · 4 of 5 sources: code `ApprovalReviewService.ts:89` · releases 2026.09 · metrics 4.4× baseline · tracker BUG-4701 |
| **Reproduction** | 🟢 seen in production |
| **Risks** | 💾 data integrity (evidenced) · 🔇 silent failure (evidenced) |
| **Route to** | **Approvals Team** |
| **Fix brief** | `triage-reports/BUG-4830.fix-brief.md` |

**Deciding factor:** confirmed regression with error swallowing at the bug site.

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

## Timeline

**Release:** 2026.09, correlation **high**. File-level overlap on ApprovalReviewService.ts. Likely introduced by #4412.

(sparkline and event table)

## Workaround

> 💡 **Re-submit the approval through the UI rather than the API.**
>
> **Who can do this:** support · **Cost:** a few clicks · **Source:** BUG-4701 resolution notes
> **Does not cover:** bulk approvals submitted by integration.

## Evidence

```
ApprovalReviewService.ts:89
} catch (e) { logger.warn('approval not committed', e); return { ok: true }; }
```

## Coverage

🟢 tracker ok · 🟢 releases ok · ⚪ metrics unavailable · ⚫ warehouse not queried · 🟢 code ok

All ten classification questions answered.

## Fields to update

```
priority  → Critical
labels    → component:approvals, severity:p2
assignee  → Approvals Team
```

> ℹ️ Nothing has been written to the tracker. Confirm before posting.
````

### Report rules

- A non-defect report stops after **Why this is a `<disposition>`**, the duplicate check
  and comments. No priority section, no correlation section unless one was gathered.
  Its route is the next action; a separate Route section would repeat it.
- The report opens with the answer as a quoted block (verdict as a heading, then Why,
  then **Next**: the fixed action in bold, the owner, and the workaround to use
  meanwhile or the triage's own step), then **What happened**: the story in a few sentences, composed by
  `scripts/story.py` from the result (symptom, release and error rise, code, prior fix,
  who is affected, existing fix). Then one at-a-glance table with no heading of its
  own, the confidence basis as one small line under it, then the Timeline (chart when
  a series exists, always the event table). Sections come after. There
  is no "Recommendation" heading: the table is the recommendation.
- Under the meta line, a strip of labels in code style says what kind of ticket this is
  and what is unusual: `regression` or `defect`, `since <release>`, `priority gap`,
  `overdue`, `needs a person`, `in a group`, `customer workaround` or `internal
  workaround`, `already fixed`. Only labels that apply are shown.
- Bold marks the facts a reader scans for: the release, the error factor, the file and
  line, the prior ticket, the account count, and the action. Each section heading
  carries one marker (⏱ Timeline, 🧭 Why, ⚖️ Against, 🧮 Priority, 💡 Workaround,
  🔎 Evidence, 💬 Comments, 📡 Coverage, ✏️ Fields). Colour in markdown is only the
  emoji vocabulary; nothing relies on HTML.
- "Why" is one sentence, claims joined with "and", never a list of fragments. For a
  non-defect it is the disposition evidence. A metrics claim reads "errors rose 4.3×
  from <date>", never the raw note.
- A route is shown as "Route to" only when it is a team or queue. An instruction
  ("link to X and close") is the Do now line, prefixed with the action when it names a
  destination ("Send to product: …"). Config keys in parentheses are stripped.
- When the triage wrote no timeline, the events are derived from the release date, the
  metrics note, the ticket date and any fix, so the sequence is still shown.
- **Say each fact once.** The priority gap is in the Priority row, not a callout. The
  owner is in Route to, not in the next action. The workaround is in Do now and its own
  section, not in the next action. Risks are one row in the at-a-glance table, not a section. Once a fix is
  merged, the report drops fix due, reproduction and complexity: the fix status says it.
- **Unanswered** replaces **Coverage** rows where a source was `off`, and the report
  says which questions went unanswered and what they would have changed.
- A source in `error` gets a `> 🛑` callout at the **top**, above
  the at-a-glance table, naming the source and the error.
- When the evidence is not strong, the callout reads, for example:

  ```markdown
  > 🛑 Evidence for where this bug lives is **weak**. Confirm the location before changing
  > code. If it cannot be confirmed, report back rather than opening a pull request
  > against a guess.
  > - code search was off, so no file or line was checked for a fault signal
  > - the only link to approvals-api/src/approvals/ApprovalReviewService.ts is a release
  >   record, which ties it by area, not by a fault found in the code
  ```
- **Evidence.** For every defect, run
  `python3 <plugin root>/scripts/render_fix_brief.py --assess <result.json>` and add an
  `Evidence` row to the at-a-glance table with its marker and level. When the level
  is not `strong`, place its `caution` text and `missing` list verbatim in a
  `> 🛑` callout above the table. Never soften, reword or omit it: the
  report, the trace and the fix brief must show the same verdict, and a fixer or
  reviewer reading any one of them must learn that the location is unconfirmed.
  Priority confidence and location evidence are separate: a confident P2 can still
  have weak evidence about which file to change.
- A disposition of `duplicate` requires a candidate the duplicate check scored
  `duplicate`. A title match is never enough.
- A workaround that failed verification is stated as not working. `not_reproduced`
  is stated as proving nothing.
- Never include a section with nothing in it. Omit it.

## 4. Tracker comment

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
Full report: triage-reports/BUG-4830-report.html
```

## Batch mode

One table, ordered by priority then by deciding factor. Non-defects in a separate
table below, never ranked among the defects.

`scripts/clusters.py` writes the batch as `batch-<date>.html` (with `clusters.json`) in
the report's look, through `scripts/pages_html.py`. It writes `batch-<date>.md` only when
`output.report_format` is `md` or `both`, or with `--markdown`. In agent mode it writes
only `clusters.json`. The queue page, `queue-<team>.html`, comes from
`render_queue.py --html` in the same look.

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
