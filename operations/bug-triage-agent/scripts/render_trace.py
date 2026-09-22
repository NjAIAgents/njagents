#!/usr/bin/env python3
"""Render a run trace: one self-contained HTML page per triaged ticket.

The trace is produced by code, not written by the model, for the same reason the
header is: a hand-written page drifts in layout from run to run, costs a long
generation per ticket, and can quietly drop the parts that make it honest (the
skipped stages, the unanswered questions, the held escalation).

Usage:
    python3 scripts/render_trace.py triage-reports/BUG-4830.result.json
    python3 scripts/render_trace.py --out triage-reports triage-reports/*.result.json

Writes <TICKET>-trace.html next to each result file, or into --out.

Exit codes:
    0  all traces written
    1  a result file failed validation (nothing is written for that ticket)

The result file is the orchestrator's structured record of one ticket. Its shape is
documented in reference/run-visibility.md and checked below.
"""
import argparse, html, json, os, sys

SOURCES = ["tracker", "releases", "metrics", "warehouse", "code"]
DISPOSITIONS = {"defect", "expected_behavior", "config_or_data", "duplicate",
                "voice_of_customer", "insufficient_information"}
LEVELS = ["P1", "P2", "P3", "P4"]
MODE_MARK = {"live": "🟢", "fixture": "🟡", "off": "⚫"}
STATUS_MARK = {"ok": "🟢", "partial": "🟡", "unavailable": "⚫", "error": "🔴",
               "skipped": "⚫"}
PRIO_MARK = {"P1": "🔴", "P2": "🟠", "P3": "🟡", "P4": "🔵"}
METER = {"high": "●●●", "medium": "●●○", "low": "●○○"}
EVIDENCE_MARK = {"strong": "🟢", "moderate": "🟡", "weak": "🔴"}


def esc(v):
    return html.escape("" if v is None else str(v))


# ---------------------------------------------------------------- validation

def validate(r):
    """Return a list of problems. Empty means renderable."""
    p = []
    for k in ("ticket", "summary", "team", "disposition", "confidence", "sources"):
        if not r.get(k):
            p.append(f"missing '{k}'")
    d = r.get("disposition")
    if d and d not in DISPOSITIONS:
        p.append(f"unknown disposition '{d}'")
    prio = r.get("priority")
    if d and d != "defect" and prio:
        p.append("a non-defect must not carry a priority. That is the gate this "
                 "trace exists to show.")
    if d == "defect" and prio not in LEVELS:
        p.append(f"a defect needs a priority in {LEVELS}, got {prio!r}")
    if r.get("confidence") and r["confidence"] not in METER:
        p.append(f"confidence must be one of {list(METER)}")
    srcs = r.get("sources") or {}
    for s in SOURCES:
        if s not in srcs:
            p.append(f"sources.{s} missing; every source is reported, even when off")
        elif srcs[s].get("mode") not in MODE_MARK:
            p.append(f"sources.{s}.mode must be live, fixture or off")
    for i, st in enumerate(r.get("steps") or []):
        for key in ("level", "ghost"):
            if st.get(key) is not None and st[key] not in LEVELS:
                p.append(f"steps[{i}].{key} must be P1-P4 or null")
    return p


# ------------------------------------------------------------------ ladder

