#!/usr/bin/env python3
"""The story of a defect in a few sentences, written from the result's own data.

A reader should not have to assemble the sequence of events from six sections. This
composes it once: what fails, what shipped and when errors rose, what the code shows,
whether it happened before, who is affected, and whether a fix already exists. Every
sentence comes from a field in the result; nothing is guessed, and a missing field
means a missing sentence, not a filler.

    python3 scripts/story.py <TICKET>.result.json
"""
import json, re, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FAULT = {"error_swallowing": "swallows the error and carries on",
         "stub": "is a stub that does nothing",
         "suppressed_type_error": "suppresses a type error"}


E0, E1 = "\x01", "\x02"


def E(x):
    """Mark a key fact for emphasis; md() and html() turn the marks into bold."""
    return f"{E0}{x}{E1}"


def _sent(s):
    s = (s or "").strip().rstrip(".")
    return (s[:1].upper() + s[1:] + ".") if s else ""


def factor(note):
    m = re.search(r"(\d+(?:\.\d+)?)\s*[x×]", note or "")
    return f"{m.group(1)}×" if m else None


def rise_date(note):
    m = re.search(r"(?:from|since|after)\s+(\d{4}-\d{2}-\d{2})", note or "")
    return m.group(1) if m else None


def sentences(r):
    if r.get("disposition") != "defect":
        return []
    out = []
    repro = r.get("repro") or {}
    out.append(_sent(repro.get("actual") or r.get("summary")))

    rel, intro = r.get("release") or {}, r.get("introduced_by") or {}
    touched = next((l for l in r.get("locations") or [] if l.get("signal") == "release_touched"), None)
    m = (r.get("sources") or {}).get("metrics") or {}
    f, d = factor(m.get("note")), rise_date(m.get("note"))
    if rel.get("version") and rel.get("confidence") in ("high", "medium", None):
        s = f"{E(rel['version'])} shipped" + (f" on {rel['shipped']}" if rel.get("shipped") else "")
        if touched:
            s += f" and changed {E(touched['path'].rsplit('/', 1)[-1])}" + (f" ({intro['pr']})" if intro.get("pr") else "")
        if f:
            s += f"; errors rose {E(f)}" + (f" from {d}" if d else " after it")
        out.append(_sent(s))
    elif rel.get("version"):
        out.append(_sent(f"No release explains it: {rel['version']} shipped in the area"
                         + (f" {rel['gap_days']} days earlier" if rel.get("gap_days") is not None else "")
                         + ", too far back to correlate"))
    elif f:
        out.append(_sent(f"Errors rose {E(f)}" + (f" from {d}" if d else "")))

    fault = next((l for l in r.get("locations") or [] if l.get("signal") in FAULT and l.get("path")), None)
    code = (r.get("sources") or {}).get("code") or {}
    if fault:
        where = fault["path"].rsplit("/", 1)[-1] + (f":{fault['line']}" if fault.get("line") else "")
        out.append(_sent(f"The code at {E(where)} {FAULT[fault['signal']]}"
                         + (f": {fault['evidence'].rstrip('.')}" if fault.get("evidence") else "")))
    elif code.get("mode") == "off":
        out.append("The code was not read: code search is off for this team.")
    elif code.get("status") == "ok":
        out.append("Code search found no fault at the candidate files, so the cause is not yet located.")

    pf = (r.get("prior_fixes") or [None])[0]
    if pf and pf.get("key"):
        note = (pf.get("note") or "").split(". ")[0].rstrip(".")
        out.append(_sent(f"The same failure was fixed before in {E(pf['key'])}" + (f" ({note[:1].lower() + note[1:]})" if note else "")))

    b = r.get("blast_radius") or {}
    wh = (r.get("sources") or {}).get("warehouse") or {}
    if b.get("accounts") is not None:
        out.append(_sent(f"{E(str(b['accounts']) + ' account(s)')} are affected, {b.get('enterprise', 0)} of them enterprise"))
    elif wh.get("status") == "ok" and wh.get("note"):
        out.append(_sent(f"Affected: {wh['note']}"))
    else:
        out.append("How many accounts are affected is not known (no warehouse).")

    import fix_status as FX
    if FX.is_fixed(r):
        out.append(_sent(FX.headline(r)))
    return [s for s in out if s]


def md(r):
    s = " ".join(sentences(r)).replace(E0, "**").replace(E1, "**")
    return [f"**What happened** · {s}", ""] if s else []


def html(r):
    import html as h
    s = h.escape(" ".join(sentences(r))).replace(E0, "<strong>").replace(E1, "</strong>")
    return f'<p class="story"><strong>What happened</strong> · {s}</p>' if s else ""


def main():
    for p in sys.argv[1:]:
        r = json.load(open(p, encoding="utf-8"))
        print(r["ticket"], "·", " ".join(sentences(r)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
