#!/usr/bin/env python3
"""Reproduction status and fix complexity, from evidence already in the result file.

Two questions an engineering lead asks before picking up a bug, and that priority does
not answer: has anyone seen it fail, and how big is the fix likely to be? Both are
derived here by rule, so every report answers them the same way, and neither changes
the priority.

    python3 scripts/effort.py <TICKET>.result.json      # prints both blocks

Reproduction, strongest first:
    reproduced          someone or something triggered the failure. Only ever taken from an
                        explicit `reproduction` block in the result, with `how`; a script
                        never claims it.
    seen_in_production  the metrics source shows the failure for this ticket (an error
                        series or a spike over baseline)
    code_path_only      a fault signal at a located file (swallowed error, stub, suppressed
                        type error), not seen failing
    not_reproduced      an attempt was made and it did not fail (explicit only)
    not_attempted       none of the above

Complexity, a 1 to 5 score with the factors that set it:
    base 1
    + files located: none +2, one 0, two or three +1, more +2
    + evidence: weak +2 (the cause is not found, so the cost is not known), moderate +1
    + a stub at the bug site +1 (the behaviour is missing, not wrong)
    + data repair needed +1 (`data_repair` in the result)
    + a group supported by evidence +1 (one fix must cover several tickets)
    capped at 5. 1-2 low, 3 medium, 4-5 high. Not scored when a fix is already merged.
"""
import json, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

REPRO = ("reproduced", "seen_in_production", "code_path_only", "not_reproduced", "not_attempted")
REPRO_LABEL = {"reproduced": "🟢 reproduced", "seen_in_production": "🟢 seen in production",
               "code_path_only": "🟡 code path only", "not_reproduced": "🔴 not reproduced",
               "not_attempted": "⚪ not attempted"}
FAULT = {"error_swallowing", "stub", "suppressed_type_error"}
LEVEL = {1: "low", 2: "low", 3: "medium", 4: "high", 5: "high"}
ICON = {"low": "🟢", "medium": "🟡", "high": "🔴"}


def _spike(r):
    m = (r.get("sources") or {}).get("metrics") or {}
    note = (m.get("note") or "").lower()
    if m.get("status") != "ok" or "no spike" in note or "no error spike" in note:
        return None
    if r.get("series") or "×" in note or "baseline" in note:
        return m.get("note") or "error series for this ticket"
    return None


def reproduction(r):
    given = r.get("reproduction")
    if given and given.get("status") in ("reproduced", "not_reproduced"):
        return given
    s = _spike(r)
    if s:
        return {"status": "seen_in_production", "how": f"metrics: {s}"}
    fl = next((l for l in r.get("locations") or [] if l.get("signal") in FAULT and l.get("path")), None)
    if fl:
        where = fl["path"].rsplit("/", 1)[-1] + (f":{fl['line']}" if fl.get("line") else "")
        return {"status": "code_path_only", "how": f"{fl['signal'].replace('_', ' ')} at {where}; not seen failing"}
    return {"status": "not_attempted", "how": "no failure observed in the sources, and no reproduction run"}


def complexity(r):
    import fix_status as FX
    if r.get("disposition") != "defect":
        return None
    if FX.is_fixed(r):
        return {"score": None, "level": None, "factors": ["fix already merged; nothing to size"]}
    from render_fix_brief import assess
    score, f = 1, []
    locs = [l for l in r.get("locations") or [] if l.get("path")]
    confirmed = {l["path"] for l in locs if l.get("signal") not in (None, "candidate", "area_only")}
    files = confirmed or {l["path"] for l in locs}
    n = len(files)
    if n == 0:
        score += 2; f.append("no file located yet (+2)")
    elif n <= 3 and n > 1:
        score += 1; f.append(f"{n} files located (+1)")
    elif n > 3:
        score += 2; f.append(f"{n} files located (+2)")
    else:
        only_cand = all(l.get("signal") in (None, "candidate") for l in r.get("locations") or [] if l.get("path"))
        f.append("one candidate file, not confirmed" if only_cand else "one file located")
    ev = assess(r)["level"]
    if ev == "weak":
        score += 2; f.append("cause not found, so the cost is not known (+2)")
    elif ev == "moderate":
        score += 1; f.append("cause likely but not confirmed (+1)")
    if any(l.get("signal") == "stub" for l in r.get("locations") or []):
        score += 1; f.append("behaviour missing at the bug site (+1)")
    if r.get("data_repair"):
        score += 1; f.append("data repair needed (+1)")
    sup = [c for c in r.get("clusters") or [] if c.get("status") == "EVIDENCE_SUPPORTED"]
    if sup:
        k = max(len(c.get("tickets") or []) for c in sup)
        score += 1; f.append(f"one fix must cover {k} tickets (+1)")
    score = min(score, 5)
    return {"score": score, "level": LEVEL[score], "factors": f}


def attach(r):
    """Fill `reproduction` and `complexity` on a result dict, keeping an explicit reproduction."""
    r["reproduction"] = reproduction(r)
    c = complexity(r)
    if c:
        r["complexity"] = c
    return r


# ------------------------------------------------------------------ rendering

def repro_cell(r, brief=False):
    rp = r.get("reproduction") or reproduction(r)
    if brief and rp["status"] in ("seen_in_production", "code_path_only", "not_attempted"):
        return REPRO_LABEL[rp["status"]]   # the evidence behind it is shown elsewhere in the report
    return f"{REPRO_LABEL[rp['status']]} · {rp.get('how', '')}"


def complexity_cell(r):
    c = r.get("complexity") or complexity(r)
    if not c:
        return None
    if c["score"] is None:
        return "not scored · " + c["factors"][0]
    return f"{ICON[c['level']]} {c['level']} ({c['score']}/5) · " + "; ".join(c["factors"])


def short(r):
    """One word for tables: low, medium, high or —."""
    c = r.get("complexity") or complexity(r)
    return (c or {}).get("level") or "—"


def validate(r):
    p = []
    rp = r.get("reproduction")
    if rp:
        if rp.get("status") not in REPRO:
            p.append(f"reproduction.status must be one of {list(REPRO)}")
        if rp.get("status") in ("reproduced", "not_reproduced") and not rp.get("how"):
            p.append("reproduction: reproduced or not_reproduced needs `how` (what was run, where)")
    c = r.get("complexity")
    if c and c.get("score") is not None:
        if c["score"] not in LEVEL or c.get("level") != LEVEL[c["score"]]:
            p.append("complexity: score must be 1 to 5 and level must match it")
    return p


def main():
    for p in sys.argv[1:]:
        r = json.load(open(p, encoding="utf-8"))
        print(json.dumps({"ticket": r["ticket"], "reproduction": reproduction(r), "complexity": complexity(r)},
                         indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
