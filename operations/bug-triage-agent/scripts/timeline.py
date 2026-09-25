#!/usr/bin/env python3
"""The regression timeline: what shipped, when errors rose, when the ticket came in.

Two optional fields in the result file feed it:

    "timeline": [{"at": "2026-09-16 21:00 UTC", "kind": "deploy", "label": "2026.09",
                  "url": "https://..."}, ...]
    "series":   {"label": "approval not committed", "unit": "per hour", "baseline": 12,
                 "points": [["2026-09-16 00:00 UTC", 11], ...]}

Kinds: release, deploy, spike, first_error, ticket, triage, fix. Every event comes
from a tool result. Nothing here fills a gap: no series means no chart, only the
event list, and no events means no section at all.

The trace draws it as an SVG; the report and fix brief as a sparkline in a code block
with numbered markers keyed to a table, because markdown viewers render no SVG.
"""
import html, re

import links
import summary as S

KINDS = {"release": "Release", "deploy": "Deploy", "spike": "Errors rise",
         "first_error": "First error", "ticket": "Ticket filed", "triage": "Triaged",
         "fix": "Fix shipped"}
BLOCKS = "▁▂▃▄▅▆▇█"
MAX_BUCKETS = 48


def _t(v):
    return S._parse(v)


def derived(r):
    """Events from fields the result already has, for a triage that wrote no timeline."""
    out = []
    rel = r.get("release") or {}
    if rel.get("version") and rel.get("shipped") and rel.get("confidence") in ("high", "medium"):
        out.append({"at": rel["shipped"], "kind": "deploy", "label": rel["version"], "url": rel.get("url")})
    m = (r.get("sources") or {}).get("metrics") or {}
    d = re.search(r"(?:from|since|after)\s+(\d{4}-\d{2}-\d{2})", m.get("note") or "")
    f = re.search(r"(\d+(?:\.\d+)?)\s*[x×]", m.get("note") or "")
    if d:
        first = re.split(r"[;.]", m.get("note") or "")[0].strip()
        out.append({"at": d.group(1), "kind": "spike", "label": f"{f.group(1)}× baseline" if f else first[:60]})
    if r.get("ticket_created"):
        out.append({"at": r["ticket_created"], "kind": "ticket", "label": r.get("ticket"), "url": r.get("ticket_url")})
    fs = r.get("fix_status") or {}
    c = fs.get("commit") or {}
    if fs.get("confidence") in ("strong", "moderate") and c.get("date"):
        out.append({"at": c["date"], "kind": "fix", "label": c.get("pr") or c.get("sha", "")[:10], "url": c.get("url")})
    if (fs.get("deployed") or {}).get("at"):
        out.append({"at": fs["deployed"]["at"], "kind": "deploy", "label": "fix deployed", "url": fs["deployed"].get("url")})
    return out


def events(r):
    out = []
    tl = r.get("timeline")
    if isinstance(tl, dict):
        tl = tl.get("events")
    for e in tl or derived(r):
        if not isinstance(e, dict):
            continue
        at = _t(e.get("at"))
        if at and e.get("kind") in KINDS:
            out.append({**e, "_at": at})
    if out and not any(e["kind"] == "triage" for e in out) and _t(r.get("triaged_at")):
        out.append({"at": r["triaged_at"], "kind": "triage", "label": "this run",
                    "_at": _t(r["triaged_at"])})
    return sorted(out, key=lambda e: e["_at"])


def points(r):
    s = r.get("series") or {}
    pts = []
    for p in s.get("points") or []:
        if isinstance(p, (list, tuple)) and len(p) == 2 and _t(p[0]) is not None \
                and isinstance(p[1], (int, float)):
            pts.append((_t(p[0]), float(p[1])))
    return sorted(pts)


def validate(r):
    p = []
    for i, e in enumerate(r.get("timeline") or []):
        if e.get("kind") not in KINDS:
            p.append(f"timeline[{i}].kind must be one of {sorted(KINDS)}")
        if not _t(e.get("at")):
            p.append(f"timeline[{i}].at is not a timestamp")
        if e.get("url") and not links.safe_url(e["url"]):
            p.append(f"timeline[{i}].url must be a plain https URL")
    s = r.get("series")
    if s is not None:
        raw = s.get("points") or []
        if len(points(r)) != len(raw):
            p.append("series.points must be [timestamp, number] pairs")
    return p


