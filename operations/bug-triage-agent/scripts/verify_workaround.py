#!/usr/bin/env python3
"""Check that a workaround actually works before the report tells anyone to use it.

Off unless the team config turns it on (`verification.enabled: true`). The config
chooses the runner, because teams test in different places:

    http     a hosted preview or staging deployment, called over HTTPS
    docker   a local container the config starts and stops, then called over HTTP
    ci       a CI workflow the agent dispatches through a bound tool; the script
             only records what it returned
    command  a test command the team wrote, run locally with the scenario file

The scenario is written by the triage from the ticket's reproduction steps and the
workaround, as <TICKET>.scenario.json:

    {"ticket": "DEMO-7",
     "reproduce":  [{"name": "approve via API", "method": "POST", "path": "/api/approve",
                     "json": {"id": "r-1"}, "expect": {"status": 200, "json": {"ok": true}}},
                    {"name": "read back", "method": "GET", "path": "/api/requests/r-1",
                     "expect": {"json": {"state": "pending_review"}}}],
     "workaround": [{"name": "approve via UI route", ...}]}

`reproduce` steps describe the bug: they pass when the bug shows. `workaround` steps
pass when the workaround gets the customer to the right outcome.

    python3 scripts/verify_workaround.py run --team-config <cfg> --scenario <file> --result <result>
    python3 scripts/verify_workaround.py record --result <result> --status passed \\
        --runner ci --url https://...     # after a CI run the agent dispatched
    python3 scripts/verify_workaround.py check --team-config <cfg>   # config only, no calls

Guards, none of which a scenario can override:
- environment `production` is refused. Verification runs against preview, staging or local.
- HTTP methods are limited to `http.allow_methods` (default GET only).
- A step's path must start with "/": it can only reach the configured base URL.
- Commands come from the team config, never from a ticket or a scenario.
- Headers are read from environment variables named in the config; no secret is ever
  written to the config, the scenario or the result.
"""
import argparse, json, os, shlex, subprocess, sys, time
from datetime import datetime, timezone
from urllib import request as urlreq, error as urlerr
from urllib.parse import urlparse

RUNNERS = ("http", "docker", "ci", "command")
ENVIRONMENTS = ("preview", "staging", "local")
STATUS = {"passed": "✅ verified", "failed": "❌ did not work", "not_reproduced": "⚠️ bug not reproduced",
          "error": "🔴 verification error", "pending": "⏳ verification running", "not_run": ""}


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def cfg_problems(cfg):
    v = (cfg or {}).get("verification") or {}
    if not v or not v.get("enabled"):
        return []
    p = []
    r = v.get("runner")
    if r not in RUNNERS:
        p.append(f"verification.runner must be one of {list(RUNNERS)}")
    env = v.get("environment")
    if env == "production":
        p.append("verification.environment is production. Verification never runs against production")
    elif env not in ENVIRONMENTS:
        p.append(f"verification.environment must be one of {list(ENVIRONMENTS)}")
    if r in ("http", "docker"):
        sec = v.get(r) or {}
        base = sec.get("base_url") or ""
        u = urlparse(base)
        local = u.hostname in ("localhost", "127.0.0.1")
        if not base or u.scheme not in ("https", "http") or (u.scheme == "http" and not local):
            p.append(f"verification.{r}.base_url must be https, or http on localhost")
        if r == "http" and local:
            p.append("verification.http.base_url is localhost; use the docker runner for local")
        if r == "docker" and not local:
            p.append("verification.docker.base_url must be on localhost")
        bad = [m for m in sec.get("allow_methods", ["GET"]) if m.upper() not in
               ("GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE")]
        if bad:
            p.append(f"verification.{r}.allow_methods has unknown methods {bad}")
        if r == "docker" and not (sec.get("start") and sec.get("stop")):
            p.append("verification.docker needs start and stop commands")
    if r == "command" and not (v.get("command") or {}).get("run"):
        p.append("verification.command.run is empty")
    if r == "ci" and not (v.get("ci") or {}).get("workflow"):
        p.append("verification.ci.workflow is empty")
    if r == "ci" and not ((cfg.get("tool_bindings") or {}).get("verification") or {}).get("dispatch"):
        p.append("verification runner is ci but tool_bindings.verification.dispatch is missing")
    return p


# ------------------------------------------------------------------ http

def _match(want, got):
    """Every key in want is in got with the same value; nested dicts compared the same way."""
    if isinstance(want, dict):
        return isinstance(got, dict) and all(k in got and _match(v, got[k]) for k, v in want.items())
    return want == got


