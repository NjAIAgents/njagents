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
import verify_workaround as V  # noqa: E402
from render_trace import validate  # noqa: E402
from render_fix_brief import assess  # noqa: E402

PRIO = {"P1": "🔴", "P2": "🟠", "P3": "🟡", "P4": "🔵"}
MODE = {"live": "🟢", "fixture": "🟡", "off": "⚫"}
EVID = {"strong": "🟢", "moderate": "🟡", "weak": "🔴"}
METER = {"high": "●●●", "medium": "●●○", "low": "●○○"}


def cell(v):
    return ("" if v is None else str(v)).replace("|", "/").replace("\n", " ")


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

    head = f"{PRIO.get(r.get('priority'), '')} {r.get('priority')} · " if defect else "⚪ "
    o += [f"# {head}{links.md(t, r.get('ticket_url'))} · {r.get('summary', '')}", ""]
    o += [f"Triaged {r.get('triaged_at', '')} · team `{r.get('team', '')}` · agent {r.get('agent_version', '')}", ""]

    # The answer, in three lines. Most readers stop here.
    o += [f"> **{summ['verdict']}**"]
    if summ["why"]:
        o += [">", "> **Why:** " + "; ".join(w.rstrip(".") for w in summ["why"]) + "."]
    if summ["do_now"]:
        o += [">", f"> **Do now:** {summ['do_now']}"]
    o.append("")
    o += H.md(r, r.get("_previous") or r.get("previous"))

    o += ["## Recommendation", "", "| | |", "| --- | --- |",
          f"| **Disposition** | `{r.get('disposition')}` |"]
    if defect:
        tp = f" → tracker \"{r['tracker_priority']}\"" if r.get("tracker_priority") else ""
        o.append(f"| **Priority** | **{PRIO.get(r['priority'], '')} {r['priority']}**{tp} |")
    o.append(f"| **Confidence** | {METER.get(r.get('confidence'), '')} {r.get('confidence', '')} |")
    if ev:
        o.append(f"| **Evidence** | {EVID[ev['level']]} {ev['level']} |")
    if corr:
        n, live = S.corroboration_line(r)
        o.append(f"| **Supported by** | {n} of {live} sources: "
                 + " · ".join(f"{c['source']} {links.md(c['label'], c['url'])}" for c in corr) + " |")
    if r.get("route"):
        o.append(f"| **Route to** | **{cell(r['route'])}** |")
    if defect:
        o.append(f"| **Fix brief** | [{t}.fix-brief.md]({t}.fix-brief.md) |")
    o.append("")
    if r.get("deciding_factor"):
        o += [f"**Deciding factor:** {r['deciding_factor']}", ""]
    cur = r.get("current_priority")
    if defect and cur and r.get("tracker_priority") and cur != r["tracker_priority"]:
        o += links.callout("important", f"**Priority gap.** The tracker has this at \"{cur}\". "
                           f"Recommended \"{r['tracker_priority']}\".") + [""]

    dev = r.get("disposition_evidence") or []
    if dev:
        o += [f"## Why this is `{r.get('disposition')}`", "", "| Evidence | Source |", "| --- | --- |"]
        for e in dev:
            src = links.md(e.get("label") or e.get("source"), e.get("url")) if e.get("url") else cell(e.get("source"))
            o.append(f"| {cell(e.get('text'))} | {src} |")
        o.append("")
    if r.get("alternative"):
        o += [r["alternative"], ""]
    o += D.md(r)

    if not defect:
        if r.get("route"):
            o += ["## Route", "", f"**{r['route']}**" + (f". {r['route_note']}" if r.get("route_note") else ""), ""]
        o += links.callout("note", "Nothing has been written to the tracker. Confirm before posting.")
        return "\n".join(o) + "\n"

    steps = r.get("steps") or []
    if steps:
        o += ["## How the priority was reached", "", "| Step | Level | Because |", "| --- | --- | --- |"]
        for s in steps:
            lvl = f"{PRIO.get(s.get('level'), '')} {s.get('level')}" if s.get("level") else "—"
            o.append(f"| `{cell(s.get('step'))}` | {lvl} | {cell(s.get('because'))} |")
        o.append("")

    rel = r.get("release") or {}
    if rel:
        o += ["## Release correlation", "",
              f"**{links.md(rel.get('version'), rel.get('url'))}**, shipped {rel.get('shipped', '?')}"
              + (f", {rel['gap_days']} days before first seen" if rel.get("gap_days") is not None else "")
              + f". {rel.get('basis', '')} **Correlation confidence: {rel.get('confidence', '?')}.**", ""]
        intro = r.get("introduced_by") or {}
        if intro.get("pr"):
            o += [f"Likely introduced by {links.md(intro['pr'], intro.get('pr_url'))}.", ""]
    o += TL.md(r)

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

    o += ["## Coverage", "", "| Source | Mode | Result | Data |", "| --- | --- | --- | --- |"]
    ages = {f["source"]: f for f in fresh}
    for s in S.SOURCES:
        src = srcs.get(s) or {}
        mode = src.get("mode", "off")
        res = "not queried" if mode == "off" else cell(src.get("note") or src.get("status", "ok"))
        f = ages.get(s) or {}
        data = ("⚠ " if f.get("stale") else "") + (f.get("note") or (f"read {f['age']} before" if f.get("age") else ""))
        o.append(f"| {s} | {MODE.get(mode, '')} {mode} | {res} | {cell(data)} |")
    o.append("")
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
    return "\n".join(o) + "\n"


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
                links.enrich(r, json.load(cf))
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
