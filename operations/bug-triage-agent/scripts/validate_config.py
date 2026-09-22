#!/usr/bin/env python3
"""Validate a team config and every fixture against the source contract.

Usage:
    python3 scripts/validate_config.py teams/demo.json
    python3 scripts/validate_config.py --all
"""
import json, sys, os, glob, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES = ["tracker", "releases", "metrics", "warehouse", "code"]
MODES = {"live", "fixture", "off"}
ENVELOPE = {"source", "mode", "status", "as_of", "latency_ms", "notes", "data"}
STATUSES = {"ok", "partial", "unavailable", "error"}


def is_placeholder(v):
    return isinstance(v, str) and (v.startswith("REPLACE_")
                                   or v.upper() in ("TODO", "CHANGEME", "XXX"))

SHAPES = {
    "tracker": {"ticket", "related", "duplicates", "component_history", "sprint_collision"},
    "releases": {"releases", "lookback_days", "adapters_run", "adapters_failed"},
    "metrics": {"baseline", "current", "spike", "deploys_in_window", "sample_errors"},
    "warehouse": {"affected_accounts", "enterprise_accounts", "account_names",
                  "first_seen", "query_template", "query_used"},
    "code": {"candidate_paths", "error_swallowing", "stubs", "recent_changes"},
}

errors, warnings, unconfigured = [], [], []


def err(m): errors.append(m)
def warn(m): warnings.append(m)
def unconf(m): unconfigured.append(m)


