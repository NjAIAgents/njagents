#!/usr/bin/env python3
"""Print the run header for a triage, before any enrichment runs.

The header is produced by code rather than written by the model so its format cannot
drift or be abbreviated. The orchestrator prints this output verbatim as its first
message, then carries on.

Usage:
    python3 scripts/run_header.py BUG-4830 BUG-4844
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
import re
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


TIER = {"config dir": 0, "working folder": 1, "plugin": 2}


def has_placeholder(o):
    if isinstance(o, dict):
        return any(has_placeholder(v) for k, v in o.items() if not str(k).startswith("//"))
    if isinstance(o, list):
        return any(has_placeholder(v) for v in o)
    return isinstance(o, str) and o.startswith("REPLACE_")


def member_of(cfg, email):
    """How specifically team.members names this email: 2 exact address, 1 a domain
    written '*@example.com', 0 not at all. A person listed by name outranks a team
    that claims their whole domain."""
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        return 0
    score = 0
    for m in cfg.get("team", {}).get("members", []) or []:
        m = str(m).strip().lower()
        if m == email:
            return 2
        if m.startswith("*@") and email.endswith(m[1:]):
            score = 1
    return score


def split_targets(teams, words):
    """Separate a bare team id or project key from ticket keys.

    Hosts may pass a command's arguments through their own parser, and a leading
    --team flag has been seen to break the command there. So a plain word works too:
    'demo-live' names a team, 'DEMO' names a project, 'DEMO-7' is a ticket. Returns
    (team_id or None, tickets, projects). Raises ValueError on a word that is none of these.
    """
    team, tickets, projects, unknown = None, [], [], []
    by_project = {}
    for tid, (cfg, _p, _l) in teams.items():
        key = str(cfg.get("tracker", {}).get("project_key", "")).upper()
        if key:
            by_project.setdefault(key, []).append(tid)
    for w in words:
        if w in teams:
            team = w
        elif w.upper() in by_project:
            projects.append(w.upper())
        elif re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*-\d+", w):
            tickets.append(w)
        else:
            unknown.append(w)
    if unknown:
        raise ValueError("No team or project named " + ", ".join(unknown) +
                         ". Known teams: " + ", ".join(sorted(teams)) +
                         (". Projects: " + ", ".join(sorted(by_project)) if by_project else ""))
    return team, tickets, projects


def resolve_team(teams, explicit=None, tickets=(), email=None):
    """Pick a team without making the user name it.

    Returns (team_id, how) on success, or (None, message) when it cannot choose
    safely. Never guesses between two equally good candidates: it asks instead.
    Configs still holding placeholder values are skipped unless named explicitly,
    because they cannot run.
    """
    if explicit:
        return (explicit, "the team named in the command") if explicit in teams else (None, f"No config for team '{explicit}'.")
    env = os.environ.get("CLAUDE_TRIAGE_TEAM")
    if env:
        return (env, "CLAUDE_TRIAGE_TEAM") if env in teams else (None, f"CLAUDE_TRIAGE_TEAM names '{env}', which has no config.")

    usable = {t: v for t, v in teams.items() if not has_placeholder(v[0])}

    def narrow(ids, how):
        ids = sorted(ids)
        if len(ids) == 1:
            return ids[0], how
        if not ids:
            return None, None
        best = min(TIER[teams[t][2]] for t in ids)
        ids = [t for t in ids if TIER[teams[t][2]] == best]
        if len(ids) == 1:
            return ids[0], how
        defaults = [t for t in ids if teams[t][0].get("team", {}).get("default")]
        if len(defaults) == 1:
            return defaults[0], how + ", marked default"
        return None, "ambiguous: " + ", ".join(ids)

    keys = [t for t in tickets if "-" in t]
    if keys:
        projects = {t.rsplit("-", 1)[0].upper() for t in keys}
        if len(projects) > 1:
            return None, ("These tickets span projects " + ", ".join(sorted(projects)) +
                          ". Triage one project per run, or pass --team.")
        proj = projects.pop()
        hits = [t for t, v in usable.items()
                if str(v[0].get("tracker", {}).get("project_key", "")).upper() == proj]
        tid, how = narrow(hits, f"ticket project {proj}")
        if tid:
            return tid, how
        if how:
            return None, f"More than one team configures project {proj} ({how[11:]}). Pass --team."
        return None, (f"No team configures project {proj}. "
                      f"Create one with /bug-triage-agent:triage-config")

    if email:
        scores = {t: member_of(v[0], email) for t, v in usable.items()}
        top = max(scores.values(), default=0)
        if top:
            label = "your email" if top == 2 else "your email domain"
            tid, how = narrow([t for t, s in scores.items() if s == top], label)
            if tid:
                return tid, how
            return None, f"Your email matches several teams ({how[11:]}). Pass --team."

    # The team's own folder outranks anything the plugin ships: a local default, then
    # a lone local config, and only then the plugin's demo default.
    local = [t for t, v in usable.items() if v[2] != "plugin"]
    tid, how = narrow([t for t in local if usable[t][0].get("team", {}).get("default")],
                      "default team in your folder")
    if tid:
        return tid, how
    if how:
        return None, f"Several configs in your folder are marked default ({how[11:]}). Pass --team."
    if len(local) == 1:
        return local[0], "the only team config in your folder"
    if len(local) > 1:
        return None, ("Several team configs in your folder (" + ", ".join(sorted(local)) +
                      "). Pass --team, or mark one with team.default.")

    tid, how = narrow([t for t, v in usable.items() if v[0].get("team", {}).get("default")],
                      "the plugin's default team")
    if tid:
        return tid, how

    return None, "Could not tell which team. Pass --team, or mark one config with team.default."


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
    ap.add_argument("--team", help="optional; resolved from the tickets, your email, or a default")
    ap.add_argument("--user-email", help="signed-in user's email, matched against team.members; "
                                         "used locally for matching only, never stored or printed")
    ap.add_argument("--config-dir")
    ap.add_argument("--workdir", help="the user's folder; default the current directory")
    ap.add_argument("--where", action="store_true",
                    help="print only the resolved config path")
    ap.add_argument("--format", choices=["text", "md"], default="text",
                    help="md for chat (tables and colour markers), text for terminals")
    ap.add_argument("tickets", nargs="*")
    a = ap.parse_args()

    teams = load_teams(a.config_dir, a.workdir)
    try:
        word_team, a.tickets, projects = split_targets(teams, a.tickets)
    except ValueError as e:
        print(e)
        return 2
    a.team = a.team or word_team
    tid, how = resolve_team(teams, a.team, a.tickets + [f"{p}-0" for p in projects],
                            a.user_email or os.environ.get("CLAUDE_TRIAGE_USER_EMAIL"))
    if tid is None:
        print(how)
        print("Looked in: " + " → ".join(d for _, d in search_dirs(a.config_dir, a.workdir)))
        if teams:
            print("Available: " + ", ".join(
                f"{t} ({teams[t][2]}, project {teams[t][0].get('tracker', {}).get('project_key', '?')})"
                for t in sorted(teams)))
        print("Create one with: /bug-triage-agent:triage-config" + (f" {a.team}" if a.team else ""))
        return 2
    a.team = tid
    a.how = how
    cfg, cfg_path, origin = teams[tid]

    if a.where:
        print(cfg_path)
        return 0
    if not a.tickets:
        print("No tickets given.")
        return 2

    srcs = cfg.get("sources", {})
    modes = {s: srcs.get(s, {}).get("mode", "off") for s in SOURCES}
    available = sum(1 for m in modes.values() if m != "off")
    reasons = {s: reason(cfg, s) for s in SOURCES}

    missing = []
    if modes["tracker"] == "fixture":
        fdir = fixture_root(cfg_path, srcs["tracker"].get("fixture", ""))
        missing = [t for t in a.tickets
                   if not os.path.exists(os.path.join(fdir, f"{t}.json"))]

    label = a.tickets[0] if len(a.tickets) == 1 else f"{len(a.tickets)} tickets"
    render = markdown if a.format == "md" else plain
    print(render(a, label, modes, reasons, available, cfg_path, origin, missing))
    return 3 if missing else 0


def plugin_copy_note(a, modes, origin):
    """A live team read from the plugin's shipped copy usually means the user's folder,
    which holds their own copy, is not the one this session is working in. Seen in a
    real run: the doctor probed the plugin's demo-live while the edited one sat unread."""
    if origin != "plugin" or not any(m == "live" for m in modes.values()):
        return None
    return (f"Using the plugin's shipped `{a.team}` config, not one from your folder. "
            f"If you have your own `triage-teams/{a.team}.json`, this session's working "
            "folder is not the one that holds it: connect that folder and run again.")


