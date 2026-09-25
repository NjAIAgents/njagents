#!/usr/bin/env python3
"""The next action for a triaged ticket, from a fixed set, decided by rule.

"Do now" is free text written for the reader, and it varies. The next action is one
value from a fixed list, so a queue, a digest, a dashboard or another agent can act on
it, and two triages of the same state always agree. The free text stays as the detail.

    python3 scripts/next_action.py <TICKET>.result.json [--team-config <config>]

Actions, decided in this order:
    await_review        the team holds this risk for a person (human_review), so nothing moves yet
    confirm_resolved    a fix is deployed: confirm with the customer, then close
    deploy_fix          a fix is released but not known to be deployed where the customer runs
    release_fix         a fix is merged but not released
    fix_now             a P1, or a P2 whose location is supported by strong or moderate evidence
    locate_first        a defect whose location evidence is weak: find the cause before fixing
    schedule_fix        a P3 or P4 with a located cause
    request_info        insufficient information: ask the reporter for what is missing
    close_duplicate     a duplicate: link to the original and close
    explain_behavior    expected behaviour: explain it to the customer
    correct_config      a configuration or data problem: correct it, no code change
    route_to_product    a request for new behaviour: send it to product

Alongside the action, `also` may hold:
    send_workaround     a workaround the customer or support can use today
    apply_workaround    a workaround only the team can apply
"""
import argparse, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ACTIONS = {
    "await_review": "Wait for a reviewer",
    "confirm_resolved": "Confirm and close",
    "deploy_fix": "Deploy the fix",
    "release_fix": "Release the fix",
    "fix_now": "Fix now",
    "locate_first": "Find the cause first",
    "schedule_fix": "Schedule the fix",
    "request_info": "Ask for missing detail",
    "close_duplicate": "Close as duplicate",
    "explain_behavior": "Explain the behaviour",
    "correct_config": "Correct config or data",
    "route_to_product": "Send to product",
}
ALSO = {"send_workaround": "send the customer the workaround",
        "apply_workaround": "apply the workaround internally"}
ICON = {"await_review": "👤", "confirm_resolved": "✅", "deploy_fix": "🚀", "release_fix": "📦",
        "fix_now": "🔧", "locate_first": "🔍", "schedule_fix": "🗓️", "request_info": "❓",
        "close_duplicate": "🔗", "explain_behavior": "💬", "correct_config": "⚙️", "route_to_product": "📨"}
BY_DISPOSITION = {"insufficient_information": "request_info", "duplicate": "close_duplicate",
                  "expected_behavior": "explain_behavior", "config_or_data": "correct_config",
                  "voice_of_customer": "route_to_product"}


VERBS = {"link", "close", "route", "send", "ask", "escalate", "assign", "forward", "return", "mark", "reopen"}


def clean_route(route):
    """Strip config-key parentheticals such as '(voc_destination)' from a route written by the triage."""
    return re.sub(r"\s*\([a-z_]+\)", "", route or "").strip()


def customer_can_apply(workaround):
    """True when the workaround's `who` says the customer or support can do it, and does not
    say the opposite ("engineer only", "not the customer")."""
    who = ((workaround or {}).get("who") or "").lower()
    if not who or re.search(r"\bnot (the )?customer|engineer[s]? only|only (an )?engineer", who):
        return False
    return "customer" in who or "support" in who


def is_team(route):
    """A route is a team or a queue when it is a short name, not an instruction."""
    t = clean_route(route)
    if not t or any(ch in t for ch in ";:()") or len(t.split()) > 4:
        return False
    return t.split()[0].lower() not in VERBS and t[:1].isupper()


