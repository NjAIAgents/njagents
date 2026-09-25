#!/usr/bin/env python3
"""Render a run trace: one self-contained HTML page per triaged ticket.

The trace is produced by code, not written by the model, for the same reason the
header is: a hand-written page drifts in layout from run to run, costs a long
generation per ticket, and can quietly drop the parts that make it honest (the
skipped stages, the unanswered questions, the held escalation).

Usage:
    python3 scripts/render_trace.py triage-reports/BUG-4830.result.json
    python3 scripts/render_trace.py --out triage-reports triage-reports/*.result.json

Writes <TICKET>-report.html next to each result file, or into --out: the full HTML report,
with the run trace (what ran, per stage) as one of its sections.

Exit codes:
    0  all traces written
    1  a result file failed validation (nothing is written for that ticket)

The result file is the orchestrator's structured record of one ticket. Its shape is
documented in reference/run-visibility.md and checked below.
"""
import argparse, html, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import links  # noqa: E402
import summary as S  # noqa: E402
import timeline as TL  # noqa: E402
import history as H  # noqa: E402
import dupes as D  # noqa: E402
import comments as CM  # noqa: E402
import fix_status as FX  # noqa: E402
import clusters as CL  # noqa: E402
import effort as EF  # noqa: E402
import risks as RK  # noqa: E402
import human_gate as HG  # noqa: E402
import next_action as NA  # noqa: E402
import counterevidence as CE  # noqa: E402
import sla as SL  # noqa: E402
import story as ST  # noqa: E402
import verify_workaround as V  # noqa: E402

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
    for where, url in _urls(r):
        if not links.safe_url(url):
            p.append(f"{where}: url must be a plain https URL")
    p += TL.validate(r)
    p += D.validate(r)
    p += CM.validate(r)
    p += FX.validate(r)
    p += CL.validate(r)
    p += EF.validate(r)
    p += RK.validate(r)
    p += HG.validate(r)
    p += NA.validate(r)
    p += CE.validate(r)
    p += SL.validate(r)
    p += V.validate(r)
    for i, st in enumerate(r.get("steps") or []):
        for key in ("level", "ghost"):
            if st.get(key) is not None and st[key] not in LEVELS:
                p.append(f"steps[{i}].{key} must be P1-P4 or null")
    return p


def _urls(r):
    """Every url field in a result, for validation."""
    out = []
    for i, l in enumerate(r.get("locations") or []):
        if l.get("url"): out.append((f"locations[{i}].url", l["url"]))
    for i, e in enumerate(r.get("disposition_evidence") or []):
        if e.get("url"): out.append((f"disposition_evidence[{i}].url", e["url"]))
    for i, p in enumerate(r.get("prior_fixes") or []):
        if p.get("url"): out.append((f"prior_fixes[{i}].url", p["url"]))
    for i, x in enumerate(r.get("links") or []):
        out.append((f"links[{i}].url", x.get("url")))
    for k, obj in (("release", r.get("release") or {}), ("introduced_by", r.get("introduced_by") or {})):
        for f in ("url", "pr_url", "release_url"):
            if obj.get(f): out.append((f"{k}.{f}", obj[f]))
    if r.get("ticket_url"): out.append(("ticket_url", r["ticket_url"]))
    return out


def evidence_section(r):
    """Where the evidence lives, each item a short label with its link behind it."""
    rows = []
    for l in r.get("locations") or []:
        rows.append((links.a(links.location_label(l), l.get("url"), code=True),
                     l.get("signal", ""), l.get("evidence", ""), l.get("source", "")))
    intro = r.get("introduced_by") or {}
    if intro.get("pr"):
        rows.append((links.a(intro["pr"], intro.get("pr_url")), "change",
                     f"introduced in {intro.get('release', '?')}", "releases"))
    for p in r.get("prior_fixes") or []:
        rows.append((links.a(p.get("key"), p.get("url")), "prior fix", p.get("summary", ""), "tracker"))
    for x in r.get("links") or []:
        rows.append((links.a(x.get("label"), x.get("url")), x.get("kind", ""), x.get("text", ""),
                     x.get("source", "")))
    if not rows:
        return ""
    body = "".join(f"<tr><td>{w}</td><td>{esc(s)}</td><td>{esc(e)}</td><td>{esc(src)}</td></tr>"
                   for w, s, e, src in rows)
    return ('<h2>Evidence</h2><div class="tbl"><table><thead><tr><th>Where</th><th>Signal</th>'
            '<th>What</th><th>Source</th></tr></thead><tbody>' + body + "</tbody></table></div>")


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