def http_step(base, step, allow, headers, timeout):
    method = (step.get("method") or "GET").upper()
    path = step.get("path") or ""
    if method not in allow:
        # Blocked by policy is not the workaround failing: the run is an error, not a verdict.
        return None, f"{method} not allowed by verification allow_methods {sorted(allow)}"
    if not path.startswith("/") or "//" in path or "://" in path:
        return None, "path must start with '/' and stay on the configured base URL"
    data = None
    h = dict(headers)
    if step.get("json") is not None:
        data = json.dumps(step["json"]).encode()
        h["Content-Type"] = "application/json"
    req = urlreq.Request(base.rstrip("/") + path, data=data, method=method, headers=h)

    class NoRedirect(urlreq.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):  # a login redirect is not a pass
            return None
    opener = urlreq.build_opener(NoRedirect)
    try:
        with opener.open(req, timeout=timeout) as res:
            status, body = res.status, res.read().decode("utf-8", "replace")
    except urlerr.HTTPError as e:
        status, body = e.code, e.read().decode("utf-8", "replace")
    except (urlerr.URLError, OSError) as e:
        return None, f"could not reach {urlparse(base).netloc}: {e}"
    exp = step.get("expect") or {}
    problems = []
    if "status" in exp and status != exp["status"]:
        problems.append(f"status {status}, expected {exp['status']}")
    if "json" in exp:
        try:
            got = json.loads(body)
        except json.JSONDecodeError:
            got = None
        if not _match(exp["json"], got):
            problems.append(f"body {body[:120]!r} does not match {json.dumps(exp['json'])}")
    if exp.get("body_contains") and exp["body_contains"] not in body:
        problems.append(f"body lacks {exp['body_contains']!r}")
    return (not problems), ("; ".join(problems) or f"{method} {path} → {status}")


def run_steps(steps, v, runner):
    sec = v.get(runner) or {}
    allow = {m.upper() for m in sec.get("allow_methods", ["GET"])}
    headers = {k: os.environ.get(env, "") for k, env in (sec.get("headers_from_env") or {}).items()
               if os.environ.get(env)}
    out = []
    for st in steps:
        ok, detail = http_step(sec["base_url"], st, allow, headers, v.get("timeout_seconds", 60))
        out.append({"name": st.get("name") or st.get("path"), "ok": ok, "detail": detail})
        if ok is None:
            break
    return out


def sh(cmd, cwd, timeout):
    return subprocess.run(shlex.split(cmd), cwd=cwd, capture_output=True, text=True, timeout=timeout)


def run(cfg, scenario, cfg_dir):
    v = cfg.get("verification") or {}
    base = {"runner": v.get("runner"), "environment": v.get("environment"), "at": now()}
    if not v.get("enabled"):
        return {**base, "status": "not_run", "note": "verification is off for this team"}
    probs = cfg_problems(cfg)
    if probs:
        return {**base, "status": "error", "note": "; ".join(probs)}
    r, timeout = v["runner"], v.get("timeout_seconds", 300)

    if r == "ci":
        return {**base, "status": "pending",
                "note": f"dispatch {v['ci']['workflow']} through tool_bindings.verification.dispatch, "
                        "then record the outcome with `record`"}

    if r == "command":
        c = v["command"]
        cmd = c["run"].replace("{scenario}", shlex.quote(scenario["_path"]))
        try:
            p = sh(cmd, os.path.join(cfg_dir, c.get("cwd", ".")), timeout)
        except (OSError, subprocess.TimeoutExpired) as e:
            return {**base, "status": "error", "note": str(e)[:200]}
        tail = (p.stdout + p.stderr).strip().splitlines()[-3:]
        return {**base, "status": "passed" if p.returncode == 0 else "failed",
                "note": " / ".join(tail)[:300]}

    started = False
    if r == "docker":
        try:
            p = sh(v["docker"]["start"], os.path.join(cfg_dir, v["docker"].get("cwd", ".")), timeout)
            if p.returncode != 0:
                return {**base, "status": "error", "note": "start failed: " + p.stderr.strip()[-200:]}
            started = True
            time.sleep(v["docker"].get("wait_seconds", 5))
        except (OSError, subprocess.TimeoutExpired) as e:
            return {**base, "status": "error", "note": f"start failed: {e}"[:200]}
    try:
        rep = run_steps(scenario.get("reproduce") or [], v, r)
        wa = run_steps(scenario.get("workaround") or [], v, r)
    finally:
        if started:
            try:
                sh(v["docker"]["stop"], os.path.join(cfg_dir, v["docker"].get("cwd", ".")), timeout)
            except (OSError, subprocess.TimeoutExpired):
                pass
    steps = [{"phase": "reproduce", **s} for s in rep] + [{"phase": "workaround", **s} for s in wa]
    blocked = next((s for s in steps if s["ok"] is None), None)
    if blocked:
        status = "error"
    elif rep and not all(s["ok"] for s in rep):
        status = "not_reproduced"
    elif not wa:
        status = "error"
    else:
        status = "passed" if all(s["ok"] for s in wa) else "failed"
    out = {**base, "status": status, "reproduced": (all(s["ok"] for s in rep) if rep else None),
           "steps": steps}
    if blocked:
        out["note"] = f"{blocked['name']}: {blocked['detail']}"
    host = urlparse((v.get(r) or {}).get("base_url", "")).netloc
    out["target"] = host
    return out


