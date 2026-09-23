#!/usr/bin/env python3
"""Duplicate detection by failure mode, not by title.

Two tickets are duplicates when they describe the same failure: the same error, the
same symptom in the description, the same stack, endpoint or file, in the same area. Similar titles are the
weakest signal there is. "Export broken" and "Export broken" can be two bugs, and
"Header offset in CSV" and "Amount column misaligned" can be one.

The tracker subagent returns candidates with their descriptions. This scores them,
deterministically, from what the text actually contains:

    python3 scripts/dupes.py --tracker tracker-envelope.json [--links-config team.json]

prints a `duplicate_check` block for the result file:

    {"searched": 6, "candidates": [{"key", "summary", "status", "score", "verdict",
      "signals": ["same error: approval not committed", ...], "url"}]}

Verdicts:
    duplicate   score >= 0.6, a failure-mode or stack signal, same area (or area unknown),
                and the candidate is still open
    recurrence  would be a duplicate, but the candidate was fixed: this is the same
                failure coming back, a defect with a prior fix, not a duplicate to close
    related     score >= 0.3, or a strong match in a different area
    different   below that

A title match alone is capped at `related`, whatever its score.
"""
import argparse, json, re, sys

ERR_PATTERNS = [
    r'"([^"\n]{6,120})"', r"'([^'\n]{6,120})'", r"`([^`\n]{6,120})`",
    r"\b((?:[A-Z]\w+)?(?:Error|Exception|Failure|Timeout)\b[:\s][^\n.]{3,100})",
    r"\b(\d{3} (?:Internal Server Error|Bad Request|Not Found|Conflict|Unprocessable Entity|Service Unavailable))",
]
FRAME = re.compile(r"(?:\bat\s+[\w.$<>]+\s*\(([\w./-]+\.\w+):\d+|File \"([\w./-]+\.py)\", line \d+)")
ENDPOINT = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/[\w/{}:.-]*)", re.I)
FILE = re.compile(r"\b([\w-]+\.(?:ts|tsx|js|jsx|py|go|java|kt|rb|cs|php|rs|sql))\b")
VERSION = re.compile(r"\b(v?\d{4}\.\d{2}(?:\.\d+)?)\b")
STOP = set("a an the and or of in on at to for with when after before from is are was were not no "
           "be by it this that as via fails fail failing failed error errors issue bug broken "
           # ticket-template words, so two tickets filed from one template do not look alike
           "steps reproduce repro expected actual result results environment browser version "
           "description summary impact workaround".split())


