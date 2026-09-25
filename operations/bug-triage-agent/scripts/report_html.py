#!/usr/bin/env python3
"""The HTML report page, rendered from a result file. Written by render_trace.py.

The page follows the approved design ("control room"): the message first, the data
after, in this order:

    header       ticket, title, status chips, theme switch
    brief        the headline, one paragraph, three action boxes (support, fix, tracker),
                 the priority with the tracker gap, confidence and the prior fix
    findings     what the run found, in order; since the last triage
    numbers      error rate now, baseline, ratio, peak, excess errors, deploy to rise
    risks        one tile per risk, certainty as a filled label
    timeline     the events on a time-scaled track; the hourly error chart
    priority     the ladder; evidence, complexity and coverage as meters
    where        locations, the code (collapsible past 12 lines), the hypothesis
    sources      each source, its status and caveats
    duplicates   candidates with their scores
    comments     used comments, evidence against, other causes
    produced     the stage flow
    fields       what to set in the tracker, on a yes

Light theme by default, dark available; the switch is remembered per viewer. Every
figure comes from the result; a missing field drops its element, never fills it.
"""
import html as H_, json, os, re, statistics, sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import links  # noqa: E402
import html_theme as THEME  # noqa: E402
from html_theme import ICON, JS  # noqa: E402
import summary as S  # noqa: E402
import timeline as TL  # noqa: E402
import history as H  # noqa: E402
import comments as CM  # noqa: E402
import fix_status as FX  # noqa: E402
import counterevidence as CE  # noqa: E402
import risks as RK  # noqa: E402
import effort as EF  # noqa: E402
import next_action as NA  # noqa: E402
import sla as SL  # noqa: E402
import story as ST  # noqa: E402
import verify_workaround as V  # noqa: E402

SOURCES = ["tracker", "releases", "metrics", "warehouse", "code"]
PRIO_WORD = {"P1": "critical", "P2": "high", "P3": "medium", "P4": "low"}
METER = {"high": "●●●", "medium": "●●○", "low": "●○○"}
GRADE = {"weak": 1, "moderate": 2, "strong": 3}
MAX_SNIPPET_OPEN = 12


def esc(v):
    return H_.escape("" if v is None else str(v))


# ------------------------------------------------------------------ link index and prose

def link_index(r):
    idx = {}
    def put(k, u):
        if k and u and links.safe_url(u) and k not in idx:
            idx[k] = u
    put(r.get("ticket"), r.get("ticket_url"))
    for e in r.get("disposition_evidence") or []:
        put(e.get("label"), e.get("url"))
    for p in r.get("prior_fixes") or []:
        put(p.get("key"), p.get("url"))
    for c in (r.get("duplicate_check") or {}).get("candidates") or []:
        put(c.get("key"), c.get("url"))
    rel = r.get("release") or {}
    put(rel.get("version"), rel.get("url"))
    intro = r.get("introduced_by") or {}
    put(intro.get("pr"), intro.get("pr_url"))
    for l in r.get("locations") or []:
        if l.get("path") and l.get("url"):
            name = l["path"].rsplit("/", 1)[-1]
            if l.get("line"):
                put(f"{name}:{l['line']}", l["url"])
            put(name, l["url"])
            put(l["path"], l["url"])
    fs = r.get("fix_status") or {}
    c = fs.get("commit") or {}
    put(c.get("pr"), c.get("url")); put(c.get("sha", "")[:10], c.get("url"))
    for x in fs.get("candidates") or []:
        put(x.get("sha"), x.get("url"))
    for x in r.get("links") or []:
        put(x.get("label"), x.get("url"))
    for e in r.get("timeline") or []:
        if isinstance(e, dict):
            put(e.get("label"), e.get("url"))
    return idx


def linkify(text, idx):
    if not text:
        return ""
    out = esc(text)
    anchors = []
    for k in sorted((k for k in idx if len(k) >= 4), key=len, reverse=True):
        pat = r"(?<![\w/.#:-])" + re.escape(esc(k)) + r"(?![\w/.-]*\w)"
        def sub(m, k=k):
            anchors.append(f'<a href="{esc(idx[k])}" target="_blank" rel="noopener">{m.group(0)}</a>')
            return f"\x03{len(anchors) - 1}\x04"
        out = re.sub(pat, sub, out)
    return re.sub(r"\x03(\d+)\x04", lambda m: anchors[int(m.group(1))], out)


def bold(text):
    return text.replace(ST.E0, "<strong>").replace(ST.E1, "</strong>")


# ------------------------------------------------------------------ numbers from the series

def series_stats(r):
    pts = TL.points(r)
    s = r.get("series") or {}
    if not pts:
        return None
    vals = [v for _, v in pts]
    base = s.get("baseline")
    ev = TL.events(r)
    spike = next((e for e in ev if e["kind"] in ("spike", "first_error")), None)
    i_sp = next((i for i, (t, _) in enumerate(pts) if spike and t >= spike["_at"]), None)
    if base is None:
        base = statistics.median(vals[:i_sp] if i_sp else vals)
    after = vals[i_sp:] if i_sp is not None else []
    cur = statistics.median(after[-24:]) if after else statistics.median(vals[-24:])
    out = {"unit": s.get("unit", "per hour"), "label": s.get("label", "errors"), "baseline": base, "current": cur,
           "ratio": (cur / base) if base else None, "peak": max(vals), "peak_at": pts[vals.index(max(vals))][0],
           "excess": sum(v - base for v in after) if after else None, "hours_after": len(after) or None}
    dep = next((e for e in ev if e["kind"] in ("deploy", "release")), None)
    if dep and spike:
        out["deploy_to_rise_h"] = (spike["_at"] - dep["_at"]).total_seconds() / 3600
    return out


def fmt_n(v):
    return f"{v:,.0f}" if isinstance(v, (int, float)) else str(v)


