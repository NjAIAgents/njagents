#!/usr/bin/env python3
"""Accuracy dashboard and calibration suggestions, built from the audit log.

Reached through triage_log.py:

    triage_log.py calibrate [--days 90] [--team demo-live]
    triage_log.py dashboard --out triage-reports/accuracy.html [--days 90]

`calibrate` reads the overrides people recorded and says where the agent is wrong the
same way repeatedly, and what to change. It follows the review table in
reference/taxonomy-calibration.md:

    one disposition over-applied       the rule is too loose: require more evidence
    one disposition missed             the evidence is not being searched for
    one escalation lowered repeatedly  its trigger or threshold is too eager
    overrides cluster in one area      area knowledge is missing: team config, not rubric
    overrides cluster on one reviewer  a policy disagreement: escalate, do not tune

It suggests; it never edits the rubric, the taxonomy or a config. A suggestion needs
`--min-overrides` overrides of the same kind (default 3) that are at least
`--min-rate` of the reviewed runs they apply to (default 30 percent).

`dashboard` writes one self-contained HTML page with tabs: Overview, Dispositions,
Priority, Trend, Calibration, Runs. No script, no network: the tabs are CSS.
"""
import html, json, os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

DISPOSITIONS = ["defect", "expected_behavior", "config_or_data", "duplicate",
                "voice_of_customer", "insufficient_information"]
LEVELS = ["P1", "P2", "P3", "P4"]
MARK = {"P1": "🔴", "P2": "🟠", "P3": "🟡", "P4": "🔵"}

# Where to look when an escalation keeps being lowered. Keys are the escalation class,
# the part before the colon in the log (release:confirmed_regression -> release).
ESCALATION_KNOBS = {
    "release": "regression.spike_ratio and regression.deploy_window_hours in the team config",
    "history": "what counts toward component history (fixed defects only) and its threshold in the rubric",
    "code": "which code signals count as a fault in the data-sources contract",
    "at_risk": "tracker.at_risk_labels in the team config: a label may be too broad",
    "blast": "the warehouse query templates in the team config",
    "enterprise": "how the warehouse query identifies an enterprise account",
}


def resolve_log(explicit):
    if explicit:
        return os.path.abspath(os.path.expanduser(explicit))
    env = os.environ.get("CLAUDE_TRIAGE_LOG")
    if env:
        return os.path.abspath(os.path.expanduser(env))
    return os.path.join(os.getcwd(), "triage-logs", "triage-log.jsonl")


def load(a):
    path = resolve_log(getattr(a, "log", None))
    rows = []
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    cutoff = (datetime.now(timezone.utc) - timedelta(days=a.days)).isoformat()
    rows = [r for r in rows if r.get("ts", "") >= cutoff]
    if getattr(a, "team", None):
        rows = [r for r in rows if r.get("team") == a.team]
    return path, rows


def reviewed(rows):
    return [r for r in rows if r.get("human_override")]


def _gap(r):
    try:
        return LEVELS.index(r["override_priority"]) - LEVELS.index(r["priority"])
    except (ValueError, KeyError, TypeError):
        return None


def _reasons(rs, n=2):
    c = Counter((r.get("override_reason") or "").strip() for r in rs if r.get("override_reason"))
    return [f"“{k}” ×{v}" if v > 1 else f"“{k}”" for k, v in c.most_common(n)]


# ------------------------------------------------------------------ analysis

def stats(rows):
    rev = reviewed(rows)
    disp = {}
    for d in DISPOSITIONS:
        sub = [r for r in rev if r.get("disposition") == d]
        if sub:
            ok = sum(1 for r in sub if r.get("override_disposition") == d)
            disp[d] = (ok, len(sub))
    matrix = defaultdict(Counter)
    for r in rev:
        matrix[r.get("disposition")][r.get("override_disposition")] += 1
    pr = [r for r in rev if r.get("disposition") == "defect" and r.get("override_disposition") == "defect"
          and r.get("priority") and r.get("override_priority")]
    gaps = [g for g in (_gap(r) for r in pr) if g is not None]
    agree = sum(1 for r in rev if r.get("override_disposition") == r.get("disposition")
                and (r.get("override_priority") or None) == (r.get("priority") or None))
    return {"runs": len(rows), "reviewed": len(rev), "agree": agree, "disp": disp, "matrix": matrix,
            "prio_n": len(gaps), "exact": sum(1 for g in gaps if g == 0),
            "within": sum(1 for g in gaps if abs(g) <= 1),
            "too_high": sum(1 for g in gaps if g > 0), "too_low": sum(1 for g in gaps if g < 0)}


