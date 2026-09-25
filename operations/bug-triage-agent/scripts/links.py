#!/usr/bin/env python3
"""Evidence links: short labels, URLs hidden behind them.

Every piece of evidence a triage cites can carry a `url`. Renderers never print a URL
bare: they show a short label (`ApprovalReviewService.ts:89`, `2026.09`, `#4412`,
`DEMO-1`, `Logs`) and put the URL behind it.

Where a URL comes from, in order:
1. The URL a tool returned with the evidence (a tracker's web URL, a commit's html
   URL, a hosting platform's deployment page, a log store's deep link). Always
   preferred.
2. A template in the team config's `links` section, filled from the evidence. Used
   only when the tool gave none. Templates are configuration because hosts differ.
3. Nothing. Evidence without a real URL shows its label as plain text. A link is
   never guessed.

    python3 scripts/links.py --check teams/demo-live.json   # fill every template with sample values
"""
import html, json, re, string, sys

MAX_LABEL = 40
TEMPLATE_KEYS = {
    "code": {"owner", "repo", "ref", "path", "line"},
    "commit": {"owner", "repo", "sha"},
    "release": {"owner", "repo", "version"},
    "pr": {"owner", "repo", "number"},
    "ticket": {"key"},
    # A metrics or log query opened in the metrics tool over the evidence window.
    # {query} is filled JSON-escaped and URL-encoded, {from} and {to} as epoch
    # milliseconds, so a template can embed them in an encoded JSON parameter.
    "log_query": {"query", "from", "to"},
}
SAMPLE = {"owner": "acme", "repo": "app", "ref": "0a1b2c3", "path": "src/a/b.ts",
          "line": 89, "sha": "0a1b2c3", "version": "2026.09", "number": 4412, "key": "ABC-1",
          "query": 'sum(count_over_time({app="x"} |= "err" [1h]))', "from": "2026-09-16T12:00:00Z",
          "to": "2026-09-23T04:00:00Z"}


def _epoch_ms(v):
    from datetime import datetime
    try:
        return str(int(datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp() * 1000))
    except ValueError:
        return None


def query_values(query, start, end):
    """Encode a query and its window for a `log_query` template."""
    from urllib.parse import quote
    q = quote(json.dumps(query)[1:-1], safe="") if query else None
    return {"query": q, "from": _epoch_ms(start), "to": _epoch_ms(end)}


def safe_url(u):
    """Only plain https URLs go behind a label."""
    if not isinstance(u, str) or not u.startswith("https://") or re.search(r'[\s"<>`]', u):
        return None
    return u


def fields(template):
    return {f for _, f, _, _ in string.Formatter().parse(template) if f}


def fill(template, **vals):
    """Fill a template, or return None when a value is missing or the result is unsafe."""
    if not template:
        return None
    need = fields(template)
    if any(vals.get(k) in (None, "") for k in need):
        return None
    try:
        return safe_url(template.format(**{k: vals[k] for k in need}))
    except (KeyError, ValueError, IndexError):
        return None


def short(text, limit=MAX_LABEL):
    text = "" if text is None else str(text)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _md_url(url):
    """Parentheses end a markdown link early, and log-query URLs are full of them."""
    url = safe_url(url)
    return url.replace("(", "%28").replace(")", "%29") if url else None


def md(label, url):
    label = short(label).replace("[", "(").replace("]", ")")
    url = _md_url(url)
    return f"[{label}]({url})" if url else label


def md_code(label, url):
    """A code-formatted label that is also a link: [`File.ts:89`](url)."""
    label = short(label).replace("`", "'")
    url = _md_url(url)
    return f"[`{label}`]({url})" if url else f"`{label}`"


def a(label, url, code=False):
    text = html.escape(short(label))
    if code:
        text = f"<code>{text}</code>"
    url = safe_url(url)
    return (f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener">{text}</a>'
            if url else text)


# Callouts that render the same in every markdown viewer. The `> [!WARNING]` alert
# syntax shows as a literal tag in most viewers, so it is not used.
CALLOUT = {"warning": "⚠️", "caution": "🛑", "important": "❗", "note": "ℹ️", "tip": "💡"}


def callout(kind, first, *more):
    """A quote block led by an icon: callout("warning", "**Stale data.** …", "- detail")."""
    lines = [f"> {CALLOUT[kind]} {first}"]
    for m in more:
        lines.append(f"> {m}" if m else ">")
    return lines


def location_label(loc):
    path = loc.get("path") or loc.get("area") or "—"
    name = path.rsplit("/", 1)[-1]
    return f"{name}:{loc['line']}" if loc.get("line") else name


def pr_number(pr):
    m = re.search(r"\d+", str(pr or ""))
    return int(m.group()) if m else None