# ------------------------------------------------------------------ pieces

def chips(r, gap, fixed):
    out = []
    p = r.get("priority")
    if p:
        out.append(f'<span class="chip c-p{p[1]}">{esc(p)} {esc(PRIO_WORD[p]).upper()}</span>')
    if r.get("disposition") == "defect":
        rel = (r.get("introduced_by") or {}).get("release") or ((r.get("release") or {}).get("version")
              if (r.get("release") or {}).get("confidence") in ("high", "medium") else None)
        out.append(f'<span class="chip c-blue">{"REGRESSION " + esc(rel) if S._regression(r) and rel else "DEFECT"}</span>')
    else:
        out.append(f'<span class="chip c-muted">{esc(r["disposition"].replace("_", " ")).upper()}</span>')
    if gap:
        out.append(f'<span class="chip c-red">TRACKER {esc(r["current_priority"]).upper()} → {esc(r["tracker_priority"]).upper()}</span>')
    if fixed:
        out.append('<span class="chip c-teal">ALREADY FIXED</span>')
    out.append(f'<span class="chip c-teal">CONF {METER.get(r.get("confidence"), "")} {esc(r.get("confidence", "")).upper()}</span>')
    return "".join(out)




def header(r, gap, fixed):
    t = r["ticket"]
    owner = NA.clean_route(r.get("route")) if NA.is_team(r.get("route")) else None
    meta = [f'<span class="muted">Owner</span> <b>{esc(owner)}</b>'] if owner else []
    meta.append(f'<span class="muted">Triaged</span> {esc(r.get("triaged_at", ""))}')
    meta.append(f'<span class="muted">Team</span> {esc(r.get("team", ""))}')
    # The markdown report is opt-in, so link it only when this run wrote one.
    opens = [("Open in tracker", r.get("ticket_url")), ("Markdown report", f"{t}.md" if r.get("_md") else None),
             ("Fix brief", f"{t}.fix-brief.md" if r.get("disposition") == "defect" else None)]
    icon = dict(zip(("Open in tracker", "Markdown report", "Fix brief"), ("open", "doc", "wrench")))
    btns = "".join(f'<a class="ibtn" href="{esc(u)}" title="{esc(l)}" aria-label="{esc(l)}"'
                   f'{" target=_blank rel=noopener" if u.startswith("http") else ""}>{ICON[icon[l]]}</a>' for l, u in opens if u)
    # Two columns, two rows: who and what on the left, status and actions on the right,
    # so the chips line up over the buttons and every control shares one height.
    theme = (f'<button type="button" class="ibtn theme-btn" id="theme-toggle" data-mode="light" title="Theme: Light" '
             f'aria-label="Theme: Light">{ICON["sun"]}{ICON["moon"]}{ICON["monitor"]}</button>')
    return (f'<header class="bar"><div class="ident"><span class="key">{links.a(t, r.get("ticket_url"), code=True)}</span>'
            f'<span class="ttl">{esc(r["summary"])}</span></div>'
            f'<div class="chips">{chips(r, gap, fixed)}</div>'
            f'<div class="meta">{" · ".join(meta)}</div>'
            f'<div class="actions"><span class="hbtns">{btns}</span>{theme}</div></header>')


def brief(r, idx, ev, fixed, gap):
    t = r["ticket"]
    defect = r.get("disposition") == "defect"
    summ = S.summary(r)
    story = bold(linkify(" ".join(ST.sentences(r)), idx)) if defect else linkify(S.why_line(summ["why"]), idx)
    wa = r.get("workaround") or {}
    na = NA.get(r)
    boxes = []
    # support
    if defect and wa.get("text"):
        who = wa.get("who") or ""
        can = NA.customer_can_apply(wa)
        extra = []
        if wa.get("source"):
            extra.append("Source: " + linkify(wa["source"], idx))
        if wa.get("does_not_cover"):
            extra.append("Does not cover: " + esc(wa["does_not_cover"]))
        vl = V.html_line(wa)
        boxes.append(("Do now · " + ("support" if can else "engineering"),
                      f'<b>{linkify(wa["text"].rstrip("."), idx)}.</b>' + (f' <span class="muted">Who: {esc(who)}.</span>' if who else "")
                      + (f'<div class="muted small">{" · ".join(extra)}</div>' if extra else "")
                      + (f'<div class="small">{vl}</div>' if vl else "")))
    elif defect:
        boxes.append(("Do now", '<span class="muted">No workaround found; the customer waits for the fix.</span>'))
    else:
        boxes.append(("Do now", f'<b>{esc(NA.ACTIONS[na["action"]])}.</b> {linkify(summ["do_now"] or "", idx)}'))
    # fix
    if defect:
        owner = NA.clean_route(r.get("route")) if NA.is_team(r.get("route")) else None
        faults = [l for l in r.get("locations") or [] if l.get("path") and l.get("signal") in ("error_swallowing", "stub", "suppressed_type_error")]
        where = " and ".join(links.a(links.location_label(l), l.get("url"), code=True) for l in faults[:2])
        cx = r.get("complexity") or EF.complexity(r)
        cxs = f' <span class="muted">Complexity {esc(cx["level"])} ({cx["score"]}/5).</span>' if cx and cx.get("score") is not None else ""
        boxes.append(("Fix · " + (esc(owner) if owner else "engineering"),
                      f'<b>{esc(NA.ACTIONS[na["action"]])}.</b>' + (f" Start at {where}." if where else "") + cxs))
    # tracker
    upd = fields_to_update(r)
    if upd:
        boxes.append(("Set in tracker · on your yes", " · ".join(
            (f'{esc(k)} <b class="warn">{esc(r.get("current_priority"))} → {esc(v)}</b>' if k == "priority" and gap else f'{esc(k)} <b>{esc(v)}</b>')
            for k, v in upd.items()) + f' · {links.a("open " + t, r.get("ticket_url"))}'))
    box_html = "".join(f'<div class="abox"><div class="lbl">{k}</div><div>{v}</div></div>' for k, v in boxes)

    p = r.get("priority")
    if defect and p:
        side = [f'<div class="bigp p{p[1]}">{esc(p)}</div>',
                f'<div><b>{esc(PRIO_WORD[p].capitalize())}</b> · {"regression" if S._regression(r) else "defect"}'
                + (f' · tracker still says {esc(r["current_priority"])}' if gap else "") + "</div>"]
    else:
        side = [f'<div class="bigp none">—</div>', f'<div><b>{esc(r["disposition"].replace("_", " "))}</b> · no priority</div>']
    corr = S.corroboration(r)
    if corr:
        n, live = S.corroboration_line(r)
        side.append(f'<div class="muted">Confidence <b>{esc(r.get("confidence", ""))}</b>: {n} of {live} sources agree '
                    f'({esc(", ".join(c["source"] for c in corr))}).' + (f' {esc(r["confidence_basis"])}' if r.get("confidence_basis") else "") + '</div>')
    pf = (r.get("prior_fixes") or [None])[0]
    if pf and pf.get("key"):
        side.append(f'<div class="muted">Same failure as {links.a(pf["key"], pf.get("url"))}' + (f': {esc(pf.get("summary", ""))}.' if pf.get("summary") else ".") + '</div>')
    if fixed:
        side.append(f'<div class="ok"><b>{esc(FX.headline(r))}.</b></div>')
    return (f'<section class="brief"><div class="brief-main"><h1>{esc(r["summary"])}</h1>'
            f'<p class="lede">{story}</p><div class="aboxes">{box_html}</div></div>'
            f'<div class="brief-side">{"".join(side)}</div></section>')


