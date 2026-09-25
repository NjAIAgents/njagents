#!/usr/bin/env python3
"""Group the defects of a batch that probably share a cause, so one fix can close several.

Triage looks at one ticket at a time. Across a batch, several tickets often point at the
same file, or started with the same release in the same area. Fixing them one by one
means several engineers reading the same code. This script groups them, from evidence
already in the result files, and says how strong each grouping is.

    python3 scripts/clusters.py --out triage-reports [--tracker-dir <dir>] [--annotate] \\
        triage-reports/*.result.json

writes <out>/batch-<date>.md (the ranked batch table, then the groups) and
<out>/clusters.json. With --annotate it also adds `clusters` to each member's result
file, so its report says which group it belongs to.

How tickets are grouped, defects only:
    file      two or more tickets locate the same file. EVIDENCE SUPPORTED when at least two
              of them have evidence at that file (a fault signal, a release or prior fix
              that changed it, or a merged fix); PROPOSED when it is only a candidate path.
    release   two or more tickets correlate with the same release in the same area, with
              high or medium confidence. Always PROPOSED: timing is not a cause.

A group never raises anyone's priority. Its priority is the highest of its members.
"""
import argparse, glob, json, os, re, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import links  # noqa: E402

EVIDENCE_SIGNALS = {"error_swallowing", "stub", "suppressed_type_error", "release_touched", "prior_fix_file"}
ORDER = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}
PRIO = {"P1": "🔴", "P2": "🟠", "P3": "🟡", "P4": "🔵"}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def component(r, tracker_dir):
    if r.get("component"):
        return r["component"]
    if tracker_dir:
        fp = os.path.join(tracker_dir, f"{r['ticket']}.json")
        if os.path.exists(fp):
            t = json.load(open(fp, encoding="utf-8")).get("data", {}).get("ticket", {})
            return t.get("component")
    return None


def build(results, tracker_dir=None):
    defects = [r for r in results if r.get("disposition") == "defect"]
    by_file, by_rel = {}, {}
    for r in defects:
        comp = component(r, tracker_dir)
        r["_component"] = comp
        fix_files = set((((r.get("fix_status") or {}).get("commit") or {}).get("files")) or []) \
            if (r.get("fix_status") or {}).get("confidence") == "strong" else set()
        for l in r.get("locations") or []:
            p = l.get("path")
            if not p:
                continue
            e = by_file.setdefault(p, {})
            strong = l.get("signal") in EVIDENCE_SIGNALS or p in fix_files
            e[r["ticket"]] = e.get(r["ticket"], False) or strong
        rel = (r.get("introduced_by") or {}).get("release") or \
            ((r.get("release") or {}).get("version") if (r.get("release") or {}).get("confidence") in ("high", "medium") else None)
        if rel and comp:
            by_rel.setdefault((rel, comp), set()).add(r["ticket"])

    res = {r["ticket"]: r for r in defects}
    clusters = []
    for path, members in by_file.items():
        if len(members) < 2:
            continue
        supported = sum(1 for v in members.values() if v) >= 2
        clusters.append(_cluster("file", path, sorted(members), res, supported,
                                 f"{len(members)} tickets locate {path.rsplit('/', 1)[-1]}"
                                 + ("; at least two have evidence there" if supported else "; only as a candidate path")))
    for (rel, comp), members in by_rel.items():
        if len(members) < 2:
            continue
        if any(set(members) <= set(c["tickets"]) for c in clusters):
            continue   # already grouped more precisely by file
        clusters.append(_cluster("release", f"{rel} · {comp}", sorted(members), res, False,
                                 f"{len(members)} tickets correlate with {rel} in {comp}"))
    clusters.sort(key=lambda c: (c["status"] != "EVIDENCE_SUPPORTED", ORDER.get(c["priority"], 9), -len(c["tickets"])))
    return clusters