def repo_for(r, cfg):
    """owner, repo name and the ref to pin code links to."""
    rr = r.get("repo") or {}
    repos = cfg.get("repos") or []
    match = next((x for x in repos if x.get("name") == rr.get("name")), repos[0] if repos else {})
    owner = rr.get("owner") or match.get("owner") or (cfg.get("release_correlation") or {}).get("vcs", {}).get("org")
    name = rr.get("name") or match.get("name")
    # Pin to a commit when one is known, so the line number stays right after later edits.
    ref = rr.get("sha") or (r.get("introduced_by") or {}).get("sha") or rr.get("base_branch") \
        or match.get("default_branch") or "main"
    return owner, name, ref


def enrich(r, cfg):
    """Fill missing `url` fields from the config's link templates. Tool-returned URLs win."""
    t = (cfg or {}).get("links") or {}
    if not t:
        return r
    owner, name, ref = repo_for(r, cfg)
    for loc in r.get("locations") or []:
        if not loc.get("url") and loc.get("path"):
            u = fill(t.get("code"), owner=owner, repo=name, ref=ref,
                     path=loc["path"], line=loc.get("line") or 1)
            # No line known: link the file, not a made-up line anchor.
            loc["url"] = u.split("#")[0] if u and not loc.get("line") else u
    rel = r.get("release") or {}
    if rel and not rel.get("url"):
        rel["url"] = fill(t.get("release"), owner=owner, repo=name, version=rel.get("version"))
    intro = r.get("introduced_by") or {}
    if intro.get("pr") and not intro.get("pr_url"):
        # A known commit is a link that certainly exists; a PR number read from a commit
        # message may not be a PR in this repo at all. Prefer the commit.
        intro["pr_url"] = (fill(t.get("commit"), owner=owner, repo=name, sha=intro.get("sha"))
                           or (fill(t.get("pr"), owner=owner, repo=name, number=pr_number(intro["pr"]))
                               if intro.get("pr_is_pr") else None))
    if intro.get("release") and not intro.get("release_url"):
        intro["release_url"] = fill(t.get("release"), owner=owner, repo=name, version=intro["release"])
    fs = r.get("fix_status") or {}
    for c in [fs.get("commit") or {}] + list(fs.get("candidates") or []):
        if c.get("sha") and not c.get("url"):
            c["url"] = fill(t.get("commit"), owner=owner, repo=name, sha=c["sha"])
    for p in r.get("prior_fixes") or []:
        if not p.get("url") and p.get("key"):
            p["url"] = fill(t.get("ticket"), key=p["key"])
    if not r.get("ticket_url"):
        r["ticket_url"] = fill(t.get("ticket"), key=r.get("ticket"))
    # Query links are the one place the team's template beats a tool's URL: deep-link
    # tools can emit an older URL shape the metrics tool no longer honours, which opens
    # an empty query over the last hour. A link that carries its `query` is rebuilt.
    if t.get("log_query"):
        m = (r.get("sources") or {}).get("metrics") or {}
        old = {}
        for ln in r.get("links") or []:
            if ln.get("query"):
                u = fill(t["log_query"], **query_values(ln["query"], ln.get("from") or m.get("data_from"),
                                                        ln.get("to") or m.get("as_of")))
                if u:
                    if ln.get("url"):
                        old[ln["url"]] = u
                    ln["url"] = u
        # The same URL may have been copied onto other evidence (a risk, a location).
        for loc in (r.get("locations") or []) + (r.get("disposition_evidence") or []):
            if loc.get("url") in old:
                loc["url"] = old[loc["url"]]
    return r


def check(cfg):
    """Problems with a config's `links` section. Empty means every template fills."""
    problems = []
    for kind, template in ((cfg or {}).get("links") or {}).items():
        if kind.startswith("//"):
            continue
        if kind not in TEMPLATE_KEYS:
            problems.append(f"links.{kind}: unknown link kind; known: {sorted(TEMPLATE_KEYS)}")
            continue
        unknown = fields(template) - TEMPLATE_KEYS[kind]
        if unknown:
            problems.append(f"links.{kind}: unknown placeholder(s) {sorted(unknown)}; "
                            f"allowed: {sorted(TEMPLATE_KEYS[kind])}")
            continue
        vals = dict(SAMPLE, **query_values(SAMPLE["query"], SAMPLE["from"], SAMPLE["to"])) \
            if kind == "log_query" else SAMPLE
        if not fill(template, **vals):
            problems.append(f"links.{kind}: does not produce an https URL when filled")
    return problems


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--check":
        with open(sys.argv[2], encoding="utf-8") as f:
            probs = check(json.load(f))
        print("\n".join(probs) or "links: ok")
        sys.exit(1 if probs else 0)
    print(__doc__)