def suggestions(rows, min_n=3, min_rate=0.3):
    """[(kind, title, detail, action)] ordered by how many overrides back each one."""
    rev = reviewed(rows)
    out = []
    for d in DISPOSITIONS:
        said = [r for r in rev if r.get("disposition") == d]
        wrong = [r for r in said if r.get("override_disposition") != d]
        if len(wrong) >= min_n and len(wrong) / len(said) >= min_rate:
            to = Counter(r.get("override_disposition") for r in wrong).most_common(1)[0][0]
            out.append((len(wrong), "over-applied", f"`{d}` is over-applied",
                        f"People changed it in {len(wrong)} of {len(said)} reviewed runs, most often to `{to}`. "
                        + " ".join(_reasons(wrong)),
                        f"Tighten `{d}` in the disposition taxonomy: name the evidence it must have, and "
                        f"what separates it from `{to}`."))
        missed = [r for r in rev if r.get("override_disposition") == d and r.get("disposition") != d]
        base = [r for r in rev if r.get("override_disposition") == d]
        if len(missed) >= min_n and len(missed) / len(base) >= min_rate:
            frm = Counter(r.get("disposition") for r in missed).most_common(1)[0][0]
            out.append((len(missed), "missed", f"`{d}` is missed",
                        f"People chose `{d}` {len(missed)} times where the agent said `{frm}`. "
                        + " ".join(_reasons(missed)),
                        f"Add a search step to the disposition procedure for the evidence that shows `{d}`."))

    pr = [r for r in rev if r.get("disposition") == "defect" and r.get("override_disposition") == "defect"
          and r.get("priority") and r.get("override_priority")]
    classes = defaultdict(list)
    for r in pr:
        for e in r.get("escalations") or []:
            classes[e.split(":", 1)[0]].append(r)
    for cls, rs in sorted(classes.items()):
        lowered = [r for r in rs if (_gap(r) or 0) > 0]
        if len(lowered) >= min_n and len(lowered) / len(rs) >= min_rate:
            out.append((len(lowered), "escalation", f"`+1 {cls}` fires too easily",
                        f"Priority was lowered in {len(lowered)} of {len(rs)} reviewed runs where it applied. "
                        + " ".join(_reasons(lowered)),
                        "Check " + ESCALATION_KNOBS.get(cls, f"the `{cls}` escalation rule in the priority rubric") + "."))
    gaps = [(_gap(r), r) for r in pr if _gap(r)]
    hi = [r for g, r in gaps if g > 0]
    lo = [r for g, r in gaps if g < 0]
    if len(lo) >= min_n and len(lo) >= 2 * max(1, len(hi)):
        out.append((len(lo), "priority", "Priorities are too low",
                    f"People raised the priority {len(lo)} times and lowered it {len(hi)} times. "
                    + " ".join(_reasons(lo)),
                    "Look for a signal the rubric does not read (a customer tier, a contract term) and "
                    "add it as a source or a config value, not a manual bump."))

    changed = [r for r in rev if r.get("override_disposition") != r.get("disposition")
               or r.get("override_priority") != r.get("priority")]
    if changed:
        areas = Counter(r.get("area") for r in changed if r.get("area"))
        if areas:
            area, n = areas.most_common(1)[0]
            if n >= min_n and n / len(changed) >= 0.5:
                out.append((n, "area", f"Overrides cluster in `{area}`",
                            f"{n} of {len(changed)} overrides are in this area.",
                            f"Add what the team knows about `{area}` to the team config (routing, key paths, "
                            "at-risk labels), not to the shared rubric."))
        # One reviewer disagreeing far more often than the rest is a policy question, not a
        # rubric one. Compare each reviewer's override rate with everyone else's.
        by = defaultdict(list)
        for r in rev:
            if r.get("override_by"):
                by[r["override_by"]].append(r in changed)
        for person, marks in by.items():
            rest = [m for p2, ms in by.items() if p2 != person for m in ms]
            n, rate = sum(marks), sum(marks) / len(marks)
            rest_rate = sum(rest) / len(rest) if rest else None
            if n >= min_n and rest_rate is not None and len(rest) >= min_n and rate >= 2 * max(rest_rate, 0.05):
                out.append((n, "reviewer", "One reviewer overrides far more than the others",
                            f"One reviewer changed {n} of {len(marks)} runs they reviewed ({int(rate * 100)}%); "
                            f"the others changed {int(rest_rate * 100)}%.",
                            "This looks like a policy disagreement. Settle the policy with the team; do not "
                            "tune the agent toward one reviewer."))
    out.sort(key=lambda x: -x[0])
    return [x[1:] for x in out]