def decide(r):
    import fix_status as FX
    import human_gate as HG
    d = r.get("disposition")
    also = []
    if d != "defect":
        base = BY_DISPOSITION.get(d, "request_info")
    else:
        fs = (r.get("fix_status") or {}).get("state")
        if FX.is_fixed(r):
            base = {"deployed": "confirm_resolved", "released": "deploy_fix"}.get(fs, "release_fix")
        else:
            from render_fix_brief import assess
            ev = assess(r)["level"]
            p = r.get("priority")
            if p == "P1" or (p == "P2" and ev != "weak"):
                base = "fix_now"
            elif ev == "weak":
                base = "locate_first"
            else:
                base = "schedule_fix"
            wa = r.get("workaround") or {}
            if wa.get("text"):
                also.append("send_workaround" if customer_can_apply(wa) else "apply_workaround")
    owner = clean_route(r.get("route")) if is_team(r.get("route")) else None
    out = {"action": base, "owner": owner}
    if also:
        out["also"] = also
    if HG.required(r):
        out = {"action": "await_review", "then": base, "owner": owner} | ({"also": also} if also else {})
    return out


def fill(r):
    if r.get("next_action") is None:
        r["next_action"] = decide(r)
    return r


def get(r):
    return r.get("next_action") or decide(r)


def label(r):
    n = get(r)
    s = f"{ICON[n['action']]} {ACTIONS[n['action']]}"
    if n.get("then"):
        s += f", then {ACTIONS[n['then']].lower()}"
    if n.get("also"):
        s += "; meanwhile " + " and ".join(ALSO[a] for a in n["also"])
    return s


def core(r):
    """The action only: no owner (the route says it) and no workaround (Do now says it)."""
    n = get(r)
    s = f"`{n['action']}` · {ICON[n['action']]} {ACTIONS[n['action']]}"
    return s + (f", then {ACTIONS[n['then']].lower()}" if n.get("then") else "")


def answer_line(r, do_now=None):
    """The action in bold, then the detail: the owner, and the workaround or the free-text
    step from the triage. Replaces "Do now" as the third line of the answer."""
    n = get(r)
    head = f"**{ICON[n['action']]} {ACTIONS[n['action']]}**"
    if n.get("then"):
        head += f", then {ACTIONS[n['then']].lower()}"
    parts = []
    if n.get("owner"):
        parts.append(n["owner"] + ".")
    wa = (r.get("workaround") or {}).get("text")
    if n["action"] in ("fix_now", "locate_first", "schedule_fix", "await_review") and wa:
        who = (r.get("workaround") or {}).get("who")
        parts.append("Meanwhile: " + wa[:1].lower() + wa[1:].rstrip(".") + "." + (f" Who: {who.rstrip('.')}." if who else ""))
    elif do_now:
        d = do_now.strip()
        low = d.lower()
        for pre in (ACTIONS[n["action"]].lower() + ": ", ACTIONS[n["action"]].lower() + ". "):
            if low.startswith(pre):
                d = d[len(pre):]
                d = d[:1].upper() + d[1:]
        if d.rstrip(".").lower() != ACTIONS[n["action"]].lower():
            parts.append(d)
    return head + (" · " + " ".join(parts) if parts else "")


def short(r):
    """For tables: the icon and the action words."""
    n = get(r)
    return f"{ICON[n['action']]} {ACTIONS[n['action']]}"


def cell(r):
    n = get(r)
    return f"`{n['action']}` · {label(r)}" + (f" · owner {n['owner']}" if n.get("owner") else "")


def validate(r):
    n = r.get("next_action")
    if not n:
        return []
    p = []
    if n.get("action") not in ACTIONS:
        p.append(f"next_action.action must be one of {list(ACTIONS)}")
    if n.get("then") and n["then"] not in ACTIONS:
        p.append("next_action.then must be an action")
    for a in n.get("also") or []:
        if a not in ALSO:
            p.append(f"next_action.also must hold only {list(ALSO)}")
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", nargs="+")
    ap.add_argument("--team-config")
    a = ap.parse_args()
    cfg = json.load(open(a.team_config, encoding="utf-8")) if a.team_config else None
    import risks as RK, human_gate as HG
    for fp in a.results:
        r = json.load(open(fp, encoding="utf-8"))
        RK.fill(r, cfg)
        HG.fill(r, cfg)
        print(json.dumps({"ticket": r["ticket"], "next_action": decide(r)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
