---
description: Check that every configured source is reachable and correctly wired
argument-hint: [--team <id>]
---

Run the readiness check for: $ARGUMENTS

1. Validate the team config against `teams/team-config.schema.json`.
   Run: `python3 scripts/validate_config.py teams/<team>.json`
   This is the named form, so it exits non-zero on any placeholder. Stop if it fails.
2. For every source in `live` mode, make one cheap read-only probe:
   - tracker: resolve `tracker.host` to its cloud id and confirm it matches `tracker.instance_id`,
     then fetch one issue from `tracker.project_key`. If `tracker.board_id` is set, confirm
     the board exists and belongs to that project
   - releases: list project versions
   - metrics: a one-hour metric query
   - warehouse: `SELECT 1`, then one configured template with a `LIMIT 1`
   - code: a single-token search in the first repo
3. Report a table: source, mode, reachable, latency, error.
4. Report which of the ten classification questions cannot be answered given the
   current modes, so the team knows what it is giving up.
5. Confirm every live source other than the tracker has an `tool_bindings` entry, and that
   each named tool suffix resolves to a tool actually present in the session.
6. Warn if any source is in `fixture` mode, and state that outputs will be banner-marked
   as demo data.

Never print credentials, tokens or connection strings. Report reachability only.