def norm(s):
    s = s.lower()
    s = re.sub(r"\b[0-9a-f]{8}-[0-9a-f-]{27,}\b", "<id>", s)
    s = re.sub(r"\b\d+\b", "<n>", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip(" .:;,")


def norm_path(p):
    return re.sub(r"/(\d+|[0-9a-f-]{16,}|\{\w+\}|:\w+)(?=/|$)", "/{id}", p.lower().rstrip("/"))


def features(t):
    text = "\n".join(str(t.get(k) or "") for k in ("summary", "description", "error_text", "stack"))
    errs = set()
    for pat in ERR_PATTERNS:
        for m in re.findall(pat, text):
            m = m if isinstance(m, str) else m[0]
            if len(m.split()) >= 2:
                errs.add(norm(m))
    frames = {a or b for a, b in FRAME.findall(text)}
    eps = {f"{m.upper()} {norm_path(p)}" for m, p in ENDPOINT.findall(text)}
    files = set(FILE.findall(text)) | {f.rsplit("/", 1)[-1] for f in frames}
    words = {w for w in re.findall(r"[a-z][a-z0-9]+", (t.get("summary") or "").lower()) if w not in STOP}
    body = [w for w in re.findall(r"[a-z][a-z0-9]+", (t.get("description") or "").lower()) if w not in STOP]
    pairs = {(a, b) for a, b in zip(body, body[1:])}
    return {"pairs": pairs, "errors": errs, "frames": frames, "endpoints": eps, "files": files,
            "versions": set(VERSION.findall(text)), "words": words,
            "area": (t.get("component") or "").lower() or None}


def _overlap(a, b):
    """Shared error phrases, allowing one to contain the other."""
    out = set()
    for x in a:
        for y in b:
            if x == y or (min(len(x), len(y)) >= 12 and (x in y or y in x)):
                out.add(min(x, y, key=len))
    return out


CLOSED_FIXED = ("fixed", "done", "resolved")


def score(ticket, cand):
    f, g = features(ticket), features(cand)
    s, signals, mode = 0.0, [], False
    e = _overlap(f["errors"], g["errors"])
    if e:
        s += 0.45
        mode = True
        signals.append("same error: " + sorted(e, key=len)[0][:60])
    if f["pairs"] and g["pairs"]:
        j = len(f["pairs"] & g["pairs"]) / min(len(f["pairs"]), len(g["pairs"]))
        if j >= 0.25:
            # Half the phrasing shared is as telling as a shared error message.
            s += (0.3 + 0.2 * min(1.0, (j - 0.25) / 0.25)) if not e else 0.1
            mode = True
            signals.append(f"same symptom described ({int(j * 100)}% of phrasing)")
    fr = f["frames"] & g["frames"]
    if len(fr) >= 2:
        s += 0.3
        mode = True
        signals.append(f"{len(fr)} stack frames in common")
    elif fr:
        s += 0.15
        signals.append("a stack frame in common: " + next(iter(fr)))
    ep = f["endpoints"] & g["endpoints"]
    if ep:
        s += 0.15
        signals.append("same endpoint: " + next(iter(ep)))
    fl = (f["files"] & g["files"]) - {x.rsplit("/", 1)[-1] for x in fr}
    if fl:
        s += 0.15
        signals.append("same file: " + ", ".join(sorted(fl)[:2]))
    same_area = f["area"] is None or g["area"] is None or f["area"] == g["area"]
    if f["area"] and g["area"]:
        if f["area"] == g["area"]:
            s += 0.1
            signals.append(f"same area: {f['area']}")
        else:
            signals.append(f"different area: {g['area']}")
    v = f["versions"] & g["versions"]
    if v:
        s += 0.05
        signals.append("same release: " + ", ".join(sorted(v)))
    if f["words"] and g["words"]:
        j = len(f["words"] & g["words"]) / len(f["words"] | g["words"])
        if j >= 0.2:
            s += round(0.1 * j, 3)
            signals.append(f"similar title ({int(j * 100)}% of words)")
    s = round(min(s, 1.0), 2)

    status = (cand.get("resolution") or cand.get("status") or "").lower()
    closed_fixed = any(w in status for w in CLOSED_FIXED) and "not" not in status
    if s >= 0.6 and mode and same_area:
        verdict = "recurrence" if closed_fixed else "duplicate"
    elif s >= 0.3 or (mode and not same_area):
        verdict = "related"
    else:
        verdict = "different"
    if not mode and not fr and not ep and not fl and verdict != "different":
        verdict = "related"  # title and area alone never make a duplicate
    return s, verdict, signals


def check(ticket, candidates, links_cfg=None):
    tmpl = ((links_cfg or {}).get("links") or {}).get("ticket")
    out = []
    for c in candidates:
        if not c.get("key") or c.get("key") == ticket.get("key"):
            continue
        s, verdict, signals = score(ticket, c)
        url = c.get("url")
        if not url and tmpl:
            import links
            url = links.fill(tmpl, key=c["key"])
        out.append({"key": c["key"], "summary": c.get("summary", ""),
                    "status": c.get("resolution") or c.get("status") or "",
                    "score": s, "verdict": verdict, "signals": signals, **({"url": url} if url else {})})
    out.sort(key=lambda x: (-x["score"], x["key"]))
    return {"searched": len(out), "candidates": out}


# ------------------------------------------------------------------ rendering

VERDICTS = {"duplicate": "🔁 duplicate", "recurrence": "↩️ recurrence", "related": "🔗 related",
            "different": "✖ different"}


def validate(r):
    p = []
    dc = r.get("duplicate_check")
    if dc is None:
        return p
    for i, c in enumerate(dc.get("candidates") or []):
        if c.get("verdict") not in VERDICTS:
            p.append(f"duplicate_check.candidates[{i}].verdict must be one of {sorted(VERDICTS)}")
        if c.get("url"):
            import links
            if not links.safe_url(c["url"]):
                p.append(f"duplicate_check.candidates[{i}].url must be a plain https URL")
    dup = [c for c in dc.get("candidates") or [] if c.get("verdict") == "duplicate"]
    if r.get("disposition") == "duplicate" and dc.get("candidates") and not dup:
        p.append("disposition is duplicate but no candidate in duplicate_check scored as one")
    return p


def md(r):
    import links
    dc = r.get("duplicate_check")
    if not dc:
        return []
    shown = [c for c in dc.get("candidates") or [] if c["verdict"] != "different"][:5]
    rest = dc.get("searched", 0) - len(shown)
    o = ["## Duplicate check", ""]
    if not shown:
        return o + [f"{dc.get('searched', 0)} candidate(s) compared by error, stack, endpoint, file and "
                    "area. None describes the same failure.", ""]
    o += ["| Ticket | Verdict | Score | Matched on |", "| --- | --- | --- | --- |"]
    for c in shown:
        sig = "; ".join(c.get("signals") or []).replace("|", "/")
        o.append(f"| {links.md(c['key'], c.get('url'))} | {VERDICTS[c['verdict']]} | {c['score']:.2f} | {sig} |")
    o.append("")
    if rest > 0:
        o += [f"{rest} other candidate(s) ruled out: no shared error, symptom, stack, endpoint or file.", ""]
    return o


def html_section(r):
    import html, links
    dc = r.get("duplicate_check")
    if not dc:
        return ""
    shown = [c for c in dc.get("candidates") or [] if c["verdict"] != "different"][:5]
    if not shown:
        return (f'<h2>Duplicate check</h2><p class="muted">{dc.get("searched", 0)} candidate(s) compared '
                'by error, stack, endpoint, file and area. None describes the same failure.</p>')
    rows = "".join(f'<tr><td>{links.a(c["key"], c.get("url"))}</td><td>{html.escape(VERDICTS[c["verdict"]])}</td>'
                   f'<td>{c["score"]:.2f}</td><td>{html.escape("; ".join(c.get("signals") or []))}</td></tr>'
                   for c in shown)
    return ('<h2>Duplicate check</h2><div class="tbl"><table><thead><tr><th>Ticket</th><th>Verdict</th>'
            '<th>Score</th><th>Matched on</th></tr></thead><tbody>' + rows + "</tbody></table></div>")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tracker", required=True, help="tracker envelope with data.ticket and data.duplicates")
    ap.add_argument("--links-config", help="team config, to link candidates from its ticket template")
    a = ap.parse_args()
    with open(a.tracker, encoding="utf-8") as f:
        env = json.load(f)
    data = env.get("data", env)
    cands = list(data.get("duplicates") or [])
    seen = {c.get("key") for c in cands}
    cands += [c for c in data.get("related") or [] if c.get("key") not in seen]
    cfg = None
    if a.links_config:
        with open(a.links_config, encoding="utf-8") as f:
            cfg = json.load(f)
    print(json.dumps(check(data.get("ticket") or {}, cands, cfg), indent=2))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
    sys.exit(main())