def findings(r, idx):
    summ = S.summary(r)
    left = f'<div class="card"><div class="lbl">Why this verdict</div><p class="m0">{linkify(S.why_line(summ["why"]), idx)}</p>'
    if r.get("deciding_factor") and r["deciding_factor"].strip().rstrip(".") not in S.why_line(summ["why"]):
        left += f'<p class="muted m0">Deciding factor: {linkify(r["deciding_factor"], idx)}</p>'
    left += FX.html_section(r).replace("<h2>Fix status</h2>", '<div class="lbl mt">Fix status</div>', 1) + "</div>"
    prev = r.get("_previous") or r.get("previous")
    ch = H.changes(r, prev) if prev else []
    right = ""
    if ch:
        rows = "".join(f'<tr><td class="muted">{esc(k)}</td><td>{esc(a)}</td><td class="now">{esc(b)}</td></tr>' for k, a, b in ch)
        when = (prev.get("triaged_at") if isinstance(prev, dict) else "") or ""
        right = (f'<div class="card"><div class="lbl">Since the last triage · {esc(when)}</div>'
                 f'<table class="delta"><thead><tr><th>Field</th><th>Before</th><th>Now</th></tr></thead><tbody>{rows}</tbody></table>'
                 + (f'<p class="muted m0">{esc(r["why_changed"])}</p>' if r.get("why_changed") else "") + "</div>")
    return f'<section class="two">{left}{right}</section>'


def numbers(r):
    st = series_stats(r)
    if not st:
        return ""
    unit = "/h" if "hour" in st["unit"] else ""
    tiles = [("Error rate now", f"{st['current']:.0f}{unit}", "median of the last 24 buckets", "warn"),
             ("Baseline", f"{st['baseline']:.0f}{unit}", "before the rise", ""),]
    if st.get("ratio"):
        tiles.append(("Ratio", f"{st['ratio']:.1f}×", "spike threshold 3.0×", "warn"))
    tiles.append(("Peak", f"{st['peak']:.0f}{unit}", f"{st['peak_at']:%m-%d %H:%M}", ""))
    if st.get("excess") is not None:
        tiles.append(("Excess errors", fmt_n(st["excess"]), f"above baseline over {st['hours_after']}h", "bad"))
    if st.get("deploy_to_rise_h") is not None:
        tiles.append(("Deploy → rise", f"{st['deploy_to_rise_h']:.0f}h", "from the correlated deploy", ""))
    return '<section class="tiles">' + "".join(
        f'<div class="tile"><div class="lbl">{k}</div><div class="num {c}">{v}</div><div class="muted">{s}</div></div>' for k, v, s, c in tiles) + "</section>"


def risks(r):
    rs = RK.get(r)
    if not rs:
        return ""
    def evidence(x):
        src = x.get("source")
        faults = [l for l in r.get("locations") or [] if l.get("url") and l.get("signal") in ("error_swallowing", "stub", "suppressed_type_error")]
        anyloc = [l for l in r.get("locations") or [] if l.get("url")]
        out = []
        if src == "code" and faults:
            out.append((links.location_label(faults[0]), faults[0]["url"]))
        elif src in ("code notes", "hypothesis") and anyloc:
            out.append((links.location_label(anyloc[0]), anyloc[0]["url"]))
        elif src == "comment":
            c = next((u for u in (r.get("comment_review") or {}).get("used") or [] if u.get("url")), None)
            if c:
                out.append(("comment", c["url"]))
        elif src in ("ticket", "triage") and r.get("ticket_url"):
            out.append((r["ticket"], r["ticket_url"]))
        q = next((l for l in r.get("links") or [] if l.get("source") == "metrics" and l.get("url")), None)
        if q and x["type"] in ("silent_failure", "data_integrity", "availability", "performance"):
            out.append(("logs", q["url"]))
        return out
    def tile(x):
        ev_ = evidence(x)
        head = f'<b>{links.a(RK.LABEL[x["type"]].capitalize(), ev_[0][1]) if ev_ else esc(RK.LABEL[x["type"]].capitalize())}</b>'
        foot = (' <span class="rlinks">' + " · ".join(links.a(l + " →", u) for l, u in ev_) + "</span>") if ev_ else ""
        return (f'<div class="rtile {x["level"]}"><div class="rhead">{head}<span class="badge {x["level"]}">{esc(x["level"])}</span></div>'
                f'<div class="muted">{esc(x["why"])}. {esc(RK.MEANING[x["type"]])}.</div>{foot}</div>')
    tiles = "".join(tile(x) for x in rs)
    return f'<section><h2>Risks · what kind of harm this bug does</h2><div class="rgrid">{tiles}</div></section>'


