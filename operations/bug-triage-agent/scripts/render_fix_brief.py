#!/usr/bin/env python3
"""Turn a triaged defect into a brief a coding agent can act on, and rate the evidence.

Two jobs, one source of truth:

  assess(result)   rates how well the evidence locates the bug: strong, moderate or
                   weak. The triage report, the run trace and the fix brief all show
                   this same verdict, so they cannot disagree about it.
  render(result)   writes <TICKET>.fix-brief.md: structured front matter a fixer can
                   parse, then problem, repro, where to look, the hypothesis to test,
                   the definition of done, constraints, unknowns and PR text.

Usage:
    python3 scripts/render_fix_brief.py --out <dir> <dir>/<TICKET>.result.json
    python3 scripts/render_fix_brief.py --assess <dir>/<TICKET>.result.json   # verdict only

Only defects get a brief. A non-defect handed to a fixer is the failure the
disposition gate exists to prevent, so the script refuses (exit 1) rather than
writing one.

Priority confidence and location evidence are different questions. Confidence says
how sure the priority is. Evidence says how sure we are *where* the fault is. A P2
with high confidence can still have weak evidence about which file to change.
"""
import argparse, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import links  # noqa: E402
import summary as S  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_trace import validate as validate_result  # noqa: E402

CODE_SIGNALS = {"error_swallowing", "stub", "suppressed_type_error"}
FILE_SIGNALS = CODE_SIGNALS | {"release_touched", "prior_fix_file"}


def assess(r):
    """Return {level, reasons, missing, caution}. Deterministic: same input, same verdict."""
    locs = r.get("locations") or []
    with_file = [l for l in locs if l.get("path")]
    code_mode = (r.get("sources", {}).get("code") or {}).get("mode", "off")

    # Signals only corroborate each other when they point at the SAME file. A fault in
    # one file and a release that touched another is two weak leads, not one strong one.
    by_file = {}
    for l in with_file:
        s = by_file.setdefault(l["path"], {"code": False, "line": False, "release": False, "prior": False})
        sig = l.get("signal")
        if sig in CODE_SIGNALS:
            s["code"] = True
            s["line"] = s["line"] or bool(l.get("line"))
        elif sig == "release_touched":
            s["release"] = True
        elif sig == "prior_fix_file":
            s["prior"] = True

    def grade(s):
        if s["code"] and s["line"] and (s["release"] or s["prior"]):
            return 3                                   # strong
        if s["code"] or (s["release"] and s["prior"]):
            return 2                                   # moderate
        return 1                                       # weak
    best_path, best = max(((p, grade(s)) for p, s in by_file.items()),
                          key=lambda x: x[1], default=(None, 1))
    level = {3: "strong", 2: "moderate", 1: "weak"}[best]
    top = by_file.get(best_path, {})
    code_hit = any(s["code"] for s in by_file.values())

    reasons, missing = [], []
    if top.get("code"):
        reasons.append(f"code search found a fault signal in {best_path}")
    if top.get("release"):
        reasons.append(f"the correlated release changed {best_path}")
    if top.get("prior"):
        reasons.append(f"a prior fix for the same failure touched {best_path}")
    if len(by_file) > 1 and best < 3:
        missing.append("signals point at different files and do not corroborate each other")

    if code_mode == "off":
        missing.append("code search was off, so no file or line was checked for a fault signal")
    elif not code_hit:
        missing.append("code search ran and found no fault signal at any candidate location")
    if not with_file:
        missing.append("no candidate file was identified; only the component or area is known")
    if with_file and not (top.get("release") or top.get("prior")):
        missing.append("no release or prior fix ties the candidate file to this failure")
    if best == 1 and best_path and (top.get("release") or top.get("prior")):
        link = "a release record" if top.get("release") else "a prior fix"
        missing.append(f"the only link to {best_path} is {link}, which ties it by area, "
                       "not by a fault found in the code")
    if r.get("confidence") == "low":
        missing.append("priority confidence is low")
    # Unanswered rubric questions (blast radius, enterprise tier) say nothing about where
    # the fault is, so they are listed under "Not checked", not in the location verdict.

    caution = None
    if level != "strong":
        caution = ("Evidence for where this bug lives is **" + level + "**. "
                   "Confirm the location before changing code. If it cannot be confirmed, "
                   "report back rather than opening a pull request against a guess.")
    return {"level": level, "reasons": reasons, "missing": missing, "caution": caution}


