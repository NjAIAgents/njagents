#!/usr/bin/env python3
"""The look shared by every HTML page the plugin writes.

The stylesheet lives in `assets/report-theme.css` and is inlined into each page, so a
page is one self-contained file that opens anywhere. A team can change the accent
colour in its config without touching the file:

    "output": { "theme": { "accent": "#0F766E", "accent_dark": "#7DD3C4" } }

`accent` is used in light mode, `accent_dark` in dark mode (defaults to `accent`).
Anything else about the look is changed in the stylesheet, for everyone.
"""
import html, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS_PATH = os.path.join(ROOT, "assets", "report-theme.css")
FONTS = ("https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600"
         "&family=IBM+Plex+Mono:wght@400;500;600&display=swap")
HEX = re.compile(r"#[0-9a-fA-F]{6}")


def css():
    with open(CSS_PATH, encoding="utf-8") as f:
        return f.read()


def valid(theme):
    """Problems with an `output.theme` block. Empty means it can be applied."""
    p = []
    for k, v in (theme or {}).items():
        if k.startswith("//"):
            continue
        if k not in ("accent", "accent_dark"):
            p.append(f"output.theme.{k}: unknown key; allowed: accent, accent_dark")
        elif not isinstance(v, str) or not HEX.fullmatch(v):
            p.append(f"output.theme.{k}: must be a #RRGGBB colour")
    return p


def overrides(theme):
    """CSS that re-points the accent tokens, or nothing when no valid accent is set."""
    theme = theme or {}
    if valid(theme) or not theme.get("accent"):
        return ""
    light, dark = theme["accent"], theme.get("accent_dark") or theme["accent"]
    soft = "color-mix(in srgb, {c} 16%, var(--surface))"
    rule = lambda c: f"--teal:{c};--teal-soft:{soft.format(c=c)}"
    return (f":root{{{rule(light)}}}"
            f'@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{{rule(dark)}}}}}'
            f':root[data-theme="dark"]{{{rule(dark)}}}')


def head(title, theme=None):
    """The <head> content of a page: charset, viewport, title, fonts and the theme."""
    return ['<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">',
            f"<title>{html.escape(title)}</title>",
            f'<link rel="stylesheet" href="{FONTS}">',
            f"<style>{css()}{overrides(theme)}</style>"]


# ------------------------------------------------------------------ shared by every page

def _svg(name, body):
    return (f'<svg class="i i-{name}" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{body}</svg>')


ICON = {
    "open": _svg("open", '<path d="M14 4h6v6"/><path d="M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>'),
    "doc": _svg("doc", '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h4"/>'),
    "wrench": _svg("wrench", '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>'),
    "sun": _svg("sun", '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'),
    "moon": _svg("moon", '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>'),
    "monitor": _svg("monitor", '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>'),
}


JS = """<script>
(function(){
  var root=document.documentElement, KEY='triage-theme';
  // One icon button cycles light, dark, system; the icon shows the current choice.
  var ORDER=['light','dark','system'], NAME={light:'Light',dark:'Dark',system:'System'}, tb=document.getElementById('theme-toggle'), cur='light';
  function apply(v){ cur=v; if(v==='system'){root.removeAttribute('data-theme');} else {root.setAttribute('data-theme',v);}
    if(tb){ tb.setAttribute('data-mode',v); var n=ORDER[(ORDER.indexOf(v)+1)%3]; tb.title='Theme: '+NAME[v]+' (click for '+NAME[n]+')'; tb.setAttribute('aria-label',tb.title); } }
  var saved='light'; try{ saved=localStorage.getItem(KEY)||'light'; }catch(e){}
  apply(ORDER.indexOf(saved)<0?'light':saved);
  if(tb){ tb.addEventListener('click',function(){ var v=ORDER[(ORDER.indexOf(cur)+1)%3]; apply(v); try{localStorage.setItem(KEY,v);}catch(e){} }); }
  document.querySelectorAll('[data-more]').forEach(function(b){ b.addEventListener('click',function(){ var f=document.getElementById(b.getAttribute('data-more')); var c=f.classList.toggle('collapsed'); b.textContent=c?b.getAttribute('data-label')||b.textContent.replace('Collapse','Show all'):'Collapse'; if(!c){b.setAttribute('data-label',b.textContent);} }); });
  document.querySelectorAll('[data-copy]').forEach(function(b){ b.addEventListener('click',function(){ var f=document.getElementById(b.getAttribute('data-copy')); var t=Array.prototype.map.call(f.querySelectorAll('.cl span:last-child'),function(s){return s.textContent;}).join('\\n');
    function done(){ b.textContent='Copied'; setTimeout(function(){b.textContent='Copy';},1200); }
    if(navigator.clipboard&&navigator.clipboard.writeText){ navigator.clipboard.writeText(t).then(done,function(){ var r=document.createRange(); r.selectNodeContents(f.querySelector('pre')); var s=window.getSelection(); s.removeAllRanges(); s.addRange(r); }); } }); });
})();
</script>"""