def ladder_svg(steps):
    """Priority path as an SVG ladder. Steps with no level are listed, not drawn."""
    drawn = [s for s in steps if s.get("level")]
    if not drawn:
        return ""
    col_w, left, top, row_h = 150, 110, 34, 46
    width = left + col_w * len(drawn) + 40
    height = top + row_h * 3 + 70
    y = {lvl: top + i * row_h for i, lvl in enumerate(LEVELS)}
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" '
             f'aria-label="Priority path across {len(drawn)} steps, ending at '
             f'{esc(drawn[-1]["level"])}">',
             '<defs><marker id="ta" viewBox="0 0 10 10" refX="9" refY="5" '
             'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
             '<path class="ah" d="M0,0 L10,5 L0,10 z"/></marker>'
             '<marker id="tg" viewBox="0 0 10 10" refX="9" refY="5" '
             'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
             '<path class="ahg" d="M0,0 L10,5 L0,10 z"/></marker></defs>']
    for lvl in LEVELS:
        parts.append(f'<line class="guide" x1="{left - 20}" y1="{y[lvl]}" '
                     f'x2="{width - 20}" y2="{y[lvl]}"/>')
        parts.append(f'<circle class="p{lvl[1]}" cx="24" cy="{y[lvl]}" r="6"/>'
                     f'<text class="lv" x="38" y="{y[lvl] + 4}">{lvl}</text>')
    prev = None
    for i, st in enumerate(drawn):
        x = left + col_w * i + col_w // 2 - 40
        cy = y[st["level"]]
        if st.get("ghost"):
            gy = y[st["ghost"]]
            if prev:
                parts.append(f'<line class="ghost" x1="{prev[0] + 8}" y1="{prev[1]}" '
                             f'x2="{x - 9}" y2="{gy + 3}" marker-end="url(#tg)"/>')
            parts.append(f'<circle class="gring" cx="{x}" cy="{gy}" r="8"/>'
                         f'<line class="gx" x1="{x - 5}" y1="{gy - 5}" x2="{x + 5}" y2="{gy + 5}"/>'
                         f'<line class="gx" x1="{x + 5}" y1="{gy - 5}" x2="{x - 5}" y2="{gy + 5}"/>'
                         f'<text class="gl" x="{x + 14}" y="{gy - 8}">held</text>')
            prev = (x, gy)
            parts.append(f'<line class="ghost" x1="{x}" y1="{gy + 9}" x2="{x}" '
                         f'y2="{cy - 10}" marker-end="url(#tg)"/>')
        elif prev:
            parts.append(f'<line class="path" x1="{prev[0] + 8}" y1="{prev[1]}" '
                         f'x2="{x - 10}" y2="{cy}" marker-end="url(#ta)"/>')
        r = 11 if i == len(drawn) - 1 else 7
        parts.append(f'<circle class="p{st["level"][1]}" cx="{x}" cy="{cy}" r="{r}"/>')
        parts.append(f'<text class="st" x="{x}" y="{height - 30}" text-anchor="middle">'
                     f'{esc(st["step"])}</text>')
        parts.append(f'<text class="sv" x="{x}" y="{height - 13}" text-anchor="middle">'
                     f'{esc(st["level"])}</text>')
        prev = (x, cy)
    parts.append("</svg>")
    return "".join(parts)


# ------------------------------------------------------------------ page

