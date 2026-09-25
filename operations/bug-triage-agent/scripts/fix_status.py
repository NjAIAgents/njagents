#!/usr/bin/env python3
"""Is this bug already fixed? Decide from commits, releases and deploys, not from wording.

An open ticket whose fix is already merged should not be scored and queued like a live
bug. The question for it is different: has the fix reached the customer? So before the
priority means anything, the triage looks for a fix.

The releases source returns candidate commits on the default branch since the ticket was
created (or since the release that introduced the bug): commits that name the ticket,
and commits that touch the files the triage located. This script grades them:

    python3 scripts/fix_status.py --result <TICKET>.result.json --releases <releases envelope.json> \\
        --tracker <tracker envelope.json>

and prints a `fix_status` block for the result file:

    {"state": "open|fixed_on_main|released|deployed",
     "confidence": "strong|moderate",          # only when a fix was found
     "commit": {"sha", "message", "date", "url", "pr"},
     "in_release": "2026.10" | null,
     "deployed": {"environment", "at", "url"} | null,
     "candidates": [...],                      # commits that might be related, not claimed
     "searched": "..."}

How a commit is graded:
    strong     its message names the ticket key
    moderate   it touches a located file, after the ticket was created, and its message
               shares the failure (the error text, or two or more words of the symptom)
    candidate  it only touches a located file: listed, never claimed as the fix

A fix is claimed only on strong or moderate. Priority is still computed, as the priority
the bug has while it is still live, but the next action becomes getting the fix to the
customer, not fixing it again.
"""
import argparse, json, re, sys

STATES = ("open", "fixed_on_main", "released", "deployed")
FAULT_SIGNALS = {"error_swallowing", "stub", "suppressed_type_error"}
STOP = set("the a an and or of to in on for with when is are was not no be by it this that from "
           "fix fixes fixed bug issue error errors update change changes handle handling add remove".split())


def _t(v):
    import summary as S
    return S._parse(v)


def _words(s):
    return {w for w in re.findall(r"[a-z][a-z0-9_]{2,}", (s or "").lower()) if w not in STOP}


def grade(commit, ticket_key, files, created, symptom, errors):
    msg = commit.get("message") or ""
    if ticket_key and re.search(rf"\b{re.escape(ticket_key)}\b", msg, re.I):
        return "strong", f"message names {ticket_key}"
    touched = {f.rsplit('/', 1)[-1] for f in commit.get("files") or []}
    located = {f.rsplit('/', 1)[-1] for f in files}
    hits = touched & located
    if not hits:
        return None, None
    when = _t(commit.get("date"))
    after = created is None or when is None or when >= created
    shared = _words(msg) & symptom
    err_hit = any(e and e.lower() in msg.lower() for e in errors)
    if after and (err_hit or len(shared) >= 2):
        why = "names the error" if err_hit else "shares " + ", ".join(sorted(shared)[:3])
        return "moderate", f"touches {', '.join(sorted(hits))} after the ticket was filed and {why}"
    return "candidate", f"touches {', '.join(sorted(hits))}"


