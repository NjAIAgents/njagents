#!/usr/bin/env python3
"""HTML pages for the queue and the batch, in the same look as the triage report.

    render_queue.py --html <file>   writes the queue page
    clusters.py                     writes batch-<date>.html next to batch-<date>.md

Both pages use the report's stylesheet (assets/report-theme.css through html_theme),
header, icons and theme switch, and link each ticket to its tracker page and, when one
exists, to its HTML report.
"""
import html, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import html_theme as THEME  # noqa: E402
import links  # noqa: E402
from html_theme import ICON, JS  # noqa: E402

esc = html.escape
WORD = {"P1": "critical", "P2": "high", "P3": "medium", "P4": "low"}

EXTRA_CSS = """<style>
.pchip{font:600 11.5px var(--mono);padding:3px 8px;border-radius:3px;white-space:nowrap}
.pchip.p1{background:var(--red-soft);color:var(--p1)}.pchip.p2{background:var(--orange-soft);color:var(--p2)}
.pchip.p3{background:var(--amber-soft);color:var(--p3)}.pchip.p4{background:var(--blue-soft);color:var(--p4)}
.pchip.none{background:var(--bg);color:var(--muted)}
.flags{display:flex;gap:6px;flex-wrap:wrap}.tag{font:500 11.5px var(--mono);padding:2px 7px;border-radius:3px;background:var(--bg);color:var(--muted);white-space:nowrap}
.tag.bad{background:var(--red-soft);color:var(--red)}.tag.warn{background:var(--amber-soft);color:var(--amber)}.tag.info{background:var(--blue-soft);color:var(--blue)}.tag.ok{background:var(--teal-soft);color:var(--teal)}
tr.hot td:first-child{box-shadow:inset 3px 0 0 var(--red)}
.cmd{display:flex;align-items:center;gap:10px;background:var(--bg);border:1px solid var(--rule);border-radius:4px;padding:10px 12px;font:13px var(--mono)}
.cmd code{flex:1;overflow-x:auto;white-space:nowrap}
.gcard{border-left:4px solid var(--amber)}.gcard.sup{border-left-color:var(--teal)}
.gmeta{display:flex;gap:18px;flex-wrap:wrap;font-size:13.5px}.gmeta b{font-weight:600}
.risk{font-size:15px;letter-spacing:2px}
td.num{font-variant-numeric:tabular-nums;white-space:nowrap}
</style>"""

COPY_JS = """<script>document.querySelectorAll('[data-copy-text]').forEach(function(b){b.addEventListener('click',function(){
var t=b.getAttribute('data-copy-text');function d(){b.textContent='Copied';setTimeout(function(){b.textContent='Copy';},1200);}
if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(t).then(d);}});});</script>"""


def pchip(p):
    return (f'<span class="pchip {p.lower()}">{esc(p)} {WORD[p].upper()}</span>' if p in WORD
            else '<span class="pchip none">—</span>')


def tag(text, kind=""):
    return f'<span class="tag {kind}">{esc(text)}</span>'


def theme_button():
    return (f'<button type="button" class="ibtn theme-btn" id="theme-toggle" data-mode="light" title="Theme: Light" '
            f'aria-label="Theme: Light">{ICON["sun"]}{ICON["moon"]}{ICON["monitor"]}</button>')


def shell(title, heading, chips, meta, body, theme=None, notes=()):
    head = THEME.head(title, theme) + [EXTRA_CSS]
    bar = (f'<header class="bar"><div class="ident"><span class="ttl">{heading}</span></div>'
           f'<div class="chips">{"".join(chips)}</div><div class="meta">{meta}</div>'
           f'<div class="actions">{theme_button()}</div></header>')
    note = "".join(f'<div class="note warn">{n}</div>' for n in notes)
    return "\n".join(head + [bar, f'<main class="page">{note}{"".join(body)}',
                             '<footer class="muted">Nothing has been written to the tracker.</footer></main>',
                             JS, COPY_JS])


def tiles(items):
    return '<section class="tiles">' + "".join(
        f'<div class="tile"><div class="lbl">{esc(l)}</div><div class="num {cls}">{esc(str(v))}</div>'
        f'<div class="muted">{esc(sub)}</div></div>' for l, v, sub, cls in items) + "</section>"


def ticket_link(key, url, report=None):
    s = links.a(key, url, code=True)
    if report:
        s += f' <a class="muted small" href="{esc(report)}" title="HTML report">report</a>'
    return s


