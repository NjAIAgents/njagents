---
name: workaround-finder
description: Find and state a workaround that unblocks the customer today, drawn from resolved tickets, docs, or the code path. Use when triaging a bug or when asked how to unblock a customer while a fix is pending.
---

# Workaround finder

The output is an action support can take today, not a yes-or-no field. Whether a
workaround exists also feeds the priority rubric, but that is secondary.

## Search order

1. **Resolved tickets, same component, same failure mode.** Read the resolution and
   the last comments. Prior workarounds are usually written there in plain language.
2. **Docs and release notes** for an alternative path to the same outcome.
3. **The code path**, when `code` is live. An alternative entry point, a feature flag,
   or a parameter that bypasses the failing branch.
4. **The ticket itself.** Reporters often describe what they tried.

## Output

```
Workaround: {imperative action}
  Applies to: {who can do it - customer, support, engineer}
  Cost: {clicks, minutes, data re-entry, none}
  Source: {ticket key | doc | code path}
  Caveats: {what it does not cover}
```

None found:

```
Workaround: none found
  Searched: {resolved tickets in component X, release notes, code path Y}
```

## Rules

- A workaround that requires an engineer to run a script is **not** a customer
  workaround. Label who can perform it. This distinction decides whether the priority
  rubric treats the customer as unblocked.
- Never invent a workaround from the shape of the problem. Cite a source or report
  none found.
- A workaround that loses data or skips a control is reported with its risk and does
  not count as "practical" for the rubric.