def _cluster(basis, key, members, res, supported, why):
    rs = [res[m] for m in members]
    prio = min((r.get("priority") for r in rs if r.get("priority")), key=lambda p: ORDER.get(p, 9), default=None)
    comps = sorted({r.get("_component") for r in rs if r.get("_component")})
    cause = next((r["hypothesis"]["statement"] for r in sorted(rs, key=lambda r: ORDER.get(r.get("priority"), 9))
                  if (r.get("hypothesis") or {}).get("statement")), None)
    notes = []
    if len(comps) > 1:
        notes.append("members span components: " + ", ".join(comps))
    for r in rs:
        fs = r.get("fix_status") or {}
        if fs.get("state") not in (None, "open") and fs.get("confidence") in ("strong", "moderate"):
            c = fs.get("commit") or {}
            notes.append(f"{r['ticket']} is already fixed by {c.get('pr') or c.get('sha', '')[:10]}: "
                         "check whether that fix also covers the others")
    routes = sorted({r.get("route") for r in rs if r.get("route")})
    return {"id": f"cl-{basis}-{slug(key)}", "basis": basis, "key": key, "why": why,
            "status": "EVIDENCE_SUPPORTED" if supported else "PROPOSED",
            "tickets": members, "priority": prio, "components": comps, "likely_shared_cause": cause,
            "notes": notes, "owner": routes[0] if len(routes) == 1 else None,
            "next": (("Investigate together; one fix may close both." if len(members) == 2 else
                      f"Investigate together; one fix may close all {len(members)}.")
                     if supported else "Check whether these share a cause before splitting the work.")}


# ------------------------------------------------------------------ rendering

