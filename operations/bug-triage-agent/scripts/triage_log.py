#!/usr/bin/env python3
"""Audit log for triage recommendations, and the accuracy report built from it.

The gap between what the agent recommended and what a human finally decided is the
only measurement this system has. Everything else is opinion.

    triage_log.py append --ticket BUG-1 --team demo --disposition defect \
        --priority P2 --confidence high --modes tracker=fixture,metrics=off \
        --escalations release:confirmed_regression --unanswered Q4
    triage_log.py override --ticket BUG-1 --disposition voice_of_customer \
        --reason "working as designed per SPEC-12"
    triage_log.py report --days 30
"""
import argparse
import datetime
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The log lives with the user, never inside the plugin: an installed plugin is
# read-only, and even where it is writable an update replaces it and the history
# (the only measurement this system has) would be lost. Resolved in main().
LOG = None


def resolve_log(explicit=None):
    if explicit:
        return os.path.abspath(os.path.expanduser(explicit))
    env = os.environ.get("CLAUDE_TRIAGE_LOG")
    if env:
        return os.path.abspath(os.path.expanduser(env))
    return os.path.join(os.getcwd(), "triage-logs", "triage-log.jsonl")
DISPOSITIONS = ["defect", "expected_behavior", "config_or_data", "duplicate",
                "voice_of_customer", "insufficient_information"]
LEVELS = ["P1", "P2", "P3", "P4"]


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def read():
    if not os.path.exists(LOG):
        return []
    out = []
    for i, line in enumerate(open(LOG), 1):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            print(f"warning: {LOG}:{i} is not valid JSON, skipped", file=sys.stderr)
    return out


def kv(s):
    d = {}
    for part in (s or "").split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            d[k.strip()] = v.strip()
    return d


def csv(s):
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def cmd_append(a):
    rec = {
        "ts": now(), "ticket": a.ticket, "team": a.team,
        "modes": kv(a.modes),
        "disposition": a.disposition,
        "priority": a.priority,
        "confidence": a.confidence,
        "escalations": csv(a.escalations),
        "unanswered": csv(a.unanswered),
        "source_errors": csv(a.source_errors),
        "flags": csv(a.flags),
        "human_override": None,
        "override_disposition": None,
        "override_priority": None,
        "override_reason": None,
        "override_ts": None,
    }
    if rec["disposition"] != "defect" and rec["priority"]:
        print("refusing: a non-defect must not carry a priority. That is the gate this "
              "tool exists to enforce.", file=sys.stderr)
        return 1
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a") as f:
            f.write(json.dumps(rec) + "\n")
    except OSError as e:
        print(f"cannot write the audit log at {LOG}: {e.strerror}. Pass --log or set "
              "CLAUDE_TRIAGE_LOG to a writable path in your own folder.", file=sys.stderr)
        return 2
    print(f"logged {rec['ticket']} {rec['disposition']} {rec['priority'] or '-'} -> {LOG}")
    return 0


def cmd_override(a):
    """Record the human's call WITHOUT altering the recommendation. The gap is the point."""
    rows = read()
    for r in reversed(rows):
        if r["ticket"] == a.ticket and not r["human_override"]:
            r["human_override"] = True
            r["override_disposition"] = a.disposition or r["disposition"]
            r["override_priority"] = a.priority or r["priority"]
            r["override_reason"] = a.reason
            r["override_ts"] = now()
            with open(LOG, "w") as f:
                for x in rows:
                    f.write(json.dumps(x) + "\n")
            print(f"override recorded for {a.ticket}: "
                  f"{r['disposition']}/{r['priority']} -> "
                  f"{r['override_disposition']}/{r['override_priority']}")
            return 0
    print(f"no un-overridden record for {a.ticket}", file=sys.stderr)
    return 1


def cmd_report(a):
    cutoff = (datetime.datetime.now(datetime.timezone.utc)
              - datetime.timedelta(days=a.days)).isoformat()
    rows = [r for r in read() if r["ts"] >= cutoff]
    if not rows:
        print(f"no records in the last {a.days} days")
        return 0

    reviewed = [r for r in rows if r["human_override"] is not None]
    print(f"Triage accuracy, last {a.days} days")
    print(f"  runs: {len(rows)}   reviewed: {len(reviewed)}")
    if not reviewed:
        print("\n  Nothing has been reviewed, so accuracy is unknown. Unreviewed runs "
              "measure volume, not correctness.")
        return 0

    # Reported per class, never as one number: a taxonomy that is right overall but
    # wrong on every voice-of-customer item has not captured the judgment that matters.
    print("\n  Disposition agreement, per class")
    for d in DISPOSITIONS:
        sub = [r for r in reviewed if r["disposition"] == d]
        if not sub:
            continue
        ok = sum(1 for r in sub if r["override_disposition"] == d)
        print(f"    {d:<26} {ok}/{len(sub)}  {100*ok//len(sub)}%")

    defects = [r for r in reviewed if r["disposition"] == "defect"
               and r["priority"] and r["override_priority"]]
    if defects:
        exact = within = 0
        for r in defects:
            try:
                gap = abs(LEVELS.index(r["priority"]) - LEVELS.index(r["override_priority"]))
            except ValueError:
                continue
            exact += gap == 0
            within += gap <= 1
        print("\n  Priority agreement")
        print(f"    exact           {exact}/{len(defects)}  {100*exact//len(defects)}%")
        print(f"    within one      {within}/{len(defects)}  {100*within//len(defects)}%")

    changed = [r for r in reviewed if r["override_disposition"] != r["disposition"]
               or r["override_priority"] != r["priority"]]
    if changed:
        print(f"\n  Overridden: {len(changed)}/{len(reviewed)}")
        for reason, n in Counter(r["override_reason"] for r in changed).most_common(5):
            print(f"    {n}x  {reason}")

    conf = Counter(r["confidence"] for r in rows)
    print(f"\n  Confidence mix: " + ", ".join(f"{k}={v}" for k, v in conf.most_common()))
    errs = Counter(e for r in rows for e in r.get("source_errors", []))
    if errs:
        print("  Source errors: " + ", ".join(f"{k}={v}" for k, v in errs.most_common()))
    flags = Counter(f for r in rows for f in r.get("flags", []))
    if flags:
        print("  Flags: " + ", ".join(f"{k}={v}" for k, v in flags.most_common()))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log", help="log file; default $CLAUDE_TRIAGE_LOG, else "
                                  "./triage-logs/triage-log.jsonl in the working folder")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("append")
    a.add_argument("--ticket", required=True)
    a.add_argument("--team", required=True)
    a.add_argument("--disposition", required=True, choices=DISPOSITIONS)
    a.add_argument("--priority", choices=LEVELS)
    a.add_argument("--confidence", required=True, choices=["high", "medium", "low"])
    a.add_argument("--modes", default="")
    a.add_argument("--escalations", default="")
    a.add_argument("--unanswered", default="")
    a.add_argument("--source-errors", default="")
    a.add_argument("--flags", default="")
    a.set_defaults(fn=cmd_append)

    o = sub.add_parser("override")
    o.add_argument("--ticket", required=True)
    o.add_argument("--disposition", choices=DISPOSITIONS)
    o.add_argument("--priority", choices=LEVELS)
    o.add_argument("--reason", required=True)
    o.set_defaults(fn=cmd_override)

    r = sub.add_parser("report")
    r.add_argument("--days", type=int, default=30)
    r.set_defaults(fn=cmd_report)

    args = ap.parse_args()
    global LOG
    LOG = resolve_log(args.log)
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
