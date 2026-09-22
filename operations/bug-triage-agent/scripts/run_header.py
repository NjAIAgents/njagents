#!/usr/bin/env python3
"""Print the run header for a triage, before any enrichment runs.

The header is produced by code rather than written by the model so its format cannot
drift or be abbreviated. The orchestrator prints this output verbatim as its first
message, then carries on.

Usage:
    python3 scripts/run_header.py --team demo BUG-4830 BUG-4844
    python3 scripts/run_header.py --team demo-live DEMO-7
    python3 scripts/run_header.py --team payments --where     # resolved path only

Team configs are looked up in this order, first match on team.id wins:
    1. --config-dir, else $CLAUDE_TRIAGE_CONFIG_DIR, else $CLAUDE_PLUGIN_OPTION_CONFIG_DIR
    2. ./triage-teams/ in the working directory
    3. teams/ shipped inside the plugin (demos and examples)

A team's own config belongs in 1 or 2, in the team's repository. The plugin's copy is
read-only once installed and is overwritten on every update.

Exit codes:
    0  header printed
    2  team not found (available ids and where they came from are listed)
    3  a ticket has no fixture while the tracker is in fixture mode
"""
import argparse, glob, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES = ["tracker", "releases", "metrics", "warehouse", "code"]
SKIP = {"team-config.schema.json", "team-config.example.json"}
PRINCIPLE = ("Absent sources lower confidence and drop escalations. "
             "They never raise severity.")


def plugin_version():
    for rel in (".claude-plugin/plugin.json", "plugin.json"):
        try:
            with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
                return json.load(f).get("version", "?")
        except (OSError, json.JSONDecodeError):
            continue
    return "?"


def search_dirs(config_dir=None, workdir=None):
    """Ordered (label, directory) pairs. Earlier wins.

    A sandboxed shell often starts somewhere other than the user's folder (Cowork
    mounts it one or two levels below the shell's home), so besides <workdir>/
    triage-teams we also look one and two levels below it, in sorted order.
    """
    explicit = (config_dir or os.environ.get("CLAUDE_TRIAGE_CONFIG_DIR")
                or os.environ.get("CLAUDE_PLUGIN_OPTION_CONFIG_DIR"))
    wd = os.path.abspath(os.path.expanduser(workdir or os.getcwd()))
    dirs = []
    if explicit:
        dirs.append(("config dir", os.path.abspath(os.path.expanduser(explicit))))
    dirs.append(("working folder", os.path.join(wd, "triage-teams")))
    plugin_teams = os.path.realpath(os.path.join(ROOT, "teams"))
    for pattern in ("*/triage-teams", "*/*/triage-teams"):
        for d in sorted(glob.glob(os.path.join(wd, pattern))):
            if os.path.realpath(d).startswith(os.path.realpath(ROOT)):
                continue
            dirs.append(("working folder", d))
    dirs.append(("plugin", plugin_teams))
    return dirs


def load_teams(config_dir=None, workdir=None):
    """team id -> (config, path, origin label). First directory to define an id wins."""
    teams = {}
    for label, d in search_dirs(config_dir, workdir):
        for path in sorted(glob.glob(os.path.join(d, "*.json"))):
            if os.path.basename(path) in SKIP:
                continue
            try:
                with open(path, encoding="utf-8") as f:
                    cfg = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            tid = cfg.get("team", {}).get("id")
            if tid and tid not in teams:
                teams[tid] = (cfg, path, label)
    return teams


def fixture_root(cfg_path, rel):
    """A fixture path resolves beside the team's config first, then in the plugin."""
    beside = os.path.join(os.path.dirname(cfg_path), rel)
    return beside if os.path.exists(beside) else os.path.join(ROOT, rel)


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
    bound = cfg.get("tool_bindings", {}).get(source) or {}
    if not bound:
        return "live, but no tool_bindings entry"
    unfilled = [k for k, v in bound.items() if not v or str(v).startswith("REPLACE_")]
    if unfilled:
        return f"live, but bindings not filled: {', '.join(unfilled)}"
    return "bound"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", required=True)
    ap.add_argument("--config-dir")
    ap.add_argument("--workdir", help="the user's folder; default the current directory")
    ap.add_argument("--where", action="store_true",
                    help="print only the resolved config path")
    ap.add_argument("tickets", nargs="*")
    a = ap.parse_args()

    teams = load_teams(a.config_dir, a.workdir)
    hit = teams.get(a.team)
    if hit is None:
        print(f"No config for team '{a.team}'.")
        print("Looked in: " + " → ".join(d for _, d in search_dirs(a.config_dir, a.workdir)))
        if teams:
            print("Available: " + ", ".join(f"{t} ({teams[t][2]})" for t in sorted(teams)))
        print(f"Create one with: /bug-triage-agent:triage-config {a.team}")
        return 2
    cfg, cfg_path, origin = hit

    if a.where:
        print(cfg_path)
        return 0
    if not a.tickets:
        print("No tickets given.")
        return 2

    srcs = cfg.get("sources", {})
    modes = {s: srcs.get(s, {}).get("mode", "off") for s in SOURCES}
    available = sum(1 for m in modes.values() if m != "off")

    label = a.tickets[0] if len(a.tickets) == 1 else f"{len(a.tickets)} tickets"
    lines = [f"Bug triage · {label} · team {a.team}", ""]
    for s in SOURCES:
        lines.append(f"  {s:<11} {modes[s]:<9} {reason(cfg, s)}")
    lines += ["", f"  {available} of {len(SOURCES)} sources available. {PRINCIPLE}"]
    lines += [f"  Config: {cfg_path} ({origin})",
              f"  Agent:  {plugin_version()} · {ROOT}"]

    if len(a.tickets) > 1:
        lines += ["", "  Tickets: " + ", ".join(a.tickets)]

    missing = []
    if modes["tracker"] == "fixture":
        fdir = fixture_root(cfg_path, srcs["tracker"].get("fixture", ""))
        missing = [t for t in a.tickets
                   if not os.path.exists(os.path.join(fdir, f"{t}.json"))]
        if missing:
            lines += ["", "  No tracker fixture for: " + ", ".join(missing),
                      "  Those tickets cannot be triaged in fixture mode."]

    print("\n".join(lines))
    return 3 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
