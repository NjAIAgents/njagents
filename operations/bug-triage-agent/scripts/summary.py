#!/usr/bin/env python3
"""What every rendered surface says first, computed once from a result file.

Three things live here so the report, the trace and the fix brief can never disagree:

- summary(r)        the three-line answer at the top: verdict, why, do now
- corroboration(r)  which independent sources support the verdict, each with its link
- freshness(r)      how old each source's data is, and whether any of it is stale

All three read only the result file. None of them calls a tool or invents a value:
a field that is absent produces no line, never a placeholder.
"""
from datetime import datetime, timezone

SOURCES = ("tracker", "releases", "metrics", "warehouse", "code")
# Same set the evidence grading uses (render_fix_brief.CODE_SIGNALS). A candidate file
# with no fault signal is a place to look, not support for the verdict.
FAULT_SIGNALS = {"error_swallowing", "stub", "suppressed_type_error"}
STALE_HOURS = 24          # as_of older than this is flagged
EXPIRY_WARN_DAYS = 2      # data this close to its retention limit is flagged


# ------------------------------------------------------------------ summary

def _regression(r):
    return any(str(s.get("step", "")).startswith("+1 release") for s in r.get("steps") or [])


def summary(r):
    """{'verdict', 'why': [..], 'do_now'}. `headline`, `deciding_factor` and
    `do_now` in the result override the computed text when the triage set them."""
    defect = r.get("disposition") == "defect"
    rel = (r.get("introduced_by") or {}).get("release") or (r.get("release") or {}).get("version")
    if r.get("headline"):
        verdict = r["headline"]
    elif defect:
        kind = f"regression in {rel}" if _regression(r) and rel else "defect"
        verdict = f"{r.get('priority')} {kind}"
    else:
        verdict = f"{r.get('disposition')}, no priority"

    # The deciding factor, when the triage named one, is the whole reason. Otherwise
    # the two strongest corroborating claims.
    if r.get("deciding_factor"):
        why = [r["deciding_factor"]]
    else:
        why = [c["claim"] for c in corroboration(r)[:2]]
    if not why:
        why = [e.get("text") for e in (r.get("disposition_evidence") or [])[:2] if e.get("text")]

    wa = r.get("workaround") or {}
    if r.get("do_now"):
        do_now = r["do_now"]
    elif defect and wa.get("text"):
        do_now = wa["text"].rstrip(".") + "." + (f" Who: {wa['who']}." if wa.get("who") else "")
    elif r.get("route"):
        # A route is either a destination ("Approvals Team", "PRODUCT") or an action
        # ("link to BUG-4849 and close"). Only a destination reads as "Route to X".
        route = r["route"].strip()
        do_now = f"Route to {route}" if route[:1].isupper() else route[:1].upper() + route[1:]
    else:
        do_now = None
    return {"verdict": verdict, "why": why, "do_now": do_now}


# ------------------------------------------------------------ corroboration

