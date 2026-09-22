#!/usr/bin/env python3
"""Enforce the repository constitution across every plugin.

The constitution is only worth something if something checks it. This runs in CI and
before packaging.

What it cannot do: prove a plugin is vendor-neutral. A denylist catches the vendor
names we know about, not the ones we have not met. Treat a pass as "no known
violation", never as a guarantee.

Deliberate escapes live in .constitution-allow, one `path:token:reason` per line, so
every exception is explicit and reviewable rather than silently tolerated.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Directories whose contents must be judgment, never vendor or customer detail.
SHARED = ("skills", "reference", "agents", "commands")

# Where per-team, vendor-specific detail is allowed to live.
TEAM_DIR = "teams"

VENDORS = [
    "jira", "atlassian", "confluence", "bitbucket",
    "datadog", "splunk", "grafana", "newrelic", "sentry",
    "snowflake", "bigquery", "redshift", "databricks",
    "zoekt", "sourcegraph", "github", "gitlab",
    "linear", "asana", "servicenow", "pagerduty", "zendesk",
]

MANIFESTS = {
    "plugin.json": "Agent Plugins",
    ".claude-plugin/plugin.json": "Claude",
    ".cursor-plugin/plugin.json": "Cursor",
}

errors, warnings = [], []


def err(m): errors.append(m)
def warn(m): warnings.append(m)


def load_allowlist():
    allowed = set()
    fp = os.path.join(ROOT, ".constitution-allow")
    if not os.path.exists(fp):
        return allowed
    for raw in open(fp):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split(":", 2)
        if len(parts) < 3 or not parts[2].strip():
            err(f".constitution-allow: '{line}' needs path:token:reason. "
                "An exception without a stated reason is not an exception.")
            continue
        allowed.add((parts[0].strip(), parts[1].strip().lower()))
    return allowed


def plugin_dirs():
    out = []
    for cat in sorted(os.listdir(ROOT)):
        cp = os.path.join(ROOT, cat)
        if not os.path.isdir(cp) or cat.startswith((".", "_")) or cat == "scripts":
            continue
        for name in sorted(os.listdir(cp)):
            pp = os.path.join(cp, name)
            if os.path.isdir(pp) and os.path.exists(os.path.join(pp, "plugin.json")):
                out.append((f"{cat}/{name}", pp))
    return out


def check_vendor_neutrality(label, path, allowed):
    """Principle I: nothing in the shared layer may name a product."""
    pattern = re.compile(r"\b(" + "|".join(VENDORS) + r")\b", re.I)
    for sub in SHARED:
        base = os.path.join(path, sub)
        if not os.path.isdir(base):
            continue
        for dirpath, _, files in os.walk(base):
            for fn in files:
                if not fn.endswith((".md", ".json", ".py", ".yaml", ".yml")):
                    continue
                fp = os.path.join(dirpath, fn)
                rel = os.path.relpath(fp, ROOT)
                for i, line in enumerate(open(fp, errors="replace"), 1):
                    for hit in pattern.findall(line):
                        if (rel, hit.lower()) in allowed:
                            continue
                        err(f"{rel}:{i}: '{hit}' in the shared layer. Vendor detail "
                            f"belongs in {label}/{TEAM_DIR}/, or add an entry with a "
                            "reason to .constitution-allow.")


def check_manifests(label, path):
    """Portability: three manifests, agreeing."""
    seen = {}
    for rel, client in MANIFESTS.items():
        fp = os.path.join(path, rel)
        if not os.path.exists(fp):
            err(f"{label}: missing {rel} ({client})")
            continue
        d = json.load(open(fp))
        seen[client] = (d.get("name"), d.get("version"))
    if len(set(seen.values())) > 1:
        err(f"{label}: manifests disagree: "
            + "; ".join(f"{k}={v}" for k, v in seen.items()))


def check_no_speckit_inside(label, path):
    """Spec Kit lives at the repository root, never inside a plugin."""
    for d in (".specify", ".claude"):
        if os.path.isdir(os.path.join(path, d)):
            err(f"{label}: contains {d}/. Spec Kit artifacts belong at the repository "
                "root; shipping them puts spec-kit skills inside an installed plugin.")


def check_status_exists(label, path):
    """Principle V: every plugin states what is unproven."""
    if not os.path.exists(os.path.join(path, "STATUS.md")):
        err(f"{label}: no STATUS.md. Every plugin must separate what is verified from "
            "what is written but unexercised.")


def check_marketplace():
    fp = os.path.join(ROOT, ".claude-plugin", "marketplace.json")
    if not os.path.exists(fp):
        err("missing .claude-plugin/marketplace.json")
        return
    m = json.load(open(fp))
    listed = {p["source"].lstrip("./") for p in m.get("plugins", [])}
    found = {label for label, _ in plugin_dirs()}
    for missing in sorted(found - listed):
        err(f"{missing} exists but is not listed in marketplace.json")
    for ghost in sorted(listed - found):
        err(f"marketplace.json lists {ghost}, which does not exist")


def main():
    allowed = load_allowlist()
    plugins = plugin_dirs()
    if not plugins:
        err("no plugins found. Expected <category>/<plugin>/plugin.json")

    print("Constitution check")
    for label, path in plugins:
        print(f"  {label}")
        check_vendor_neutrality(label, path, allowed)
        check_manifests(label, path)
        check_no_speckit_inside(label, path)
        check_status_exists(label, path)
    check_marketplace()

    print()
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    if errors:
        print(f"\n{len(errors)} violation(s). See .specify/memory/constitution.md")
        sys.exit(1)
    print(f"PASS ({len(plugins)} plugin(s), {len(allowed)} allowed exception(s))")
    print("Note: a denylist catches known vendor names, not unknown ones. "
          "This is 'no known violation', not a guarantee.")


if __name__ == "__main__":
    main()
