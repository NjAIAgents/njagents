#!/usr/bin/env python3
"""Name the risks a defect carries, from a fixed list, with where each one came from.

Priority says how urgent a bug is. It does not say what kind of harm it can do, and two
P2s can need very different handling: one leaks data, the other sends an email twice.
This script tags each defect with named risk types so reviewers, the fix brief and
later gates (a human sign-off for security or payment) can act on them.

    python3 scripts/risks.py <TICKET>.result.json [--team-config <config>]

Risk types, most serious first:
    security                authentication, permissions, tokens, exposed personal data
    payment                 charges, invoices, refunds, settlements, balances, payouts
    data_integrity          records lost, not saved, duplicated or wrong
    compliance              audit trail, retention, consent, regulation
    availability            outage, crash, errors that stop the service
    silent_failure          the system reports success when it failed
    customer_communication  emails or notifications wrong, missing or repeated
    performance             slow responses, timeouts

How sure each one is:
    evidenced   a code signal shows it (a swallowed error, a failed write reported as done),
                or the triage recorded that data needs repair
    reported    the ticket or a comment the triage used says it
    suspected   only the triage's hypothesis or its notes on the code mention it

Risks never change the priority by themselves. The rubric's own rules still apply.
Teams add words per type in `risks.terms`, or turn a type off in `risks.off`.
"""
import argparse, json, re, sys

TYPES = ("security", "payment", "data_integrity", "compliance", "availability",
         "silent_failure", "customer_communication", "performance")
ICON = {"security": "🔒", "payment": "💳", "data_integrity": "💾", "compliance": "📜",
        "availability": "🚨", "silent_failure": "🔇", "customer_communication": "✉️", "performance": "🐢"}
LABEL = {t: t.replace("_", " ") for t in TYPES}
MEANING = {"security": "access, tokens or personal data at risk",
           "payment": "money, charges or balances affected",
           "data_integrity": "records lost, not saved or wrong",
           "compliance": "audit trail, retention or regulation",
           "availability": "the service stops working",
           "silent_failure": "reports success when it failed",
           "customer_communication": "emails or notifications wrong, missing or repeated",
           "performance": "slow responses"}
LEVELS = ("evidenced", "reported", "suspected")

TERMS = {
    "security": ["authentication", "authorization", "unauthorized", "unauthorised", "permission", "permissions",
                 "access control", "token", "session", "password", "credential", "credentials", "privilege",
                 "leak", "leaked", "exposed", "exposes", "pii", "personal data", "xss", "injection", "csrf"],
    "payment": ["payment", "payments", "charge", "charged", "invoice", "invoices", "refund", "refunds",
                "settlement", "settlements", "billing", "payout", "payouts", "balance", "ledger",
                "transaction", "transactions", "card"],
    "data_integrity": ["not committed", "not saved", "not stored", "never happened", "lost", "data loss",
                       "corrupt", "corrupted", "overwritten", "duplicate records", "wrong total",
                       "remain in pending", "stays in pending"],
    "compliance": ["audit", "audit log", "audit trail", "gdpr", "retention", "consent", "regulatory",
                   "compliance", "sox", "hipaa", "pci"],
    "availability": ["outage", "is down", "unavailable", "crash", "crashes", "503", "502", "cannot log in",
                     "not loading"],
    "silent_failure": ["silently", "no error", "reports success", "returns 200", "ok: true", "still reports",
                       "still adds"],
    "customer_communication": ["email", "emails", "notification", "notifications", "reminder", "reminders",
                               "sms", "sent twice"],
    "performance": ["slow", "slowly", "latency", "takes minutes", "times out for users"],
}
SIGNAL = {"error_swallowing": ["silent_failure"]}
WRITE = re.compile(r"\b(commit|commits|committed|write|writes|save|saved|persist|stored?)\b", re.I)


def _find(text, terms):
    t = (text or "").lower()
    for w in terms:
        if re.search(r"(?<![a-z0-9])" + re.escape(w.lower()) + r"(?![a-z0-9])", t):
            return w
    return None


def _terms(cfg):
    rc = (cfg or {}).get("risks") or {}
    terms = {k: list(v) for k, v in TERMS.items()}
    for k, extra in (rc.get("terms") or {}).items():
        if k in terms:
            terms[k] += list(extra)
    return terms, set(rc.get("off") or [])


