#!/usr/bin/env python3
"""Automatic triage: choose what to triage unattended, and summarise what was done.

Off unless the team config says `automation.enabled: true`. When on, a scheduler (or a
tracker event) runs the `triage-auto` skill, which uses this script twice:

    python3 scripts/auto_triage.py plan --workdir <folder> <team> [--issues open.json] [KEY ...]
    python3 scripts/auto_triage.py digest --workdir <folder> <team> --results <r1.json> ...

`plan` prints JSON: the tickets to triage this run and why the others were skipped.
It exits 3 when automation is off, so a scheduled job that outlived its config stops
quietly instead of triaging anyway.

`digest` writes <reports_dir>/auto/<date>-<team>.md, a review list: one row per ticket
with the verdict, and the commands to accept or correct each. Automatic triage never
writes to the tracker. Posting a comment or changing a field stays a human decision,
made from the digest.
"""
import argparse, json, os, sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_header import load_teams, resolve_team, split_targets  # noqa: E402
from render_queue import build_rows, last_triage, fixture_issues, parse_ts  # noqa: E402
import summary as S  # noqa: E402

DEFAULTS = {"enabled": False, "trigger": "schedule", "schedule": "0 * * * *", "lookback_hours": 72,
            "max_per_run": 10, "retriage_changed": True, "skip_labels": ["no-auto-triage"]}
PRIO = {"P1": "🔴", "P2": "🟠", "P3": "🟡", "P4": "🔵"}
LOCK_MINUTES = 60


def policy(cfg):
    return {**DEFAULTS, **(cfg.get("automation") or {})}


def config_problems(cfg):
    a = cfg.get("automation")
    if not a:
        return []
    p = []
    if a.get("trigger", "schedule") not in ("schedule", "event"):
        p.append("automation.trigger must be schedule or event")
    if a.get("trigger", "schedule") == "schedule" and a.get("enabled") and \
            len(str(a.get("schedule", DEFAULTS["schedule"])).split()) != 5:
        p.append("automation.schedule must be a five-field cron expression")
    if not 1 <= int(a.get("max_per_run", 10)) <= 50:
        p.append("automation.max_per_run must be between 1 and 50")
    if a.get("tracker_write") not in (None, "none"):
        p.append("automation.tracker_write: automatic triage never writes to the tracker; only 'none' is allowed")
    return p


def _team(a):
    teams = load_teams(a.config_dir, a.workdir)
    word, tickets, projects = split_targets(teams, a.target)
    tid, how = resolve_team(teams, a.team or word, tickets or [f"{p}-0" for p in projects], None)
    if tid is None:
        raise SystemExit(print(how) or 2)
    cfg, path, _ = teams[tid]
    return tid, cfg, path, tickets


def _lock(workdir):
    return os.path.join(workdir, "triage-logs", "auto-triage.lock")


def cmd_plan(a):
    tid, cfg, path, keys = _team(a)
    pol = policy(cfg)
    if not pol["enabled"]:
        print(json.dumps({"team": tid, "enabled": False,
                          "message": f"Automatic triage is off for team {tid}. Turn it on with "
                                     f"/bug-triage-agent:triage-config {tid} automation"}))
        return 3
    lock = _lock(a.workdir)
    if os.path.exists(lock) and not a.force:
        age = (datetime.now(timezone.utc).timestamp() - os.path.getmtime(lock)) / 60
        if age < LOCK_MINUTES:
            print(json.dumps({"team": tid, "enabled": True, "tickets": [],
                              "message": f"Another automatic run started {age:.0f} min ago. Skipping."}))
            return 4
    mode = cfg.get("sources", {}).get("tracker", {}).get("mode")
    if a.issues:
        issues = json.load(open(a.issues, encoding="utf-8"))
    elif mode == "fixture":
        issues = fixture_issues(cfg, path)
    elif keys:
        issues = [{"key": k, "summary": ""} for k in keys]
    else:
        print("Live tracker: pass the open bugs with --issues (fetched by the tracker subagent).",
              file=sys.stderr)
        return 2
    if keys:  # an event names its tickets; the policy still applies to them
        issues = [i for i in issues if i["key"] in keys] or [{"key": k, "summary": ""} for k in keys]

    log = a.log or os.path.join(a.workdir, "triage-logs", "triage-log.jsonl")
    rows = build_rows(cfg, issues, last_triage(log))
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=pol["lookback_hours"])
    skip = set(pol.get("skip_labels") or [])
    chosen, skipped = [], []
    for r in rows:
        i, rec = r["i"], r["rec"]
        created = parse_ts(i.get("created"))
        if skip & set(i.get("labels") or []):
            skipped.append({"key": i["key"], "why": "carries a skip label"})
        elif rec and not (pol["retriage_changed"] and r["changed"]):
            skipped.append({"key": i["key"], "why": "already triaged, unchanged since"})
        elif not keys and created and created < cutoff and not r["overdue"]:
            skipped.append({"key": i["key"], "why": f"older than {pol['lookback_hours']}h and not overdue"})
        else:
            chosen.append({"key": i["key"], "why": "overdue" if r["overdue"] else
                           ("changed since last triage" if rec else "new, not triaged")})
    over = chosen[pol["max_per_run"]:]
    chosen = chosen[: pol["max_per_run"]]
    skipped += [{"key": c["key"], "why": f"over max_per_run ({pol['max_per_run']}), next run"} for c in over]
    if chosen and not a.dry_run:
        os.makedirs(os.path.dirname(lock), exist_ok=True)
        with open(lock, "w") as f:
            f.write(now.isoformat())
    print(json.dumps({"team": tid, "enabled": True, "config": path, "tickets": chosen,
                      "skipped": skipped}, indent=2))
    return 0