def slug(s, n=40):
    """Branch-safe, cut at a word boundary so it never ends mid-word."""
    words, out = re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).split(), []
    for w in words:
        if len("-".join(out + [w])) > n:
            break
        out.append(w)
    return "-".join(out) or "fix"


def yq(v):
    """Quote a scalar for the front matter without a YAML library."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    s = str(v)
    return json.dumps(s, ensure_ascii=False) if re.search(r"[:#\-\[\]{}&*!|>'\"%@`,]|^\s|\s$", s) else s


def render(r):
    ev = assess(r)
    t = r["ticket"]
    repo = r.get("repo") or {}
    locs = r.get("locations") or []
    files = [f"{l['path']}:{l['line']}" if l.get("line") else l["path"] for l in locs if l.get("path")]
    branch = f"fix/{t.lower()}-{slug(r.get('summary'))}"
    repro = r.get("repro") or {}
    hyp = r.get("hypothesis") or {}

    fm = ["---",
          f"ticket: {yq(t)}",
          f"title: {yq(r.get('summary'))}",
          f"team: {yq(r.get('team'))}",
          f"repo: {yq(repo.get('name'))}",
          f"base_branch: {yq(repo.get('base_branch'))}",
          f"branch: {yq(branch)}",
          f"priority: {yq(r.get('priority'))}",
          f"priority_confidence: {yq(r.get('confidence'))}",
          f"evidence: {ev['level']}",
          f"location_confirmed: {yq(ev['level'] == 'strong')}",
          "candidate_files:" + ("" if files else " []")]
    fm += [f"  - {yq(f)}" for f in files]
    fm += [f"route_to: {yq(r.get('route'))}",
           f"generated_by: {yq('bug-triage-agent ' + str(r.get('agent_version', '')))}",
           "---", ""]

    o = fm + [f"# Fix brief · {links.md(t, r.get('ticket_url'))} · {r.get('summary', '')}", ""]
    if ev["caution"]:
        o += links.callout("caution", ev["caution"])
        for m in ev["missing"]:
            o.append(f"> - {m}")
        o.append("")

    corr = S.corroboration(r)
    if corr:
        o += ["**Supported by:** " + " · ".join(f"{c['source']} {links.md(c['label'], c['url'])}" for c in corr), ""]
    _, stale = S.freshness(r)
    if stale:
        o += links.callout("warning", "**Stale data.** " + "; ".join(stale) + ". Re-check before acting.") + [""]

    o += ["This brief was produced by triage, not by reading the fix. Treat every location "
          "and cause below as a lead to verify, not a finding.", ""]

    o += ["## Problem", ""]
    if repro.get("expected") or repro.get("actual"):
        o += [f"- **Expected:** {repro.get('expected', 'not stated in the ticket')}",
              f"- **Actual:** {repro.get('actual', 'not stated in the ticket')}", ""]
    else:
        o += ["Expected and actual behaviour were not separable from the ticket text. "
              "Read the ticket before starting.", ""]

    o += ["## Reproduce", ""]
    steps = repro.get("steps") or []
    o += ([f"{i}. {s}" for i, s in enumerate(steps, 1)] if steps else
          ["No reproduction steps in the ticket. Establish one before changing code."])
    o.append("")

    cr = [u for u in (r.get("comment_review") or {}).get("used") or []
          if u.get("category") in ("detail", "workaround_tried")]
    if cr:
        o += ["From the ticket's comments:", ""]
        o += [f"- {'Tried already' if u['category'] == 'workaround_tried' else 'Detail'}: “{u['quote']}”" for u in cr]
        o.append("")

    o += ["## Where to look", ""]
    if locs:
        o += ["| # | Location | Signal | Evidence | From |", "| --- | --- | --- | --- | --- |"]
        for i, l in enumerate(locs, 1):
            if l.get("path"):
                # Short label, link behind it; the full path is in candidate_files above.
                where = links.md_code(links.location_label(l), l.get("url"))
            else:
                where = l.get("area") or "—"
            o.append(f"| {i} | {where} | `{l.get('signal', '—')}` | "
                     f"{(l.get('evidence') or '').replace('|', '/')} | {l.get('source', '—')} |")
    else:
        o.append("No candidate location. Start from the affected component and the release below.")
    intro = r.get("introduced_by") or {}
    if intro:
        o += ["", f"Likely introduced by release **{links.md(intro.get('release', '?'), intro.get('release_url'))}**"
                  + (f", PR {links.md(intro['pr'], intro.get('pr_url'))}" if intro.get("pr") else "")
                  + ". Read that diff first."]
    extra = [links.md(x.get("label"), x.get("url")) for x in r.get("links") or [] if x.get("label")]
    if extra:
        o += ["", "Evidence: " + " · ".join(extra)]
    o.append("")
    import timeline as TL
    o += TL.md(r)

    prior = r.get("prior_fixes") or []
    if prior:
        o += ["## Prior fixes in this area", ""]
        o += [f"- **{links.md(p.get('key'), p.get('url'))}**: {p.get('summary', '')}. {p.get('note', '')}".rstrip()
              for p in prior]
        o += ["", "A regression of an earlier fix usually means that fix's test did not "
                  "cover this path. Check it.", ""]

    o += ["## Hypothesis to test", ""]
    if hyp.get("statement"):
        o += [f"**{hyp['statement']}**", "",
              f"- Confirmed if: {hyp.get('confirm_by', 'not stated')}",
              f"- Refuted if: {hyp.get('refute_by', 'not stated')}", "",
              "This is a hypothesis. If the test refutes it, stop and report what you found "
              "instead of fixing somewhere else.", ""]
    else:
        o += ["No cause was hypothesised. Diagnose before fixing.", ""]

    o += ["## Definition of done", ""]
    acc = r.get("acceptance") or []
    if not acc:
        acc = ["A test that reproduces the failure above, failing before the change",
               "The same test passing after the change",
               "The existing test suite passing"]
        wa = r.get("workaround") or {}
        if wa.get("text"):
            acc.append(f"The path the workaround relies on still works: {wa['text']}")
            import verify_workaround as V
            if V.line(wa):
                acc.append("Workaround check from triage: " + V.md_line(wa))
    o += [f"- [ ] {a}" for a in acc] + [""]

    o += ["## Constraints", "",
          "- Keep the change to the fault. No drive-by refactors in the same PR.",
          "- Do not change a public API contract or response shape without calling it out "
          "in the PR description.",
          "- Do not comment on, transition or edit the ticket. The PR links to it; a person "
          "updates the tracker.",
          f"- Branch from `{repo.get('base_branch') or 'the default branch'}` as `{branch}`."]
    o += [f"- {c}" for c in r.get("constraints") or []] + [""]

    unk = ev["missing"] + [f"unanswered: {u}" for u in r.get("unanswered") or []]
    if unk:
        o += ["## Not checked by triage", ""] + [f"- {m}" for m in unk] + [""]

    o += ["## Pull request", "",
          f"**Title:** `{t}: {r.get('summary', '')}`", "", "**Body:**", "", "```markdown",
          f"Fixes {t}.", "",
          "## Cause", "<what the fault was, and how you confirmed it>", "",
          "## Change", "<what changed and why this is the minimal fix>", "",
          "## Tests", "<the test that failed before and passes now>", "",
          f"Triage: {r.get('priority') or '-'} · evidence {ev['level']} · "
          f"generated by bug-triage-agent {r.get('agent_version', '')}",
          "```", ""]
    return "\n".join(o)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="+")
    ap.add_argument("--out", help="directory; default next to each result")
    ap.add_argument("--assess", action="store_true", help="print the evidence verdict as JSON only")
    ap.add_argument("--team-config", help="team config; fills evidence links from its `links` templates")
    a = ap.parse_args()

    failed = 0
    for path in a.results:
        with open(path, encoding="utf-8") as f:
            r = json.load(f)
        if a.team_config:
            with open(a.team_config, encoding="utf-8") as cf:
                links.enrich(r, json.load(cf))
        problems = validate_result(r)
        if problems:
            print(f"{path}: invalid result: " + "; ".join(problems), file=sys.stderr)
            failed += 1
            continue
        if a.assess:
            print(json.dumps({"ticket": r["ticket"], **assess(r)}, ensure_ascii=False))
            continue
        if r.get("disposition") != "defect":
            print(f"{path}: refusing: {r['ticket']} is `{r.get('disposition')}`, not a defect. "
                  "Only defects go to a fixer.", file=sys.stderr)
            failed += 1
            continue
        out_dir = a.out or os.path.dirname(os.path.abspath(path))
        os.makedirs(out_dir, exist_ok=True)
        dest = os.path.join(out_dir, f"{r['ticket']}.fix-brief.md")
        with open(dest, "w", encoding="utf-8") as f:
            f.write(render(r))
        print(f"wrote {dest} (evidence {assess(r)['level']})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
