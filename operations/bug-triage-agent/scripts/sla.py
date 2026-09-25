#!/usr/bin/env python3
"""Fix-by dates from the team's SLA, so a priority comes with a deadline.

Off unless the team config sets `sla.fix_within`:

    "sla": {"fix_within": {"P1": "1d", "P2": "5d", "P3": "30d", "P4": "90d"},
            "clock": "created", "business_days": false}

    fix_within      per priority: hours ("24h") or days ("5d")
    clock           when the clock starts: "created" (the ticket, default) or "triaged"
    business_days   count days Monday to Friday only (default false)

A defect's due date is clock start plus its priority's time. Its state:
    met        a fix was deployed on or before the due date
    breached   the due date has passed with no fix deployed
    due_soon   a quarter or less of the time is left
    on_track   otherwise

Non-defects get no due date. The due date never changes the priority.

    python3 scripts/sla.py <TICKET>.result.json --team-config <config> [--now 2026-09-24T12:00:00Z]
"""
import argparse, json, os, re, sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ICON = {"met": "✅", "breached": "🔴", "due_soon": "🟠", "on_track": "🟢"}


def _t(v):
    import summary as S
    return S._parse(v)


def policy(cfg):
    s = (cfg or {}).get("sla") or {}
    if not s.get("fix_within"):
        return None
    return {"fix_within": s["fix_within"], "clock": s.get("clock", "created"),
            "business_days": bool(s.get("business_days", False))}


def parse_span(v):
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([hd])\s*", str(v or ""))
    if not m:
        return None
    n = float(m.group(1))
    return ("h", n) if m.group(2) == "h" else ("d", n)


def add(start, span, business):
    unit, n = span
    if unit == "h" or not business:
        return start + (timedelta(hours=n) if unit == "h" else timedelta(days=n))
    d, left = start, int(n)
    while left > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            left -= 1
    return d


def created(r):
    if r.get("ticket_created"):
        return _t(r["ticket_created"])
    tl = r.get("timeline")
    for e in (tl.get("events") if isinstance(tl, dict) else None) or []:
        if e.get("kind") == "ticket":
            return _t(e.get("at"))
    return None


def _dur(td):
    h = abs(td.total_seconds()) / 3600
    return f"{h:.0f}h" if h < 48 else f"{h / 24:.0f}d"


def compute(r, cfg, now=None):
    p = policy(cfg)
    if not p or r.get("disposition") != "defect" or not r.get("priority"):
        return None
    span = parse_span(p["fix_within"].get(r["priority"]))
    if not span:
        return None
    start = _t(r.get("triaged_at")) if p["clock"] == "triaged" else created(r)
    if not start:
        return {"state": None, "why": "no start time for the clock (ticket created date missing)"}
    due = add(start, span, p["business_days"])
    at_triage = now is None and bool(_t(r.get("triaged_at")))
    now = now or _t(r.get("triaged_at")) or datetime.now(timezone.utc)
    fs = r.get("fix_status") or {}
    dep = _t((fs.get("deployed") or {}).get("at")) if fs.get("state") == "deployed" else None
    total = due - start
    if dep and dep <= due:
        state = "met"
    elif now > due:
        state = "breached"
    elif (due - now) <= total / 4:
        state = "due_soon"
    else:
        state = "on_track"
    return {"due": due.strftime("%Y-%m-%d %H:%M UTC"), "state": state,
            "rule": f"{r['priority']}: {p['fix_within'][r['priority']]}"
                    + (" business" if p["business_days"] and span[0] == "d" else "")
                    + f" from {'triage' if p['clock'] == 'triaged' else 'created'}",
            "delta": ("" if state == "met" else
                      (f"overdue by {_dur(now - due)}" if state == "breached" else f"{_dur(due - now)} left")
                      + (" at triage" if at_triage else ""))}


def fill(r, cfg, now=None):
    if r.get("sla") is None:
        s = compute(r, cfg, now)
        if s:
            r["sla"] = s
    return r


def cell(r):
    s = r.get("sla")
    if not s or not s.get("state"):
        return (s or {}).get("why")
    return f"{ICON[s['state']]} {s['due'][:10]} · {s['state'].replace('_', ' ')}" \
           + (f", {s['delta']}" if s.get("delta") else "") + f" ({s['rule']})"


def short(r):
    s = r.get("sla")
    if not s or not s.get("state"):
        return ""
    return f"{ICON[s['state']]} due {s['due'][5:10]}"


def validate(r):
    s = r.get("sla")
    if not s or not s.get("state"):
        return []
    return [] if s["state"] in ICON else [f"sla.state must be one of {list(ICON)}"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", nargs="+")
    ap.add_argument("--team-config", required=True)
    ap.add_argument("--now")
    a = ap.parse_args()
    cfg = json.load(open(a.team_config, encoding="utf-8"))
    now = _t(a.now) if a.now else None
    for p in a.results:
        r = json.load(open(p, encoding="utf-8"))
        print(json.dumps({"ticket": r["ticket"], "sla": compute(r, cfg, now)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