CSS = """
:root{--bg:#F3F5F4;--surface:#FFFFFF;--ink:#17201C;--muted:#56645E;--rule:#C9D2CE;
--accent:#0B7A69;--accent-soft:#DCEFEA;--signal:#B4502A;--signal-soft:#F7E5DC;
--p1:#C73A3A;--p2:#D2701C;--p3:#B08600;--p4:#2E6BC0}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;
--bg:#0F1412;--surface:#161E1B;--ink:#E3EAE7;--muted:#96A49E;--rule:#2C3733;
--accent:#3CC0A7;--accent-soft:#12302A;--signal:#E58B60;--signal-soft:#36221A;
--p1:#EE6E6E;--p2:#F09A4E;--p3:#E1BE42;--p4:#72A5EE}}
:root[data-theme="dark"]{color-scheme:dark;--bg:#0F1412;--surface:#161E1B;--ink:#E3EAE7;
--muted:#96A49E;--rule:#2C3733;--accent:#3CC0A7;--accent-soft:#12302A;--signal:#E58B60;
--signal-soft:#36221A;--p1:#EE6E6E;--p2:#F09A4E;--p3:#E1BE42;--p4:#72A5EE}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:920px;margin:0 auto;padding-inline:18px;padding-block:28px 56px}
code,.mono{font:13px ui-monospace,"SF Mono",Menlo,Consolas,monospace}
.eyebrow{font:500 12px ui-monospace,Menlo,monospace;letter-spacing:.06em;
text-transform:uppercase;color:var(--muted);margin:0 0 10px}
h1{font-size:clamp(22px,4vw,30px);line-height:1.2;margin:0 0 14px;text-wrap:balance}
h2{font-size:17px;margin:34px 0 10px}
.banner{border:1px solid var(--signal);background:var(--signal-soft);border-radius:6px;
padding:10px 14px;margin:0 0 20px}
.verdict{display:flex;flex-wrap:wrap;gap:10px 28px;padding:14px 0;
border-block:1px solid var(--rule)}
.verdict div{min-width:120px}
.verdict dt{font:500 11px ui-monospace,Menlo,monospace;letter-spacing:.05em;
text-transform:uppercase;color:var(--muted)}
.verdict dd{margin:2px 0 0;font-weight:600}
.gap{color:var(--signal);font-weight:600}
ol.run{list-style:none;margin:0;padding:0;border-left:2px solid var(--rule)}
ol.run li{position:relative;padding:8px 0 8px 18px}
ol.run li::before{content:"";position:absolute;left:-7px;top:15px;width:12px;height:12px;
border-radius:50%;background:var(--surface);border:2px solid var(--accent)}
ol.run li.exit::before{border-color:var(--signal);background:var(--signal-soft)}
ol.run li.skip{color:var(--muted)}
ol.run li.skip::before{border-color:var(--rule);border-style:dashed}
.sname{font:600 13px ui-monospace,Menlo,monospace}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.chip{font:12px ui-monospace,Menlo,monospace;border:1px solid var(--rule);
background:var(--surface);border-radius:999px;padding:2px 10px}
.fig{overflow-x:auto;background:var(--surface);border:1px solid var(--rule);
border-radius:8px;padding:10px}
.fig svg{display:block;min-width:520px;width:100%;height:auto}
.guide{stroke:var(--rule);stroke-dasharray:2 5}
.path{stroke:var(--accent);stroke-width:2.2;fill:none}
.ghost{stroke:var(--signal);stroke-width:1.6;stroke-dasharray:6 5;fill:none}
.ah{fill:var(--accent)} .ahg{fill:var(--signal)}
.gring{fill:none;stroke:var(--signal);stroke-width:1.6;stroke-dasharray:3 3}
.gx{stroke:var(--signal);stroke-width:1.8}
.gl{font:500 11px ui-monospace,Menlo,monospace;fill:var(--signal)}
.p1{fill:var(--p1)} .p2{fill:var(--p2)} .p3{fill:var(--p3)} .p4{fill:var(--p4)}
.lv{font:500 12px ui-monospace,Menlo,monospace;fill:var(--ink)}
.st{font:600 12.5px system-ui,sans-serif;fill:var(--ink)}
.sv{font:12px ui-monospace,Menlo,monospace;fill:var(--muted)}
.tbl{overflow-x:auto}
table{border-collapse:collapse;width:100%;min-width:520px;font-size:14px}
th,td{text-align:left;padding:8px 12px 8px 0;border-bottom:1px solid var(--rule);
vertical-align:top}
th{font:500 11px ui-monospace,Menlo,monospace;letter-spacing:.05em;
text-transform:uppercase;color:var(--muted)}
.caution{border:1px solid var(--signal);background:var(--signal-soft);border-radius:6px;
padding:10px 14px;margin:12px 0}
.caution ul{margin:6px 0 0;padding-left:20px}
.tip{border-left:3px solid var(--accent);background:var(--accent-soft);
padding:10px 14px;border-radius:0 6px 6px 0}
.muted{color:var(--muted)}
footer{margin-top:40px;padding-top:12px;border-top:1px solid var(--rule);
font-size:12.5px;color:var(--muted)}
"""


def stage_list(r):
    srcs = r["sources"]
    defect = r["disposition"] == "defect"
    items = []

    items.append(('ok', "Stage 0 · information gate", "passed", []))

    base = [f'{STATUS_MARK.get(srcs[s].get("status", "ok"), "🟢")} {s} · '
            f'{srcs[s]["mode"]}' for s in ("tracker", "releases")]
    items.append(('ok', "Stage 1 · base enrichment", "", base))

    if defect:
        items.append(('ok', "Stage 2 · disposition", "defect", []))
    else:
        items.append(('exit', "Stage 2 · disposition",
                      f"⚪ {r['disposition']} · leaves here, no priority", []))

    if defect:
        chips = []
        for s in ("metrics", "warehouse", "code"):
            mode = srcs[s]["mode"]
            status = "skipped" if mode == "off" else srcs[s].get("status", "ok")
            note = srcs[s].get("note")
            chips.append(f'{STATUS_MARK.get(status, "🟢")} {s} · '
                         f'{"skipped, off" if mode == "off" else status}'
                         f'{" · " + note if note else ""}')
        items.append(('ok', "Stage 3 · deep enrichment", "", chips))
        items.append(('ok', "Stage 4 · classify",
                      f'{PRIO_MARK[r["priority"]]} {r["priority"]} · '
                      f'{METER[r["confidence"]]} {r["confidence"]}', []))
    else:
        items.append(('skip', "Stage 3 · deep enrichment", "skipped, non-defect", []))
        items.append(('skip', "Stage 4 · classify", "skipped, non-defect", []))

    items.append(('ok', "Stage 5 · output + log", "report, trace, audit record", []))

    out = ['<ol class="run">']
    for cls, name, detail, chips in items:
        c = {"exit": ' class="exit"', "skip": ' class="skip"'}.get(cls, "")
        out.append(f'<li{c}><span class="sname">{esc(name)}</span>'
                   f'{" · " + esc(detail) if detail else ""}')
        if chips:
            out.append('<div class="chips">' +
                       "".join(f'<span class="chip">{esc(x)}</span>' for x in chips) +
                       "</div>")
        out.append("</li>")
    out.append("</ol>")
    return "".join(out)