# ------------------------------------------------------------------ calibrate

def cmd_calibrate(a):
    path, rows = load(a)
    rev = reviewed(rows)
    print(f"**Calibration** · last {a.days} days · {len(rows)} runs, {len(rev)} reviewed · `{path}`")
    print()
    if not rev:
        print("Nothing has been reviewed, so there is nothing to calibrate against. Record "
              "agreements and corrections with `/bug-triage-agent:triage-review`.")
        return 0
    sug = suggestions(rows, a.min_overrides, a.min_rate)
    if not sug:
        print(f"No repeated pattern: no kind of override reached {a.min_overrides} occurrences "
              f"and {int(a.min_rate * 100)}% of the runs it applies to. Nothing to change yet.")
    for i, (kind, title, detail, action) in enumerate(sug, 1):
        print(f"{i}. **{title}.** {detail}")
        print(f"   - **Suggested change:** {action}")
    if len(rev) < 10:
        print()
        print(f"> ⚠️ Only {len(rev)} reviewed runs. Treat any pattern here as a lead, not a finding.")
    print()
    print("Suggestions only. Nothing is edited. Rubric and taxonomy changes go through review "
          "like code; config changes through `/bug-triage-agent:triage-config`.")
    return 0


# ------------------------------------------------------------------ dashboard

CSS = """
:root{--bg:#F3F5F4;--surface:#FFFFFF;--ink:#17201C;--muted:#56645E;--rule:#C9D2CE;--accent:#0B7A69;
--accent-soft:#DCEFEA;--signal:#B4502A;--signal-soft:#F7E5DC;--p4:#2E6BC0}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--bg:#0F1412;
--surface:#161E1B;--ink:#E3EAE7;--muted:#96A49E;--rule:#2C3733;--accent:#3CC0A7;--accent-soft:#12302A;
--signal:#E58B60;--signal-soft:#36221A;--p4:#72A5EE}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:980px;margin:0 auto;padding:28px 16px 56px}
h1{font-size:clamp(22px,4vw,28px);margin:0 0 6px}.muted{color:var(--muted)}
.banner{border:1px solid var(--signal);background:var(--signal-soft);border-radius:6px;padding:8px 12px;margin:12px 0}
.tabs input{position:absolute;opacity:0;pointer-events:none}
.tabs label{display:inline-block;padding:8px 14px;border:1px solid var(--rule);border-bottom:none;
border-radius:6px 6px 0 0;margin-right:4px;cursor:pointer;background:var(--bg);font-weight:600;font-size:14px}
.tabs input:checked+label{background:var(--surface);color:var(--accent)}
.tabs input:focus-visible+label{outline:2px solid var(--accent)}
.panel{display:none;background:var(--surface);border:1px solid var(--rule);border-radius:0 8px 8px 8px;padding:18px}
#t1:checked~#p1,#t2:checked~#p2,#t3:checked~#p3,#t4:checked~#p4,#t5:checked~#p5,#t6:checked~#p6{display:block}
.kpis{display:flex;flex-wrap:wrap;gap:12px}.kpi{flex:1 1 150px;border:1px solid var(--rule);border-radius:8px;padding:12px}
.kpi b{display:block;font-size:26px}.kpi span{color:var(--muted);font-size:13px}
.tbl{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px;margin:8px 0}
th,td{text-align:left;padding:7px 10px 7px 0;border-bottom:1px solid var(--rule);vertical-align:top}
th{font:500 11px ui-monospace,Menlo,monospace;letter-spacing:.05em;text-transform:uppercase;color:var(--muted)}
td.n{text-align:right;font-variant-numeric:tabular-nums}.hit{background:var(--accent-soft);font-weight:600}
.miss{background:var(--signal-soft)}
.bar{height:10px;border-radius:5px;background:var(--rule);overflow:hidden;min-width:120px}
.bar i{display:block;height:100%;background:var(--accent)}
.sug{border-left:4px solid var(--signal);padding:8px 12px;margin:10px 0;background:var(--signal-soft);border-radius:0 6px 6px 0}
.sug p{margin:4px 0}code{font:13px ui-monospace,Menlo,monospace}
footer{margin-top:28px;font-size:12.5px;color:var(--muted)}
"""


def _e(v):
    return html.escape("" if v is None else str(v))


def _pct(a, b):
    return f"{100 * a // b}%" if b else "—"