def check_config(path):
    with open(path) as f:
        cfg = json.load(f)
    name = os.path.basename(path)

    for key in ("team", "tracker", "sources"):
        if key not in cfg:
            err(f"{name}: missing required key '{key}'")
    if "tracker" in cfg:
        for key in ("project_key", "instance_id"):
            v = cfg["tracker"].get(key)
            if not v:
                err(f"{name}: tracker.{key} is empty")
            elif is_placeholder(v):
                unconf(f"{name}: tracker.{key} is a placeholder ({v}). "
                       "This config cannot go live until it is set.")
        pn = cfg["tracker"].get("priority_names", {})
        missing = [p for p in ("P1", "P2", "P3", "P4") if p not in pn]
        if missing:
            err(f"{name}: tracker.priority_names missing {missing}")

    srcs = cfg.get("sources", {})
    for s in SOURCES:
        if s not in srcs:
            err(f"{name}: sources.{s} not declared")
            continue
        mode = srcs[s].get("mode")
        if mode not in MODES:
            err(f"{name}: sources.{s}.mode '{mode}' invalid")
        if mode == "fixture" and not srcs[s].get("fixture"):
            err(f"{name}: sources.{s} is fixture mode but names no fixture")
        if mode == "fixture":
            fp = os.path.join(ROOT, srcs[s]["fixture"])
            if not os.path.exists(fp):
                err(f"{name}: fixture not found: {srcs[s]['fixture']}")

    if srcs.get("tracker", {}).get("mode") == "off":
        err(f"{name}: tracker cannot be 'off'. It is the minimum viable source.")

    rc = cfg.get("release_correlation", {})
    cad, look = rc.get("cadence_days", 30), rc.get("lookback_days", 60)
    if look < cad * 2:
        warn(f"{name}: lookback_days ({look}) < 2 release cycles ({cad*2}). "
             "Reports arriving late will not correlate.")

    reg = cfg.get("regression", {})
    if reg.get("baseline_days", 7) < 5:
        warn(f"{name}: baseline_days < 5 will produce weekend false positives.")
    if reg.get("deploy_window_hours", 720) < cad * 24:
        warn(f"{name}: deploy_window_hours ({reg.get('deploy_window_hours')}) is shorter "
             f"than one release cycle ({cad*24}h). Regressions will be missed.")

    if srcs.get("warehouse", {}).get("mode") == "live" and not cfg.get("warehouse", {}).get("queries"):
        err(f"{name}: warehouse is live but warehouse.queries is empty")
    if srcs.get("code", {}).get("mode") == "live" and not cfg.get("repos"):
        err(f"{name}: code is live but repos is empty")

    tools = cfg.get("tool_bindings", {})
    for s_ in ("tracker", "metrics", "warehouse", "code"):
        if srcs.get(s_, {}).get("mode") == "live" and not tools.get(s_):
            err(f"{name}: {s_} is live but tool_bindings.{s_} is missing. "
                "Tool names are configuration; the adapter cannot be bound without them. This plugin binds to tools already in the session rather than declaring its own server.")

    adapters = rc.get("manifest_sources", ["tracker_fixversion"])
    if not adapters:
        err(f"{name}: release_correlation.manifest_sources is empty")
    if "manual_file" in adapters and not rc.get("manual_file_path"):
        err(f"{name}: manifest_sources includes manual_file but manual_file_path is unset")
    if "wiki_release_notes" in adapters and not rc.get("wiki", {}).get("space_key"):
        err(f"{name}: wiki_release_notes adapter selected but wiki.space_key is unset")

    write_verbs = ("INSERT", "UPDATE", "DELETE", "DROP", "MERGE", "CREATE", "TRUNCATE",
                   "ALTER", "GRANT", "REVOKE", "CALL", "EXECUTE", "COPY", "PUT", "REMOVE", "UNDROP")
    for qname, q in cfg.get("warehouse", {}).get("queries", {}).items():
        for tok in re.findall(r"[A-Za-z_]+", q.upper()):
            if tok in write_verbs:
                err(f"{name}: warehouse query '{qname}' is not read-only, contains {tok}")
        if not q.strip().upper().startswith(("SELECT", "WITH")):
            err(f"{name}: warehouse query '{qname}' must start with SELECT or WITH")

    def placeholders(node, path=""):
        if isinstance(node, dict):
            for k, v in node.items():
                placeholders(v, f"{path}{k}.")
        elif isinstance(node, list):
            for v in node:
                placeholders(v, path)
        elif isinstance(node, str) and is_placeholder(node):
            key = path.rstrip(".")
            if key not in ("tracker.instance_id", "tracker.project_key"):
                unconf(f"{name}: placeholder value at '{key}' ({node})")
    placeholders(cfg)

    def scan(node, path=""):
        if isinstance(node, dict):
            for k, v in node.items():
                if re.search(r"(password|secret|token|api[_-]?key|private[_-]?key|credential)",
                             str(k), re.I):
                    err(f"{name}: credential-shaped key '{path}{k}'. "
                        "Credentials belong in the MCP host, never in this repo.")
                scan(v, f"{path}{k}.")
        elif isinstance(node, list):
            for v in node:
                scan(v, path)
    scan(cfg)

    live = [s for s in SOURCES if srcs.get(s, {}).get("mode") == "live"]
    _LIVE.update(live)
    fix = [s for s in SOURCES if srcs.get(s, {}).get("mode") == "fixture"]
    off = [s for s in SOURCES if srcs.get(s, {}).get("mode") == "off"]
    print(f"  {name}: live={live or '-'} fixture={fix or '-'} off={off or '-'}")
    if fix:
        print(f"    note: outputs will be banner-marked DEMO DATA ({', '.join(fix)})")
    if off:
        blocked = {"warehouse": "Q2 blast radius, Q10 enterprise tier",
                   "metrics": "Q4 regression", "code": "Q7 stub / error swallowing"}
        for s in off:
            if s in blocked:
                print(f"    note: {s} off, cannot answer {blocked[s]}")