def render(r):
    t = r["ticket"]
    defect = r["disposition"] == "defect"
    fixtures = [s for s in SOURCES if r["sources"][s]["mode"] == "fixture"]
    off = [s for s in SOURCES if r["sources"][s]["mode"] == "off"]

    if defect:
        head_mark = f'{PRIO_MARK[r["priority"]]} {r["priority"]} · '
    else:
        head_mark = "⚪ "

    # The charset must come first. Opened from disk, a page with no declaration is
    # decoded as Windows-1252 and every non-ASCII mark (·, ●, ⚪, 🟢) turns to
    # mojibake. A hosting shell may add its own; a local file never does.
    o = ['<meta charset="utf-8">',
         '<meta name="viewport" content="width=device-width, initial-scale=1">',
         f'<title>Trace {esc(t)}</title>', f"<style>{CSS}</style>",
         '<div class="wrap">',
         f'<p class="eyebrow">Run trace · team {esc(r["team"])} · '
         f'{esc(r.get("triaged_at", ""))} · agent {esc(r.get("agent_version", ""))}</p>']

    if fixtures:
        o.append(f'<div class="banner"><strong>Demo data.</strong> '
                 f'{esc(", ".join(fixtures))} on fixtures. Not live figures.</div>')

    o.append(f'<h1>{head_mark}{esc(t)} · {esc(r["summary"])}</h1>')

    o.append('<dl class="verdict">')
    o.append(f'<div><dt>Disposition</dt><dd><code>{esc(r["disposition"])}</code></dd></div>')
    if defect:
        mapped = f' → “{esc(r["tracker_priority"])}”' if r.get("tracker_priority") else ""
        o.append(f'<div><dt>Priority</dt><dd>{PRIO_MARK[r["priority"]]} '
                 f'{esc(r["priority"])}{mapped}</dd></div>')
    o.append(f'<div><dt>Confidence</dt><dd>{METER[r["confidence"]]} '
             f'{esc(r["confidence"])}</dd></div>')
    ev = None
    if defect:
        from render_fix_brief import assess  # local import: that module imports this one
        ev = assess(r)
        o.append(f'<div><dt>Evidence</dt><dd>{EVIDENCE_MARK[ev["level"]]} {esc(ev["level"])}</dd></div>')
    if r.get("route"):
        o.append(f'<div><dt>Route to</dt><dd>{esc(r["route"])}</dd></div>')
    o.append("</dl>")
    if ev and ev["caution"]:
        o.append('<div class="caution"><strong>Weak evidence.</strong> '
                 + esc(ev["caution"].replace("**", "")) + "<ul>"
                 + "".join(f"<li>{esc(m)}</li>" for m in ev["missing"]) + "</ul></div>")

    cur = r.get("current_priority")
    if defect and cur and r.get("tracker_priority") and cur != r["tracker_priority"]:
        o.append(f'<p class="gap">⚠ Priority gap: the tracker has “{esc(cur)}”, '
                 f'recommended “{esc(r["tracker_priority"])}”.</p>')
    if r.get("confidence_basis"):
        o.append(f'<p class="muted">{esc(r["confidence_basis"])}</p>')

    o.append("<h2>What ran</h2>")
    o.append(stage_list(r))

    ev = r.get("disposition_evidence") or []
    if ev:
        o.append(f'<h2>Why <code>{esc(r["disposition"])}</code></h2><div class="tbl">'
                 '<table><thead><tr><th>Evidence</th><th>Source</th></tr></thead><tbody>')
        for e in ev:
            o.append(f'<tr><td>{esc(e.get("text"))}</td><td>{esc(e.get("source"))}</td></tr>')
        o.append("</tbody></table></div>")
    if r.get("alternative"):
        o.append(f'<p class="muted">{esc(r["alternative"])}</p>')

    steps = r.get("steps") or []
    if defect and steps:
        o.append("<h2>How the priority was reached</h2>")
        svg = ladder_svg(steps)
        if svg:
            o.append(f'<div class="fig">{svg}</div>')
        o.append('<div class="tbl"><table><thead><tr><th>Step</th><th>Level</th>'
                 '<th>Because</th></tr></thead><tbody>')
        for s in steps:
            lvl = s.get("level")
            cell = f'{PRIO_MARK[lvl]} {lvl}' if lvl else "not counted"
            if s.get("ghost"):
                cell += f' <span class="gap">(arithmetic {esc(s["ghost"])}, held)</span>'
            o.append(f'<tr><td><code>{esc(s["step"])}</code></td><td>{cell}</td>'
                     f'<td>{esc(s.get("because"))}</td></tr>')
        o.append("</tbody></table></div>")

    rel = r.get("release")
    if rel:
        o.append("<h2>Release correlation</h2>")
        o.append(f'<p><strong>{esc(rel.get("version"))}</strong>, shipped '
                 f'{esc(rel.get("shipped"))}, {esc(rel.get("gap_days"))} days before first '
                 f'seen. {esc(rel.get("basis", ""))} Correlation confidence: '
                 f'<strong>{esc(rel.get("confidence"))}</strong>.</p>')

    wa = r.get("workaround")
    if wa:
        o.append("<h2>Workaround</h2>")
        o.append(f'<div class="tip"><strong>{esc(wa.get("text"))}</strong><br>'
                 f'Who can do this: {esc(wa.get("who"))} · Source: {esc(wa.get("source"))}'
                 '</div>')

    o.append('<h2>Coverage</h2><div class="tbl"><table><thead><tr><th>Source</th>'
             '<th>Mode</th><th>Result</th></tr></thead><tbody>')
    for s in SOURCES:
        src = r["sources"][s]
        mode = src["mode"]
        if mode == "off":
            res = "not queried"
        elif not defect and s in ("metrics", "warehouse", "code"):
            res = "not needed, non-defect"
        else:
            res = src.get("note") or src.get("status", "ok")
        o.append(f'<tr><td>{s}</td><td>{MODE_MARK[mode]} {mode}</td>'
                 f'<td>{esc(res)}</td></tr>')
    o.append("</tbody></table></div>")

    un = r.get("unanswered") or []
    if un:
        o.append("<h2>Unanswered</h2><p>Left unanswered because a source was off. "
                 "Each lowers confidence; none raises severity.</p><ul>" +
                 "".join(f"<li>{esc(u)}</li>" for u in un) + "</ul>")
    elif defect and not off:
        o.append('<p class="muted">All ten classification questions answered.</p>')

    o.append('<footer>Generated by <code>scripts/render_trace.py</code> from '
             f'<code>{esc(t)}.result.json</code>. Nothing has been written to the '
             'tracker.</footer></div>')
    return "\n".join(o)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="+")
    ap.add_argument("--out", help="directory for the traces; default next to each result")
    a = ap.parse_args()

    failed = 0
    for path in a.results:
        try:
            with open(path) as f:
                r = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"{path}: cannot read ({e})", file=sys.stderr)
            failed += 1
            continue
        problems = validate(r)
        if problems:
            print(f"{path}: refusing to render", file=sys.stderr)
            for p in problems:
                print(f"  - {p}", file=sys.stderr)
            failed += 1
            continue
        out_dir = a.out or os.path.dirname(os.path.abspath(path))
        os.makedirs(out_dir, exist_ok=True)
        dest = os.path.join(out_dir, f'{r["ticket"]}-trace.html')
        with open(dest, "w", encoding="utf-8") as f:
            f.write(render(r))
        print(f"wrote {dest}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
