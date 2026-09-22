# Feature Specification: Decisive-source prompting

**Feature Branch**: `001-prompt-only-when`
**Created**: 2026-09-21
**Status**: Draft
**Input**: "Check for external connectors at the start, at least one per category, and prompt the user when the agent's output is going to be compromised."

## Summary

When a source a triage depends on is missing or failing, the agent should say so at the
moment it matters, and only then. This specification narrows the original request: it
replaces "prompt whenever a category has no connector" with "prompt when a missing or
failing source would plausibly change *this* recommendation".

Two findings drove the narrowing.

A blanket per-run warning recreates the dynamic that killed the previous attempt. That
design inflated priority when blast radius was unknown, so teams with incomplete setup
got worse output and stopped using it. A warning on every run punishes the same
incompleteness with friction and the message "this is not really working for you".
Constitution Principle III is explicit: absent capability lowers confidence, it does not
degrade the tool's standing.

Requiring one connector per category contradicts the zero-setup tier, which is the
adoption mechanism. The tracker-only path must stay first class.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A configured source is silently failing (Priority: P1)

A team has the metrics source configured. The connector is timing out. A triage runs,
finds no regression signal, and returns a lower priority than the truth.

The user believes they have regression detection. They do not. Today this surfaces only
as a `low` confidence line that is easy to skim past.

**Why P1**: this is the only case where the user holds a false belief about coverage. An
`off` source is a known gap; an `error` source is an unknown one.

**Acceptance**:
1. **Given** metrics is `live` and its probe fails, **When** a triage runs, **Then** the
   output leads with the failure, names the source and the error, and states which
   questions went unanswered because of it.
2. **Given** the same, **Then** confidence is capped at `low` and the audit record
   carries `source_errors`.
3. **Given** an `off` source in the same run, **Then** it is reported as a normal gap and
   is **not** escalated to the same prominence.

### User Story 2 - A missing source is decisive for this ticket (Priority: P2)

A ticket says "several customers are hitting this". The warehouse is `off`, so blast
radius cannot be counted. That single fact could move the recommendation between P3 and
P2.

**Acceptance**:
1. **Given** warehouse is `off` **and** the ticket text indicates multi-account or
   systemic impact, **When** the triage runs, **Then** the agent asks whether the user
   can supply the account count, or confirms proceeding without it.
2. **Given** warehouse is `off` **and** the ticket describes a single-account cosmetic
   issue, **Then** no prompt appears. The missing source is not decisive.
3. **Given** metrics is `off` **and** the ticket says the behaviour started recently or
   after a release, **Then** the agent asks, because regression is decisive.
4. **Given** any prompt is raised, **Then** the output records which question triggered
   it and what answer was given.

### User Story 3 - First run for a team (Priority: P3)

A team installs the plugin and triages its first ticket without ever running the
readiness check.

**Acceptance**:
1. **Given** no readiness check has been recorded for this team, **When** the first
   triage runs, **Then** the agent reports source modes and reachability once before
   producing the recommendation.
2. **Given** a readiness check has been recorded, **Then** subsequent runs do not repeat
   it.
3. **Given** the check runs, **Then** it does not block the triage. It informs.

### Edge Cases

- **Unattended execution.** Batch mode and the future event trigger have no human to
  answer. A prompt must degrade to a flag on the output and a field in the audit record.
  It must never block.
- **Every source off except the tracker.** The zero-setup tier must not produce a prompt
  on every ticket. Only decisiveness triggers one.
- **Prompt fatigue.** If a team is prompted for the same missing source repeatedly, that
  is a signal to suggest configuring it once, not to keep asking.
- **The user declines to answer.** Proceed, record the unanswered question, cap
  confidence. Declining is not an error.
- **A source errors midway** after stage 1 has already succeeded. Report per-source, do
  not discard the stages that worked.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST distinguish three source states in output and logs: `off`
  (deliberate), `error` (configured and failing), `unavailable` (not configured).
- **FR-002**: The system MUST surface an `error` state prominently, naming the source and
  the error text, on every run where it occurs.
- **FR-003**: The system MUST NOT raise a prompt solely because a source is `off`.
- **FR-004**: The system MUST evaluate, per ticket, whether an absent source is
  *decisive*: whether a plausible value for it would change the disposition or the
  priority level.
- **FR-005**: The system MUST raise at most one prompt per run, naming the decisive
  question and what it would change.
- **FR-006**: The system MUST proceed without blocking when no human can answer, and
  record the unanswered decisive question on the output and in the audit record.
- **FR-007**: The system MUST record, per team, that a readiness check has run, and MUST
  NOT repeat it on later runs.
- **FR-008**: Absent or failing sources MUST NOT raise the recommended priority. Existing
  round-up rules remain tied to evidence in the ticket.
- **FR-009**: The audit record MUST carry `source_errors`, `decisive_gaps`,
  `prompt_raised` and `prompt_answer` so prompting behaviour can be measured.

### Key Entities

- **Source state**: one of off, error, unavailable, ok. Per source, per run.
- **Decisive gap**: an absent or failing source plus the classification question it
  would answer plus the levels the answer could move the result between.
- **Readiness record**: per team, whether the check has run and when.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the zero-setup tier, fewer than 1 in 5 tickets raise a prompt. If more,
  the decisiveness test is too loose and is behaving like the blanket warning this
  specification exists to avoid.
- **SC-002**: Every run with a source in `error` surfaces it. No silent failures.
- **SC-003**: Across the calibration set, tickets where a prompt was raised show a higher
  rate of human override than tickets where none was, confirming prompts land on genuinely
  uncertain cases.
- **SC-004**: No run produces a higher priority than the same run with all sources
  available.
- **SC-005**: Unattended runs never block.

## Assumptions

- The audit log and `/triage-review` exist by the time SC-003 can be measured. Neither is
  implemented yet.
- A calibration set exists to test against. It does not yet.
- Ticket text is a usable signal for decisiveness. **This is the weakest assumption in the
  specification.** Judging from prose whether blast radius matters is exactly the kind of
  rule that reads well and behaves unpredictably. It must be measured against real tickets
  before rollout, not reasoned about further.

## Open Questions

- [NEEDS CLARIFICATION] Should a prompt ever block an interactive run, or always inform
  and proceed? Blocking guarantees attention and guarantees annoyance.
- [NEEDS CLARIFICATION] Where does the per-team readiness record live? The plugin has no
  writable state today beyond the audit log.
- [NEEDS CLARIFICATION] Is one prompt per run the right cap, or should several decisive
  gaps be presented together?