def md_batch(results, clusters, cfg=None):
    now = datetime.now(timezone.utc)
    defects = sorted([r for r in results if r.get("disposition") == "defect"],
                     key=lambda r: (ORDER.get(r.get("priority"), 9), r["ticket"]))
    others = [r for r in results if r.get("disposition") != "defect"]
    member, label = {}, {}
    for i, c in enumerate(clusters, 1):
        label[c["id"]] = f"G{i}"
        for t in c["tickets"]:
            member.setdefault(t, []).append(c)
    o = [f"# Batch triage · {len(results)} tickets · {now:%Y-%m-%d %H:%M} UTC", ""]
    if any(s.get("mode") == "fixture" for r in results for s in (r.get("sources") or {}).values()):
        o += links.callout("warning", "**Demo data.** Some sources are recorded fixtures.") + [""]
    sup = [c for c in clusters if c["status"] == "EVIDENCE_SUPPORTED"]
    o += [f"{len(defects)} defect(s), {len(others)} other disposition(s), "
          f"{len(clusters)} group(s) ({len(sup)} supported by evidence).", ""]
    if defects:
        import effort as EF
        import risks as RK
        import next_action as NA
        o += ["## Defects, ranked", "", "| Ticket | Priority | Summary | Next action | Risks | Complexity | Group |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
        for r in defects:
            g = ", ".join(f"{label[c['id']]} · {c['key'].rsplit('/', 1)[-1]}" for c in member.get(r["ticket"], [])) or "—"
            import sla as SL
            due = f" · {SL.short(r)}" if SL.short(r) else ""
            o.append(f"| {links.md(r['ticket'], r.get('ticket_url'))} | {PRIO.get(r.get('priority'), '')} {r.get('priority')}{due} "
                     f"| {links.short(r.get('summary'), 70).replace('|', '/')} | {NA.short(r)} | {RK.icons(r)} | {EF.short(r)} | {g} |")
        o.append("")
        o += legend(defects, bool(clusters))
    if clusters:
        o += ["## Groups", ""]
        for c in clusters:
            badge = "🔗 supported by evidence" if c["status"] == "EVIDENCE_SUPPORTED" else "❔ proposed"
            short = c["key"].rsplit("/", 1)[-1] if c["basis"] == "file" else c["key"]
            o += [f"### {label[c['id']]} · {short} · {badge}", ""]
            if c["basis"] == "file":
                o += [f"**File:** `{c['key']}`", ""]
            o += [
                  f"**Tickets:** {', '.join(c['tickets'])} · **Priority:** {PRIO.get(c['priority'], '')} {c['priority']} "
                  "(highest member; a group never raises it)" + (f" · **Owner:** {c['owner']}" if c.get("owner") else ""), "",
                  f"**Why grouped:** {c['why']}.", ""]
            if c.get("likely_shared_cause"):
                o += [f"**Likely shared cause:** {c['likely_shared_cause']}", ""]
            for n in c["notes"]:
                o += links.callout("important", n[:1].upper() + n[1:] + ".") + [""]
            o += [f"**Next:** {c['next']}", ""]
    else:
        o += ["No two defects share a located file or a release and area.", ""]
    if others:
        import next_action as NA
        o += ["## Not defects", "", "| Ticket | Disposition | Next action | Route |", "| --- | --- | --- | --- |"]
        o += [f"| {links.md(r['ticket'], r.get('ticket_url'))} | `{r.get('disposition')}` | {NA.short(r)} "
              f"| {(NA.clean_route(r.get('route')) or '—').replace('|', '/')} |" for r in others]
        o.append("")
    o += links.callout("note", "Groups are suggestions from the evidence in each result. Nothing has been linked "
                       "or written in the tracker.")
    return "\n".join(o) + "\n"


def legend(defects, grouped=False):
    """One line naming the risk icons used in the batch table."""
    import risks as RK
    used = [t for t in RK.TYPES if any(x["type"] == t for r in defects for x in RK.get(r))]
    return [f"*Risks:* " + " · ".join(f"{RK.ICON[t]} {RK.LABEL[t]}" for t in used), ""] if used else []


def md_membership(r):
    cs = r.get("clusters") or []
    if not cs:
        return []
    o = []
    for c in cs:
        kind = "supported by evidence" if c.get("status") == "EVIDENCE_SUPPORTED" else "proposed"
        others = [t for t in c.get("tickets", []) if t != r.get("ticket")]
        o += links.callout("note", f"**Part of a group ({kind}):** {c.get('why')}. Also in it: {', '.join(others)}. "
                           f"{c.get('next', '')}")
    return o + [""]


def validate(r):
    p = []
    for i, c in enumerate(r.get("clusters") or []):
        if c.get("status") not in ("EVIDENCE_SUPPORTED", "PROPOSED"):
            p.append(f"clusters[{i}].status must be EVIDENCE_SUPPORTED or PROPOSED")
        if r.get("ticket") not in (c.get("tickets") or []):
            p.append(f"clusters[{i}] does not list this ticket among its members")
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tracker-dir", help="tracker envelopes, to read each ticket's component")
    ap.add_argument("--team-config", help="fills ticket links")
    ap.add_argument("--annotate", action="store_true", help="add `clusters` to each member's result file")
    ap.add_argument("--markdown", action="store_true", help="also write batch-<date>.md")
    a = ap.parse_args()
    paths = [p for g in a.results for p in glob.glob(g)] or a.results
    results = [json.load(open(p, encoding="utf-8")) for p in paths]
    cfg = None
    if a.team_config:
        cfg = json.load(open(a.team_config, encoding="utf-8"))
        import risks as RK
        for r in results:
            links.enrich(r, cfg)
            RK.fill(r, cfg)
            import sla as SL
            SL.fill(r, cfg)
    clusters = build(results, a.tracker_dir)
    for r in results:   # so the batch table sizes each fix with its group, as the reports will
        mine = [c for c in clusters if r["ticket"] in c["tickets"]]
        if mine:
            r["clusters"] = mine
    os.makedirs(a.out, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M")
    with open(os.path.join(a.out, "clusters.json"), "w", encoding="utf-8") as f:
        json.dump(clusters, f, indent=2, ensure_ascii=False)
    # The batch page follows the team's report_format: HTML by default, markdown on
    # request, and in agent mode only clusters.json (no page for people).
    fmt = ((cfg or {}).get("output") or {}).get("report_format") or "html"
    written = [os.path.join(a.out, "clusters.json")]
    if fmt in ("html", "both"):
        import pages_html as P
        dest = os.path.join(a.out, f"batch-{stamp}.html")
        with open(dest, "w", encoding="utf-8") as f:
            f.write(P.batch(results, clusters, cfg))
        written.append(dest)
    if fmt in ("md", "both") or a.markdown:
        dest = os.path.join(a.out, f"batch-{stamp}.md")
        with open(dest, "w", encoding="utf-8") as f:
            f.write(md_batch(results, clusters))
        written.append(dest)
    dest = " and ".join(written)
    if a.annotate:
        for p, r in zip(paths, results):
            mine = [{k: c[k] for k in ("id", "basis", "key", "status", "why", "tickets", "next")}
                    for c in clusters if r["ticket"] in c["tickets"]]
            raw = json.load(open(p, encoding="utf-8"))
            if mine:
                raw["clusters"] = mine
            else:
                raw.pop("clusters", None)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(raw, f, indent=2, ensure_ascii=False)
                f.write("\n")
    print(f"wrote {dest} ({len(clusters)} group(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
