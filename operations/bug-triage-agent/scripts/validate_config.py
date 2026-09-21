#!/usr/bin/env python3
"""Validate a team config and every fixture against the source contract.

Usage:
    python3 scripts/validate_config.py teams/demo.json
    python3 scripts/validate_config.py --all
"""
import json, sys, os, glob, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES = ["jira", "releases", "datadog", "snowflake", "code"]
MODES = {"live", "fixture", "off"}
ENVELOPE = {"source", "mode", "status", "as_of", "latency_ms", "notes", "data"}
STATUSES = {"ok", "partial", "unavailable", "error"}


def is_placeholder(v):
    return isinstance(v, str) and (v.startswith("REPLACE_")
                                   or v.upper() in ("TODO", "CHANGEME", "XXX"))

SHAPES = {
    "jira": {"ticket", "related", "duplicates", "component_history", "sprint_collision"},
    "releases": {"releases", "lookback_days", "adapters_run", "adapters_failed"},
    "datadog": {"baseline", "current", "spike", "deploys_in_window", "sample_errors"},
    "snowflake": {"affected_accounts", "enterprise_accounts", "account_names",
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

    for key in ("team", "jira", "sources"):
        if key not in cfg:
            err(f"{name}: missing required key '{key}'")
    if "jira" in cfg:
        for key in ("project_key", "cloud_id"):
            v = cfg["jira"].get(key)
            if not v:
                err(f"{name}: jira.{key} is empty")
            elif is_placeholder(v):
                unconf(f"{name}: jira.{key} is a placeholder ({v}). "
                       "This config cannot go live until it is set.")
        pn = cfg["jira"].get("priority_names", {})
        missing = [p for p in ("P1", "P2", "P3", "P4") if p not in pn]
        if missing:
            err(f"{name}: jira.priority_names missing {missing}")

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

    if srcs.get("jira", {}).get("mode") == "off":
        err(f"{name}: jira cannot be 'off'. It is the minimum viable source.")

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

    if srcs.get("snowflake", {}).get("mode") == "live" and not cfg.get("snowflake", {}).get("queries"):
        err(f"{name}: snowflake is live but snowflake.queries is empty")
    if srcs.get("code", {}).get("mode") == "live" and not cfg.get("repos"):
        err(f"{name}: code is live but repos is empty")

    tools = cfg.get("mcp_tools", {})
    for s_ in ("datadog", "snowflake", "code"):
        if srcs.get(s_, {}).get("mode") == "live" and not tools.get(s_):
            err(f"{name}: {s_} is live but mcp_tools.{s_} is missing. "
                "Tool names are configuration; the adapter cannot be bound without them.")

    adapters = rc.get("manifest_sources", ["jira_fixversion"])
    if not adapters:
        err(f"{name}: release_correlation.manifest_sources is empty")
    if "manual_file" in adapters and not rc.get("manual_file_path"):
        err(f"{name}: manifest_sources includes manual_file but manual_file_path is unset")
    if "confluence_release_notes" in adapters and not rc.get("confluence", {}).get("space_key"):
        err(f"{name}: confluence_release_notes adapter selected but confluence.space_key is unset")

    write_verbs = ("INSERT", "UPDATE", "DELETE", "DROP", "MERGE", "CREATE", "TRUNCATE",
                   "ALTER", "GRANT", "REVOKE", "CALL", "EXECUTE", "COPY", "PUT", "REMOVE", "UNDROP")
    for qname, q in cfg.get("snowflake", {}).get("queries", {}).items():
        for tok in re.findall(r"[A-Za-z_]+", q.upper()):
            if tok in write_verbs:
                err(f"{name}: snowflake query '{qname}' is not read-only, contains {tok}")
        if not q.strip().upper().startswith(("SELECT", "WITH")):
            err(f"{name}: snowflake query '{qname}' must start with SELECT or WITH")

    def placeholders(node, path=""):
        if isinstance(node, dict):
            for k, v in node.items():
                placeholders(v, f"{path}{k}.")
        elif isinstance(node, list):
            for v in node:
                placeholders(v, path)
        elif isinstance(node, str) and is_placeholder(node):
            key = path.rstrip(".")
            if key not in ("jira.cloud_id", "jira.project_key"):
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
    fix = [s for s in SOURCES if srcs.get(s, {}).get("mode") == "fixture"]
    off = [s for s in SOURCES if srcs.get(s, {}).get("mode") == "off"]
    print(f"  {name}: live={live or '-'} fixture={fix or '-'} off={off or '-'}")
    if fix:
        print(f"    note: outputs will be banner-marked DEMO DATA ({', '.join(fix)})")
    if off:
        blocked = {"snowflake": "Q2 blast radius, Q10 enterprise tier",
                   "datadog": "Q4 regression", "code": "Q7 stub / error swallowing"}
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
    if d["source"] == "releases":
        for r in d["data"].get("releases", []):
            need = {"version", "released_on", "components", "issue_keys",
                    "files_touched", "notes_url", "sources"}
            rm = need - set(r)
            if rm:
                err(f"{name}: release {r.get('version','?')} missing {sorted(rm)}")
            if r.get("files_touched") and not ({"github_tag", "github_pr"} & set(r.get("sources", []))):
                err(f"{name}: release {r.get('version','?')} has files_touched but no github "
                    "adapter in sources. Only github adapters yield file-level detail.")
    miss = SHAPES[d["source"]] - set(d["data"])
    if miss:
        err(f"{name}: data missing {sorted(miss)}. Fixtures must match the live contract "
            "exactly, with no extra nesting.")


def main():
    args = sys.argv[1:]
    print("Config:")
    targets = ([p for p in glob.glob(os.path.join(ROOT, "teams", "*.json"))
                if "schema" not in p and "example" not in p]
               if (not args or args[0] == "--all") else
               [a if os.path.isabs(a) else os.path.join(ROOT, a) for a in args])
    for t in targets:
        check_config(t)

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