def _gap(a, b):
    h = (b - a).total_seconds() / 3600
    if h < 1:
        return f"+{int(h * 60)}m"
    if h < 72:
        return f"+{h:.0f}h"
    return f"+{h / 24:.0f}d"


def _buckets(pts, n):
    """Downsample to n buckets by time, keeping each bucket's max so a spike survives."""
    if len(pts) <= n:
        return pts
    t0, t1 = pts[0][0], pts[-1][0]
    span = (t1 - t0).total_seconds() or 1
    out = [None] * n
    for t, v in pts:
        i = min(n - 1, int((t - t0).total_seconds() / span * n))
        out[i] = (t, v) if out[i] is None or v > out[i][1] else out[i]
    return [b for b in out if b is not None]


# ------------------------------------------------------------------ markdown

def md(r):
    ev, pts = events(r), points(r)
    if not ev and not pts:
        return []
    s = r.get("series") or {}
    o = ["## Timeline", ""]
    if pts:
        b = _buckets(pts, MAX_BUCKETS)
        hi = max(v for _, v in b) or 1
        spark = "".join(BLOCKS[min(7, int(v / hi * 7.999))] for _, v in b)
        marks = [" "] * len(b)
        t0, t1 = b[0][0], b[-1][0]
        span = (t1 - t0).total_seconds() or 1
        for n, e in enumerate(ev, 1):
            if t0 <= e["_at"] <= t1 and n < 10:
                i = min(len(b) - 1, int((e["_at"] - t0).total_seconds() / span * len(b)))
                marks[i] = str(n)
        cap = f"{s.get('label', 'errors')} ({s.get('unit', 'per bucket')})"
        if s.get("baseline") is not None:
            cap += f" · baseline {s['baseline']:g} · peak {max(v for _, v in pts):g}"
        o += ["```", spark, "".join(marks).rstrip(), cap, "```", ""]
    if ev:
        o += ["| # | When (UTC) | Event | Gap |", "| --- | --- | --- | --- |"]
        prev = None
        for n, e in enumerate(ev, 1):
            label = links.md(e.get("label") or KINDS[e["kind"]], e.get("url"))
            what = f"{KINDS[e['kind']]}: {label}" if e.get("label") else label
            o.append(f"| {n} | {e['_at'].strftime('%Y-%m-%d %H:%M')} | {what} | "
                     f"{_gap(prev, e['_at']) if prev else ''} |")
            prev = e["_at"]
        o.append("")
    return o


# ------------------------------------------------------------------ svg

CSS = """
.tl-bar{fill:var(--accent);opacity:.55}.tl-bar.hot{fill:var(--signal);opacity:.85}
.tl-base{stroke:var(--muted);stroke-dasharray:4 4}
.tl-ev{stroke:var(--ink);stroke-width:1.2;stroke-dasharray:2 3}
.tl-ev.deploy,.tl-ev.release{stroke:var(--p4);stroke-dasharray:none;stroke-width:1.8}
.tl-ev.spike,.tl-ev.first_error{stroke:var(--signal);stroke-width:1.6}
.tl-ev.ticket{stroke:var(--p2)}.tl-ev.fix{stroke:var(--accent);stroke-dasharray:none}
.tl-lab{font:600 11.5px system-ui,sans-serif;fill:var(--ink)}
.tl-sub{font:11px ui-monospace,Menlo,monospace;fill:var(--muted)}
.tl-axis{stroke:var(--rule)}
"""