def detect(r, cfg=None):
    if r.get("disposition") != "defect":
        return []
    terms, off = _terms(cfg)
    locs = r.get("locations") or []
    repro = r.get("repro") or {}
    used = [u.get("quote") for u in (r.get("comment_review") or {}).get("used") or []]
    texts = [("reported", "ticket", " ".join(x or "" for x in [r.get("summary"), repro.get("actual")])),
             ("reported", "comment", " ".join(q or "" for q in used)),
             ("suspected", "hypothesis", (r.get("hypothesis") or {}).get("statement")),
             ("suspected", "code notes", " ".join(l.get("evidence") or "" for l in locs))]
    found = {}

    def add(t, level, source, why):
        if t in off:
            return
        cur = found.get(t)
        if not cur or LEVELS.index(level) < LEVELS.index(cur["level"]):
            found[t] = {"type": t, "level": level, "source": source, "why": why}

    for l in locs:
        for t in SIGNAL.get(l.get("signal"), []):
            where = (l.get("path") or "").rsplit("/", 1)[-1] + (f":{l['line']}" if l.get("line") else "")
            add(t, "evidenced", "code", f"{l['signal'].replace('_', ' ')} at {where}")
        if l.get("signal") == "error_swallowing" and WRITE.search((l.get("evidence") or "") + " " +
                                                                 ((r.get("hypothesis") or {}).get("statement") or "")):
            add("data_integrity", "evidenced", "code", "a failed write is caught and reported as done")
    for level, source, text in texts:
        for t in TYPES:
            w = _find(text, terms[t])
            if w:
                add(t, level, source, f"“{w}” in the {source}")
    if r.get("data_repair"):
        add("data_integrity", "evidenced", "triage", "records already written wrong need repair")
    return [found[t] for t in TYPES if t in found]


# ------------------------------------------------------------------ rendering

def fill(r, cfg=None):
    """Compute risks with the team's terms, unless the result already records them."""
    if r.get("risks") is None and r.get("disposition") == "defect":
        r["risks"] = detect(r, cfg)
    return r


def get(r, cfg=None):
    return r.get("risks") if r.get("risks") is not None else detect(r, cfg)


def cell(r, cfg=None):
    rs = get(r, cfg)
    return " · ".join(f"{ICON[x['type']]} {LABEL[x['type']]} ({x['level']})" for x in rs) if rs else "none named"


def icons(r, cfg=None):
    return " ".join(ICON[x["type"]] for x in get(r, cfg)) or "—"


def md(r, cfg=None):
    rs = get(r, cfg)
    if not rs:
        return []
    o = ["## Risks", "", "| Risk | What it means | How sure | Why |", "| --- | --- | --- | --- |"]
    o += [f"| {ICON[x['type']]} {LABEL[x['type']]} | {MEANING[x['type']]} | {x['level']} | {x['why'].replace('|', '/')} |"
          for x in rs]
    return o + ["", "*How sure:* **evidenced** the code shows it · **reported** the ticket or a comment says it · "
                "**suspected** only the triage's hypothesis or code notes mention it. "
                "Risks name the kind of harm. They do not change the priority.", ""]


def html_section(r, cfg=None):
    import html
    rs = get(r, cfg)
    if not rs:
        return ""
    rows = "".join(f"<tr><td>{ICON[x['type']]} {html.escape(LABEL[x['type']])}</td>"
                   f"<td>{html.escape(MEANING[x['type']])}</td><td>{x['level']}</td>"
                   f"<td>{html.escape(x['why'])}</td></tr>" for x in rs)
    return ('<h2>Risks</h2><div class="tbl"><table><thead><tr><th>Risk</th><th>What it means</th><th>How sure</th>'
            f'<th>Why</th></tr></thead><tbody>{rows}</tbody></table></div><p class="muted">How sure: evidenced '
            '= the code shows it; reported = the ticket or a comment says it; suspected = only the hypothesis or '
            'code notes mention it. Risks name the kind of harm. They do not change the priority.</p>')


def validate(r):
    p = []
    for i, x in enumerate(r.get("risks") or []):
        if x.get("type") not in TYPES:
            p.append(f"risks[{i}].type must be one of {list(TYPES)}")
        if x.get("level") not in LEVELS:
            p.append(f"risks[{i}].level must be one of {list(LEVELS)}")
        if not x.get("why"):
            p.append(f"risks[{i}] needs `why`")
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", nargs="+")
    ap.add_argument("--team-config")
    a = ap.parse_args()
    cfg = json.load(open(a.team_config, encoding="utf-8")) if a.team_config else None
    for p in a.results:
        r = json.load(open(p, encoding="utf-8"))
        print(json.dumps({"ticket": r["ticket"], "risks": detect(r, cfg)}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
