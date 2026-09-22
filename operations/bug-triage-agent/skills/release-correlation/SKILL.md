---
name: release-correlation
description: Identify which release most likely touched the area a bug affects, using fix versions and merged pull requests over a full release-cycle lookback. Use when triaging a bug, asking which release caused an issue, or asking what shipped near a report date.
---

# Release correlation

Answers: which recent release touched this area, and how does the report date sit
relative to it.

Works with tracker alone. Code search improves it but is not required.

## Window

`release_correlation.lookback_days`, default two release cycles. A 24-hour deploy
window is wrong for a monthly cadence: bugs surface days or weeks after a release.

## Procedure

1. **Build the release list** for the window by running every adapter in
   `release_correlation.manifest_sources`, in order, and merging on the normalized
   version string. The adapters are defined in `skills/data-sources/SKILL.md`.

   Match the order to the org's ecosystem. tracker-and-wiki-heavy orgs start with
   `tracker_fixversion` and `wiki_release_notes`, which need no connector beyond
   the one tracker already requires. Add `vcs_tag` when file-level resolution is
   wanted.

   Each release records which adapters contributed. Report that in the output: a
   correlation resting on a release-note page is weaker evidence than one resting on
   the merged pull requests, and the reader should be able to tell them apart.

2. **Determine the bug's affected area.** In order of strength: the component field,
   the code paths returned by the `code` source, the service named in the metrics source errors,
   the feature named in the ticket text.

3. **Score each release** on:
   - **area overlap**: does the release touch the same component, service, or file?
   - **timing**: days between release date and first report. Inside one cycle is
     ordinary; a report on the day of release is stronger; a report before the release
     rules it out.
   - **signal**: an error-rate change at the release boundary, when the metrics source is live.

4. **Rank and report.** Name the strongest candidate and the runner-up. State the
   evidence class for each.

## Confidence

| Confidence | Condition |
| --- | --- |
| high | File-level overlap (`vcs_tag` or `vcs_pr`) plus a the metrics source change at the release boundary. |
| medium | Component-level overlap (`tracker_fixversion` or `wiki_release_notes`) plus plausible timing. |
| low | Timing only, no area overlap, or the only adapter available was `manual_file`. |

Low confidence is reported as "shipped near the report date, no evidence it touched
this area". Do not present proximity in time as causation.

## Honest negatives

If no release in the window touched the area, say so explicitly. "No release in the
last 60 days touched the approval review path" is a useful finding: it points at data,
configuration, or a latent bug rather than a regression.