# ------------------------------------------------------------------ queue

def queue(rows, *, project, team, how, policy_line, names, cfg, log_path, reports_abs, limit_note="", demo=False, now=None):
    """rows: from render_queue.build_rows."""
    import sla as SL
    from datetime import datetime, timezone
    now = now or datetime.now(timezone.utc)
    untriaged = [r for r in rows if r["rec"] is None]
    overdue = [r for r in rows if r["overdue"]]
    stuck = [r for r in rows if r["stuck"]]
    changed = [r for r in rows if r["changed"]]
    tmpl = (cfg.get("links") or {}).get("ticket")

    chips = [f'<span class="chip c-muted">{len(rows)} OPEN</span>',
             f'<span class="chip c-blue">{len(untriaged)} UNTRIAGED</span>']
    if overdue:
        chips.append(f'<span class="chip c-red">⏰ {len(overdue)} OVERDUE</span>')
    if stuck:
        chips.append(f'<span class="chip c-p3">🧊 {len(stuck)} STUCK</span>')
    meta = (f'<span class="muted">Team</span> <b>{esc(team)}</b> · <span class="muted">chosen by</span> {esc(how)}'
            f' · {esc(policy_line)}')

    trs = []
    for r in rows:
        i, rec = r["i"], r["rec"]
        url = i.get("url") or links.fill(tmpl, key=i["key"])
        rep = None
        if rec and os.path.exists(os.path.join(reports_abs, f"{i['key']}-report.html")):
            rep = f"{i['key']}-report.html"
        flags = []
        if r["risky"]:
            flags.append(tag("at-risk", "bad"))
        if r["overdue"]:
            flags.append(tag(f"⏰ overdue {_dur(r['over_by'])}", "bad"))
        if r["changed"]:
            flags.append(tag("changed since triage", "info"))
        if r["stuck"]:
            flags.append(tag(f"🧊 no movement {r['since']}d", "warn"))
        if rec and "human_review" in (rec.get("flags") or []) and not rec.get("human_override"):
            flags.append(tag("👤 needs a person", "warn"))
        if rec and "already_fixed" in (rec.get("flags") or []):
            flags.append(tag("✅ fix merged", "ok"))
        if rec and rec.get("human_override"):
            flags.append(tag("reviewed", "ok"))
        if rec is None:
            verdict = '<span class="stat s-amber">not triaged</span>'
        elif rec.get("disposition") == "defect" and rec.get("priority"):
            p = rec["priority"]
            verdict = pchip(p)
            want, have = names.get(p), i.get("priority")
            if want and have and want != have:
                flags.append(tag(f"tracker {have} → {want}", "bad"))
            s = SL.compute({"disposition": "defect", "priority": p, "ticket_created": i.get("created"),
                            "triaged_at": rec.get("ts")}, cfg, now=now)
            if s and s.get("state") in ("breached", "due_soon"):
                flags.append(tag(f"{SL.ICON[s['state']]} fix {s['delta']}", "bad" if s["state"] == "breached" else "warn"))
        else:
            verdict = tag(rec.get("disposition", "").replace("_", " "))
        when = esc((rec or {}).get("ts", "")[:10]) or "—"
        age = f"{r['age']}d" if r["age"] is not None else "—"
        trs.append(f'<tr class="{"hot" if r["overdue"] else ""}"><td>{ticket_link(i["key"], url, rep)}</td>'
                   f'<td>{esc(i.get("summary") or "")}</td><td class="muted">{esc(i.get("component") or "—")}</td>'
                   f'<td>{esc(i.get("priority") or "—")}</td><td class="num">{age}</td><td>{verdict}</td>'
                   f'<td class="muted num">{when}</td><td><div class="flags">{"".join(flags)}</div></td></tr>')
    table = ('<section><div class="card"><div class="lbl">Open bugs · recommended order' + (f" · {esc(limit_note)}" if limit_note else "")
             + '</div><div class="tbl"><table><thead><tr><th>Ticket</th><th>Summary</th><th>Area</th><th>Tracker</th>'
             '<th>Age</th><th>Triage</th><th>On</th><th>Flags</th></tr></thead><tbody>' + "".join(trs)
             + "</tbody></table></div></div></section>") if rows else '<section><div class="card">No open bugs.</div></section>'

    nxt = []
    todo = [r["i"]["key"] for r in untriaged][:5]
    if todo:
        cmd = "/bug-triage-agent:triage " + " ".join(todo)
        nxt.append(f'<div class="lbl">Next · triage the untriaged ones</div><div class="cmd"><code>{esc(cmd)}</code>'
                   f'<button type="button" class="hbtn" data-copy-text="{esc(cmd, quote=True)}">Copy</button></div>')
    if changed:
        nxt.append(f'<p class="m0">Changed since their last triage: {", ".join(esc(r["i"]["key"]) for r in changed[:5])}. Worth a re-run.</p>')
    if stuck:
        nxt.append('<p class="m0">P1 or P2 with no tracker activity since triage: '
                   + ", ".join(f'{esc(r["i"]["key"])} ({r["since"]}d)' for r in stuck[:5]) + ". Chase the owner.</p>")
    if not nxt:
        nxt.append('<p class="m0">Everything open has been triaged and nothing changed since.</p>')
    body = [tiles([("Open", len(rows), f"project {project}", ""),
                   ("Not triaged", len(untriaged), "waiting for the agent", "warn" if untriaged else ""),
                   ("Overdue", len(overdue), "past the triage limit", "bad" if overdue else ""),
                   ("Changed", len(changed), "since their last triage", ""),
                   ("Stuck", len(stuck), "triaged P1/P2, no movement", "warn" if stuck else "")]),
            f'<section><div class="card">{"".join(nxt)}</div></section>', table,
            f'<p class="muted m0">Audit log: <code>{esc(log_path)}</code></p>']
    notes = ["<b>Demo data.</b> The tracker is on fixtures. Not live tickets."] if demo else []
    return shell(f"{project} queue", f"Bug queue · {esc(project)}", chips, meta, body, cfg.get("output", {}).get("theme"), notes)


