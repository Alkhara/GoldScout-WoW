#!/usr/bin/env python3
"""Builds the GoldScout website into site/dist/ (static HTML, no JavaScript).

  python site/build.py

Cloudflare Pages runs this on every push to main, so the community stats on
the page always match the data in the repository.
"""
import datetime
import html
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DIST = HERE / "dist"
sys.path.insert(0, str(ROOT / "tools"))
import merge_data  # noqa: E402

REPO = "https://github.com/Alkhara/GoldScout-WoW"
LINKS = {
    "curseforge": "https://www.curseforge.com/projects/1790110",
    "wago": "https://addons.wago.io/addons/QKyqnaK7",
    "releases": REPO + "/releases/latest",
    "companion": REPO + "/releases/latest/download/GoldScoutCompanion.exe",
    "share": REPO + "/issues/new?template=data-submission.yml",
    "guide": REPO + "/blob/main/GoldScout/README.md",
    "issues": REPO + "/issues/new/choose",
    "privacy": REPO + "/blob/main/docs/PRIVACY.md",
    "terms": REPO + "/blob/main/docs/CONTRIBUTOR_TERMS.md",
    "data_license": REPO + "/blob/main/DATA_LICENSE.md",
    "source": REPO,
}

SCREENSHOTS = [
    ("Frame.JPG", "Farm tab", "What this character can farm, ranked by gold per hour, with live auction prices."),
    ("CraftFrame.JPG", "Craft tab", "Every recipe you know, ranked by profit after materials."),
    ("Tracker.JPG", "Hunt mode", "Kills, drops and gold per hour while you farm."),
    ("TaggedMobs.JPG", "Hunt markers", "The mobs you're hunting, marked on their nameplates."),
]


def git(*args):
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def stats():
    """Numbers for the community section, from data/submissions/."""
    results = merge_data.load(ROOT / "data" / "submissions")
    merged = merge_data.merge([r.mobs for r in results], 1000)
    shown = {npc: e for npc, e in merged.items() if e["k"] + e["p"] >= 5}
    updated = git("log", "-1", "--format=%cs", "--", "GoldScout/Data_Community.lua")
    if updated:
        updated = datetime.date.fromisoformat(updated).strftime("%B %-d, %Y" if sys.platform != "win32"
                                                               else "%B %#d, %Y")
    return {
        "contributors": len(results),
        "mobs": len(shown),
        "kills": sum(e["k"] for e in merged.values()),
        "picks": sum(e["p"] for e in merged.values()),
        "drops": sum(d for e in merged.values() for d, _ in list(e["i"].values()) + list(e["pi"].values())),
        "updated": updated,
    }


