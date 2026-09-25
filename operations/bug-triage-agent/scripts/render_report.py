#!/usr/bin/env python3
"""Render the triage report, <TICKET>.md, from the result file.

The report used to be written by the model from a template, so its wording and layout
drifted between runs and it could disagree with the trace rendered from the same
result. It is now rendered by code from <TICKET>.result.json, the same file the trace
and the fix brief read, so the three always agree.

    python3 scripts/render_report.py --team-config <config> --out triage-reports \\
        triage-reports/DEMO-7.result.json

Layout follows reference/output-templates.md section 2. Evidence links sit behind short
labels (scripts/links.py). The summary, corroboration and freshness come from
scripts/summary.py, shared with the trace and the fix brief.
"""
import argparse, json, os, sys

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
from render_trace import validate  # noqa: E402
from render_fix_brief import assess  # noqa: E402

PRIO = {"P1": "🔴", "P2": "🟠", "P3": "🟡", "P4": "🔵"}
MODE = {"live": "🟢", "fixture": "🟡", "off": "⚫"}
EVID = {"strong": "🟢", "moderate": "🟡", "weak": "🔴"}
METER = {"high": "●●●", "medium": "●●○", "low": "●○○"}


def cell(v):
    return ("" if v is None else str(v)).replace("|", "/").replace("\n", " ")


def labels(r, fixed, gap):
    """Short labels a reader scans before the table: what kind of ticket this is and what
    is unusual about it. Built only from data that is set."""
    t = []
    if r.get("disposition") == "defect":
        t.append("regression" if S._regression(r) else "defect")
        if fixed:
            t.append("already fixed")
    else:
        t.append(r["disposition"].replace("_", " "))
    relo = r.get("release") or {}
    rel = relo.get("version") if relo.get("confidence") in ("high", "medium", None) and relo.get("version") else None
    if rel:
        t.append(f"since {rel}")
    if r.get("component"):
        t.append(r["component"])
    if gap:
        t.append("priority gap")
    sl = r.get("sla") or {}
    if sl.get("state") in ("breached", "due_soon"):
        t.append("overdue" if sl["state"] == "breached" else "due soon")
    if HG.required(r):
        t.append("needs a person")
    if r.get("clusters"):
        t.append("in a group")
    w = r.get("workaround") or {}
    if w.get("text"):
        t.append("customer workaround" if NA.customer_can_apply(w) else "internal workaround")
    return t


def lead_bold(text):
    """Bold the instruction itself, up to the first clause break, leaving the who and why plain."""
    import re
    m = re.match(r"(.+?)([;:.] |$)", text)
    return f"**{m.group(1)}**{text[len(m.group(1)):]}" if m else text


HEAD = {"Timeline": "⏱", "Why this is": "🧭", "Against this": "⚖️", "Duplicate check": "🔁", "Comments": "💬",
        "How the priority": "🧮", "Workaround": "💡", "Evidence": "🔎", "Coverage": "📡", "Fields to update": "✏️",
        "Risks": "🛡", "Fix status": "🔧"}


def mark_headings(lines):
    out = []
    for ln in lines:
        if ln.startswith("## "):
            k = next((v for key, v in HEAD.items() if ln[3:].startswith(key)), None)
            ln = f"## {k} {ln[3:]}" if k else ln
        out.append(ln)
    return out


def timeline_block(r):
    """The timeline (chart when there is a series, always the event table) with the release
    correlation as its first line. Placed right after the story: it is the story, drawn."""
    rel = r.get("release") or {}
    intro = r.get("introduced_by") or {}
    rel_line = []
    if rel:
        rel_line = [f"**Release:** {links.md(rel.get('version'), rel.get('url'))}, correlation "
                    f"**{rel.get('confidence', '?')}**. {rel.get('basis', '')}"
                    + (f" Likely introduced by {links.md(intro['pr'], intro.get('pr_url'))}." if intro.get("pr") else ""), ""]
    tl = TL.md(r)
    if tl:
        return tl[:2] + rel_line + tl[2:]
    return (["## Release", ""] + rel_line) if rel_line else []