# ------------------------------------------------------------------ rendering

def line(wa):
    """One line for the report: what verification found, or nothing when it did not run."""
    ver = (wa or {}).get("verified") or {}
    st = ver.get("status")
    if not st or st == "not_run":
        return ""
    where = " · ".join(x for x in (ver.get("runner"), ver.get("environment"), ver.get("target")) if x)
    s = f"**{STATUS[st]}** on {where}, {ver.get('at', '')}"
    if st == "not_reproduced":
        s += ". The bug did not show in that environment, so the workaround proves nothing there"
    elif st in ("failed", "error") and ver.get("note"):
        s += f". {ver['note']}"
    else:
        bad = [x for x in ver.get("steps") or [] if not x.get("ok")]
        if bad:
            s += f". Failed: {bad[0]['name']}: {bad[0]['detail']}"
    return s + "."


def md_line(wa):
    import links
    s = line(wa)
    url = ((wa or {}).get("verified") or {}).get("url")
    return s + (f" {links.md('Run', url)}" if s and url else "")


def html_line(wa):
    import html, re, links
    s = line(wa)
    if not s:
        return ""
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    url = ((wa or {}).get("verified") or {}).get("url")
    return s + (" " + links.a("Run", url) if url else "")


def validate(r):
    ver = (r.get("workaround") or {}).get("verified")
    if not ver:
        return []
    p = []
    if ver.get("status") not in STATUS:
        p.append(f"workaround.verified.status must be one of {sorted(STATUS)}")
    if ver.get("environment") == "production":
        p.append("workaround.verified.environment is production, which verification never uses")
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("run")
    a.add_argument("--team-config", required=True)
    a.add_argument("--scenario", required=True)
    a.add_argument("--result", help="result file to write workaround.verified into")
    c = sub.add_parser("check")
    c.add_argument("--team-config", required=True)
    rc = sub.add_parser("record")
    rc.add_argument("--result", required=True)
    rc.add_argument("--status", required=True, choices=sorted(set(STATUS) - {"not_run"}))
    rc.add_argument("--runner", default="ci")
    rc.add_argument("--environment")
    rc.add_argument("--url")
    rc.add_argument("--note")
    args = ap.parse_args()

    if args.cmd == "check":
        with open(args.team_config, encoding="utf-8") as f:
            cfg = json.load(f)
        probs = cfg_problems(cfg)
        v = cfg.get("verification") or {}
        print("\n".join(probs) or (f"verification: {v.get('runner')} on {v.get('environment')}"
                                   if v.get("enabled") else "verification: off"))
        return 1 if probs else 0

    if args.cmd == "record":
        with open(args.result, encoding="utf-8") as f:
            r = json.load(f)
        ver = {"status": args.status, "runner": args.runner, "at": now()}
        for k in ("environment", "url", "note"):
            if getattr(args, k):
                ver[k] = getattr(args, k)
        if ver.get("environment") == "production":
            print("refusing: verification never records a production run", file=sys.stderr)
            return 1
        r.setdefault("workaround", {})["verified"] = ver
        with open(args.result, "w", encoding="utf-8") as f:
            json.dump(r, f, indent=2, ensure_ascii=False)
        print(line(r["workaround"]))
        return 0

    with open(args.team_config, encoding="utf-8") as f:
        cfg = json.load(f)
    with open(args.scenario, encoding="utf-8") as f:
        scen = json.load(f)
    scen["_path"] = os.path.abspath(args.scenario)
    ver = run(cfg, scen, os.path.dirname(os.path.abspath(args.team_config)))
    if args.result:
        with open(args.result, encoding="utf-8") as f:
            r = json.load(f)
        if (r.get("workaround") or {}).get("text"):
            r["workaround"]["verified"] = ver
            with open(args.result, "w", encoding="utf-8") as f:
                json.dump(r, f, indent=2, ensure_ascii=False)
    print(json.dumps(ver, indent=2))
    return 0 if ver["status"] in ("passed", "not_run", "pending") else 1


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.exit(main())