CSS = """
:root {
  --bg: #071820; --bg2: #0c2530; --panel: #10303d; --line: #1f4a5a;
  --text: #e7eef1; --muted: #9fb6bf; --gold: #f2c255; --gold2: #d99a2b; --link: #8fd3ff;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0; background: radial-gradient(1200px 600px at 30% -10%, #16485a 0%, var(--bg) 60%) fixed, var(--bg);
  color: var(--text); font: 17px/1.6 "Segoe UI", system-ui, -apple-system, Roboto, sans-serif;
}
a { color: var(--link); }
img { max-width: 100%; }
h1, h2, h3, p, li { overflow-wrap: break-word; }
.hero > *, .grid > *, .two > * { min-width: 0; }
.wrap { max-width: 1080px; margin: 0 auto; padding: 0 20px; }
header.top { display: flex; align-items: center; justify-content: space-between; padding: 18px 0; }
.brand { display: flex; align-items: center; gap: 10px; color: var(--text); text-decoration: none; font-weight: 700; font-size: 20px; }
.brand img { width: 36px; height: 36px; border-radius: 8px; }
nav a { color: var(--muted); text-decoration: none; margin-left: 18px; font-size: 15px; }
nav a:hover { color: var(--text); }
.hero { display: grid; grid-template-columns: 1.1fr 0.9fr; gap: 40px; align-items: center; padding: 40px 0 56px; }
.hero h1 { font-size: 46px; line-height: 1.1; margin: 0 0 16px; letter-spacing: -0.5px; }
.hero h1 span { color: var(--gold); }
.hero p.lead { font-size: 19px; color: var(--muted); margin: 0 0 26px; max-width: 34em; }
.hero .shot { border-radius: 12px; border: 1px solid var(--line); box-shadow: 0 20px 60px rgba(0,0,0,.45); width: 100%; height: auto; }
.buttons { display: flex; flex-wrap: wrap; gap: 12px; }
.btn { display: inline-block; padding: 12px 20px; border-radius: 10px; font-weight: 600; text-decoration: none; border: 1px solid var(--line); color: var(--text); background: var(--panel); }
.btn:hover { border-color: var(--gold2); }
.btn.primary { background: linear-gradient(180deg, var(--gold), var(--gold2)); color: #1b1203; border-color: transparent; }
.small { font-size: 14px; color: var(--muted); }
section { padding: 56px 0; border-top: 1px solid rgba(255,255,255,.06); }
section h2 { font-size: 30px; margin: 0 0 8px; }
section p.sub { color: var(--muted); margin: 0 0 28px; max-width: 46em; }
.grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 22px; }
.card { background: linear-gradient(180deg, var(--panel), var(--bg2)); border: 1px solid var(--line); border-radius: 14px; padding: 18px; }
.card img { width: 100%; height: auto; border-radius: 8px; border: 1px solid rgba(0,0,0,.4); display: block; margin-bottom: 12px; }
.card h3 { margin: 0 0 4px; font-size: 19px; color: var(--gold); }
.card p { margin: 0; color: var(--muted); font-size: 15px; }
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 18px; }
.stat { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 18px; text-align: center; }
.stat b { display: block; font-size: 32px; color: var(--gold); font-variant-numeric: tabular-nums; }
.stat span { color: var(--muted); font-size: 14px; }
.steps { counter-reset: step; list-style: none; padding: 0; margin: 0; display: grid; gap: 14px; }
.steps li { counter-increment: step; background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px 14px 56px; position: relative; }
.steps li::before { content: counter(step); position: absolute; left: 16px; top: 13px; width: 28px; height: 28px; border-radius: 50%; background: var(--gold); color: #1b1203; font-weight: 700; display: grid; place-items: center; font-size: 15px; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 28px; }
ul.ticks { padding-left: 20px; margin: 0; } ul.ticks li { margin: 6px 0; }
footer { padding: 36px 0 48px; color: var(--muted); font-size: 14px; border-top: 1px solid rgba(255,255,255,.06); }
footer a { color: var(--muted); margin-right: 16px; }
@media (max-width: 820px) {
  .hero, .two, .grid { grid-template-columns: 1fr; }
  .hero { padding-top: 16px; } .hero h1 { font-size: 34px; }
  .stats { grid-template-columns: repeat(2, 1fr); }
  nav { display: none; }
}
"""


def page(s):
    e = html.escape
    shots = "\n".join(
        '<div class="card"><img src="screenshots/%s" alt="%s" loading="lazy"><h3>%s</h3><p>%s</p></div>'
        % (e(name), e(title), e(title), e(text)) for name, title, text in SCREENSHOTS)
    updated = " Last updated %s." % e(s["updated"]) if s["updated"] else ""
    contributors_label = "contributor" if s["contributors"] == 1 else "contributors"
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GoldScout: gold farming guide for WoW Forever</title>
<meta name="description" content="A free WoW Forever addon that tells each character what's worth farming or crafting for gold, using your own auction house prices and drop rates shared by players.">
<meta property="og:title" content="GoldScout">
<meta property="og:description" content="What should this character farm for gold right now? A free WoW Forever addon.">
<meta property="og:image" content="logo-400.png">
<link rel="icon" href="favicon.png">
<style>%(css)s</style>
</head>
<body>
<div class="wrap">
<header class="top">
  <a class="brand" href="#"><img src="logo-400.png" alt="">GoldScout</a>
  <nav><a href="#features">Features</a><a href="#data">Community data</a><a href="#companion">Companion</a><a href="%(guide)s">Guide</a></nav>
</header>

<div class="hero">
  <div>
    <h1>What should <span>this character</span> farm for gold right now?</h1>
    <p class="lead">GoldScout is a free WoW Forever addon. Open the auction house and it ranks what the character you're playing can farm or craft for the most gold per hour, for its level, class, faction and professions.</p>
    <div class="buttons">
      <a class="btn primary" href="%(curseforge)s">Get it on CurseForge</a>
      <a class="btn" href="%(wago)s">Wago</a>
      <a class="btn" href="%(releases)s">GitHub</a>
    </div>
    <p class="small">Free, open source, and every feature is the same for everyone.</p>
  </div>
  <img class="shot" src="screenshots/Frame.JPG" alt="The GoldScout Farm tab">
</div>
</div>

<section id="features"><div class="wrap">
  <h2>Everything a gold farmer needs, for the character you're on</h2>
  <p class="sub">Live prices from your own auction house, drop rates from real players, and a Hunt mode that takes you to the spot and keeps score.</p>
  <div class="grid">%(shots)s</div>
</div></section>

