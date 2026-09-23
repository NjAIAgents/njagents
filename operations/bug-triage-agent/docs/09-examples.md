# Examples

Worked runs you can copy. Each one gives the command, what you should see, and what to
check. The outputs shown are real, produced by version 0.7.0 against the shipped demo
configs.

## Before you start

1. Install or update the plugin to **0.7.0** and start a new session.
2. Run it in **Cowork or Claude Code**, not a regular Chat. A Chat syncs only the skill
   folders, so the scripts and configs are missing and the triage stops at step one.
3. In Cowork, connect a working folder. Reports, traces, fix briefs and the log are
   written there, never into the plugin.

Commands are namespaced by the plugin. In Cowork type `/bug-triage-agent:triage`; in
Claude Code `/triage` also works when no other plugin claims the name.

Two demo teams ship with the plugin:

| Team | Tickets | Needs | Use it to |
| --- | --- | --- | --- |
| `demo` | `BUG-4830`, `BUG-4844`, `BUG-4851`, `BUG-4858` | Nothing. All five sources are recorded fixtures | See every stage and every disposition without connecting anything |
| `demo-live` | `DEMO-1` to `DEMO-10` | Jira (`DEMO`), GitHub (`NjAIAgents/njagents-demo-app`), Grafana Cloud Loki, Vercel | A full live run: tracker, releases, metrics and code from real systems carrying one synthetic story |

You do not pass `--team` for either. The team is found from the ticket's project key:
`BUG-*` resolves to `demo`, `DEMO-*` to `demo-live`.

## 1. Triage one ticket, no connectors

```
/bug-triage-agent:triage BUG-4830
```

**First thing you see** is the run header, printed before any work starts:

> **Bug triage · BUG-4830 · team `demo`**
>
> | Source | Mode | |
> | --- | --- | --- |
> | tracker | 🟡 fixture | fixtures/tracker |
> | releases | 🟡 fixture | fixtures/releases.json |
> | metrics | 🟡 fixture | fixtures/metrics |
> | warehouse | 🟡 fixture | fixtures/warehouse |
> | code | 🟡 fixture | fixtures/code |
>
> **5 of 5 sources available.** Absent sources lower confidence and drop escalations. They never raise severity.
> Team **demo**, chosen by ticket project BUG · Config: `…/teams/demo.json` (plugin) · Agent **0.7.0**

Then a task list ticks through the stages (disposition, enrichment, correlation,
workaround, priority, outputs), each rewritten with its result as it finishes.

**Expected result**

| Field | Value |
| --- | --- |
| Disposition | `defect` |
| Priority | 🟠 **P2**, confidence high |
| Why P2 | Base P3 because a workaround exists, `+1 release` for a confirmed regression after 2026.09 |
| Evidence | 🟢 **strong**: error swallowing at `ApprovalReviewService.ts:89`, and the same file changed in 2026.09 |
| Priority gap | Tracker says "Minor", recommended "Critical" |
| Route to | Approvals Team |

**Files written** to `triage-reports/` in your working folder:

| File | What it is |
| --- | --- |
| `BUG-4830.md` | The report, with colour markers and the full reasoning |
| `BUG-4830-trace.html` | The run trace: every stage, every source call, every rule that fired |
| `BUG-4830.fix-brief.md` | A brief a fix-bug agent can pick up (see example 4) |

A line is also added to `triage-logs/triage-log.jsonl`.

**Check:** nothing was posted to the tracker. A comment is only offered, and only posted
after you confirm it for that ticket.

## 2. Triage a batch and see every disposition

```
/bug-triage-agent:triage BUG-4830 BUG-4844 BUG-4851 BUG-4858
```

One header, then one task per ticket, then a ranked table. Expected:

| Ticket | Disposition | Priority | Evidence | Why |
| --- | --- | --- | --- | --- |
| BUG-4851 | `defect` | 🟠 P2 | 🔴 weak | Core workflow blocked, only an engineer-only workaround; at-risk renewal. No fault signal found in code |
| BUG-4830 | `defect` | 🟠 P2 | 🟢 strong | Regression after 2026.09, error swallowed at the bug site |
| BUG-4844 | `voice_of_customer` | none | | Held balance release is deliberately manual (BUG-3120 closed as designed); routed as a request |
| BUG-4858 | `duplicate` | none | | Same failure mode as open BUG-4849 |

**Check:** the two non-defects have **no priority**. Disposition always comes first, and
a ticket that is not a defect is never scored.

