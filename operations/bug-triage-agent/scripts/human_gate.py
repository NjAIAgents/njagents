#!/usr/bin/env python3
"""Hold a triage for a person when it carries a risk the team will not leave to the agent.

Off by default: the agent's recommendation is advice either way, and every tracker post
already needs a person's yes. A team that wants more for some risks (typically security
and payment) turns this on, and those tickets are then marked as needing a person's
decision, not just a yes:

    "human_review": {"enabled": true, "risk_types": ["security", "payment"],
                     "min_level": "reported", "reviewers": ["Priya (security)", "*@fin.example.com"]}

    enabled     false by default
    risk_types  which named risks (scripts/risks.py) trigger the gate; default security, payment
    min_level   how sure a risk must be to trigger it: evidenced, reported (default) or suspected
    reviewers   who may confirm; shown in the report. Empty means any person.

When the gate is on for a ticket:
    report and trace   open with who must decide and why; the recommendation is advice only
    fix brief          says it is not for an automated fix agent until a person confirms
    automatic triage   lists it under "Needs a person" in the digest
    audit log          records the flag `human_review`; the queue shows it until reviewed
    tracker            nothing is posted until a reviewer confirms, by name

    python3 scripts/human_gate.py <TICKET>.result.json --team-config <config>
"""
import argparse, json, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import risks as RK  # noqa: E402

DEFAULT_TYPES = ["security", "payment"]
LEVELS = ("evidenced", "reported", "suspected")


def policy(cfg):
    hr = (cfg or {}).get("human_review") or {}
    return {"enabled": bool(hr.get("enabled", False)),
            "risk_types": list(hr.get("risk_types") or DEFAULT_TYPES),
            "min_level": hr.get("min_level") or "reported",
            "reviewers": list(hr.get("reviewers") or [])}


def evaluate(r, cfg=None):
    p = policy(cfg)
    if not p["enabled"] or r.get("disposition") != "defect":
        return None
    limit = LEVELS.index(p["min_level"]) if p["min_level"] in LEVELS else 1
    hits = [x for x in RK.get(r, cfg) if x["type"] in p["risk_types"] and LEVELS.index(x["level"]) <= limit]
    if not hits:
        return None
    return {"required": True, "because": [{k: x[k] for k in ("type", "level", "why")} for x in hits],
            "reviewers": p["reviewers"]}


def fill(r, cfg=None):
    if r.get("human_review") is None:
        g = evaluate(r, cfg)
        if g:
            r["human_review"] = g
    return r


def required(r):
    return bool((r.get("human_review") or {}).get("required"))


def _because(r):
    return "; ".join(f"{RK.ICON[x['type']]} {RK.LABEL[x['type']]} ({x['level']}: {x['why']})"
                     for x in r["human_review"]["because"])


def _who(r):
    rv = r["human_review"].get("reviewers") or []
    return ("a reviewer named in the team config (" + ", ".join(rv) + ")") if rv else "a person"


# ------------------------------------------------------------------ rendering

def md(r):
    import links
    if not required(r):
        return []
    return links.callout("caution", f"👤 **A person must decide this one.** {_because(r)}.",
                         "", f"The recommendation below is advice only. Nothing is posted to the tracker and "
                             f"nothing goes to an automated fix agent until {_who(r)} confirms it by name.") + [""]


def html_section(r):
    import html
    if not required(r):
        return ""
    return (f'<div class="caution"><strong>👤 A person must decide this one.</strong> {html.escape(_because(r))}.'
            f'<br>The recommendation is advice only. Nothing is posted to the tracker and nothing goes to an '
            f'automated fix agent until {html.escape(_who(r))} confirms it by name.</div>')


def brief_callout(r):
    import links
    if not required(r):
        return []
    return links.callout("caution", f"👤 **Not for an automated fix agent until a person confirms.** {_because(r)}. "
                         f"Wait for {_who(r)}.") + [""]


def validate(r):
    g = r.get("human_review")
    if not g:
        return []
    p = []
    if g.get("required") and not g.get("because"):
        p.append("human_review: a required review must say which risk triggered it")
    for i, x in enumerate(g.get("because") or []):
        if x.get("type") not in RK.TYPES or x.get("level") not in LEVELS:
            p.append(f"human_review.because[{i}] must name a risk type and level")
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", nargs="+")
    ap.add_argument("--team-config", required=True)
    a = ap.parse_args()
    cfg = json.load(open(a.team_config, encoding="utf-8"))
    for fp in a.results:
        r = json.load(open(fp, encoding="utf-8"))
        print(json.dumps({"ticket": r["ticket"], "human_review": evaluate(r, cfg)}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