def render(r):
    t, defect = r["ticket"], r.get("disposition") == "defect"
    srcs = r.get("sources") or {}
    ev = assess(r) if defect else None
    summ = S.summary(r)
    corr = S.corroboration(r)
    fresh, stale = S.freshness(r)
    o = []

    fixtures = [s for s in S.SOURCES if (srcs.get(s) or {}).get("mode") == "fixture"]
    if fixtures:
        o += links.callout("warning", f"**Demo data.** {', '.join(fixtures)} on fixtures. Not live figures.") + [""]
    errored = [s for s in S.SOURCES if (srcs.get(s) or {}).get("status") == "error"]
    if errored:
        o += links.callout("caution", "**Source error:** " + "; ".join(
            f"{s}: {cell((srcs[s] or {}).get('note') or 'failed')}" for s in errored)) + [""]
    if ev and ev["level"] != "strong":
        o += links.callout("caution", ev["caution"], *[f"- {m}" for m in ev["missing"]]) + [""]
    if stale:
        o += links.callout("warning", "**Stale data.** " + "; ".join(stale)
                           + ". Re-check before acting; the evidence may not be reproducible later.") + [""]

    fixed = defect and FX.is_fixed(r)
    cur, tp = r.get("current_priority"), r.get("tracker_priority")
    gap = bool(defect and tp and cur and cur != tp)

    # Masthead: ticket, then one line of the facts a reader scans for.
    head = f"{PRIO.get(r.get('priority'), '')} {r.get('priority')} · " if defect else "⚪ "
    o += [f"# {head}{links.md(t, r.get('ticket_url'))} · {r.get('summary', '')}", ""]
    o += [f"*Triaged {r.get('triaged_at', '')} · team `{r.get('team', '')}` · agent {r.get('agent_version', '')}*", ""]
    tags = labels(r, fixed, gap)
    if tags:
        o += [" ".join(f"`{t}`" for t in tags), ""]
    o += HG.md(r)

    # The answer, in three lines. Most readers stop here.
    o += [f"> ### {summ['verdict']}"]
    if summ["why"]:
        o += [">", "> **Why** · " + S.why_line(summ["why"])]
    o += [">", f"> **Next** · {NA.answer_line(r, summ['do_now'])}"]
    o.append("")
    o += ST.md(r)

    # At a glance: two-column key facts, no section heading needed.
    rows = [("Disposition", f"`{r.get('disposition')}`")]
    if defect:
        rows.append(("Priority", f"**{PRIO.get(r['priority'], '')} {r['priority']}**"
                     + (f" · ❗ tracker has \"{cur}\", set it to \"{tp}\"" if gap else f" → tracker \"{tp}\"" if tp else "")))
        if SL.cell(r) and not fixed:
            rows.append(("Fix due", cell(SL.cell(r))))
    rows.append(("Confidence", f"{METER.get(r.get('confidence'), '')} {r.get('confidence', '')}"))
    if corr:
        n, live = S.corroboration_line(r)
        lead = f"{EVID[ev['level']]} {ev['level']} evidence · " if ev else ""
        rows.append(("Supported by", f"{lead}{n} of {live} sources: "
                     + " · ".join(f"{c['source']} {links.md(c['label'], c['url'])}" for c in corr)))
    elif ev:
        rows.append(("Evidence", f"{EVID[ev['level']]} {ev['level']}"))
    if defect and not fixed:
        rp = r.get("reproduction") or EF.reproduction(r)
        if rp["status"] != "not_attempted":
            rows.append(("Reproduction", cell(EF.repro_cell(r, brief=True))))
        cx = EF.complexity_cell(r)
        if cx:
            rows.append(("Fix complexity", cell(cx)))
        rs = RK.get(r)
        if rs:
            rows.append(("Risks", " · ".join(f"{RK.ICON[x['type']]} {RK.LABEL[x['type']]} ({x['level']})" for x in rs)))
    if NA.is_team(r.get("route")):
        rows.append(("Route to", f"**{cell(NA.clean_route(r['route']))}**"))
    if defect:
        rows.append(("Fix brief", f"[{t}.fix-brief.md]({t}.fix-brief.md)"))
    o += ["| | |", "| --- | --- |"] + [f"| **{k}** | {v} |" for k, v in rows] + [""]
    if r.get("confidence_basis"):
        b = r["confidence_basis"].strip()
        o += [f"*Confidence is {r.get('confidence', '')} because {b[:1].lower() + b[1:]}*", ""]

    o += H.md(r, r.get("_previous") or r.get("previous"))
    o += FX.md(r)
    if defect:
        o += timeline_block(r)
    o += CL.md_membership(r)
    if r.get("deciding_factor"):
        o += [f"**Deciding factor:** {r['deciding_factor']}", ""]

    dev = r.get("disposition_evidence") or []
    if dev:
        o += [f"## Why this is `{r.get('disposition')}`", "", "| Evidence | Source |", "| --- | --- |"]
        for e in dev:
            src = links.md(e.get("label") or e.get("source"), e.get("url")) if e.get("url") else cell(e.get("source"))
            o.append(f"| {cell(e.get('text'))} | {src} |")
        o.append("")
    if r.get("alternative"):
        o += [r["alternative"], ""]
    o += CE.md(r)
    o += D.md(r)
    o += CM.md(r)

    if not defect:
        if r.get("route_note"):
            o += [r["route_note"], ""]
        o += links.callout("note", "Nothing has been written to the tracker. Confirm before posting.")
        return "\n".join(mark_headings(o)) + "\n"

    steps = r.get("steps") or []
    if steps:
        o += ["## How the priority was reached", "", "| Step | Level | Because |", "| --- | --- | --- |"]
        for s in steps:
            lvl = f"{PRIO.get(s.get('level'), '')} {s.get('level')}" if s.get("level") else "—"
            o.append(f"| `{cell(s.get('step'))}` | {lvl} | {cell(s.get('because'))} |")
        o.append("")


    wa = r.get("workaround") or {}
    if wa.get("text"):
        o += ["## Workaround", ""] + links.callout(
            "tip", f"**{wa['text']}**", "",
            f"**Who can do this:** {wa.get('who', '?')} · **Source:** {wa.get('source', '?')}")
        if wa.get("does_not_cover"):
            o.append(f"> **Does not cover:** {wa['does_not_cover']}")
        if V.line(wa):
            o += [">", f"> {V.md_line(wa)}"]
        o.append("")

    locs = r.get("locations") or []
    extra = r.get("links") or []
    if locs or extra:
        o += ["## Evidence", "", "| Where | Signal | What | Source |", "| --- | --- | --- | --- |"]
        for l in locs:
            o.append(f"| {links.md_code(links.location_label(l), l.get('url'))} | `{l.get('signal', '—')}` | "
                     f"{cell(l.get('evidence'))} | {l.get('source', '—')} |")
        for x in extra:
            o.append(f"| {links.md(x.get('label'), x.get('url'))} | {cell(x.get('kind'))} | "
                     f"{cell(x.get('text'))} | {cell(x.get('source'))} |")
        o.append("")
        for l in locs:
            if l.get("snippet"):
                o += ["```", f"{links.location_label(l)}", l["snippet"], "```", ""]

    # What each source found is already in the evidence above; here only whether it answered.
    ages = {f["source"]: f for f in fresh}
    parts = []
    for s in S.SOURCES:
        src = srcs.get(s) or {}
        mode = src.get("mode", "off")
        st = "not queried" if mode == "off" else src.get("status", "ok")
        f = ages.get(s) or {}
        stale_ = " ⚠ stale" if f.get("stale") else ""
        mark = {"ok": "🟢", "unavailable": "⚪", "error": "🔴", "not queried": "⚫"}.get(st, "🟡")
        parts.append(f"{mark} {s} {st}{stale_}")
    o += ["## Coverage", "", " · ".join(parts), ""]
    un = r.get("unanswered") or []
    o += (["**Unanswered** (a source was off; each lowers confidence, none raises severity):", ""]
          + [f"- {u}" for u in un] + [""]) if un else ["All ten classification questions answered.", ""]

    upd = r.get("fields_to_update") or {}
    if not upd and r.get("tracker_priority") and r.get("tracker_priority") != cur:
        upd = {"priority": r["tracker_priority"]}
    if r.get("route") and "assignee" not in upd:
        upd = {**upd, "assignee": r["route"]}
    if upd:
        w = max(len(k) for k in upd)
        o += ["## Fields to update", "", "```"] + [f"{k.ljust(w)}  → {v}" for k, v in upd.items()] + ["```", ""]
    o += links.callout("note", "Nothing has been written to the tracker. Confirm before posting.")
    return "\n".join(mark_headings(o)) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="+")
    ap.add_argument("--out", help="directory; default next to each result")
    ap.add_argument("--team-config", help="team config; fills evidence links from its `links` templates")
    a = ap.parse_args()
    failed = 0
    for path in a.results:
        with open(path, encoding="utf-8") as f:
            r = json.load(f)
        if a.team_config:
            with open(a.team_config, encoding="utf-8") as cf:
                _cfg = json.load(cf)
                links.enrich(r, _cfg)
                RK.fill(r, _cfg)
                HG.fill(r, _cfg)
                SL.fill(r, _cfg)
                r["_providers"] = {k: v.get("provider") for k, v in (_cfg.get("sources") or {}).items() if isinstance(v, dict) and v.get("provider")}
        H.attach(path, r)
        problems = validate(r)
        if problems:
            print(f"{path}: refusing to render: " + "; ".join(problems), file=sys.stderr)
            failed += 1
            continue
        out = a.out or os.path.dirname(os.path.abspath(path))
        os.makedirs(out, exist_ok=True)
        dest = os.path.join(out, f"{r['ticket']}.md")
        with open(dest, "w", encoding="utf-8") as f:
            f.write(render(r))
        print(f"wrote {dest}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
