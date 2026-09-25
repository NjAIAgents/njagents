#!/usr/bin/env python3
"""The handoff index: which fix briefs a fix agent may pick up now, and why the rest wait.

Triage writes one fix brief per defect. A fix pipeline needs one place to look, and must
not pick up a brief a person has to decide on first, or one whose fix already exists.

    python3 scripts/brief_index.py --reports <reports_dir> [--team-config <config>] \\
        [--log <triage-log.jsonl>]

writes <reports_dir>/briefs.json:

    {"generated_at", "team",
     "ready": [{"ticket", "priority", "fix_due", "brief", "branch", "fault", "evidence",
                "next_action", "ticket_url"}],
     "held":  [{"ticket", "priority", "brief", "reason", "detail"}]}

`ready` is ordered for pickup: priority, then the earliest fix-by date, then the ticket.
A brief is held, with its reason, when:
    human_review     the team holds this risk for a person and no one has reviewed it since
    already_fixed    a fix is merged, released or deployed; confirm and close, do not refix
    locate_first     the location evidence is weak; find the cause before fixing
    no_brief         the result is a defect but its brief file is missing

Only defects appear, and with --team-config only that team's. The newest result per ticket wins (history/ is ignored). Nothing
is written anywhere else, and nothing is sent to a fix agent: this is the list it reads.
"""
import argparse, glob, json, os, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import human_gate as HG  # noqa: E402
import fix_status as FX  # noqa: E402
import next_action as NA  # noqa: E402
import links  # noqa: E402

ORDER = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}


def reviewed_after(log_path, ticket, since):
    """True when the audit log has a human override for the ticket at or after `since`."""
    if not log_path or not os.path.exists(log_path):
        return False
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("ticket") == ticket and rec.get("human_override") and (rec.get("ts") or "") >= (since or ""):
                return True
    return False


def entry(r, reports, log_path):
    """(bucket, row) for one defect result."""
    from render_fix_brief import assess, slug
    t = r["ticket"]
    brief = f"{t}.fix-brief.md"
    base = {"ticket": t, "priority": r.get("priority"), "brief": brief}
    if not os.path.exists(os.path.join(reports, brief)):
        return "held", dict(base, reason="no_brief", detail="the result is a defect but its fix brief was not written")
    if FX.is_fixed(r):
        return "held", dict(base, reason="already_fixed", detail=FX.headline(r))
    if HG.required(r) and not reviewed_after(log_path, t, r.get("triaged_at")):
        who = ", ".join((r.get("human_review") or {}).get("reviewers") or []) or "any person"
        return "held", dict(base, reason="human_review", detail=f"waiting for a decision by {who}")
    ev = assess(r)["level"]
    if NA.get(r)["action"] == "locate_first":
        return "held", dict(base, reason="locate_first", detail=f"location evidence is {ev}; confirm the cause first")
    fault = next((l for l in r.get("locations") or [] if l.get("path") and l.get("line")
                  and l.get("signal") not in ("release_touched", None)), None)
    return "ready", dict(base, fix_due=(r.get("sla") or {}).get("due"),
                         branch=f"fix/{t.lower()}-{slug(r.get('summary'))}",
                         fault={"file": fault["path"], "line": fault["line"], "url": fault.get("url")} if fault else None,
                         evidence=ev, next_action=NA.get(r)["action"], ticket_url=r.get("ticket_url"))


def build(reports, cfg=None, log_path=None, now=None):
    import sla as SL
    team = ((cfg or {}).get("team") or {}).get("id")
    newest = {}
    for p in glob.glob(os.path.join(reports, "*.result.json")):
        try:
            r = json.load(open(p, encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if r.get("disposition") != "defect" or not r.get("ticket"):
            continue
        if team and r.get("team") != team:   # a reports folder can hold more than one team
            continue
        if r["ticket"] not in newest or (r.get("triaged_at") or "") > (newest[r["ticket"]].get("triaged_at") or ""):
            newest[r["ticket"]] = r
    out = {"generated_at": (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "team": team or next((r.get("team") for r in newest.values()), None),
           "ready": [], "held": []}
    for r in newest.values():
        if cfg:
            links.enrich(r, cfg)
            HG.fill(r, cfg)
            SL.fill(r, cfg)
        bucket, row = entry(r, reports, log_path)
        out[bucket].append(row)
    key = lambda x: (ORDER.get(x.get("priority"), 9), x.get("fix_due") or "9999", x["ticket"])
    out["ready"].sort(key=key)
    out["held"].sort(key=key)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reports", required=True, help="the team's reports_dir")
    ap.add_argument("--team-config")
    ap.add_argument("--log", help="audit log, to see whether a held ticket was reviewed")
    a = ap.parse_args()
    cfg = json.load(open(a.team_config, encoding="utf-8")) if a.team_config else None
    idx = build(a.reports, cfg, a.log)
    dest = os.path.join(a.reports, "briefs.json")
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(idx, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"wrote {dest}: {len(idx['ready'])} ready, {len(idx['held'])} held"
          + "".join(f"\n  held {h['ticket']}: {h['reason']}" for h in idx["held"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