def assess(result, releases_env, ticket=None):
    data = releases_env.get("data", releases_env)
    ticket = ticket or {}
    commits = data.get("commits_since") or []
    key = result.get("ticket")
    files = [l["path"] for l in result.get("locations") or [] if l.get("path")]
    created = _t(result.get("ticket_created") or ticket.get("created"))
    symptom = _words(result.get("summary")) | _words((result.get("repro") or {}).get("actual"))
    errors = [e for e in result.get("error_text") or [] if e]
    # A fault the code source still sees at HEAD cannot have been fixed by a commit that
    # touched that file: the change is in the history, the fault is still there.
    still_faulty = {l["path"].rsplit("/", 1)[-1] for l in result.get("locations") or []
                    if l.get("path") and l.get("source") == "code" and l.get("signal") in FAULT_SIGNALS}
    graded = []
    for c in commits:
        level, why = grade(c, key, files, created, symptom, errors)
        if level in ("strong", "moderate"):
            hit = still_faulty & {f.rsplit("/", 1)[-1] for f in c.get("files") or []}
            if hit:
                level, why = "candidate", f"{why}, but the fault is still present in {', '.join(sorted(hit))} on the default branch"
        if level:
            graded.append((level, why, c))
    order = {"strong": 0, "moderate": 1, "candidate": 2}
    graded.sort(key=lambda g: (order[g[0]], -(_t(g[2].get("date")).timestamp() if _t(g[2].get("date")) else 0)))
    fix = next((g for g in graded if g[0] in ("strong", "moderate")), None)
    out = {"state": "open", "searched": f"{len(commits)} commit(s) on the default branch"
                                       + (f" since {data.get('commits_since_from')}" if data.get("commits_since_from") else "")}
    cands = [{"sha": c.get("sha", "")[:10], "message": (c.get("message") or "").splitlines()[0][:120],
              "why": why, "url": c.get("url")} for lvl, why, c in graded if lvl == "candidate" or (fix and c is not fix[2])]
    if cands:
        out["candidates"] = cands[:5]
    if not fix:
        return out
    level, why, c = fix
    sha = c.get("sha", "")
    out.update({"confidence": level, "why": why,
                "commit": {k: v for k, v in {"sha": sha, "message": (c.get("message") or "").splitlines()[0][:160],
                                             "date": c.get("date"), "url": c.get("url"), "pr": c.get("pr"),
                                             "files": c.get("files")}.items() if v}})
    rel = next((r for r in data.get("releases") or [] if sha and any(
        str(x).startswith(sha[:7]) or sha.startswith(str(x)[:7]) for x in r.get("commits") or [])), None)
    dep = next((d for d in data.get("deploys") or [] if sha and any(
        str(x).startswith(sha[:7]) or sha.startswith(str(x)[:7]) for x in d.get("commits") or [])), None)
    if dep:
        out["state"] = "deployed"
        out["deployed"] = {k: dep.get(k) for k in ("environment", "at", "url") if dep.get(k)}
        out["in_release"] = dep.get("version") or (rel or {}).get("version")
    elif rel:
        out["state"], out["in_release"] = "released", rel.get("version")
    else:
        out["state"] = "fixed_on_main"
    return out


# ------------------------------------------------------------------ rendering

LABEL = {"fixed_on_main": "Fix merged on the default branch, not yet in a release",
         "released": "Fix released", "deployed": "Fix deployed"}


def is_fixed(r):
    fs = r.get("fix_status") or {}
    return fs.get("state") in ("fixed_on_main", "released", "deployed") and fs.get("confidence") in ("strong", "moderate")


def headline(r):
    fs = r["fix_status"]
    c = fs.get("commit") or {}
    ref = (c.get("pr") or c.get("sha", "")[:10])
    if fs["state"] == "deployed":
        where = (fs.get("deployed") or {}).get("environment") or "production"
        return f"Already fixed: {ref} deployed to {where}" + (f" in {fs['in_release']}" if fs.get("in_release") else "")
    if fs["state"] == "released":
        return f"Already fixed: {ref} shipped in {fs['in_release']}"
    return f"Already fixed on the default branch: {ref}, not yet released"


def do_now(r):
    fs = r["fix_status"]
    wa = (r.get("workaround") or {}).get("text")
    if fs["state"] == "deployed":
        return "Ask the customer to confirm it is resolved, then close as fixed."
    if fs["state"] == "released":
        return (f"Check whether {fs['in_release']} is deployed where the customer runs. If it is, confirm with "
                "them and close; if not, schedule the upgrade.")
    s = "Get the merged fix into the next release, or backport it if the customer cannot wait."
    return s + (f" Until then: {wa[:1].lower() + wa[1:].rstrip('.')}." if wa else "")