def plain(a, label, modes, reasons, available, cfg_path, origin, missing):
    lines = [f"Bug triage · {label} · team {a.team}", ""]
    for s in SOURCES:
        lines.append(f"  {s:<11} {modes[s]:<9} {reasons[s]}")
    lines += ["", f"  {available} of {len(SOURCES)} sources available. {PRINCIPLE}"]
    lines += [f"  Team:   {a.team} (chosen by {a.how})",
              f"  Config: {cfg_path} ({origin})",
              f"  Agent:  {plugin_version()} · {ROOT}"]
    if len(a.tickets) > 1:
        lines += ["", "  Tickets: " + ", ".join(a.tickets)]
    note = plugin_copy_note(a, modes, origin)
    if note:
        lines += ["", "  ! " + note.replace("`", "")]
    if missing:
        lines += ["", "  No tracker fixture for: " + ", ".join(missing),
                  "  Those tickets cannot be triaged in fixture mode."]
    return "\n".join(lines)


# Same vocabulary as reference/output-templates.md, so a colour means the same thing
# in the header, the stage lines, the report and the trace.
MODE_MARK = {"live": "🟢", "fixture": "🟡", "off": "⚫"}


def short(path):
    parts = os.path.normpath(path).split(os.sep)
    return path if len(parts) <= 3 else "…/" + "/".join(parts[-2:])


