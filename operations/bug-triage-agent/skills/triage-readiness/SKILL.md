---
name: triage-readiness
description: "Check that a bug triage team config is valid and every configured source is reachable, with each tool binding present in the session, and list sources that are off but could be connected. Use when the user asks to check, test or diagnose the triage setup, why a source is not working, or whether a team is ready to go live. Also use it when the whole request is just doctor or check, optionally with a team. Run it straight away."
---

# Triage readiness check

The `/triage-doctor` command is a thin wrapper over this skill. Clients that load skills but
not commands reach it by name.

Run the readiness check for: the user's request

0. Resolve `<plugin root>` and `<working folder>` as in `skills/bug-triage` Setup
   step 0, and report both, with the plugin version from its manifest.
1. Resolve which file this team actually uses, and say so:
   `python3 <plugin root>/scripts/run_header.py --workdir <working folder> [<team or project>] [--user-email <email>] --where`
   Pass a team id or project key from the arguments as a plain word; `--team <id>` also works.
   and report which rule chose the team.
   It looks in the config dir, then `triage-teams/` in the working folder, then the
   plugin's shipped configs. If it exits 2, there is no config: offer
   the `triage-config` skill (`/triage-config <team>` where commands load) and stop.
   Then validate that exact file against `teams/team-config.schema.json`:
   `python3 <plugin root>/scripts/validate_config.py <resolved path>`
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
5. Confirm every live source has a `tool_bindings` entry **and that each named tool
   suffix resolves to a tool actually present in this session**. This is the real
   readiness check: the plugin declares no MCP servers, so a source is usable exactly
   when its tools are present, whatever provided them.

   For each live source report: the tool names it needs, whether each was found, and
   which provider supplied it. Where a tool is missing, say what the user must connect
   in their own settings. Do not tell them to configure anything inside the plugin.
6. For every source that is `off`, check whether the session has tools that could serve
   it (log or metric query tools for metrics, SQL query tools for warehouse, code or
   repository search tools for code). List any as **available but off**, with the
   way to bind them: the `triage-config` skill. Never bind or use
   them from here.
7. Warn if any source is in `fixture` mode, and state that outputs will be banner-marked
   as demo data.
8. Report the three optional behaviours, one line each, with how to change them:
   - **Automatic triage:** on or off (`automation.enabled`), and the trigger and
     schedule when on. Run `python3 <plugin root>/scripts/auto_triage.py plan --dry-run
     --workdir <working folder> <id>` and report what the next run would pick up.
   - **Workaround verification:** run `python3 <plugin root>/scripts/verify_workaround.py
     check --team-config <config>` and report its line. For the `ci` runner, confirm the
     `tool_bindings.verification` tools are present as in step 5. Never run a scenario
     from here.
   - **Queue limits:** the triage-within hours in force, from `queue` or the defaults.

Never print credentials, tokens or connection strings. Report reachability only.