**Check:** BUG-4851 carries a caution in its report and its fix brief, because the
evidence for *where* the bug lives is weak even though the priority is P2. Priority
says how much it matters; evidence says how sure we are where to look.

## 3. See what still needs triage

```
/bug-triage-agent:queue
```

With no ticket to read a project key from and no config in your folder, this falls
back to the plugin's default team, `demo`:

> ### Bug queue · BUG · team demo · 4 open
>
> Team chosen by the plugin's default team.
> 4 not yet triaged · 0 triaged by the agent
>
> | Ticket | Summary | Area | Tracker priority | Age | Last triage |
> | --- | --- | --- | --- | --- | --- |
> | BUG-4851 | Nightly settlement export missing for Fabrikam since Frid… · `at-risk` | settlements | Critical | 1d | **not triaged** |
> | BUG-4830 | Approval step fails silently for Northwind Co when submit… | approvals | Minor | 8d | **not triaged** |
> | BUG-4844 | Held balance is not released on the final approval and th… | approvals | Major | 6d | **not triaged** |
> | BUG-4858 | Amount column misaligned in the reporting export header | reporting | Major | 3d | **not triaged** |
>
> Next, triage the untriaged ones:
>
>     /bug-triage-agent:triage BUG-4851 BUG-4830 BUG-4844 BUG-4858

Untriaged first, at-risk first within that, oldest next. Run it again after example 2
and the last column fills in, with ⚠ where the tracker priority disagrees with the
agent's.

## 4. Hand a bug to a fix-bug agent

Every defect gets a fix brief. Open `triage-reports/BUG-4830.fix-brief.md`. It starts
with front matter another agent can parse:

```yaml
ticket: "BUG-4830"
title: Approval step fails silently for Northwind Co when submitted via API
team: demo
repo: "approvals-api"
base_branch: main
branch: "fix/bug-4830-approval-step-fails-silently-for"
priority: P2
priority_confidence: high
evidence: strong
location_confirmed: true
candidate_files:
  - "approvals-api/src/approvals/ApprovalReviewService.ts:89"
  - "approvals-api/src/approvals/ApprovalReviewService.ts"
route_to: Approvals Team
generated_by: "bug-triage-agent 0.7.0"
```

Then: Problem, Reproduce, Where to look, Prior fixes, Hypothesis to test, Definition of
done, Constraints, Not checked by triage, and Pull request.

Give it to your fix agent as it stands, for example:

```
Fix the bug described in triage-reports/BUG-4830.fix-brief.md. Follow its constraints.
```

**Check BUG-4851's brief too.** It says `evidence: weak` and opens with:

> Evidence for where this bug lives is **weak**. Confirm the location before changing
> code. If it cannot be confirmed, report back rather than opening a pull request
> against a guess.

Triage never opens a branch or a pull request itself. The brief is the handoff.

## 5. The live demo

Needs Jira, GitHub, Grafana and Vercel connected, and the Loki data seeded within the
last week (`seed/seed_grafana.py` in the demo repo; Grafana Cloud drops older lines).
The story every system tells is in the demo repo's `docs/STORY.md`.

```
/bug-triage-agent:triage-doctor demo-live
/bug-triage-agent:queue demo-live
/bug-triage-agent:triage DEMO-7
```

A command takes a team or project as a plain word: `demo-live` names the team, `DEMO`
names the project. `--team demo-live` also works in Claude Code, but some hosts reject a
command whose first argument is a flag, so the plain word is the form to use.

**Doctor** checks every source is reachable and every tool binding resolves. Tracker,
releases, metrics and code are 🟢 live; warehouse is ⚫ off. If it says it is using the
plugin's shipped config, your folder with `triage-teams/demo-live.json` is not the one
connected.

**Triage DEMO-7.** Expected:

| Field | Value |
| --- | --- |
| Disposition | `defect` |
| Release | 2026.09 changed `ApprovalReviewService.ts` (#4412), from the GitHub tag |
| Metrics | Loki: "approval not committed" rises 4.4x, 52h after the deploy. Vercel: the warning appears only on the 2026.09 deployment |
| Code | Error swallowing at `ApprovalReviewService.ts:89`, found by search or, while GitHub search lags, by the file-read fallback |
| Priority | 🟠 **P2**, confirmed regression |
| Evidence | 🟢 strong: code signal and the release both point at the same file |
| History | Only fixed defects count toward `+1 history`. A works-as-designed closure in the same area does not |

Other live tickets: DEMO-9 is an at-risk defect whose nightly export has been silent
since the seeded date; DEMO-10 is a duplicate of DEMO-6; DEMO-8 is a customer request
with no priority.

**Check:** no tracker cards appear in the chat. Live reads run inside a subagent and
only a summary comes back.

**Check:** if a metrics, SQL or code connector is connected in your session, the
header adds one line such as:

> **Available but off:** a metrics connector is connected in this session, but
> metrics is off for team `demo-live`. To use it: `/bug-triage-agent:triage-config demo-live`.

The agent does not use that connector for this run. The team config decides what a
triage reads, so results do not change with who happens to be signed in.

## 6. Record a disagreement and read the log

```
/bug-triage-agent:triage-review DEMO-8 voice_of_customer "held balance release is by design"
/bug-triage-agent:triage-log
/bug-triage-agent:triage-log DEMO-7
/bug-triage-agent:triage-log accuracy
```

| Command | Shows |
| --- | --- |
| `triage-review` | Records your decision against the agent's, with the reason |
| `triage-log` | Recent decisions, newest first, with overrides marked |
| `triage-log DEMO-7` | One ticket's full history |
| `triage-log accuracy` | How often people agreed, per disposition and per escalation class |

The gap between what the agent said and what a person decided is the measurement that
improves the rubric. See [Operations](06-operations.md).

## 7. What 0.7.0 adds to a report

Render the shipped results and open `BUG-4830.md` and `BUG-4830-trace.html`:

```
python3 scripts/render_report.py --out /tmp/r fixtures/results/*.result.json
python3 scripts/render_trace.py  --out /tmp/r fixtures/results/*.result.json
```

**Check:** BUG-4830 opens with **Since the last triage**: P3 → P2, evidence moderate →
strong, metrics off → fixture, and why. Its **Timeline** shows the 2026.09 deploy, the
error rise 52 hours later and the ticket 12 hours after that. Its **Duplicate check**
calls BUG-4701 a `recurrence` (fixed before, same error), so it stays a defect. Its
workaround is marked ✅ verified.

**Check:** BUG-4858's duplicate check scores BUG-4849 `duplicate` on the same symptom,
and rules out BUG-4790, whose title is nearly identical but whose failure is not.

## 8. Overdue bugs, automatic triage, calibration

```
/bug-triage-agent:queue demo
/bug-triage-agent:triage-auto demo
/bug-triage-agent:triage-log calibrate
/bug-triage-agent:triage-log dashboard
```

**Queue:** fixture tickets are days old, so every one shows **⏰ overdue**, the at-risk
BUG-4851 first.

**Automatic triage:** `demo` does not enable it, so the command says automation is off
and does nothing. That is the default for every team. Turn it on with
`/bug-triage-agent:triage-config <team> automation`.

**Calibrate and dashboard** read your own log. With few reviewed runs they say so rather
than suggest changes.

## 9. Set up your own team

```
/bug-triage-agent:triage-config payments
```

It asks a short series of questions, discovers which connectors are in the session,
proves each tool name, and writes `triage-teams/payments.json` in your working folder.

**Check that it stops.** Skip the project key question. It should stop and write
nothing. The team id, tracker instance, project key, P1 to P4 mapping and where to
write the file are never defaulted or guessed from other signals.

Once written, tickets from that project resolve to `payments` by project key:

```
/bug-triage-agent:triage-doctor payments
/bug-triage-agent:triage PAY-123
```

Commit `triage-teams/payments.json` so your team shares it. See
[Configuration](04-configuration.md) for every key and the lookup order.

## When something looks wrong

| You see | Likely cause | Fix |
| --- | --- | --- |
| "Unknown skill" or scripts not found | Running in a regular Chat, or an old plugin version | Use Cowork or Claude Code, update to 0.7.0, start a new session |
| "Could not tell which team" | No ticket, no config in your folder, no default | Name the team or project, e.g. `/bug-triage-agent:queue demo-live`, or run `/bug-triage-agent:triage-config` |
| "Unknown skill" only when you add arguments | The host rejected a leading `--flag` | Use the plain word: `/bug-triage-agent:queue demo-live` |
| "No team configures project X" | Ticket from a project no config names | Add it with `triage-config`, or name the team |
| 🔴 in the header for a live source | Tool bindings not filled or not found | `/bug-triage-agent:triage-doctor <id>` |
| Report written but no trace | Old version | Update to 0.7.0 |
