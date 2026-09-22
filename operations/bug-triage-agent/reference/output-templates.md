# Output templates (shared)

Every output carries a provenance line naming which sources were live, fixture, or
unavailable. A recommendation whose basis is invisible is not reviewable.

## P1 fast path

```
P1 DETECTED - {KEY} - {summary}

Reason: {which P1 criterion, in one sentence}
Signal: {outage | data loss | security | at-risk stoppage | auto-approval blocked}

Immediate actions:
1. Page the on-call engineer
2. Open an incident channel
3. Notify affected clients within 15 minutes
4. Set tracker priority to {priority_names.P1}

Sources: {provenance line}
```

## Standard output

```
Ticket: {KEY} - {summary}

Disposition: {disposition} ({confidence})
  Evidence: {ref} - "{quote}"
  {Considered {alternative}; ruled out because {why_not}.}

--- below this line only if disposition = defect ---

Recommended priority: {P1-P4} -> tracker "{mapped name}"
Deciding factor: {one sentence}
Escalations applied: {class: signal}, capped at 2

Release correlation:
  {version} shipped {date}, {n} days before first report
  Touched: {components or files}
  Evidence: {tracker fixversion | github tag}
  {No release in the {lookback} day window touched this area.}

Workaround: {action support can take today}
  Source: {ticket key | doc | code path}
  {None found. Searched: {what was searched}.}

Blast radius: {n} accounts, {n} enterprise
Confidence: {high|medium|low} - {basis}
Unanswered: {questions skipped because a source was off or errored}

Sources: {provenance line}
```

## Provenance line

```
Sources: tracker=live  releases=live  metrics=off  warehouse=off  code=error(timeout)
```

If any source is `fixture`, prefix the entire output with:

```
DEMO DATA - {sources in fixture mode}. Not live figures.
```

## tracker comment

Generated as text. Posting requires explicit confirmation per ticket. Include the
provenance line in the comment so reviewers in tracker see the same basis.

## Fields to update

Emitted as a checklist, never applied automatically:

```
priority  -> {mapped name}
labels    -> component:{component}, severity:{p-level}
assignee  -> {routing[component]}
```