def _bar(a, b):
    w = 100 * a / b if b else 0
    return f'<div class="bar" role="img" aria-label="{_pct(a, b)}"><i style="width:{w:.0f}%"></i></div>'


def _md_code(s):
    import re
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", _e(s))


def cmd_dashboard(a):
    path, rows = load(a)
    st = stats(rows)
    rev = reviewed(rows)
    fixture = any("fixture" in (r.get("modes") or {}).values() for r in rows)
    now = datetime.now(timezone.utc)
    o = ['<meta charset="utf-8">', '<meta name="viewport" content="width=device-width, initial-scale=1">',
         "<title>Triage accuracy</title>", f"<style>{CSS}</style>", '<div class="wrap">',
         "<h1>Triage accuracy</h1>",
         f'<p class="muted">Last {a.days} days' + (f" · team {_e(a.team)}" if a.team else "")
         + f" · {st['runs']} runs · {st['reviewed']} reviewed · generated {now:%Y-%m-%d %H:%M} UTC</p>"]
    if fixture:
        o.append('<div class="banner"><strong>Includes demo runs.</strong> Some runs read fixtures, '
                 "not live systems.</div>")
    if st["reviewed"] < 10:
        o.append(f'<div class="banner">Only {st["reviewed"]} reviewed runs. Rates below are early '
                 "signals, not measurements.</div>")
    tabs = ["Overview", "Dispositions", "Priority", "Trend", "Calibration", "Runs"]
    o.append('<div class="tabs">')
    for i, t in enumerate(tabs, 1):
        o.append(f'<input type="radio" name="tab" id="t{i}"{" checked" if i == 1 else ""}>'
                 f'<label for="t{i}">{t}</label>')

    # Overview
    o.append('<section class="panel" id="p1"><div class="kpis">')
    for val, lab in ((_pct(st["agree"], st["reviewed"]), "fully agreed (disposition and priority)"),
                     (f"{st['reviewed']}/{st['runs']}", "runs reviewed by a person"),
                     (_pct(st["exact"], st["prio_n"]), "priority exact"),
                     (_pct(st["within"], st["prio_n"]), "priority within one level")):
        o.append(f'<div class="kpi"><b>{val}</b><span>{lab}</span></div>')
    o.append("</div>")
    if st["reviewed"] < st["runs"]:
        o.append(f'<p class="muted">{st["runs"] - st["reviewed"]} runs have no review. Unreviewed runs '
                 "measure volume, not correctness.</p>")
    o.append("<h3>Agreement by disposition</h3><div class='tbl'><table><thead><tr><th>Agent said</th>"
             "<th>Agreed</th><th></th><th>Rate</th></tr></thead><tbody>")
    for d, (ok, n) in st["disp"].items():
        o.append(f"<tr><td><code>{d}</code></td><td class='n'>{ok}/{n}</td><td>{_bar(ok, n)}</td>"
                 f"<td class='n'>{_pct(ok, n)}</td></tr>")
    o.append("</tbody></table></div><p class='muted'>Target before go-live: no class below 70%.</p></section>")

    # Dispositions: confusion matrix
    cols = [d for d in DISPOSITIONS if any(st["matrix"][x][d] for x in st["matrix"])]
    rows_d = [d for d in DISPOSITIONS if st["matrix"].get(d)]
    o.append('<section class="panel" id="p2"><p>Rows: what the agent said. Columns: what a person '
             "decided.</p><div class='tbl'><table><thead><tr><th>Agent ↓ / person →</th>"
             + "".join(f"<th>{_e(c)}</th>" for c in cols) + "</tr></thead><tbody>")
    for d in rows_d:
        cells = []
        for c in cols:
            n = st["matrix"][d][c]
            cls = "hit" if c == d and n else ("miss" if n else "")
            cells.append(f'<td class="n {cls}">{n or ""}</td>')
        o.append(f"<tr><th><code>{d}</code></th>{''.join(cells)}</tr>")
    o.append("</tbody></table></div></section>")

    # Priority
    o.append('<section class="panel" id="p3">')
    o.append(f"<p>{st['prio_n']} reviewed defects with both priorities. Agent higher than the person: "
             f"<strong>{st['too_high']}</strong>. Lower: <strong>{st['too_low']}</strong>.</p>")
    grid = defaultdict(Counter)
    for r in rev:
        if r.get("priority") and r.get("override_priority") and r.get("override_disposition") == "defect":
            grid[r["priority"]][r["override_priority"]] += 1
    o.append("<div class='tbl'><table><thead><tr><th>Agent ↓ / person →</th>"
             + "".join(f"<th>{MARK[p]} {p}</th>" for p in LEVELS) + "</tr></thead><tbody>")
    for p in LEVELS:
        if grid.get(p):
            o.append(f"<tr><th>{MARK[p]} {p}</th>" + "".join(
                f'<td class="n {"hit" if q == p and grid[p][q] else ("miss" if grid[p][q] else "")}">'
                f'{grid[p][q] or ""}</td>' for q in LEVELS) + "</tr>")
    o.append("</tbody></table></div><h3>By escalation</h3><div class='tbl'><table><thead><tr><th>Escalation</th>"
             "<th>Applied</th><th>Priority kept</th><th>Lowered</th><th>Raised</th></tr></thead><tbody>")
    cl = defaultdict(list)
    for r in rev:
        if r.get("priority") and r.get("override_priority"):
            for e in r.get("escalations") or []:
                cl[e.split(":", 1)[0]].append(_gap(r) or 0)
    for c, gs in sorted(cl.items()):
        o.append(f"<tr><td><code>+1 {_e(c)}</code></td><td class='n'>{len(gs)}</td>"
                 f"<td class='n'>{sum(1 for g in gs if g == 0)}</td><td class='n'>{sum(1 for g in gs if g > 0)}</td>"
                 f"<td class='n'>{sum(1 for g in gs if g < 0)}</td></tr>")
    o.append("</tbody></table></div></section>")

    # Trend by ISO week
    weeks = defaultdict(lambda: [0, 0, 0])
    for r in rows:
        try:
            d = datetime.fromisoformat(r["ts"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        k = f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}"
        weeks[k][0] += 1
        if r.get("human_override"):
            weeks[k][1] += 1
            if r.get("override_disposition") == r.get("disposition") and \
                    (r.get("override_priority") or None) == (r.get("priority") or None):
                weeks[k][2] += 1
    o.append('<section class="panel" id="p4"><div class="tbl"><table><thead><tr><th>Week</th><th>Runs</th>'
             "<th>Reviewed</th><th>Agreed</th><th></th></tr></thead><tbody>")
    for k in sorted(weeks):
        n, rv, ok = weeks[k]
        o.append(f"<tr><td>{k}</td><td class='n'>{n}</td><td class='n'>{rv}</td>"
                 f"<td class='n'>{_pct(ok, rv)}</td><td>{_bar(ok, rv)}</td></tr>")
    o.append("</tbody></table></div><p class='muted'>Agreement should rise as calibration suggestions "
             "are applied. A fall after a rubric change means the change made things worse.</p></section>")

    # Calibration
    sug = suggestions(rows, a.min_overrides, a.min_rate)
    o.append('<section class="panel" id="p5">')
    if not sug:
        o.append(f"<p>No repeated pattern yet: no kind of override reached {a.min_overrides} occurrences "
                 f"and {int(a.min_rate * 100)}% of the runs it applies to.</p>")
    for kind, title, detail, action in sug:
        o.append(f'<div class="sug"><p><strong>{_md_code(title)}</strong></p><p>{_md_code(detail)}</p>'
                 f"<p><strong>Suggested change:</strong> {_md_code(action)}</p></div>")
    o.append("<p class='muted'>Suggestions only. Nothing is edited automatically.</p></section>")

    # Runs
    o.append('<section class="panel" id="p6"><div class="tbl"><table><thead><tr><th>When</th><th>Ticket</th>'
             "<th>Agent</th><th>Person</th><th>Reason</th></tr></thead><tbody>")
    for r in sorted(rows, key=lambda x: x.get("ts", ""), reverse=True)[:200]:
        ag = f"{r.get('disposition')} {r.get('priority') or ''}".strip()
        hu = f"{r.get('override_disposition')} {r.get('override_priority') or ''}".strip() \
            if r.get("human_override") else "—"
        cls = "" if hu in ("—", ag) else ' class="miss"'
        o.append(f"<tr{cls}><td>{_e(r.get('ts', '')[:16].replace('T', ' '))}</td><td>{_e(r.get('ticket'))}</td>"
                 f"<td>{_e(ag)}</td><td>{_e(hu)}</td><td>{_e(r.get('override_reason') or '')}</td></tr>")
    o.append("</tbody></table></div></section>")
    o.append("</div>")
    o.append(f"<footer>Generated by <code>scripts/triage_log.py dashboard</code> from "
             f"<code>{_e(os.path.basename(path))}</code>. Reads the local log only.</footer></div>")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("\n".join(o))
    print(f"wrote {a.out} ({st['runs']} runs, {st['reviewed']} reviewed, {len(sug)} suggestion(s))")
    return 0
