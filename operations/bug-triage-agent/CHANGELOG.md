# Changelog

All notable changes to the bug triage agent. Newest first. Each release opens with a
one-line summary, then what was added, changed and fixed.

Versions follow semantic versioning: a minor version adds features or changes
behaviour a team would notice, a patch fixes something. The four manifests and the
marketplace entry always carry the same version, and `scripts/validate_config.py`
fails if this file has no entry for it.

## 0.8.0 · 2026-09-25

**Summary:** the HTML report becomes the default and the report grows up: a story at the
top, named risks, reproduction and fix complexity, groups of related tickets, evidence
against the verdict, SLA dates and a human-review gate; an agent mode and a handoff
index feed a fix agent; the queue, batch and automatic-run pages share the report's
look; and the validator now checks every page it can render.

### Added
- **Already fixed?** Before a defect is treated as live, the triage looks for a fix on the
  default branch (`fix_status.py`). A commit that names the ticket is a fix (strong); one
  that touches a located file after the ticket was filed and shares its error or symptom
  is a likely fix (moderate); one that only touches the file is listed as related, never
  claimed. The state says how far the fix has got: merged, released, or deployed.
- When a fix is found, the report opens with it, the next action becomes release,
  deploy or confirm with the customer, the fix brief says not to start a new fix, and
  the queue marks the ticket. The priority is kept as the priority while the bug is live.
- A merged fix that names the ticket counts as strong evidence of where the bug was.
- Demo ticket BUG-4866, fixed in 2026.09.1 but still open.
- **Groups in a batch** (`clusters.py`). After a batch, defects that locate the same file,
  or started with the same release in the same area, are grouped so one fix can close
  several. A group is *supported by evidence* only when at least two members have
  evidence at that file; otherwise it is *proposed*. Its priority is the highest member's
  and never raises anyone's. The batch report gains a group column and a groups section,
  and each member's report and trace say which group it is in.
- Demo ticket BUG-4872, a second swallowed error in ApprovalReviewService.ts.
- **Reproduction status and fix complexity** (`effort.py`), in the report, trace, fix brief
  and batch table. Reproduction says how far the failure has been seen: reproduced, seen
  in production, code path only, not reproduced, or not attempted. A script never claims
  "reproduced" on its own; that needs a record of what was run. Complexity is a 1 to 5
  score with the factors that set it (files located, evidence grade, missing behaviour,
  data repair, tickets one fix must cover). Neither changes the priority.
- **Named risks** (`risks.py`). Each defect is tagged from a fixed list: security, payment,
  data integrity, compliance, availability, silent failure, customer communication and
  performance. Each tag says how sure it is: *evidenced* by a code signal, *reported* in
  the ticket or a used comment, or only *suspected* from the hypothesis or code notes.
  The report, trace and batch table show them; the fix brief turns each into a check to
  test against. Teams add domain words in `risks.terms` or turn a type off in
  `risks.off`. Risks never change the priority by themselves.
- **Fix-by dates from the team's SLA** (`sla.py`, `sla` in the config). Off unless
  `sla.fix_within` is set. Each defect gets a due date from its priority, counted from
  the ticket's creation (or its triage), in hours, days or business days, and a state:
  on track, due soon, breached, or met when a fix was deployed in time. The report,
  trace, fix brief and batch table show it, and the queue flags triaged bugs that are
  due soon or breached. It never changes the priority. The `demo` config has example
  values.
- **Evidence against, and other causes** (`counterevidence.py`). The report and trace
  gain an "Against this, and other causes" section: each piece of evidence against the
  verdict, marked addressed (with why) or open, and the other plausible causes with why
  each is less likely. Some contradictions are found by rule: a release that shipped
  after the failure was first seen, a regression with no error rise, a duplicate found.
  The fix brief lists the alternatives as what to test next if the hypothesis fails.
  Rendering refuses high confidence while a contradiction against the disposition or
  priority is open, and weak location evidence with no alternative cause.
- **Next action from a fixed set** (`next_action.py`). Every triage ends in one of twelve
  actions (fix now, find the cause first, schedule the fix, release, deploy or confirm a
  merged fix, ask for information, close as duplicate, explain the behaviour, correct
  config or data, send to product, or wait for a reviewer), decided by rule, with the
  owner and any workaround to send or apply meanwhile. It shows in the report, trace,
  fix brief, batch table and automatic-triage digest. "Do now" stays as the detail.