CSS = TL.CSS + """
:root{--bg:#F4F5F7;--surface:#FFFFFF;--ink:#1B1F24;--muted:#5F6B7A;--rule:#D9DEE5;--rule-soft:#EDF0F3;
--accent:#2F5BEA;--accent-soft:#E8EEFD;--signal:#B4502A;--signal-soft:#F7E5DC;--ok:#1E7F4F;--ok-soft:#E3F3EA;
--p1:#C73A3A;--p2:#D2701C;--p3:#B08600;--p4:#2E6BC0;--p1-soft:#FBE4E4;--p2-soft:#FCEBDC;--p3-soft:#FBF3D6;--p4-soft:#E1ECFB}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;
--bg:#0F1216;--surface:#171B21;--ink:#E6E9ED;--muted:#98A3B0;--rule:#2A313A;--rule-soft:#20262E;
--accent:#7B9BFF;--accent-soft:#1B2540;--signal:#E58B60;--signal-soft:#36221A;--ok:#5CCB8C;--ok-soft:#14301F;
--p1:#EE6E6E;--p2:#F09A4E;--p3:#E1BE42;--p4:#72A5EE;--p1-soft:#3A1C1C;--p2-soft:#3A2816;--p3-soft:#36300F;--p4-soft:#16263C}}
:root[data-theme="dark"]{color-scheme:dark;--bg:#0F1216;--surface:#171B21;--ink:#E6E9ED;--muted:#98A3B0;--rule:#2A313A;
--rule-soft:#20262E;--accent:#7B9BFF;--accent-soft:#1B2540;--signal:#E58B60;--signal-soft:#36221A;--ok:#5CCB8C;--ok-soft:#14301F;
--p1:#EE6E6E;--p2:#F09A4E;--p3:#E1BE42;--p4:#72A5EE;--p1-soft:#3A1C1C;--p2-soft:#3A2816;--p3-soft:#36300F;--p4-soft:#16263C}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1040px;margin:0 auto;padding:16px 16px 56px}
code,.mono{font:13px ui-monospace,"SF Mono",Menlo,Consolas,monospace}
a{color:var(--accent)}
pre{background:var(--bg);border:1px solid var(--rule);border-radius:8px;padding:10px 12px;overflow-x:auto;font-size:13px}
.eyebrow{font:500 12px ui-monospace,Menlo,monospace;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:0 0 6px}
h1{font-size:clamp(20px,3.4vw,27px);line-height:1.25;margin:0;text-wrap:balance}
h1 a{color:inherit;text-decoration:none;border-bottom:2px solid var(--rule)}
h2{font-size:16px;margin:0 0 12px;display:flex;align-items:center;gap:8px}
h2 .n{font:500 11px ui-monospace,Menlo,monospace;color:var(--muted);letter-spacing:.06em}
.masthead{background:var(--surface);border:1px solid var(--rule);border-radius:12px;padding:20px 22px;
display:flex;gap:20px;align-items:flex-start;justify-content:space-between;flex-wrap:wrap}
.masthead .t{flex:1 1 420px;min-width:0}
.badge{flex:0 0 auto;text-align:center;border-radius:12px;padding:12px 18px;min-width:132px;border:1px solid var(--rule)}
.badge b{display:block;font-size:30px;line-height:1;letter-spacing:.02em}
.badge small{display:block;font-size:12px;color:var(--muted);margin-top:6px}
.badge.p1{background:var(--p1-soft);color:var(--p1)} .badge.p2{background:var(--p2-soft);color:var(--p2)}
.badge.p3{background:var(--p3-soft);color:var(--p3)} .badge.p4{background:var(--p4-soft);color:var(--p4)}
.badge.none{background:var(--rule-soft);color:var(--muted)}
.badge .gapline{color:var(--signal);font-weight:600}
.banner{border:1px solid var(--signal);background:var(--signal-soft);border-radius:8px;padding:8px 14px;margin:0 0 12px;font-size:14px}
.answer{background:var(--surface);border:1px solid var(--rule);border-left:5px solid var(--accent);border-radius:12px;
padding:14px 18px;margin:14px 0 0;display:grid;grid-template-columns:auto 1fr;gap:6px 18px}
.answer .k{font:500 11px ui-monospace,Menlo,monospace;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);padding-top:3px}
.answer .v{margin:0} .answer .v.big{font-size:18px;font-weight:650}
.story{background:var(--surface);border:1px solid var(--rule);border-radius:12px;padding:12px 18px;margin:10px 0 0;line-height:1.6}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin:14px 0 0}
.tile{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:10px 14px;min-width:0}
.tile.wide{grid-column:1/-1}
.tile dt{font:500 11px ui-monospace,Menlo,monospace;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:0 0 4px}
.tile dd{margin:0;font-weight:600;overflow-wrap:anywhere;line-height:1.4}
.tile dd small{display:block;font-weight:400;color:var(--muted);font-size:12.5px;margin-top:2px}
.tile dd .muted{font-weight:400;font-size:12.5px}
.tile.warn{border-color:var(--signal);background:var(--signal-soft)} .tile.good{border-color:var(--ok);background:var(--ok-soft)}
.basis{color:var(--muted);font-size:13px;margin:8px 2px 0}
nav.toc{position:sticky;top:0;z-index:2;background:var(--bg);padding:10px 0;margin:14px 0 4px;border-bottom:1px solid var(--rule);
display:flex;gap:6px;overflow-x:auto;scrollbar-width:none}
nav.toc a{white-space:nowrap;font-size:12.5px;color:var(--muted);text-decoration:none;border:1px solid var(--rule);
background:var(--surface);border-radius:999px;padding:3px 11px}
nav.toc a:hover{color:var(--ink);border-color:var(--ink)}
section.card{background:var(--surface);border:1px solid var(--rule);border-radius:12px;padding:16px 18px;margin:14px 0;scroll-margin-top:56px}
section.card>p:first-of-type{margin-top:0}
.gap{color:var(--signal);font-weight:600}
.stale{background:var(--signal-soft);border-left:4px solid var(--signal);padding:8px 12px;margin:10px 0;border-radius:4px}
ol.run{list-style:none;margin:0;padding:0;border-left:2px solid var(--rule)}
ol.run li{position:relative;padding:8px 0 8px 18px}
ol.run li::before{content:"";position:absolute;left:-7px;top:15px;width:12px;height:12px;border-radius:50%;background:var(--surface);border:2px solid var(--accent)}
ol.run li.exit::before{border-color:var(--signal);background:var(--signal-soft)}
ol.run li.skip{color:var(--muted)}
ol.run li.skip::before{border-color:var(--rule);border-style:dashed}
.sname{font:600 13px ui-monospace,Menlo,monospace}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.chip{font:12px ui-monospace,Menlo,monospace;border:1px solid var(--rule);background:var(--bg);border-radius:999px;padding:2px 10px}
.fig{overflow-x:auto;background:var(--bg);border:1px solid var(--rule);border-radius:8px;padding:10px}
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
th,td{text-align:left;padding:8px 12px 8px 0;border-bottom:1px solid var(--rule-soft);vertical-align:top}
tr:last-child td{border-bottom:0}
th{font:500 11px ui-monospace,Menlo,monospace;letter-spacing:.05em;text-transform:uppercase;color:var(--muted)}
.caution{border:1px solid var(--signal);background:var(--signal-soft);border-radius:8px;padding:10px 14px;margin:12px 0}
.caution ul{margin:6px 0 0;padding-left:20px}
.tip{border-left:3px solid var(--ok);background:var(--ok-soft);padding:10px 14px;border-radius:0 8px 8px 0}
.muted{color:var(--muted)}
.changed{border:1px solid var(--p4);background:var(--p4-soft);border-radius:8px;padding:8px 14px;margin:10px 0}
.changed ul{margin:4px 0 0;padding-left:20px}
footer{color:var(--muted);font-size:12.5px;margin-top:20px}
@media (max-width:600px){.answer{grid-template-columns:1fr}.answer .k{padding-top:6px}.masthead{padding:16px}}
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
    """The HTML report page. Layout and content live in report_html.py; this module keeps
    validation, the priority ladder and the stage list, which the page imports."""
    import report_html
    return report_html.render(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="+")
    ap.add_argument("--out", help="directory for the traces; default next to each result")
    ap.add_argument("--team-config", help="team config; fills evidence links from its `links` templates")
    ap.add_argument("--markdown", action="store_true",
                    help="a markdown report was written for this run; link it from the header. "
                         "Implied when the team's output.report_format is md or both")
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
        if a.team_config:
            with open(a.team_config, encoding="utf-8") as cf:
                _cfg = json.load(cf)
                links.enrich(r, _cfg)
                RK.fill(r, _cfg)
                HG.fill(r, _cfg)
                SL.fill(r, _cfg)
                r["_providers"] = {k: v.get("provider") for k, v in (_cfg.get("sources") or {}).items() if isinstance(v, dict) and v.get("provider")}
                r["_md"] = (_cfg.get("output") or {}).get("report_format") in ("md", "both")
                r["_theme"] = (_cfg.get("output") or {}).get("theme")
        if a.markdown:
            r["_md"] = True
        H.attach(path, r)
        problems = validate(r)
        if problems:
            print(f"{path}: refusing to render", file=sys.stderr)
            for p in problems:
                print(f"  - {p}", file=sys.stderr)
            failed += 1
            continue
        out_dir = a.out or os.path.dirname(os.path.abspath(path))
        os.makedirs(out_dir, exist_ok=True)
        dest = os.path.join(out_dir, f'{r["ticket"]}-report.html')
        with open(dest, "w", encoding="utf-8") as f:
            f.write(render(r))
        print(f"wrote {dest}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