def markdown(a, label, modes, reasons, available, cfg_path, origin, missing):
    """For chat. Printed as markdown, never inside a code block: a code block is
    monospace with no colour, which is exactly what this format exists to avoid."""
    lines = [f"**Bug triage · {label} · team `{a.team}`**", "",
             "| Source | Mode | |", "| --- | --- | --- |"]
    for s in SOURCES:
        broken = modes[s] == "live" and reasons[s].startswith("live, but")
        mark = "🔴" if broken else MODE_MARK.get(modes[s], "")
        lines.append(f"| {s} | {mark} {modes[s]} | {reasons[s].replace('|', '/')} |")
    lines += ["",
              f"> **{available} of {len(SOURCES)} sources available.** {PRINCIPLE}",
              f"> Team **{a.team}**, chosen by {a.how} · Config: `{short(cfg_path)}` ({origin})"
              f" · Agent **{plugin_version()}**"]
    if len(a.tickets) > 1:
        lines += ["", "Tickets: " + ", ".join(f"`{t}`" for t in a.tickets)]
    if any(m == "fixture" for m in modes.values()):
        fx = [s for s in SOURCES if modes[s] == "fixture"]
        lines += ["", "> [!WARNING]",
                  f"> **Demo data.** {', '.join(fx)} on fixtures. Not live figures."]
    note = plugin_copy_note(a, modes, origin)
    if note:
        lines += ["", "> [!WARNING]", "> " + note]
    if missing:
        lines += ["", f"> [!CAUTION]", f"> No tracker fixture for {', '.join(missing)}. "
                  "Those tickets cannot be triaged in fixture mode."]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