def svg(r):
    ev, pts = events(r), points(r)
    if not ev and not pts:
        return ""
    s = r.get("series") or {}
    W, H, L, R, TOP, BOT = 860, 250, 16, 16, 64, 34
    # The chart spans the series. An event far outside it (usually the triage itself, days
    # later) would squash the bars into a corner, so it is pinned to the edge instead.
    times = [t for t, _ in pts] or [e["_at"] for e in ev]
    t0, t1 = min(times), max(times)
    if pts:
        pad = (t1 - t0) * 0.15
        near = [e["_at"] for e in ev if t0 - pad <= e["_at"] <= t1 + pad]
        t0, t1 = min([t0] + near), max([t1] + near)
    span = (t1 - t0).total_seconds() or 3600
    x = lambda t: L + (t - t0).total_seconds() / span * (W - L - R)  # noqa: E731
    ch = H - TOP - BOT
    base_y = H - BOT
    o = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Timeline of '
         f'{len(ev)} events' + (f' over {html.escape(s.get("label", "errors"))}' if pts else "") + '">']
    o.append(f'<line class="tl-axis" x1="{L}" y1="{base_y}" x2="{W - R}" y2="{base_y}"/>')
    if pts:
        hi = max(v for _, v in pts) or 1
        b = _buckets(pts, 160)
        bw = max(2.0, (W - L - R) / max(1, len(b)) - 1)
        thr = s.get("baseline")
        for t, v in b:
            h = v / hi * ch
            hot = " hot" if thr is not None and v > thr * 2 else ""
            o.append(f'<rect class="tl-bar{hot}" x="{x(t) - bw / 2:.1f}" y="{base_y - h:.1f}" '
                     f'width="{bw:.1f}" height="{h:.1f}"><title>{t:%Y-%m-%d %H:%M} · {v:g}</title></rect>')
        if thr is not None:
            y = base_y - thr / hi * ch
            o.append(f'<line class="tl-base" x1="{L}" y1="{y:.1f}" x2="{W - R}" y2="{y:.1f}"/>'
                     f'<text class="tl-sub" x="{L + 4}" y="{y - 4:.1f}">'
                     f'baseline {thr:g}</text>')
    for i, e in enumerate(ev):
        off = e["_at"] > t1 or e["_at"] < t0
        ex = x(min(max(e["_at"], t0), t1))
        row = i % 3
        ly = 14 + row * 16
        anchor = "end" if ex > W * 0.8 else "start"
        dx = -4 if anchor == "end" else 4
        lab = f'{KINDS[e["kind"]]} · {e.get("label") or ""}'.rstrip(" ·")
        if off:
            lab = (f"{_gap(t1, e['_at'])} later: " if e["_at"] > t1 else "earlier: ") + lab
        lab = html.escape(links.short(lab, 40))
        text = f'<text class="tl-lab" x="{ex + dx:.1f}" y="{ly}" text-anchor="{anchor}">{lab}</text>'
        url = links.safe_url(e.get("url"))
        if url:
            text = f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener">{text}</a>'
        if not off:
            o.append(f'<line class="tl-ev {e["kind"]}" x1="{ex:.1f}" y1="{ly + 4}" x2="{ex:.1f}" y2="{base_y}"/>')
        o.append(text)
    o.append(f'<text class="tl-sub" x="{L}" y="{H - 10}">{t0:%Y-%m-%d %H:%M} UTC</text>')
    o.append(f'<text class="tl-sub" x="{W - R}" y="{H - 10}" text-anchor="end">{t1:%Y-%m-%d %H:%M} UTC</text>')
    if pts:
        o.append(f'<text class="tl-sub" x="{W / 2}" y="{H - 10}" text-anchor="middle">'
                 f'{html.escape(s.get("label", "errors"))} · {html.escape(s.get("unit", ""))}</text>')
    o.append("</svg>")
    return "".join(o)


def html_section(r):
    g = svg(r)
    if not g:
        return ""
    ev = events(r)
    rows = []
    prev = None
    for e in ev:
        rows.append(f'<tr><td>{e["_at"]:%Y-%m-%d %H:%M}</td><td>{html.escape(KINDS[e["kind"]])}</td>'
                    f'<td>{links.a(e.get("label") or "", e.get("url"))}</td>'
                    f'<td>{_gap(prev, e["_at"]) if prev else ""}</td></tr>')
        prev = e["_at"]
    table = ('<div class="tbl"><table><thead><tr><th>When (UTC)</th><th>Event</th><th>What</th>'
             '<th>Gap</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>") if rows else ""
    return f'<h2>Timeline</h2><div class="fig">{g}</div>{table}'