<section id="data"><div class="wrap">
  <h2>Data from players, not scraped</h2>
  <p class="sub">Every drop rate and spawn point in GoldScout comes from players looting in game. Nothing is copied from Wowhead or anywhere else. The more people share, the better everyone's Farm tab gets.%(updated)s</p>
  <div class="stats">
    <div class="stat"><b>%(contributors)s</b><span>%(contributors_label)s</span></div>
    <div class="stat"><b>%(mobs)s</b><span>mobs with drop rates</span></div>
    <div class="stat"><b>%(kills)s</b><span>kills recorded</span></div>
    <div class="stat"><b>%(drops)s</b><span>item drops recorded</span></div>
  </div>
  <ol class="steps">
    <li><b>You play.</b> GoldScout learns what every mob you loot really drops, on all your characters.</li>
    <li><b>You share.</b> The companion does it automatically, or use <code>/gscout export</code> and the <a href="%(share)s">share form</a>. No character or account names, ever.</li>
    <li><b>It's checked.</b> Every submission is validated, and unusual drop rates are reviewed before they're used.</li>
    <li><b>Everyone gets it.</b> New community data ships in a release every week. Your own loot is never counted twice.</li>
  </ol>
</div></section>

<section id="companion"><div class="wrap two">
  <div>
    <h2>GoldScout Companion</h2>
    <p class="sub">An optional Windows app that shares what GoldScout learns, so you never have to think about it.</p>
    <ul class="ticks">
      <li>Runs quietly in the system tray and starts with Windows.</li>
      <li>Never shows pop-ups over your game.</li>
      <li>Shares new data automatically after you agree once, and can be paused any time.</li>
      <li>Only reads GoldScout's saved data. It never touches the game.</li>
      <li>Code-signed, so Windows shows who published it.</li>
    </ul>
    <p style="margin-top:22px"><a class="btn primary" href="%(companion)s">Download for Windows</a></p>
  </div>
  <div>
    <h2>Plays by the rules</h2>
    <p class="sub">GoldScout only shows information. It never moves, targets, attacks, loots or clicks anything for you, and it respects every limit Blizzard puts on addons.</p>
    <ul class="ticks">
      <li>The addon never connects to anything; sharing is always your choice.</li>
      <li>Open source on <a href="%(source)s">GitHub</a>, so anyone can check what it does.</li>
      <li>Read the <a href="%(privacy)s">privacy policy</a> and <a href="%(terms)s">contributor terms</a>.</li>
    </ul>
  </div>
</div></section>

<footer><div class="wrap">
  <p><a href="%(source)s">GitHub</a><a href="%(guide)s">Guide</a><a href="%(issues)s">Report a bug</a><a href="%(privacy)s">Privacy</a><a href="%(terms)s">Contributor terms</a><a href="%(data_license)s">Data license</a></p>
  <p>GoldScout is a fan project, not affiliated with or endorsed by Blizzard Entertainment. World of Warcraft is a trademark of Blizzard Entertainment, Inc.</p>
</div></footer>
</body>
</html>
""" % dict(LINKS, css=CSS, shots=shots, updated=updated, contributors_label=contributors_label,
           contributors=format(s["contributors"], ","), mobs=format(s["mobs"], ","),
           kills=format(s["kills"], ","), drops=format(s["drops"], ","))


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "screenshots").mkdir(parents=True)
    for name, _, _ in SCREENSHOTS:
        shutil.copy2(ROOT / "docs" / "screenshots" / name, DIST / "screenshots" / name)
    shutil.copy2(ROOT / "docs" / "logo" / "goldscout-logo-400.png", DIST / "logo-400.png")
    shutil.copy2(ROOT / "companion" / "icon.png", DIST / "favicon.png")
    s = stats()
    (DIST / "index.html").write_text(page(s), encoding="utf-8")
    (DIST / "404.html").write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"><title>Not found: GoldScout</title>'
        '<link rel="icon" href="/favicon.png"><style>%s</style></head><body><div class="wrap">'
        '<header class="top"><a class="brand" href="/"><img src="/logo-400.png" alt="">GoldScout</a></header>'
        '<section><h2>Page not found</h2><p class="sub">That page doesn\'t exist.</p>'
        '<a class="btn primary" href="/">Go to the GoldScout home page</a></section></div></body></html>' % CSS,
        encoding="utf-8")
    (DIST / "_headers").write_text(
        "/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n"
        "  Content-Security-Policy: default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'\n", encoding="utf-8")
    print("Built %s: %d contributors, %d mobs, %d kills." % (DIST, s["contributors"], s["mobs"], s["kills"]))


if __name__ == "__main__":
    main()