def _dur(h):
    return f"{h:.0f}h" if h < 48 else f"{h / 24:.0f}d"


# ------------------------------------------------------------------ batch

def batch(results, clusters, cfg=None, now=None):
    import effort as EF, risks as RK, next_action as NA, sla as SL
    from datetime import datetime, timezone
    now = now or datetime.now(timezone.utc)
    order = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}
    defects = sorted([r for r in results if r.get("disposition") == "defect"],
                     key=lambda r: (order.get(r.get("priority"), 9), r["ticket"]))
    others = [r for r in results if r.get("disposition") != "defect"]
    label, member = {}, {}
    for n, c in enumerate(clusters, 1):
        label[c["id"]] = f"G{n}"
        for t in c["tickets"]:
            member.setdefault(t, []).append(c)
    sup = [c for c in clusters if c["status"] == "EVIDENCE_SUPPORTED"]
    counts = {p: sum(1 for r in defects if r.get("priority") == p) for p in order}

    chips = [f'<span class="chip c-p{p[1]}">{counts[p]} × {p}</span>' for p in order if counts[p]]
    chips.append(f'<span class="chip c-teal">{len(clusters)} GROUPS</span>')
    meta = f'<span class="muted">Triaged</span> {now:%Y-%m-%d %H:%M} UTC · {len(results)} tickets'

    def report_link(r):
        return f"{r['ticket']}-report.html"

    rows = []
    for r in defects:
        g = " ".join(f'<a href="#{esc(label[c["id"]])}" class="tag {"ok" if c["status"] == "EVIDENCE_SUPPORTED" else "warn"}">'
                     f'{esc(label[c["id"]])}</a>' for c in member.get(r["ticket"], [])) or '<span class="muted">—</span>'
        due = SL.short(r)
        rows.append(f'<tr><td>{ticket_link(r["ticket"], r.get("ticket_url"), report_link(r))}</td>'
                    f'<td>{pchip(r.get("priority"))}' + (f' <span class="muted small">{esc(due)}</span>' if due else "") + '</td>'
                    f'<td>{esc(r.get("summary") or "")}</td><td>{esc(NA.short(r))}</td>'
                    f'<td class="risk" title="{esc(", ".join(RK.LABEL[x["type"]] for x in RK.get(r)))}">{esc(RK.icons(r))}</td>'
                    f'<td>{esc(EF.short(r))}</td><td>{g}</td></tr>')
    body = [tiles([("Tickets", len(results), "in this batch", ""),
                   ("Defects", len(defects), "ranked below", ""),
                   ("P1 · P2", counts["P1"] + counts["P2"], "fix first", "bad" if counts["P1"] else ("warn" if counts["P2"] else "")),
                   ("Groups", len(clusters), f"{len(sup)} supported by evidence", ""),
                   ("Not defects", len(others), "no fix needed", "")])]
    if defects:
        used = [t for t in RK.TYPES if any(x["type"] == t for r in defects for x in RK.get(r))]
        leg = " · ".join(f"{RK.ICON[t]} {RK.LABEL[t]}" for t in used)
        body.append('<section><div class="card"><div class="lbl">Defects, ranked</div><div class="tbl"><table><thead><tr>'
                    '<th>Ticket</th><th>Priority</th><th>Summary</th><th>Next action</th><th>Risks</th><th>Complexity</th>'
                    '<th>Group</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>"
                    + (f'<p class="muted m0 small">Risks: {esc(leg)}</p>' if leg else "") + "</div></section>")
    if clusters:
        cards = []
        for c in clusters:
            s = c["status"] == "EVIDENCE_SUPPORTED"
            short = c["key"].rsplit("/", 1)[-1] if c["basis"] == "file" else c["key"]
            notes = "".join(f'<div class="note">{esc(n[:1].upper() + n[1:])}.</div>' for n in c.get("notes") or [])
            cards.append(
                f'<div class="card gcard {"sup" if s else ""}" id="{esc(label[c["id"]])}">'
                f'<div class="rhead"><b>{esc(label[c["id"]])} · {esc(short)}</b>'
                f'{tag("🔗 supported by evidence", "ok") if s else tag("❔ proposed", "warn")}</div>'
                + (f'<div class="muted small"><code>{esc(c["key"])}</code></div>' if c["basis"] == "file" else "")
                + f'<div class="gmeta"><span><span class="muted">Tickets</span> '
                + ", ".join(links.a(t, next((r.get("ticket_url") for r in results if r["ticket"] == t), None)) for t in c["tickets"])
                + f'</span><span><span class="muted">Priority</span> {pchip(c.get("priority"))}</span>'
                + (f'<span><span class="muted">Owner</span> <b>{esc(c["owner"])}</b></span>' if c.get("owner") else "")
                + f'</div><p class="m0"><b>Why grouped.</b> {esc(c["why"])}.</p>'
                + (f'<p class="m0"><b>Likely shared cause.</b> {esc(c["likely_shared_cause"])}</p>' if c.get("likely_shared_cause") else "")
                + notes + f'<p class="m0"><b>Next.</b> {esc(c["next"])}</p></div>')
        body.append('<section><h2>Groups</h2><div class="two">' + "".join(cards) + "</div>"
                    '<p class="muted small">A group\'s priority is its highest member; grouping never raises anyone\'s priority.</p></section>')
    else:
        body.append('<section><div class="card strip"><div class="lbl">Groups</div><div>No two defects share a located file '
                    'or a release and area.</div></div></section>')
    if others:
        body.append('<section><div class="card"><div class="lbl">Not defects</div><div class="tbl"><table><thead><tr>'
                    '<th>Ticket</th><th>Disposition</th><th>Next action</th><th>Route</th></tr></thead><tbody>'
                    + "".join(f'<tr><td>{ticket_link(r["ticket"], r.get("ticket_url"), report_link(r))}</td>'
                              f'<td>{tag(r.get("disposition", "").replace("_", " "))}</td><td>{esc(NA.short(r))}</td>'
                              f'<td>{esc(NA.clean_route(r.get("route")) or "—")}</td></tr>' for r in others)
                    + "</tbody></table></div></div></section>")
    demo = any(s.get("mode") == "fixture" for r in results for s in (r.get("sources") or {}).values())
    notes = ["<b>Demo data.</b> Some sources are recorded fixtures."] if demo else []
    return shell(f"Batch triage {now:%Y-%m-%d}", f"Batch triage · {len(results)} tickets", chips, meta, body,
                 ((cfg or {}).get("output") or {}).get("theme"), notes)


