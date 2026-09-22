#!/usr/bin/env python3
"""Render the bug queue: open bugs in the team's tracker, merged with the audit log.

The list of open bugs comes from the tracker (fetched by a subagent, so the host does
not render every ticket as a card) and is passed in as JSON. In fixture mode the
recorded tracker envelopes are the queue, so the demo needs no connector.

Usage:
    python3 scripts/render_queue.py --team demo-live --workdir <folder> --issues open.json
    python3 scripts/render_queue.py ... --limit 10 --untriaged-only

Issues JSON: a list of
    {"key", "summary", "status", "priority", "component", "labels", "created", "updated"}
Only "key" and "summary" are required.

Read-only. Prints markdown; writes nothing.
"""
import re
import argparse, json, os, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_header import load_teams, fixture_root, resolve_team, split_targets  # noqa: E402

PRIO_MARK = {"P1": "🔴", "P2": "🟠", "P3": "🟡", "P4": "🔵"}


def parse_ts(s):
    if not s:
        return None
    s = str(s).strip().replace("Z", "+00:00")
    # Trackers send offsets without a colon (Jira: 2026-09-18T10:21:33.123-0500) and
    # fractions of any length. Python before 3.11 accepts neither, so normalise both.
    s = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", s)
    s = re.sub(r"\.(\d{1,6})\d*(?=[+-]\d{2}:\d{2}$|$)", lambda m: "." + m.group(1).ljust(6, "0"), s)
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def fixture_issues(cfg, cfg_path):
    d = fixture_root(cfg_path, cfg["sources"]["tracker"].get("fixture", ""))
    out = []
    for name in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if not name.endswith(".json"):
            continue
        with open(os.path.join(d, name), encoding="utf-8") as f:
            t = json.load(f).get("data", {}).get("ticket", {})
        if t.get("key"):
            out.append({"key": t["key"], "summary": t.get("summary", ""),
                        "status": "open", "priority": t.get("priority"),
                        "component": t.get("component"), "labels": t.get("labels", []),
                        "created": t.get("created"), "updated": t.get("created")})
    return out


def last_triage(log_path):
    """ticket -> latest record. Missing or unreadable log means nothing triaged yet."""
    latest = {}
    if not os.path.exists(log_path):
        return latest
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            k = r.get("ticket")
            if k and (k not in latest or r.get("ts", "") >= latest[k].get("ts", "")):
                latest[k] = r
    return latest


def area(issue, prefix):
    if issue.get("component"):
        return issue["component"]
    if prefix:
        for lab in issue.get("labels") or []:
            if lab.startswith(prefix):
                return lab[len(prefix):]
    return "—"