def cmd_digest(a):
    tid, cfg, _path, _ = _team(a)
    reports = (cfg.get("output") or {}).get("reports_dir", "triage-reports")
    rows = []
    for fp in a.results:
        try:
            r = json.load(open(fp, encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            rows.append((None, fp, str(e)))
            continue
        rows.append((r, fp, None))
    now = datetime.now(timezone.utc)
    out_dir = os.path.join(a.workdir, reports, "auto")
    os.makedirs(out_dir, exist_ok=True)
    dest = os.path.join(out_dir, f"{now:%Y-%m-%d-%H%M}-{tid}.md")

    defects = sorted([x for x in rows if x[0] and x[0].get("disposition") == "defect"],
                     key=lambda x: x[0].get("priority") or "P9")
    others = [x for x in rows if x[0] and x[0].get("disposition") != "defect"]
    failed = [x for x in rows if not x[0]] + [({"ticket": k}, None, why) for k, why in
                                              (s.split("=", 1) for s in a.failed or [])]
    o = [f"# Automatic triage · team {tid} · {now:%Y-%m-%d %H:%M} UTC", "",
         f"{len(defects)} defect(s), {len(others)} other disposition(s)"
         + (f", {len(failed)} not completed" if failed else "") + ". **Nothing was written to the tracker.** "
         "Review each row, then post or correct it yourself.", ""]
    if defects:
        o += ["## Defects", "", "| Ticket | Priority | Verdict | Do now | Report |", "| --- | --- | --- | --- | --- |"]
        for r, fp, _ in defects:
            sm = S.summary(r)
            o.append(f"| {r['ticket']} | {PRIO.get(r.get('priority'), '')} {r.get('priority')} | "
                     f"{sm['verdict']} | {(sm['do_now'] or '').replace('|', '/')} | [{r['ticket']}.md](../{r['ticket']}.md) |")
        o.append("")
    if others:
        o += ["## Not defects", "", "| Ticket | Disposition | Route |", "| --- | --- | --- |"]
        for r, fp, _ in others:
            o.append(f"| {r['ticket']} | `{r.get('disposition')}` | {(r.get('route') or '—').replace('|', '/')} |")
        o.append("")
    if failed:
        o += ["## Not completed", ""] + [f"- {x[0].get('ticket') or x[1]}: {x[2]}" for x in failed] + [""]
    o += ["## Review", "",
          "Agree with a row: nothing to do, or post its comment after reading the report.",
          "Disagree: record it, so the agent learns from it:", "",
          "    /bug-triage-agent:triage-review <TICKET> <disposition or priority> \"<reason>\"", ""]
    with open(dest, "w", encoding="utf-8") as f:
        f.write("\n".join(o))
    try:
        os.remove(_lock(a.workdir))
    except OSError:
        pass
    print("\n".join(o))
    print(f"\nwrote {dest}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "digest"):
        p = sub.add_parser(name)
        p.add_argument("--workdir", default=os.getcwd())
        p.add_argument("--config-dir")
        p.add_argument("--team")
        p.add_argument("target", nargs="*", help="team id or project key, and for plan optional ticket keys")
    pl = sub.choices["plan"]
    pl.add_argument("--issues")
    pl.add_argument("--log")
    pl.add_argument("--dry-run", action="store_true", help="plan only; take no lock")
    pl.add_argument("--force", action="store_true", help="ignore another run's lock")
    dg = sub.choices["digest"]
    dg.add_argument("--results", nargs="*", default=[])
    dg.add_argument("--failed", nargs="*", help="KEY=reason for tickets the run could not finish")
    a = ap.parse_args()
    return cmd_plan(a) if a.cmd == "plan" else cmd_digest(a)


if __name__ == "__main__":
    sys.exit(main())