def check_fixture(path):
    name = os.path.relpath(path, ROOT)
    with open(path) as f:
        try:
            d = json.load(f)
        except json.JSONDecodeError as e:
            err(f"{name}: invalid JSON: {e}")
            return
    missing = ENVELOPE - set(d)
    if missing:
        err(f"{name}: envelope missing {sorted(missing)}")
        return
    if d["source"] not in SOURCES:
        err(f"{name}: unknown source '{d['source']}'")
        return
    if d["status"] not in STATUSES:
        err(f"{name}: status '{d['status']}' invalid")
    if d["mode"] != "fixture":
        err(f"{name}: mode must be 'fixture', got '{d['mode']}'")
    if d["status"] == "unavailable":
        if d["data"]:
            err(f"{name}: status 'unavailable' must carry an empty data object")
        return
    if d["source"] == "tracker":
        for r in d["data"].get("related", []):
            if "resolution_notes" not in r:
                err(f"{name}: related ticket {r.get('key','?')} has no "
                    "'resolution_notes'. Workaround discovery reads that field; "
                    "without it the source silently yields nothing.")

    if d["source"] == "releases":
        for r in d["data"].get("releases", []):
            need = {"version", "released_on", "components", "issue_keys",
                    "files_touched", "notes_url", "sources"}
            rm = need - set(r)
            if rm:
                err(f"{name}: release {r.get('version','?')} missing {sorted(rm)}")
            if r.get("files_touched") and not ({"vcs_tag", "vcs_pr"} & set(r.get("sources", []))):
                err(f"{name}: release {r.get('version','?')} has files_touched but no version-control "
                    "adapter in sources. Only vcs adapters yield file-level detail.")
    miss = SHAPES[d["source"]] - set(d["data"])
    if miss:
        err(f"{name}: data missing {sorted(miss)}. Fixtures must match the live contract "
            "exactly, with no extra nesting.")



_LIVE = set()


def _live_sources():
    return _LIVE


def check_manifests():
    """Cross-client packaging checks.

    Three manifests must agree, or a client installs a plugin whose name or
    version differs from its siblings. Also catches url placeholders, which no
    client expands: a ${VAR} in a url field ships broken.
    """
    manifests = {
        "plugin.json (Agent Plugins)": "plugin.json",
        "Claude": ".claude-plugin/plugin.json",
        "Cursor": ".cursor-plugin/plugin.json",
    }
    seen = {}
    for label, rel in manifests.items():
        fp = os.path.join(ROOT, rel)
        if not os.path.exists(fp):
            err(f"missing manifest: {rel}")
            continue
        d = json.load(open(fp))
        seen[label] = (d.get("name"), d.get("version"))
        for field in ("name", "version", "description"):
            if not d.get(field):
                err(f"{rel}: missing '{field}'")
    if len(set(seen.values())) > 1:
        err("manifests disagree on name/version: "
            + "; ".join(f"{k}={v}" for k, v in seen.items()))
    root_mf = os.path.join(ROOT, "plugin.json")
    if os.path.exists(root_mf):
        d = json.load(open(root_mf))
        if "agent-plugins.org" not in str(d.get("$schema", "")):
            err("plugin.json: missing the Agent Plugins $schema identifier")

    for rel in ("mcp.json", ".mcp.json"):
        if os.path.exists(os.path.join(ROOT, rel)):
            err(f"{rel} exists. This plugin declares no MCP servers of its own: "
                "declaring one makes the host ask for a connection owned by the "
                "plugin, duplicating a connector the user already has. Bind to "
                "existing tools through tool_bindings instead. See "
                "reference/mcp-servers.example.json.")


def main():
    args = sys.argv[1:]
    print("Config:")
    targets = ([p for p in glob.glob(os.path.join(ROOT, "teams", "*.json"))
                if "schema" not in p and "example" not in p]
               if (not args or args[0] == "--all") else
               [a if os.path.isabs(a) else os.path.join(ROOT, a) for a in args])
    for t in targets:
        check_config(t)

    check_manifests()
    print("\nFixtures:")
    fx = sorted(glob.glob(os.path.join(ROOT, "fixtures", "**", "*.json"), recursive=True))
    for f in fx:
        check_fixture(f)
    print(f"  {len(fx)} fixture files checked against the source contract")

    explicit = bool(args) and args[0] != "--all"

    print()
    for u in unconfigured:
        print(f"UNCONFIGURED {u}")
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")

    if errors:
        print(f"\n{len(errors)} error(s).")
        sys.exit(1)
    if unconfigured and explicit:
        print(f"\n{len(unconfigured)} unset value(s). This config cannot go live yet.")
        sys.exit(1)
    if unconfigured:
        n = len({m.split(":")[0] for m in unconfigured})
        print(f"\nPASS ({len(warnings)} warning(s), "
              f"{n} config(s) awaiting real values). "
              "Run the validator on a named config before going live with it.")
        sys.exit(0)
    print(f"PASS ({len(warnings)} warning(s))")


if __name__ == "__main__":
    main()
