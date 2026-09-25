#!/usr/bin/env python3
"""Evidence against the verdict, and the other causes still in play.

A triage that lists only what supports its answer reads as more certain than it is.
This script collects what argues against it, so the reader sees both sides, and makes
sure the other plausible causes travel with the hypothesis into the fix brief.

    python3 scripts/counterevidence.py <TICKET>.result.json

Two inputs:
    contradictions   written by the triage: [{"text", "source", "against", "addressed"?}]
                     `against` is disposition, priority or hypothesis. `addressed` says
                     why it does not change the verdict; leave it out when it is open.
    hypothesis.alternatives
                     other causes: [{"statement", "confirm_by", "why_less_likely"}]

and rules that find contradictions in the result on their own:
    release after the failure   the release blamed shipped after the failure was first seen
    no rise after the release   a regression is claimed but metrics show no error rise
    duplicate found             the duplicate check says duplicate, yet it is triaged as a defect

Checks (render validation refuses a result that breaks them):
    - confidence `high` with an open contradiction against the disposition or priority
    - weak location evidence with no alternative cause
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

AGAINST = ("disposition", "priority", "hypothesis")


def _t(v):
    import summary as S
    return S._parse(v)


def derive(r):
    out = []
    if r.get("disposition") != "defect":
        return out
    rel = r.get("release") or {}
    intro = (r.get("introduced_by") or {}).get("release")
    shipped = _t(rel.get("shipped")) if rel.get("version") and (not intro or intro == rel.get("version")) else None
    import timeline as TL
    first = None
    for e in TL.events(r):
        if e.get("kind") in ("spike", "ticket", "first_error"):
            if first is None or e["_at"] < first:
                first = e["_at"]
    first = first or _t(r.get("ticket_created"))
    if shipped and first and shipped > first:
        out.append({"text": f"{rel['version']} shipped after the failure was first seen", "source": "releases",
                    "against": "hypothesis", "rule": "release_after_failure"})
    if intro and rel.get("confidence") == "low":
        out.append({"text": f"The triage names {intro} as the introducing release but rates its correlation low",
                    "source": "releases", "against": "hypothesis", "rule": "introduced_by_low_correlation"})
    note = ((r.get("sources") or {}).get("metrics") or {}).get("note") or ""
    if intro and "no spike" in note.lower():
        out.append({"text": f"a regression in {intro} is claimed, but metrics show no error rise after it",
                    "source": "metrics", "against": "hypothesis", "rule": "no_rise_after_release"})
    if (r.get("duplicate_check") or {}).get("verdict") == "duplicate":
        out.append({"text": "the duplicate check found a duplicate, yet this is triaged as a new defect",
                    "source": "tracker", "against": "disposition", "rule": "duplicate_found"})
    return out


def collect(r):
    given = list(r.get("contradictions") or [])
    seen = {(c.get("rule") or c.get("text")) for c in given}
    return given + [c for c in derive(r) if c["rule"] not in seen]


def alternatives(r):
    return (r.get("hypothesis") or {}).get("alternatives") or []


def open_items(r):
    return [c for c in collect(r) if not c.get("addressed")]


def validate(r):
    p = []
    for i, c in enumerate(r.get("contradictions") or []):
        if not c.get("text") or c.get("against") not in AGAINST:
            p.append(f"contradictions[{i}] needs text and `against` (one of {list(AGAINST)})")
    for i, a in enumerate(alternatives(r)):
        if not a.get("statement"):
            p.append(f"hypothesis.alternatives[{i}] needs a statement")
    if r.get("confidence") == "high":
        hard = [c for c in open_items(r) if c.get("against") in ("disposition", "priority")]
        if hard:
            p.append("confidence is high but a contradiction against the "
                     f"{hard[0]['against']} is open ({hard[0]['text']}); address it or lower the confidence")
    return p


def gaps(r):
    """Things the triage should have written but did not. Rendered as a caution, never a refusal,
    so results from before the rule still render."""
    g = []
    if r.get("disposition") == "defect":
        from render_fix_brief import assess
        if assess(r)["level"] == "weak" and not alternatives(r):
            g.append("Location evidence is weak and no other cause was considered. Before fixing, list the "
                     "alternatives in `hypothesis.alternatives`.")
    return g


# ------------------------------------------------------------------ rendering

def _line(c):
    tail = f" Addressed: {c['addressed'].rstrip('.')}." if c.get("addressed") else " **Open.**"
    return f"- ⚖️ {c['text'].rstrip('.')} ({c.get('source', 'triage')}, against the {c['against']}).{tail}"


def md(r):
    cs, alts = collect(r), alternatives(r)
    if not cs and not alts and not gaps(r):
        return []
    o = ["## Against this, and other causes", ""]
    for g in gaps(r):
        o += ["> ⚠️ " + g, ""]
    if cs:
        o += ["**Evidence against**", ""] + [_line(c) for c in cs] + [""]
    if alts:
        o += ["**Other possible causes**", ""]
        o += [f"{i}. {a['statement']}" + (f" *Less likely because* {a['why_less_likely'][:1].lower()}"
                                          f"{a['why_less_likely'][1:].rstrip('.')}." if a.get("why_less_likely") else "")
              for i, a in enumerate(alts, 1)]
        o.append("")
    return o


def html_section(r):
    import html
    cs, alts = collect(r), alternatives(r)
    if not cs and not alts and not gaps(r):
        return ""
    o = ["<h2>Against this, and other causes</h2>"]
    o += [f'<div class="caution">{html.escape(g)}</div>' for g in gaps(r)]
    if cs:
        o.append("<ul>" + "".join(
            f"<li>⚖️ {html.escape(c['text'])} <span class=\"muted\">({html.escape(c.get('source', 'triage'))}, "
            f"against the {c['against']})</span> "
            + (f"Addressed: {html.escape(c['addressed'])}" if c.get("addressed") else "<strong>Open.</strong>")
            + "</li>" for c in cs) + "</ul>")
    if alts:
        o.append("<p><strong>Other possible causes</strong></p><ol>" + "".join(
            f"<li>{html.escape(a['statement'])}"
            + (f' <span class="muted">Less likely because {html.escape(a["why_less_likely"])}</span>'
               if a.get("why_less_likely") else "") + "</li>" for a in alts) + "</ol>")
    return "".join(o)


def brief_md(r):
    cs = [c for c in collect(r) if c.get("against") == "hypothesis"]
    alts = alternatives(r)
    o = []
    if cs:
        o += ["Evidence against this hypothesis:", ""] + [_line(c) for c in cs] + [""]
    if alts:
        o += ["If the test refutes it, test these next, in order:", ""]
        o += [f"{i}. {a['statement']}" + (f" Confirmed if: {a['confirm_by']}" if a.get("confirm_by") else "")
              for i, a in enumerate(alts, 1)]
        o.append("")
    return o


def main():
    for p in sys.argv[1:]:
        r = json.load(open(p, encoding="utf-8"))
        print(json.dumps({"ticket": r["ticket"], "contradictions": collect(r), "alternatives": alternatives(r),
                          "problems": validate(r)}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
