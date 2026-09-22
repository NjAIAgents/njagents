#!/usr/bin/env python3
"""Print the run header for a triage, before any enrichment runs.

The header is produced by code rather than written by the model so its format cannot
drift or be abbreviated. The orchestrator prints this output verbatim as its first
message, then carries on.

Usage:
    python3 scripts/run_header.py --team demo BUG-4830 BUG-4844
    python3 scripts/run_header.py --team demo-live DEMO-7

Exit codes:
    0  header printed
    2  team not found (available ids are listed)
    3  a ticket has no fixture while the tracker is in fixture mode
"""
import argparse, glob, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES = ["tracker", "releases", "metrics", "warehouse", "code"]
SKIP = {"team-config.schema.json", "team-config.example.json"}
PRINCIPLE = ("Absent sources lower confidence and drop escalations. "
             "They never raise severity.")


def load_teams():
    teams = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "teams", "*.json"))):
        if os.path.basename(path) in SKIP:
            continue
        try:
            with open(path) as f:
                cfg = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        tid = cfg.get("team", {}).get("id")
        if tid:
            teams[tid] = cfg
    return teams


def first_sentence(text):
    text = (text or "").strip()
    for stop in (". ", ".\n"):
        if stop in text:
            return text.split(stop, 1)[0]
    return text.rstrip(".")


def reason(cfg, source):
    spec = cfg.get("sources", {}).get(source, {})
    mode = spec.get("mode", "off")
    if mode == "fixture":
        return spec.get("fixture", "fixture")
    if mode == "off":
        return first_sentence(spec.get("//")) or "not configured"
    # live
    if source == "tracker":
        return f"project {cfg.get('tracker', {}).get('project_key', '?')}"
    if source == "releases":
        adapters = cfg.get("release_correlation", {}).get("manifest_sources", [])
        return ", ".join(adapters) if adapters else "live"
    bound = cfg.get("tool_bindings", {}).get(source)
    return "bound" if bound else "live, but no tool_bindings entry"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", required=True)
    ap.add_argument("tickets", nargs="+")
    a = ap.parse_args()

    teams = load_teams()
    cfg = teams.get(a.team)
    if cfg is None:
        print(f"No team with id '{a.team}'. Available: {', '.join(sorted(teams))}")
        return 2

    srcs = cfg.get("sources", {})
    modes = {s: srcs.get(s, {}).get("mode", "off") for s in SOURCES}
    available = sum(1 for m in modes.values() if m != "off")

    label = a.tickets[0] if len(a.tickets) == 1 else f"{len(a.tickets)} tickets"
    lines = [f"Bug triage · {label} · team {a.team}", ""]
    for s in SOURCES:
        lines.append(f"  {s:<11} {modes[s]:<9} {reason(cfg, s)}")
    lines += ["", f"  {available} of {len(SOURCES)} sources available. {PRINCIPLE}"]

    if len(a.tickets) > 1:
        lines += ["", "  Tickets: " + ", ".join(a.tickets)]

    missing = []
    if modes["tracker"] == "fixture":
        fdir = os.path.join(ROOT, srcs["tracker"].get("fixture", ""))
        missing = [t for t in a.tickets
                   if not os.path.exists(os.path.join(fdir, f"{t}.json"))]
        if missing:
            lines += ["", "  No tracker fixture for: " + ", ".join(missing),
                      "  Those tickets cannot be triaged in fixture mode."]

    print("\n".join(lines))
    return 3 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