- **Human review for chosen risks** (`human_review` in the config, `human_gate.py`).
  **Off by default.** When on, a defect carrying a chosen risk (security and payment by
  default, at "reported" or surer) is held for a person's decision: the report, trace
  and fix brief open with who must decide and why, automatic triage lists it under
  "Needs a person", the queue shows 👤 until it is reviewed, and nothing is posted or
  handed to a fix agent until a named reviewer confirms. Set up with
  `triage-config <team> review`.

### Fixed
- **Metrics query links opened an empty query.** The link used an older URL shape that
  the metrics tool redirects to a blank query over the last hour. A new
  `links.log_query` template (placeholders `{query}` `{from}` `{to}`) rebuilds every
  result link that carries a `query`, with the query and the evidence window, and
  `links.py --check` validates it. The demo-live config carries the template. The
  metrics envelope now returns `queries` (each query's text and window), the
  `enrich-metrics` agent is told to fill it, the orchestrator copies it into `links`,
  and the validator warns on a query link that lacks `query`, `from` or `to`.

### Changed
- **The HTML report is the default report; markdown is opt-in.** `triage` and
  `triage-auto` write `<TICKET>-report.html` and no longer write `<TICKET>.md` unless
  the new `output.report_format` is `md` or `both`, `output.run_trace` is `never`, or
  the user asks for markdown in that run. The HTML header links the markdown report
  only when one was written (`render_trace.py --markdown`). The fix brief stays
  markdown. Header links and the theme switch are now icon buttons.
- **Page checks in the validator.** `scripts/page_check.py` checks a rendered page for
  tags closed out of order or left open, a missing utf-8 declaration, empty, http or
  javascript links, new-tab links without `rel="noopener"`, in-page links to missing ids,
  and metrics-tool links in the old shape that open an empty query. The validator runs
  it on every shipped result's HTML report and on the batch, automatic-run and queue
  pages. It also runs on its own: `python3 scripts/page_check.py <page>.html`. The icons
  and page script moved to `html_theme.py`, so the pages no longer depend on the
  report renderer.
- **Automatic-run digest as a page.** `auto_triage.py digest` writes
  `<reports_dir>/auto/<date>-<team>.html` in the report's look: totals, "Needs a
  person", defects with verdict and next step, not-defects, runs not completed, briefs
  ready for a fix agent, and a copyable review command. The markdown file is written
  only for `report_format` `md` or `both`; the markdown is still printed for the chat.
  Report links now point at the ticket's HTML report, or its markdown when that is all
  there is (they pointed at `<TICKET>.md`, which is no longer written by default).
- **Handoff index for fix agents.** `scripts/brief_index.py` writes
  `<reports_dir>/briefs.json` after every run: the fix briefs a fix agent may pick up
  (`ready`, ordered by priority then fix-by date, with branch, fault and evidence) and
  the ones that wait (`held`, with the reason: `human_review` until a person records a
  review, `already_fixed`, `locate_first` for weak location evidence, `no_brief`).
  Scoped to the team when given its config.
- **Agent mode, and a parseable fix brief.** `output.report_format: agent` writes only
  the result file and, for defects, the fix brief, for a pipeline that hands defects
  to a fix agent. The brief's front matter (`brief_version: 2`) adds `ticket_url`,
  `fault` (file, line, signal, url), `introduced_by`, `fix_status`, `already_fixed`,
  `hypothesis` with its confirm and refute tests, `alternatives` and `acceptance`.
  Values YAML would read as another type (a version like `2026.09`) are quoted.
- **Labels, bold facts and heading markers in the markdown report.** A label strip under
  the title (`regression`, `since 2026.09`, `priority gap`, `overdue`, `needs a person`,
  `customer workaround`, …), the key facts in the story in bold, and one marker per
  section heading. The answer's third line is now **Next**: the fixed action in bold,
  the owner, and the workaround to use meanwhile; "Do now" is gone. The "Next action"
  table row and tile are gone with it.
- **HTML report redesigned** from an approved design canvas. It opens with the message:
  a plain paragraph of what happened, three action boxes (what support does now, what
  the owning team fixes and where, what to set in the tracker on a yes), and the
  priority with the tracker gap and confidence. Then: the numbers from the error series
  (rate now, baseline, ratio, peak, excess errors, deploy to rise), the risks as tiles
  with a filled certainty label that link to their evidence (the code line, the log
  query, the ticket or comment), a time-scaled timeline with the bug's live span, the
  hourly error chart with baseline and 3× lines, the priority ladder and evidence
  meters, where it is (code blocks show 12 lines, collapse the rest, highlight the fault
  line, copy), a sources table naming each provider (`sources.<s>.provider` in the
  config), duplicates as score bars, comments and evidence against, the stage flow with
  each stage's status, and the fields to update. Light theme by default, with a
  Light / Dark / System switch remembered per viewer.
- **HTML report** (`report_html.py`, written by `render_trace.py` as
  `<TICKET>-report.html`). A designed page: a left rail with the ticket, the priority,
  the tracker gap, the owner, buttons to the tracker, the markdown report and the fix
  brief, the contents, and every source read; a reading column in this order: the
  answer (verdict, why, next, what happened, key facts), when it started (the timeline
  and the error chart), where it is (locations, code, the release and commit), why it
  is a defect (with the evidence against and other causes), the priority ladder, the
  workaround, fix status and history, comments, duplicates, how it was produced, and
  the fields to update. Every ticket key, file, line, release, commit, PR, log query,
  deploy and comment links, including mentions inside prose. Serif headings, sans body,
  mono for keys and code; light and dark themes; collapses to one column on a phone.
  The markdown report is unchanged in content and stays the version to post and diff.
- The markdown report uses no raw HTML: the meta line and the confidence basis are
  italic lines, so they render in every viewer.
- **The story at the top.** Under the answer, a "What happened" paragraph tells the
  sequence in a few sentences, composed from the result: the symptom, what shipped and
  when errors rose, what the code shows (or that it was not read), whether the same
  failure was fixed before, who is affected, and whether a fix already exists
  (`story.py`). "Why" is one readable sentence. The confidence basis sits under the
  table as one small line. A route shows as "Route to" only for a team; an
  instruction becomes the Do now line with the action in front. The timeline is
  derived from the release, metrics and ticket dates when the triage wrote none, and
  it now sits right under the story, before the detail sections.
  Reproduction is shown only when something was seen or tried; complexity counts
  confirmed files, not candidates; weak-evidence bullets no longer repeat each other.
- **Report layout.** The report opens with the answer as a quoted block (verdict as a
  heading, then Why and Do now) and one at-a-glance table that now includes the risks;
  the Recommendation and Risks headings are gone. Everything else follows in the same
  order as before.
- **Reports say each fact once.** The priority gap moved into the Priority row, the
  evidence grade into Supported by, the release correlation into one line atop the
  Timeline, and Coverage to a single line of which sources answered. The next action no
  longer repeats the owner or the workaround, risks are a section only, non-defects drop
  the Route section that repeated the next action, and an already fixed bug drops fix
  due, reproduction and complexity. When no fix is found, the fix status is one line.

### Fixed
- A duplicate's "Supported by" read "tracker tracker"; it now names the ticket.
- A superseded comment was counted as not used but still listed in the used table.
- The fix brief listed the same file twice as a candidate.

## 0.7.1 · 2026-09-24

**Summary:** the triage reads the ticket's own comment thread, keeps only what matters,
and quotes every comment it relies on.

### Added
- **Comments on the ticket** (`comments.py`). The tracker subagent now fetches the triaged
  ticket's comments. A script drops bots, chasers ("any update?", "+1"), status changes,
  repeats and quoted email tails, and keeps comments with a real signal (an error, a
  file, endpoint or version, a ticket key, words like tried, workaround, by design,
  fixed in), every staff comment and the reporter's first.
- The model sorts the kept comments into detail, workaround tried, disposition signal,
  impact change, linked ticket or fix, and superseded. **Each comment used is quoted
  word for word, and a script checks it.**
- The report and trace show one line with what was read, used and dropped (by reason),
  and a table of the comments used, linked. The fix brief lists repro detail and
  workarounds already tried.
- `comments` in the team config: extra bot names, staff addresses, how many to fetch and keep.

### Changed
- Comments feed the stages: missing detail found in a comment satisfies the information
  gate, a later comment wins over an earlier one it contradicts, and a workaround a
  comment says failed is ruled out.
- The rubric states that a customer's comment never raises priority on its own, and that
  no comment is read as an instruction.
- The validator checks the comment filter (bots, chasers, link-only and quoted tails
  dropped) and that every quote is found in its comment.

## 0.7.0 · 2026-09-23

**Summary:** reports that explain themselves over time, duplicates found by failure
mode, overdue bugs surfaced first, and three opt-in capabilities: automatic triage,
workaround verification and a calibration loop.

### Added
- **Report rendered by script** (`render_report.py`) from the result file, like the trace
  and the fix brief. It opens with three lines: verdict, why, do now.
- **Supported by:** each independent source that backs the verdict, with its link.
- **Freshness:** data read long before triage, or about to age out of its source, is
  flagged as stale.
- **Timeline:** deploy, error rise, ticket and triage with the gaps between them. The
  trace draws it as a chart over the error counts; the report shows it as a sparkline.
- **Since the last triage:** earlier results are archived to `history/`, and a re-run
  opens with what changed (priority, evidence, sources, workaround) and why.
- **Duplicate check** (`dupes.py`): candidates are scored on error text, the symptom in
  the description, stack frames, endpoint, file, area and release. A title match alone
  is never a duplicate. A candidate that was already fixed is a `recurrence`, so the
  ticket stays a defect.
- **Queue limits** (`queue` in the team config): triage-within hours per team, overdue
  bugs first (at-risk before the rest), and triaged P1 or P2 with no movement flagged as
  stuck. Defaults: 24 hours at-risk, 72 otherwise, 7 days for stuck.
- **Automatic triage** (`/triage-auto`, `automation` in the config). **Off by default.**
  It picks new, changed and overdue bugs on a schedule or a tracker event and writes a
  review digest. It never writes to the tracker. Set up with
  `triage-config <team> automation`.
- **Workaround verification** (`verification` in the config). **Off by default.** It
  checks that the workaround works before the report recommends it, with an `http`,
  `docker`, `ci` or `command` runner. It never runs against production, allows only GET
  unless configured, and cannot leave the configured base URL.
- **Calibration** (`/triage-log calibrate`): repeated override patterns and the change
  each suggests. For example, a disposition that is over-applied, an escalation that
  keeps being lowered (with the config key to check), or overrides clustering in one
  area or on one reviewer.
- **Accuracy dashboard** (`/triage-log dashboard`): one HTML page with tabs for overview,
  dispositions, priority, trend, calibration and runs.
- The audit log records `area` and `override_by` for calibration.

### Changed
- The tracker subagent returns up to 10 duplicate candidates, with their descriptions.
- `triage-doctor` reports automation, verification and queue limits.
- The validator checks the new config sections, and holds a set of guards: a title-only
  match never scores as a duplicate, production verification is refused, and automatic
  triage cannot write to the tracker.

### Documentation
- The architecture diagram shows duplicate scoring, workaround verification, the result
  file as the single source for every output, history, and automatic triage. A new
  feedback-loop diagram covers queue, triage, review, calibration and dashboard.
- Overview, glossary, extending guide, documentation index, output templates and status
  are updated for 0.7.0.

## 0.6.7 · 2026-09-23

**Summary:** every piece of evidence links to its source, behind a short label.

### Added
- Links on code locations (pinned to a commit), releases, commits, tickets, log queries
  and deploys, shown behind labels such as `ApprovalReviewService.ts:89` or `2026.09`.
- A `links` section in the team config with URL templates, used only when a tool returns
  no URL.

### Fixed
- Log query URLs with parentheses broke markdown links; they are now encoded.
- A file link no longer gets an invented `#L1` anchor.
- A PR link falls back to the commit when the number may not be a PR.

## 0.6.6 · 2026-09-22

**Summary:** code evidence even when search lags, richer metrics, and a warning when a
run reads the plugin's own config.

### Added
- The code source reads files under `key_paths` when code search returns nothing.
- Metrics can combine a log store with a hosting platform's deploys and runtime logs.
- The header warns when a live run uses the config shipped inside the plugin rather
  than the team's own.
- The live demo runs on a real tracker, code host, log store and hosting platform.

## 0.6.5 · 2026-09-22

**Summary:** change one section of a team config without walking the whole setup.

### Added
- `triage-config <team> <section>` changes only that section and shows a diff. Naming
  the code host sets up code search and release tags together.

## 0.6.4 · 2026-09-22

**Summary:** Codex and ChatGPT now load the skills.

### Fixed
- Added `.codex-plugin/plugin.json`. Without it the plugin installed but loaded no
  skills, so `@bug-triage-agent` had nothing to call. The validator now checks it.

## 0.6.3 · 2026-09-22

**Summary:** every command is backed by a skill, so clients without commands lose
nothing.

### Added
- New skills `triage-readiness`, `triage-history` and `triage-override`; commands are thin
  wrappers over skills, and the validator enforces it.
- A bare word such as `queue` or `log` routes straight to its skill.
- The plugin-root search knows the Cursor and Codex install folders.

## 0.6.2 · 2026-09-22

**Summary:** name the team or project as a plain word.

### Changed
- `queue demo-live` or `queue DEMO` works. Some hosts rejected a command whose first
  argument was a flag.

### Fixed
- The queue now reads ages from tracker dates with offsets written without a colon.

## 0.6.1 · 2026-09-22

**Summary:** three commands reappear.

### Fixed
- Command hints starting with `[` were unquoted, so `/queue`, `/triage-log` and
  `/triage-doctor` did not load. The validator now checks front matter.

## 0.6.0 · 2026-09-22

**Summary:** a bug queue, a triage log, fix briefs for a fixing agent, and no need to
name the team.

### Added
- `/queue`: open bugs and what still needs triage, with priority gaps and tickets
  changed since their last triage.
- `/triage-log`: recommendations and overrides, with agreement rates.
- A fix brief per defect for a fix-bug agent, with evidence graded strong, moderate or
  weak, and a caution in report, trace and brief when it is not strong.
- Team chosen from the ticket's project key, then the user's email, then a local or
  plugin default.
- A colour-marked markdown header, and live stage progress.
- A hint when a connector is connected but its source is off.

### Changed
- `+1 history` counts only fixed defects.
- `triage-config` stops when a required answer is skipped.
- The shipped configs are trimmed to `demo` and `demo-live`.

## 0.5.3 · 2026-09-22

**Summary:** runs from a sandboxed shell.

### Fixed
- The plugin root and the user's folder are resolved first, so a sandboxed shell no
  longer reports the plugin's files as missing.
- `triage-teams/` is found under the working folder, not the shell's start directory.
- The audit log is written to `triage-logs/` in the working folder, never inside the
  plugin.
- The header prints the agent version and the root it ran from.

## 0.5.2 · 2026-09-22

**Summary:** live tracker calls stay out of the chat.

### Changed
- Live tracker calls run in the `enrich-tracker` subagent, so the chat is not flooded
  with ticket cards.

## 0.5.1 · 2026-09-22

**Summary:** team files and release files live with the team.

### Fixed
- A relative config path means the user's folder first.
- The header no longer calls placeholder bindings "bound".
- `manual_file_path` resolves beside the team config first.

## 0.5.0 · 2026-09-22

**Summary:** set up a team by conversation, in the team's own folder.

### Added
- `/triage-config`: discovers connected tools, reads project keys, priorities and
  labels from them, proves the tracker by fetching one issue, and never asks for
  credentials.
- Config lookup order: config directory, then `triage-teams/` in the working folder,
  then the plugin's demos.

## 0.4.4 · 2026-09-22

**Summary:** traces opened from disk render correctly.

### Fixed
- Rendered traces declare UTF-8. Without it, browsers showed mojibake for every marker.

## 0.4.3 · 2026-09-22

**Summary:** the run trace is rendered by code.

### Added
- `render_trace.py` renders `<TICKET>-trace.html` from a result file, with a priority
  ladder that shows held escalations. Worked results for the demo tickets.
- Architecture diagrams.

## 0.4.2 · 2026-09-22

**Summary:** a colour vocabulary for reports.

### Added
- Fixed markers for priority, source status and confidence, and one callout per
  purpose. Every colour is paired with text.

## 0.4.1 · 2026-09-22

**Summary:** the header comes from code, and the run narrates itself.

### Added
- `run_header.py` prints the header deterministically before any work starts.
- Stage lines as each stage completes.

## 0.4.0 · 2026-09-22

**Summary:** show the run, not just the answer.

### Added
- Run visibility: header, stage lines, task list and run trace.
- The live demo team config.

## 0.3.0 · 2026-09-21

**Summary:** three outputs for three readers.

### Added
- A chat summary, a report file and a plain-text tracker comment, each shaped for its
  reader.

## 0.2.1 · 2026-09-21

**Summary:** read-only is an instruction, not an enforced boundary.

### Fixed
- The agent tool allowlists granted no tools at all. Agents now declare all tools, and
  read-only is documented honestly as an instruction. The real barriers are the
  read-only account, the SQL check and per-ticket confirmation.
- A ticket with no component no longer makes history project-wide without saying so.

## 0.2.0 · 2026-09-21

**Summary:** the plugin binds to connectors you already have.

### Changed
- **Breaking:** the plugin no longer declares MCP servers of its own. It binds to tools
  already in the session through `tool_bindings`, including the tracker.

## 0.1.0 · 2026-09-21

**Summary:** first release.

### Added
- Disposition before priority, release correlation over a full release cycle,
  workaround discovery, and a priority rubric with escalation caps.
- A shared rubric, with one config file per team.
- Recorded fixtures, a validator and an audit log.