def md(r):
    import links
    fs = r.get("fix_status")
    if not fs:
        return []
    o = ["## Fix status", ""]
    if is_fixed(r):
        c = fs.get("commit") or {}
        o += links.callout("tip", f"**{headline(r)}.** "
                           + f"{links.md_code(c.get('sha', '')[:10], c.get('url'))} “{c.get('message', '')}” "
                           + f"({fs['confidence']}: {fs.get('why', '')}).",
                           "", "The priority below is the priority while the bug is still live for this customer. "
                               "The work is getting the fix to them, not fixing it again.")
        o.append("")
    else:
        # No fix: one line, with any related commits inline. The section is for when there is news.
        rel = "; ".join(f"{links.md_code(x['sha'], x.get('url'))} {x['message']}" for x in fs.get("candidates") or [])
        return [f"**Fix status:** no fix found in {fs.get('searched', 'the default branch')}."
                + (f" Related, not claimed: {rel}." if rel else ""), ""]
    if fs.get("candidates"):
        o += ["Related commits, not claimed as the fix:", ""]
        o += [f"- {links.md_code(x['sha'], x.get('url'))} {x['message']} ({x['why']})" for x in fs["candidates"]]
        o.append("")
    return o


def html_section(r):
    import html, links
    fs = r.get("fix_status")
    if not fs:
        return ""
    if is_fixed(r):
        c = fs.get("commit") or {}
        body = (f'<div class="tip"><strong>{html.escape(headline(r))}.</strong> '
                f'{links.a(c.get("sha", "")[:10], c.get("url"), code=True)} “{html.escape(c.get("message", ""))}” '
                f'({html.escape(fs["confidence"])}: {html.escape(fs.get("why", ""))}).<br>'
                'The priority is the priority while the bug is still live for this customer.</div>')
    else:
        body = f'<p class="muted">No fix found. Searched {html.escape(fs.get("searched", "the default branch"))}.</p>'
    cands = "".join(f'<li>{links.a(x["sha"], x.get("url"), code=True)} {html.escape(x["message"])} '
                    f'<span class="muted">({html.escape(x["why"])})</span></li>' for x in fs.get("candidates") or [])
    if cands:
        body += f"<p>Related commits, not claimed as the fix:</p><ul>{cands}</ul>"
    return "<h2>Fix status</h2>" + body


def validate(r):
    fs = r.get("fix_status")
    if not fs:
        return []
    p = []
    if fs.get("state") not in STATES:
        p.append(f"fix_status.state must be one of {list(STATES)}")
    if fs.get("state") != "open":
        if fs.get("confidence") not in ("strong", "moderate"):
            p.append("fix_status: a fix is claimed only on strong or moderate evidence")
        if not (fs.get("commit") or {}).get("sha"):
            p.append("fix_status: a claimed fix needs the commit sha")
    if fs.get("state") in ("released", "deployed") and not fs.get("in_release") and fs.get("state") == "released":
        p.append("fix_status: released needs in_release")
    import links
    for where, u in [("commit.url", (fs.get("commit") or {}).get("url")),
                     ("deployed.url", (fs.get("deployed") or {}).get("url"))] + \
            [(f"candidates[{i}].url", x.get("url")) for i, x in enumerate(fs.get("candidates") or [])]:
        if u and not links.safe_url(u):
            p.append(f"fix_status.{where} must be a plain https URL")
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--result", required=True)
    ap.add_argument("--releases", required=True)
    ap.add_argument("--tracker", help="tracker envelope, for the ticket's creation date")
    a = ap.parse_args()
    r = json.load(open(a.result, encoding="utf-8"))
    env = json.load(open(a.releases, encoding="utf-8"))
    t = None
    if a.tracker:
        te = json.load(open(a.tracker, encoding="utf-8"))
        t = te.get("data", te).get("ticket")
    print(json.dumps(assess(r, env, t), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
    sys.exit(main())
