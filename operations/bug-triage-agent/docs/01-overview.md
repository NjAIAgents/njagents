# Overview

## The problem

Triage has two questions in it, and most tools only answer the second.

1. **Is this a defect at all?** Or is it working as designed, a duplicate, a
   configuration problem, or a request for different behaviour?
2. **If it is a defect, how urgent is it?**

Tools that skip the first question score everything, including the tickets that should
never have entered the defect queue. A ticket confidently marked P2 that turns out to
be expected behaviour is worse than no triage: it consumes engineering attention and
teaches people to distrust the label.

The judgment to answer question one usually sits with two or three experienced people.
It works, and it does not scale. As release cadence increases, triage volume rises and
the window to connect a report back to what shipped shrinks.

## What this does

Given a bug ticket, in order:

1. **Checks it can be triaged at all.** Missing repro, component or error goes back to
   the reporter rather than being guessed at.
2. **Assigns a disposition** with cited evidence, and routes non-defects away.
3. **Correlates to a release**, over a full release cycle rather than a 24-hour deploy
   window, and reports honestly when no release touched the area.
4. **Finds a workaround** and states who can perform it, because an engineer-run script
   does not unblock a customer.
5. **Scores priority** for defects only, showing its arithmetic.
6. **Logs the recommendation** so the gap between it and the human's final call can be
   measured.

## Four design decisions, and why

**Disposition before priority.** The ordering is the product. Everything else is
commodity.

**One shared rubric, thin per-team configuration.** A team owns one config file and
never a copy of the rubric. When two teams hold different copies of a rubric, they
grade the same bug differently and neither is wrong by its own configuration. That is
how "one quality bar across teams" fails in practice.

**Absent sources lower confidence, never raise priority.** A predecessor rounded
priority up when blast radius was unknown, so teams that had not finished connector
setup got inflated priorities, stopped trusting the output, and stopped using it. Here,
escalation is tied to evidence in the ticket; a switched-off connector costs you an
answered question and some confidence, nothing else.

**Evidence or abstain.** Any disposition other than `defect` must cite a document,
ticket or config value. Uncited, it degrades to `defect` with low confidence, because
wrongly closing a real bug costs more than wrongly scoring a non-bug.

## What it deliberately does not do

- **Write to the tracker on its own.** Output is paste-ready text and a field
  checklist. Posting needs per-ticket confirmation.
- **Replace incident management.** It detects a P1 signal and emits an escalation
  block. Your incident process takes it from there.
- **Fix bugs.** No code generation, no auto-fix pull requests.

## The honest caveat

The disposition taxonomy shipped here is a *construction*, not any organization's
observed judgment. It is a starting hypothesis with a measurement attached. See
[`reference/taxonomy-calibration.md`](../reference/taxonomy-calibration.md) for how to
replace it with the real thing, and why the tracker changelog gives you a labelled test
set for free.
