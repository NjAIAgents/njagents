#!/usr/bin/env python3
"""What changed since the last triage of the same ticket.

Before a re-run writes a new result file, the old one is archived:

    python3 scripts/history.py archive triage-reports/DEMO-7.result.json

which copies it to triage-reports/history/DEMO-7.<triaged_at>.result.json. The
renderers then compare the new result with the latest archived one and open with a
short "since the last triage" block: priority P3 → P2, metrics off → live, evidence
moderate → strong. Nothing is inferred: a field absent from either run is not compared.

    python3 scripts/history.py diff triage-reports/DEMO-7.result.json   # print the block
"""
import glob, json, os, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import summary as S  # noqa: E402

SOURCES = S.SOURCES


def _stamp(r):
    t = S._parse(r.get("triaged_at"))
    return t.strftime("%Y%m%dT%H%M") if t else "unknown"


def archive(path):
    """Copy an existing result into history/ before it is overwritten. Returns the copy."""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        r = json.load(f)
    d = os.path.join(os.path.dirname(os.path.abspath(path)), "history")
    os.makedirs(d, exist_ok=True)
    dest = os.path.join(d, f"{r.get('ticket', 'UNKNOWN')}.{_stamp(r)}.result.json")
    shutil.copyfile(path, dest)
    return dest


def previous(path, r):
    """The latest archived result for this ticket, older than r. Embedded `previous` wins."""
    if isinstance(r.get("previous"), dict):
        return r["previous"]
    if not path:
        return None
    d = os.path.join(os.path.dirname(os.path.abspath(path)), "history")
    now = S._parse(r.get("triaged_at"))
    best = None
    for fp in glob.glob(os.path.join(d, f"{r.get('ticket')}.*.result.json")):
        try:
            with open(fp, encoding="utf-8") as f:
                p = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        t = S._parse(p.get("triaged_at"))
        if not t or (now and t >= now):
            continue
        if best is None or t > S._parse(best.get("triaged_at")):
            best = p
    return best


def _evidence(r):
    if r.get("disposition") != "defect":
        return None
    if r.get("evidence"):
        return r["evidence"]
    try:
        from render_fix_brief import assess
        return assess(r)["level"]
    except Exception:  # noqa: BLE001
        return None


def snapshot(r):
    wa = r.get("workaround") or {}
    ver = (wa.get("verified") or {}).get("status")
    rel = r.get("release")
    rel = rel if isinstance(rel, str) else (rel or {}).get("version")
    sup = r.get("supported_by")
    if sup is None and (r.get("locations") or r.get("links") or r.get("release") or r.get("prior_fixes")):
        sup = len(S.corroboration(r))
    return {
        "disposition": r.get("disposition"),
        "priority": r.get("priority"),
        "confidence": r.get("confidence"),
        "evidence": _evidence(r),
        "release": rel,
        "route": r.get("route"),
        "workaround": ("verified" if ver == "passed" else "found") if wa.get("text") else "none",
        "supported_by": sup,
        "modes": {s: ((r.get("sources") or {}).get(s) or {}).get("mode") for s in SOURCES},
    }


LABEL = {"disposition": "Disposition", "priority": "Priority", "confidence": "Confidence",
         "evidence": "Evidence", "release": "Release", "route": "Route",
         "workaround": "Workaround", "supported_by": "Sources supporting the verdict"}


def changes(r, prev):
    """[(label, before, after)] for every compared field that differs."""
    if not prev:
        return []
    a, b = snapshot(prev), snapshot(r)
    out = []
    for k in LABEL:
        if a.get(k) is None and b.get(k) is None:
            continue
        # A snapshot saved by an older version may lack a field. Compare only what both have,
        # except priority, whose appearance or disappearance is itself the news.
        if k != "priority" and (a.get(k) is None or b.get(k) is None):
            continue
        if a.get(k) != b.get(k):
            out.append((LABEL[k], a.get(k) or "none", b.get(k) or "none"))
    for s in SOURCES:
        ma, mb = (a.get("modes") or {}).get(s), (b.get("modes") or {}).get(s)
        if ma and mb and ma != mb:
            out.append((f"{s} source", ma, mb))
    return out


def _when(prev):
    t = S._parse(prev.get("triaged_at"))
    return t.strftime("%Y-%m-%d %H:%M UTC") if t else "an earlier run"


def md(r, prev):
    if not prev:
        return []
    ch = changes(r, prev)
    head = f"**Since the last triage** ({_when(prev)}"
    ver = prev.get("agent_version")
    head += f", agent {ver})" if ver and ver != r.get("agent_version") else ")"
    if not ch:
        return [f"{head}: no change in verdict, priority, evidence or sources.", ""]
    o = [head + ":", ""]
    o += [f"- {lab}: {before} → **{after}**" for lab, before, after in ch]
    if prev.get("why_changed") or r.get("why_changed"):
        o += ["", f"Why: {r.get('why_changed') or prev.get('why_changed')}"]
    return o + [""]


def html_block(r, prev):
    import html as h
    if not prev:
        return ""
    ch = changes(r, prev)
    if not ch:
        return (f'<p class="muted">Since the last triage ({h.escape(_when(prev))}): no change in '
                'verdict, priority, evidence or sources.</p>')
    items = "".join(f"<li>{h.escape(lab)}: {h.escape(str(b))} → <strong>{h.escape(str(a))}</strong></li>"
                    for lab, b, a in ch)
    why = f'<p>Why: {h.escape(r["why_changed"])}</p>' if r.get("why_changed") else ""
    return (f'<div class="changed"><strong>Since the last triage</strong> '
            f'({h.escape(_when(prev))})<ul>{items}</ul>{why}</div>')


def attach(path, r):
    """Load the previous result into r['_previous'] for the renderers."""
    p = previous(path, r)
    if p:
        r["_previous"] = p
    return r


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "archive":
        dest = archive(sys.argv[2])
        print(f"archived to {dest}" if dest else "nothing to archive: no earlier result")
        sys.exit(0)
    if len(sys.argv) == 3 and sys.argv[1] == "diff":
        with open(sys.argv[2], encoding="utf-8") as f:
            res = json.load(f)
        print("\n".join(md(res, previous(sys.argv[2], res))) or "No earlier triage of this ticket.")
        sys.exit(0)
    print(__doc__)
    sys.exit(2)
