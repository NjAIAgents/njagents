# Changelog

All notable changes to the bug triage agent. Newest first. Each release opens with a
one-line summary, then what was added, changed and fixed.

Versions follow semantic versioning: a minor version adds features or changes
behaviour a team would notice, a patch fixes something. The four manifests and the
marketplace entry always carry the same version, and `scripts/validate_config.py`
fails if this file has no entry for it.

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