def cell(s, n=58):
    s = (s or "").replace("|", "/").replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", help="optional; resolved from your email or a default")
    ap.add_argument("--user-email")
    ap.add_argument("--workdir", default=os.getcwd())
    ap.add_argument("--config-dir")
    ap.add_argument("--issues", help="JSON list of open bugs; '-' for stdin; omit in fixture mode")
    ap.add_argument("--log", help="audit log; default <workdir>/triage-logs/triage-log.jsonl")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--untriaged-only", action="store_true")
    ap.add_argument("target", nargs="*", help="a team id or a project key, e.g. demo-live or DEMO")
    a = ap.parse_args()

    teams = load_teams(a.config_dir, a.workdir)
    try:
        word_team, _t, projects = split_targets(teams, a.target)
    except ValueError as e:
        print(e)
        return 2
    tid, how = resolve_team(teams, a.team or word_team, [f"{p}-0" for p in projects], a.user_email or os.environ.get("CLAUDE_TRIAGE_USER_EMAIL"))
    if tid is None:
        print(how)
        return 2
    a.team = tid
    cfg, cfg_path, _ = teams[tid]
    tracker = cfg.get("tracker", {})
    mode = cfg.get("sources", {}).get("tracker", {}).get("mode")
    prefix = tracker.get("component_label_prefix")
    names = tracker.get("priority_names", {})

    if a.issues:
        raw = sys.stdin.read() if a.issues == "-" else open(a.issues, encoding="utf-8").read()
        issues = json.loads(raw)
    elif mode == "fixture":
        issues = fixture_issues(cfg, cfg_path)
    else:
        print("Live tracker: pass the open bugs with --issues (fetched by the tracker subagent).")
        return 2

    log_path = a.log or os.path.join(a.workdir, "triage-logs", "triage-log.jsonl")
    done = last_triage(log_path)
    at_risk = set(tracker.get("at_risk_labels", []))
    now = datetime.now(timezone.utc)

    rows = []
    for i in issues:
        rec = done.get(i["key"])
        created, updated = parse_ts(i.get("created")), parse_ts(i.get("updated"))
        risky = bool(at_risk & set(i.get("labels") or []))
        age = (now - created).days if created else None
        changed = bool(rec and updated and parse_ts(rec.get("ts")) and updated > parse_ts(rec["ts"]))
        rows.append(dict(i=i, rec=rec, risky=risky, age=age, changed=changed))

    # Untriaged first; within each group at-risk first, then oldest first.
    rows.sort(key=lambda r: (r["rec"] is not None, not r["risky"],
                             -(r["age"] if r["age"] is not None else -1)))
    untriaged = [r for r in rows if r["rec"] is None]
    shown = [r for r in rows if not (a.untriaged_only and r["rec"])][: a.limit]

    out = []
    if mode == "fixture":
        out += ["> [!WARNING]", "> **Demo data.** The tracker is on fixtures. Not live tickets.", ""]
    out.append(f"### Bug queue · {tracker.get('project_key', '?')} · team {a.team} · "
               f"{len(rows)} open")
    out.append("")
    out.append(f"Team chosen by {how}.")
    out.append(f"{len(untriaged)} not yet triaged · {len(rows) - len(untriaged)} triaged by the agent"
               + (f" · showing {len(shown)}" if len(shown) < len(rows) else ""))
    out.append("")
    if not rows:
        out.append("No open bugs.")
        print("\n".join(out))
        return 0

    out.append("| Ticket | Summary | Area | Tracker priority | Age | Last triage |")
    out.append("| --- | --- | --- | --- | --- | --- |")
    for r in shown:
        i, rec = r["i"], r["rec"]
        summ = cell(i.get("summary")) + (" · `at-risk`" if r["risky"] else "")
        age = f"{r['age']}d" if r["age"] is not None else "—"
        if rec is None:
            last = "**not triaged**"
        elif rec.get("disposition") == "defect" and rec.get("priority"):
            p = rec["priority"]
            last = f"{PRIO_MARK.get(p, '')} {p} · {rec.get('ts', '')[:10]}"
            want, have = names.get(p), i.get("priority")
            if want and have and want != have:
                last += f" · ⚠ tracker says {have}, recommended {want}"
        else:
            last = f"⚪ `{rec.get('disposition')}` · {rec.get('ts', '')[:10]}"
        if rec and rec.get("human_override"):
            last += " · reviewed"
        if r["changed"]:
            last += " · changed since triage"
        out.append(f"| {i['key']} | {summ} | {area(i, prefix)} | {i.get('priority') or '—'} "
                   f"| {age} | {last} |")

    todo = [r["i"]["key"] for r in untriaged][:5]
    stale = [r["i"]["key"] for r in rows if r["changed"]][:5]
    out.append("")
    if todo:
        out.append("Next, triage the untriaged ones:")
        out.append("")
        out.append(f"    /bug-triage-agent:triage {' '.join(todo)}")
    if stale:
        out.append("")
        out.append(f"Changed since their last triage: {', '.join(stale)}. Worth a re-run.")
    if not todo and not stale:
        out.append("Everything open has been triaged and nothing changed since.")
    out.append("")
    out.append(f"Audit log: `{log_path}`" + ("" if os.path.exists(log_path) else " (none yet)"))
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