def timeline_track(r):
    ev = TL.events(r)
    if len(ev) < 2:
        return ""
    t0, t1 = ev[0]["_at"], ev[-1]["_at"]
    span = (t1 - t0).total_seconds() or 1
    W, Hh, x0, x1, y = 1160, 150, 70, 1090, 78
    X = lambda t: x0 + (x1 - x0) * (t - t0).total_seconds() / span
    col = {"deploy": "var(--blue)", "release": "var(--blue)", "spike": "var(--red)", "first_error": "var(--red)",
           "ticket": "var(--ink)", "triage": "var(--teal)", "fix": "var(--teal)"}
    o = [f'<svg viewBox="0 0 {W} {Hh}" class="track" role="img" aria-label="Timeline of {len(ev)} events">',
         f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="var(--rule)" stroke-width="4" stroke-linecap="round"></line>']
    sp = next((e for e in ev if e["kind"] in ("spike", "first_error")), None)
    tri = next((e for e in ev if e["kind"] == "triage"), None)
    if sp and tri and tri["_at"] > sp["_at"]:
        o.append(f'<rect x="{X(sp["_at"]):.1f}" y="{y-2}" width="{X(tri["_at"]) - X(sp["_at"]):.1f}" height="4" fill="var(--orange)"></rect>')
        h = (tri["_at"] - sp["_at"]).total_seconds() / 3600
        o.append(f'<text x="{(X(sp["_at"]) + X(tri["_at"])) / 2:.1f}" y="{y-40}" text-anchor="middle" class="tl-note">bug live for {h:.0f}h before triage</text>')
    for a, b in zip(ev, ev[1:]):
        o.append(f'<text x="{(X(a["_at"]) + X(b["_at"])) / 2:.1f}" y="{y+22}" text-anchor="middle" class="tl-gap">{esc(TL._gap(a["_at"], b["_at"]))}</text>')
    for i, e in enumerate(ev):
        x, up = X(e["_at"]), i % 2 == 0
        ty = y - 26 if up else y + 48
        c = col.get(e["kind"], "var(--muted)")
        o.append(f'<line x1="{x:.1f}" y1="{y-14 if up else y+8}" x2="{x:.1f}" y2="{y+8 if up else y+34}" stroke="{c}" stroke-width="1.5"></line>')
        o.append(f'<circle cx="{x:.1f}" cy="{y}" r="7" fill="{c}" stroke="var(--surface)" stroke-width="2"></circle>')
        name = f'{esc(TL.KINDS[e["kind"]])}: {esc(e.get("label") or "")}' if e.get("label") else esc(TL.KINDS[e["kind"]])
        txt = f'<text x="{x:.1f}" y="{ty}" text-anchor="middle" class="tl-name">{name}</text>'
        u = links.safe_url(e.get("url")) if e.get("url") else None
        o.append(f'<a href="{esc(u)}" target="_blank" rel="noopener">{txt}</a>' if u else txt)
        o.append(f'<text x="{x:.1f}" y="{ty+15}" text-anchor="middle" class="tl-gap">{e["_at"]:%m-%d %H:%M}</text>')
    o.append("</svg>")
    return "".join(o)


def error_chart(r):
    pts = TL.points(r)
    if not pts:
        return ""
    s = r.get("series") or {}
    st = series_stats(r)
    vals = [v for _, v in pts]
    W, Hh, x0, y0, cw, ch = 1160, 230, 50, 16, 1100, 170
    peak = max(vals) * 1.05 or 1
    t0, t1 = pts[0][0], pts[-1][0]
    span = (t1 - t0).total_seconds() or 1
    X = lambda t: x0 + cw * (t - t0).total_seconds() / span
    Y = lambda v: y0 + ch - v / peak * ch
    path = "M" + " L".join(f"{X(t):.1f},{Y(v):.1f}" for t, v in pts)
    area = path + f" L{X(t1):.1f},{Y(0):.1f} L{X(t0):.1f},{Y(0):.1f} Z"
    o = [f'<svg viewBox="0 0 {W} {Hh}" class="chart" role="img" aria-label="{esc(s.get("label", "errors"))} over time">']
    ticks = sorted({0, round(st["baseline"]), round(st["baseline"] * 3), round(max(vals))})
    for g in ticks:
        if g <= peak:
            o.append(f'<line x1="{x0}" y1="{Y(g):.1f}" x2="{x0+cw}" y2="{Y(g):.1f}" stroke="var(--rule)"></line>'
                     f'<text x="{x0-8}" y="{Y(g)+4:.1f}" text-anchor="end" class="ax">{g}</text>')
    days = [t for t, _ in pts if t.hour == 0 and t.minute == 0]
    for d in days:
        o.append(f'<text x="{X(d):.1f}" y="{y0+ch+16}" text-anchor="middle" class="ax">{d:%m-%d}</text>')
    b = st["baseline"]
    o.append(f'<line x1="{x0}" y1="{Y(b):.1f}" x2="{x0+cw}" y2="{Y(b):.1f}" stroke="var(--teal)" stroke-dasharray="6 4"></line>'
             f'<text x="{x0+cw}" y="{Y(b)-5:.1f}" text-anchor="end" class="ax teal">baseline {b:.0f}</text>')
    if b * 3 < peak:
        o.append(f'<line x1="{x0}" y1="{Y(b*3):.1f}" x2="{x0+cw}" y2="{Y(b*3):.1f}" stroke="var(--orange)" stroke-dasharray="6 4"></line>'
                 f'<text x="{x0+cw}" y="{Y(b*3)-5:.1f}" text-anchor="end" class="ax orange">3× baseline = {b*3:.0f}</text>')
    o.append(f'<path d="{area}" fill="var(--orange)" opacity=".12"></path><path d="{path}" fill="none" stroke="var(--orange)" stroke-width="1.8"></path>')
    k = 0
    for e in TL.events(r):
        if e["kind"] == "triage" or not (t0 <= e["_at"] <= t1):
            continue
        c = {"spike": "var(--red)", "first_error": "var(--red)", "ticket": "var(--ink)"}.get(e["kind"], "var(--blue)")
        o.append(f'<line x1="{X(e["_at"]):.1f}" y1="{y0}" x2="{X(e["_at"]):.1f}" y2="{y0+ch}" stroke="{c}" stroke-dasharray="3 3"></line>'
                 f'<text x="{X(e["_at"])+5:.1f}" y="{y0+12+14*k}" class="ax" fill="{c}">{esc(TL.KINDS[e["kind"]])} {esc(e.get("label") or "")} · {e["_at"]:%m-%d %H:%M}</text>')
        k += 1
    o.append("</svg>")
    title = f'{esc(s.get("label", "errors"))} · {esc(s.get("unit", "per hour"))}'
    q = next((x for x in r.get("links") or [] if x.get("source") == "metrics" and x.get("url")), None)
    if q:
        title += f' · {links.a("open query", q["url"])}'
    return f'<div class="card"><div class="lbl">{title}</div>{"".join(o)}</div>'


def when(r):
    track = timeline_track(r)
    chart = error_chart(r)
    if not track and not chart:
        return ""
    rel = r.get("release") or {}
    intro = r.get("introduced_by") or {}
    line = ""
    if rel.get("version"):
        line = (f'<p class="muted m0">Release {links.a(rel["version"], rel.get("url"))}, correlation <b>{esc(rel.get("confidence", "?"))}</b>. {esc(rel.get("basis", ""))}'
                + (f' Likely introduced by {links.a(intro["pr"], intro.get("pr_url"))}.' if intro.get("pr") else "") + "</p>")
    return (f'<section><h2>Timeline</h2>' + (f'<div class="card">{track}</div>' if track else "") + chart + line + "</section>")


def priority(r, ev):
    steps = r.get("steps") or []
    if not steps:
        return ""
    drawn = [s for s in steps if s.get("level")]
    hts = {"P1": 88, "P2": 66, "P3": 44, "P4": 22}
    cols = "".join(f'<div class="lstep"><div class="lbar p{s["level"][1]}" style="height:{hts[s["level"]]}px">{esc(s["level"])}</div>'
                   f'<div class="lname">{esc(s.get("step"))}</div>' + (f'<div class="muted">held; would be {esc(s["ghost"])}</div>' if s.get("ghost") else "") + "</div>" for s in drawn)
    notes = "".join(f'<tr><td><code>{esc(s.get("step"))}</code></td><td>{esc(s.get("level") or "—")}</td><td>{esc(s.get("because"))}</td></tr>' for s in steps)
    left = f'<div class="card"><div class="lbl">How the priority was reached</div><div class="ladder">{cols}</div><table class="steps"><tbody>{notes}</tbody></table></div>'
    n, live = S.corroboration_line(r)
    meters = [seg("Independent sources supporting the verdict", n, max(live, 1))]
    if ev:
        meters.append(seg(f"Evidence grade · {ev['level']}", GRADE[ev["level"]], 3))
    cx = r.get("complexity") or EF.complexity(r)
    if cx and cx.get("score") is not None:
        meters.append(seg(f"Fix complexity · {cx['level']}", cx["score"], 5, "ok"))
    un = r.get("unanswered") or []
    meters.append(seg("Rubric questions answered", 10 - len(un), 10, "amber"))
    right = f'<div class="card"><div class="lbl">Evidence and coverage</div>{"".join(meters)}' + \
            (f'<p class="muted m0">Unanswered: {esc("; ".join(un))}.</p>' if un else "") + "</div>"
    return f'<section class="two">{left}{right}</section>'


def seg(label, n, total, cls="teal"):
    cells = "".join(f'<i class="{"on " + cls if i < n else ""}"></i>' for i in range(total))
    return f'<div class="seg"><div class="segl"><span>{esc(label)}</span><span class="muted">{n}/{total}</span></div><div class="segb">{cells}</div></div>'


def code_block(l, k):
    snip = l.get("snippet")
    if not snip:
        return ""
    lines = snip.split("\n")
    fault = l.get("line")
    start = fault - next((i for i, ln in enumerate(lines) if "catch" in ln or "return" in ln), 0) if fault else None
    rows = []
    for i, ln in enumerate(lines):
        no = (start + i) if start else i + 1
        hot = fault and no == fault
        rows.append(f'<div class="cl{" hot" if hot else ""}"><span class="ln">{no}</span><span>{esc(ln)}</span></div>')
    long = len(lines) > MAX_SNIPPET_OPEN
    body = "".join(rows)
    return (f'<figure class="code{" collapsed" if long else ""}" id="code{k}"><figcaption>{links.a(links.location_label(l), l.get("url"), code=True)}'
            f'<span class="tools"><button type="button" class="copy" data-copy="code{k}">Copy</button>'
            + (f'<button type="button" class="more" data-more="code{k}">Show all {len(lines)} lines</button>' if long else "")
            + f'</span></figcaption><pre>{body}</pre></figure>')


def where(r, idx):
    locs = r.get("locations") or []
    extra = r.get("links") or []
    if not locs and not extra:
        return ""
    rows = "".join(f'<tr><td>{links.a(links.location_label(l), l.get("url"), code=True)}</td><td><code class="{("bad" if l.get("signal") in ("error_swallowing", "stub", "suppressed_type_error") else "")}">{esc(l.get("signal", "—"))}</code></td>'
                   f'<td>{linkify(l.get("evidence"), idx)}</td><td class="muted">{esc(l.get("source", "—"))}</td></tr>' for l in locs)
    rows += "".join(f'<tr><td>{links.a(x.get("label"), x.get("url"))}</td><td><code>{esc(x.get("kind"))}</code></td><td>{esc(x.get("text"))}</td><td class="muted">{esc(x.get("source"))}</td></tr>' for x in extra)
    o = [f'<table class="grid"><thead><tr><th>Where</th><th>Signal</th><th>What</th><th>Source</th></tr></thead><tbody>{rows}</tbody></table>']
    o += [code_block(l, k) for k, l in enumerate(locs)]
    hyp = r.get("hypothesis") or {}
    if hyp.get("statement"):
        o.append(f'<p class="m0"><b>Hypothesis.</b> {linkify(hyp["statement"], idx)}</p><ul class="tight"><li>Confirmed if: {linkify(hyp.get("confirm_by"), idx)}</li><li>Refuted if: {linkify(hyp.get("refute_by"), idx)}</li></ul>')
    return f'<section><h2>Where it is</h2><div class="card">{"".join(o)}</div></section>'


def source_link(r, s):
    if s == "tracker":
        return r.get("ticket_url"), "ticket"
    if s == "releases":
        rel = r.get("release") or {}
        intro = r.get("introduced_by") or {}
        return rel.get("url") or intro.get("pr_url"), rel.get("version") or "release"
    if s == "metrics":
        q = next((x for x in r.get("links") or [] if x.get("source") == "metrics" and x.get("url")), None)
        return (q["url"], q.get("label") or "query") if q else (None, None)
    if s == "code":
        l = next((l for l in r.get("locations") or [] if l.get("source") == "code" and l.get("url")), None)
        return (l["url"], links.location_label(l)) if l else (None, None)
    return None, None


def sources(r):
    srcs = r.get("sources") or {}
    prov = r.get("_providers") or {}
    ages = {f["source"]: f for f in S.freshness(r)[0]}
    rows = []
    for s in SOURCES:
        m = srcs.get(s) or {}
        st = "off" if m.get("mode") == "off" else m.get("status", "ok")
        cls = {"ok": "s-ok", "partial": "s-amber", "off": "s-off", "unavailable": "s-off", "error": "s-bad"}.get(st, "s-amber")
        label = {"ok": "connected · data", "partial": "connected · partial", "off": "not connected", "unavailable": "connected · no data",
                 "error": "error"}.get(st, st)
        if m.get("mode") == "fixture":
            label = "recorded fixture"
        stale = ' <span class="warn">stale</span>' if (ages.get(s) or {}).get("stale") else ""
        u, ul = source_link(r, s)
        when = (m.get("as_of") or "")[:16].replace("T", " ")
        name = f'<b>{s}</b>' + (f' <span class="muted">({esc(prov[s])})</span>' if prov.get(s) else "")
        rows.append(f'<tr><td>{name}</td><td><span class="stat {cls}">{esc(label)}</span>{stale}</td>'
                    f'<td>{esc(m.get("note") or "")}</td><td class="muted nowrap">{esc(when)}</td>'
                    f'<td class="nowrap">{links.a(ul, u) if u else ""}</td></tr>')
    return ('<div class="card wide"><div class="lbl">Sources and coverage</div><div class="tbl"><table class="grid">'
            '<thead><tr><th>Source</th><th>Status</th><th>What it returned</th><th>Read at (UTC)</th><th>Open</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div></div>')


def dupes(r):
    d = r.get("duplicate_check") or {}
    cands = d.get("candidates") or []
    if not cands:
        return ""
    # Only matches earn a bar. Tickets ruled out ("different") are counted and linked in one
    # line, so a search that found nothing costs one line however many tickets it compared.
    n = max(d.get("searched") or 0, len(cands))
    rank = {"duplicate": 0, "recurrence": 1, "related": 2}
    hits = sorted((c for c in cands if c.get("verdict") in rank),
                  key=lambda c: (rank[c["verdict"]], -(c.get("score") or 0)))
    shown, rest = hits[:3], [c for c in cands if c not in hits[:3]]
    keys = ", ".join(f'<span class="nowrap">{links.a(c.get("key"), c.get("url"))}</span>' for c in rest[:10])
    more = f" and {len(rest) - 10} more" if len(rest) > 10 else ""
    if not shown:
        return (f'<div class="card strip"><div class="lbl">Duplicate check</div><div>Checked {n} similar '
                f'ticket{"s" if n != 1 else ""}, <strong>none the same bug</strong>: '
                f'<span class="muted">{keys}{more}</span></div></div>')
    verdicts = [c["verdict"] for c in hits]
    head = ("a duplicate found" if "duplicate" in verdicts else "a recurrence found"
            if "recurrence" in verdicts else "related tickets, none the same bug")
    rows = "".join(f'<div class="drow">{links.a(c.get("key"), c.get("url"))}<div class="dbar"><div style="width:{int(min(1, c.get("score", 0)) * 100)}%" class="{"hot" if c["verdict"] in ("duplicate", "recurrence") else ""}"></div></div>'
                   f'<span class="muted">{esc(c["verdict"])} · {esc("; ".join(c.get("signals") or []))}</span></div>' for c in shown)
    tail = (f'<div class="muted small">And {len(rest)} other{"s" if len(rest) != 1 else ""} checked, '
            f'not the same bug: {keys}{more}</div>') if rest else ""
    return f'<div class="card"><div class="lbl">Duplicate check · {n} checked, {head}</div>{rows}{tail}</div>'


def comments_and_against(r, idx):
    o = []
    cm = CM.html_section(r).replace("<h2>Comments on the ticket</h2>", '<div class="lbl">Comments on the ticket</div>', 1)
    if cm:
        o.append(cm)
    ce = against(r, idx)
    if ce:
        o.append(ce)
    dev = r.get("disposition_evidence") or []
    if dev and r.get("disposition") != "defect":
        o.insert(0, f'<div class="lbl">Why this is {esc(r["disposition"].replace("_", " "))}</div><ul class="tight">' + "".join(
            f'<li>{linkify(e.get("text"), idx)} <span class="muted">({links.a(e.get("label") or e.get("source"), e.get("url")) if e.get("url") else esc(e.get("source"))})</span></li>' for e in dev) + "</ul>")
    return f'<div class="card">{"".join(o)}</div>' if o else ""


def source_url(r, src):
    """The best link for a piece of evidence, by the source that produced it."""
    src = (src or "").lower()
    if src.startswith("release"):
        u, _ = source_link(r, "releases")
        return u
    if src.startswith("metric") or src.startswith("log"):
        u, _ = source_link(r, "metrics")
        return u
    if src.startswith("comment"):
        c = next((u for u in (r.get("comment_review") or {}).get("used") or [] if u.get("url")), None)
        return c["url"] if c else r.get("ticket_url")
    if src.startswith("code"):
        u, _ = source_link(r, "code")
        return u
    if src.startswith("tracker") or src.startswith("ticket"):
        return r.get("ticket_url")
    return None


def evidence_phrases(r, idx):
    """Common phrases in the triage's own prose that name a piece of evidence, mapped to it."""
    out = dict(idx)
    logs, _ = source_link(r, "metrics")
    dep = next((x.get("url") for x in r.get("links") or [] if x.get("kind") == "deployment" and x.get("url")), None) or \
        next((e.get("url") for e in r.get("timeline") or [] if isinstance(e, dict) and e.get("kind") == "deploy" and e.get("url")), None)
    code, _ = source_link(r, "code")
    rel = (r.get("release") or {}).get("url")
    for phrase, u in (("deployer log", dep), ("the deploy", dep), ("error rise", logs), ("error rate", logs), ("the log", logs),
                      ("log line", logs), ("tag commit", rel), ("release body", rel), ("the catch", code), ("the code", code)):
        if u and phrase not in out:
            out[phrase] = u
    return out


def against(r, idx):
    idx = evidence_phrases(r, idx)
    cs, alts = CE.collect(r), CE.alternatives(r)
    gaps = CE.gaps(r)
    if not cs and not alts and not gaps:
        return ""
    o = ['<div class="lbl mt">Against this, and other causes</div>']
    o += [f'<div class="note warn">{esc(g)}</div>' for g in gaps]
    if cs:
        items = []
        for c in cs:
            u = source_url(r, c.get("source"))
            src = links.a(c.get("source", "triage"), u) if u else esc(c.get("source", "triage"))
            state = (f'<span class="stat s-ok">addressed</span> {linkify(c["addressed"], idx)}' if c.get("addressed")
                     else '<span class="stat s-bad">open</span>')
            items.append(f'<li><b>{linkify(c["text"], idx)}</b> <span class="muted">({src}, against the {esc(c.get("against", ""))})</span><br>{state}</li>')
        o.append('<ul class="tight against">' + "".join(items) + "</ul>")
    if alts:
        o.append('<div class="lbl mt">Other possible causes</div><ol class="tight">' + "".join(
            f'<li>{linkify(a["statement"], idx)}'
            + (f'<br><span class="muted">Confirm: {linkify(a["confirm_by"], idx)}</span>' if a.get("confirm_by") else "")
            + (f'<br><span class="muted">Less likely because {linkify(a["why_less_likely"], idx)}</span>' if a.get("why_less_likely") else "")
            + "</li>" for a in alts) + "</ol>")
    return "".join(o)


def workaround_card(r, idx):
    wa = r.get("workaround") or {}
    if not wa.get("text"):
        return ""
    o = f'<div class="card"><div class="lbl">Workaround</div><p class="m0"><b>{linkify(wa["text"], idx)}</b></p><p class="muted m0">Who: {esc(wa.get("who", "?"))} · Source: {linkify(wa.get("source", "?"), idx)}'
    if wa.get("does_not_cover"):
        o += f' · Does not cover: {esc(wa["does_not_cover"])}'
    o += "</p>" + (f'<p class="m0">{V.html_line(wa)}</p>' if V.html_line(wa) else "") + "</div>"
    return o


def flow(r):
    srcs = r.get("sources") or {}
    defect = r.get("disposition") == "defect"
    def sstat(s):
        m = srcs.get(s) or {}
        return "off" if m.get("mode") == "off" else m.get("status", "ok")
    nodes = [("0", "Gate", "passed", "done"),
             ("1", "Base sources", "tracker · releases", "done"),
             ("2", "Disposition", esc(r.get("disposition", "")), "done"),
             ("3", "Deep sources", "", "done" if defect else "skipped"),
             ("4", "Classify", f'{esc(r.get("priority") or "—")} · {esc(r.get("confidence", ""))}' if defect else "not scored", "done" if defect else "skipped"),
             ("5", "Outputs", "report · page\nbrief · log", "done")]
    W, Hh, nw, nh, gap, x0, y0 = 1160, 175, 160, 58, 30, 20, 16
    o = [f'<svg viewBox="0 0 {W} {Hh}" class="flow" role="img" aria-label="Triage stages">',
         '<defs><marker id="ar" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="var(--muted)"></path></marker></defs>']
    for i, (n, t, res, st) in enumerate(nodes):
        x = x0 + i * (nw + gap)
        c = "var(--orange)" if n == "4" and st == "done" else "var(--teal)" if st == "done" else "var(--rule)"
        o.append(f'<rect x="{x}" y="{y0}" width="{nw}" height="{nh}" rx="4" fill="var(--surface)" stroke="{c}" stroke-width="1.5"' + (' stroke-dasharray="4 3"' if st != "done" else "") + '></rect>')
        o.append(f'<circle cx="{x+14}" cy="{y0+16}" r="5" fill="{c}"></circle><text x="{x+26}" y="{y0+20}" class="fl-lab">STAGE {n} · {st.upper()}</text>')
        o.append(f'<text x="{x+14}" y="{y0+40}" class="fl-name">{t}</text>')
        for j, line in enumerate(res.split("\n") if res else []):
            o.append(f'<text x="{x+14}" y="{y0+nh+16+j*15}" class="fl-res">{line}</text>')
        if i < len(nodes) - 1:
            o.append(f'<line x1="{x+nw+2}" y1="{y0+nh/2}" x2="{x+nw+gap-2}" y2="{y0+nh/2}" stroke="var(--muted)" stroke-width="1.5" marker-end="url(#ar)"></line>')
    # Stage 3 fans out to the deep sources: a spine drops from the box's left edge and
    # a short branch reaches each source pill, so no line crosses a pill or its text.
    x3 = x0 + 3 * (nw + gap)
    sx, px, ph, step = x3 + 14, x3 + 30, 20, 26
    deep = ("metrics", "code", "warehouse")
    last = y0 + nh + 20 + (len(deep) - 1) * step
    o.append(f'<line x1="{sx}" y1="{y0+nh}" x2="{sx}" y2="{last}" stroke="var(--muted)" stroke-width="1.2"></line>')
    for k, s in enumerate(deep):
        st = sstat(s) if defect else "skipped"
        cy = y0 + nh + 20 + k * step
        c = "var(--ok)" if st == "ok" else "var(--amber)" if st == "partial" else "var(--muted)"
        dash = ' stroke-dasharray="3 3"' if st in ("off", "skipped", "unavailable") else ""
        o.append(f'<line x1="{sx}" y1="{cy}" x2="{px}" y2="{cy}" stroke="var(--muted)" stroke-width="1.2"></line>'
                 f'<rect x="{px}" y="{cy-ph/2}" width="{x3+nw-px}" height="{ph}" rx="3" fill="var(--bg)" stroke="{c}"{dash}></rect>'
                 f'<circle cx="{px+10}" cy="{cy}" r="3.5" fill="{c}"></circle>'
                 f'<text x="{px+20}" y="{cy+4}" class="fl-res" fill="{c}">{s} · {esc(st)}</text>')
    x2 = x0 + 2 * (nw + gap)
    o.append(f'<text x="{x2+14}" y="{y0+nh+34}" class="fl-res">{"non-defects exit here" if defect else "exited here: no priority"}</text></svg>')
    return f'<div class="card"><div class="lbl">How this was produced</div>{"".join(o)}<p class="muted m0">Team {esc(r["team"])} · {esc(r.get("triaged_at", ""))} · agent {esc(r.get("agent_version", ""))}.</p></div>'


def fields_to_update(r):
    cur = r.get("current_priority")
    upd = dict(r.get("fields_to_update") or {})
    if not upd and r.get("tracker_priority") and r.get("tracker_priority") != cur:
        upd = {"priority": r["tracker_priority"]}
    if NA.is_team(r.get("route")) and "assignee" not in upd:
        upd["assignee"] = NA.clean_route(r["route"])
    return upd


# ------------------------------------------------------------------ page

def render(r):
    t = r["ticket"]
    defect = r.get("disposition") == "defect"
    fixed = defect and FX.is_fixed(r)
    cur, tp = r.get("current_priority"), r.get("tracker_priority")
    gap = bool(defect and tp and cur and cur != tp)
    ev = None
    if defect:
        from render_fix_brief import assess
        ev = assess(r)
    idx = link_index(r)
    srcs = r.get("sources") or {}
    notes = []
    fx = [s for s in SOURCES if (srcs.get(s) or {}).get("mode") == "fixture"]
    if fx:
        notes.append(f'<div class="note warn"><b>Demo data.</b> {esc(", ".join(fx))} on fixtures. Not live figures.</div>')
    _, stale = S.freshness(r)
    if stale:
        notes.append(f'<div class="note warn"><b>Stale data.</b> {esc("; ".join(stale))}. Re-check before acting.</div>')
    if ev and ev["caution"]:
        notes.append('<div class="note bad"><b>Weak location evidence.</b> ' + esc(ev["caution"].replace("**", "")) + "<ul>" + "".join(f"<li>{esc(m)}</li>" for m in ev["missing"]) + "</ul></div>")
    hist = H.html_block(r, r.get("_previous") or r.get("previous"))
    body = [header(r, gap, fixed), '<main class="page">', "".join(notes), brief(r, idx, ev, fixed, gap), findings(r, idx)]
    if defect:
        body += [numbers(r), risks(r), when(r), priority(r, ev), where(r, idx), f'<section>{sources(r)}</section>']
    else:
        body += [f'<section>{comments_and_against(r, idx)}</section>', f'<section>{sources(r)}</section>']
    # Stacked, not side by side: the duplicate check is usually one line and would leave
    # its column mostly empty next to the comments.
    parts = [dupes(r), comments_and_against(r, idx) if defect else ""]
    body += [f"<section>{p}</section>" for p in parts if p]
    body.append(f'<section>{flow(r)}</section>')
    body.append(f'<footer class="muted">Rendered by <code>scripts/render_trace.py</code> from <code>{esc(t)}.result.json</code>. Nothing has been written to the tracker.</footer></main>')
    body.append(JS)
    return "\n".join(THEME.head(f"{t} triage", r.get("_theme")) + body)