def corroboration(r):
    """One entry per independent source that supports the verdict.

    Independent means a different system: two findings from code search are one
    source. Order is code, releases, metrics, tracker, warehouse, which is roughly
    how directly each points at the fault."""
    found = {}
    for loc in r.get("locations") or []:
        sig = loc.get("signal")
        if loc.get("source") == "code" and sig in FAULT_SIGNALS and "code" not in found:
            where = loc.get("path", "").rsplit("/", 1)[-1] + (f":{loc['line']}" if loc.get("line") else "")
            found["code"] = {"source": "code", "claim": f"{sig.replace('_', ' ')} at {where}",
                             "label": where, "url": loc.get("url")}
        if sig == "release_touched" and "releases" not in found:
            rel = (r.get("introduced_by") or {}).get("release") or (r.get("release") or {}).get("version")
            name = loc.get("path", "").rsplit("/", 1)[-1]
            found["releases"] = {"source": "releases",
                                 "claim": f"{rel} changed {name}" if rel else f"a release changed {name}",
                                 "label": rel or name,
                                 "url": (r.get("release") or {}).get("url") or loc.get("url")}
    rel = r.get("release") or {}
    if "releases" not in found and rel.get("version") and rel.get("confidence") in ("high", "medium"):
        found["releases"] = {"source": "releases", "claim": f"{rel['version']} correlates "
                             f"({rel['confidence']} confidence)", "label": rel["version"], "url": rel.get("url")}
    for x in r.get("links") or []:
        if x.get("source") == "metrics" and "metrics" not in found:
            found["metrics"] = {"source": "metrics", "claim": x.get("text") or x.get("label"),
                                "label": x.get("label"), "url": x.get("url")}
    m = (r.get("sources") or {}).get("metrics") or {}
    if "metrics" not in found and m.get("mode") in ("live", "fixture") and m.get("note") and _regression(r):
        found["metrics"] = {"source": "metrics", "claim": m["note"],
                            "label": m["note"] if len(m["note"]) <= 24 else m["note"][:23] + "…", "url": None}
    for p in r.get("prior_fixes") or []:
        if "tracker" not in found:
            found["tracker"] = {"source": "tracker", "claim": f"same failure fixed before in {p.get('key')}",
                                "label": p.get("key"), "url": p.get("url")}
    if "tracker" not in found:
        for e in r.get("disposition_evidence") or []:
            if e.get("source") == "tracker":
                found["tracker"] = {"source": "tracker", "claim": e.get("text"),
                                    "label": e.get("label") or "tracker", "url": e.get("url")}
                break
    b = r.get("blast_radius") or {}
    if b.get("accounts") is not None:
        found["warehouse"] = {"source": "warehouse",
                              "claim": f"{b['accounts']} account(s) affected, {b.get('enterprise', 0)} enterprise",
                              "label": "warehouse", "url": b.get("url")}
    order = ("code", "releases", "metrics", "tracker", "warehouse")
    return [found[k] for k in order if k in found]


def corroboration_line(r):
    c = corroboration(r)
    live = [s for s in SOURCES if ((r.get("sources") or {}).get(s) or {}).get("mode") in ("live", "fixture")]
    return len(c), len(live)


# ---------------------------------------------------------------- freshness

def _parse(ts):
    if not ts:
        return None
    s = str(ts).strip().replace("Z", "+00:00").replace(" UTC", "+00:00")
    for fmt in (None, "%Y-%m-%d %H:%M%z", "%Y-%m-%d"):
        try:
            d = datetime.fromisoformat(s) if fmt is None else datetime.strptime(s, fmt)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _age(hours):
    if hours is None:
        return None
    if hours < 1:
        return "under an hour"
    if hours < 48:
        return f"{int(hours)}h"
    return f"{int(hours // 24)}d"


def freshness(r, now=None):
    """Rows {source, as_of, age, note, stale} for live and fixture sources, and warnings.

    Reads sources.<s>.as_of (when the source was read), and optionally data_from (the
    oldest data point the finding relies on) with retention_days (how long the source
    keeps data). A finding whose data is about to age out of its source cannot be
    re-checked later, so it is flagged."""
    now = now or datetime.now(timezone.utc)
    ref = _parse(r.get("triaged_at")) or now
    rows, warnings = [], []
    for s in SOURCES:
        src = (r.get("sources") or {}).get(s) or {}
        if src.get("mode") not in ("live", "fixture"):
            continue
        as_of = _parse(src.get("as_of"))
        hours = (ref - as_of).total_seconds() / 3600 if as_of else None
        note, stale = "", False
        if hours is not None and hours > STALE_HOURS and src.get("mode") == "live":
            stale = True
            note = f"read {_age(hours)} before triage"
        frm, keep = _parse(src.get("data_from")), src.get("retention_days")
        if frm and keep:
            left = keep - (now - frm).total_seconds() / 86400
            if left <= 0:
                stale, note = True, "oldest data used is past the source's retention"
            elif left <= EXPIRY_WARN_DAYS:
                stale, note = True, f"oldest data used ages out in about {max(1, round(left))}d"
        if src.get("mode") == "fixture":
            note = note or "recorded fixture"
        rows.append({"source": s, "as_of": src.get("as_of"), "age": _age(hours), "note": note,
                     "stale": stale})
        if stale:
            warnings.append(f"{s}: {note}")
    return rows, warnings