# ------------------------------------------------------------------ automatic-run digest

def report_for(ticket, reports_abs):
    """The report a person should open for a ticket: the HTML page, else the markdown."""
    for name in (f"{ticket}-report.html", f"{ticket}.md"):
        if os.path.exists(os.path.join(reports_abs, name)):
            return name
    return None


def digest(team, defects, others, failed, *, cfg, reports_abs, index=None, now=None):
    """The review page for one automatic run. The page lives in <reports_dir>/auto/, so
    report links go one folder up."""
    import next_action as NA, risks as RK, summary as S
    from datetime import datetime, timezone
    now = now or datetime.now(timezone.utc)
    held = [r for r in defects if (r.get("human_review") or {}).get("required")]
    rel = lambda r: (lambda n: f"../{n}" if n else None)(report_for(r["ticket"], reports_abs))

    chips = [f'<span class="chip c-muted">{len(defects) + len(others)} TRIAGED</span>']
    if held:
        chips.append(f'<span class="chip c-p3">👤 {len(held)} NEED A PERSON</span>')
    if failed:
        chips.append(f'<span class="chip c-red">{len(failed)} NOT COMPLETED</span>')
    chips.append('<span class="chip c-teal">NOTHING WRITTEN TO THE TRACKER</span>')
    meta = f'<span class="muted">Team</span> <b>{esc(team)}</b> · <span class="muted">Run</span> {now:%Y-%m-%d %H:%M} UTC'

    ready = len((index or {}).get("ready") or [])
    body = [tiles([("Defects", len(defects), "ranked below", ""),
                   ("Need a person", len(held), "held by team policy", "warn" if held else ""),
                   ("Not defects", len(others), "no fix needed", ""),
                   ("Not completed", len(failed), "rerun these", "bad" if failed else ""),
                   ("Briefs ready", ready, "for a fix agent · briefs.json", "")])]
    if held:
        items = "".join(
            f'<li>{ticket_link(r["ticket"], r.get("ticket_url"), rel(r))} · '
            + ", ".join(f'{RK.ICON[b["type"]]} {esc(RK.LABEL[b["type"]])} ({esc(b["level"])})' for b in r["human_review"]["because"])
            + "</li>" for r in held)
        body.append('<section><div class="card"><div class="lbl">Needs a person</div><p class="m0">The team config holds these '
                    'for a person\'s decision. Do not post them, and no fix agent picks them up, until a named reviewer '
                    f'confirms.</p><ul class="tight">{items}</ul></div></section>')
    if defects:
        trs = []
        for r in defects:
            sm = S.summary(r)
            trs.append(f'<tr><td>{ticket_link(r["ticket"], r.get("ticket_url"), rel(r))}</td><td>{pchip(r.get("priority"))}</td>'
                       f'<td>{esc(NA.short(r))}</td><td>{esc(sm.get("verdict") or "")}</td>'
                       f'<td class="muted">{esc(sm.get("do_now") or "")}</td></tr>')
        body.append('<section><div class="card"><div class="lbl">Defects</div><div class="tbl"><table><thead><tr>'
                    '<th>Ticket</th><th>Priority</th><th>Next action</th><th>Verdict</th><th>Do now</th></tr></thead><tbody>'
                    + "".join(trs) + "</tbody></table></div></div></section>")
    if others:
        body.append('<section><div class="card"><div class="lbl">Not defects</div><div class="tbl"><table><thead><tr>'
                    '<th>Ticket</th><th>Disposition</th><th>Route</th></tr></thead><tbody>'
                    + "".join(f'<tr><td>{ticket_link(r["ticket"], r.get("ticket_url"), rel(r))}</td>'
                              f'<td>{tag(r.get("disposition", "").replace("_", " "))}</td>'
                              f'<td>{esc(NA.clean_route(r.get("route")) or "—")}</td></tr>' for r in others)
                    + "</tbody></table></div></div></section>")
    if failed:
        body.append('<section><div class="card"><div class="lbl">Not completed</div><ul class="tight">'
                    + "".join(f"<li><b>{esc(k)}</b>: {esc(why)}</li>" for k, why in failed) + "</ul></div></section>")
    cmd = '/bug-triage-agent:triage-review <TICKET> <disposition or priority> "<reason>"'
    body.append('<section><div class="card"><div class="lbl">Review</div><p class="m0">Agree with a row: nothing to do, or '
                'post its comment after reading the report. Disagree: record it, so the agent learns from it.</p>'
                f'<div class="cmd"><code>{esc(cmd)}</code><button type="button" class="hbtn" '
                f'data-copy-text="{esc(cmd, quote=True)}">Copy</button></div></div></section>')
    return shell(f"Automatic triage {team}", f"Automatic triage · {esc(team)}", chips, meta, body,
                 (cfg.get("output") or {}).get("theme"))
