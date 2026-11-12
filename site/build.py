#!/usr/bin/env python3
"""Builds the GoldScout website into site/dist/ (static HTML, plus prices.js
for live auction prices on the data pages).

  python site/build.py

Cloudflare Pages runs this on every push to main, so the community stats on
the page always match the data in the repository.
"""
import datetime
import html
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DIST = HERE / "dist"
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))
import data_pages  # noqa: E402
import merge_data  # noqa: E402

SITE_URL = data_pages.SITE_URL
API_URL = "https://api.wowgoldscout.com"   # also in prices.js
REPO = "https://github.com/Alkhara/GoldScout-WoW"
LINKS = {
    "curseforge": "https://www.curseforge.com/projects/1790110",
    "wago": "https://addons.wago.io/addons/QKyqnaK7",
    "releases": REPO + "/releases/latest",
    "companion": REPO + "/releases/latest/download/GoldScoutCompanion.exe",
    "companion_mac": REPO + "/releases/latest/download/GoldScoutCompanion-macOS.zip",
    "share": REPO + "/issues/new?template=data-submission.yml",
    "guide": REPO + "/blob/main/GoldScout/README.md",
    "issues": REPO + "/issues/new/choose",
    "privacy": REPO + "/blob/main/docs/PRIVACY.md",
    "terms": REPO + "/blob/main/docs/CONTRIBUTOR_TERMS.md",
    "data_license": REPO + "/blob/main/DATA_LICENSE.md",
    "source": REPO,
    "companion_guide": REPO + "/blob/main/companion/README.md#on-a-mac",
    "discord": "https://discord.gg/rJdZcuepzN",
    "contact": "mailto:admin@wowgoldscout.com",
}

SCREENSHOTS = [
    ("Frame.JPG", "Farm tab", "What this character can farm, ranked by gold per hour, with live auction prices."),
    ("CraftFrame.JPG", "Craft tab", "Every recipe you know, ranked by profit after materials."),
    ("Tracker.JPG", "Hunt mode", "Kills, drops and gold per hour while you farm."),
    ("TaggedMobs.JPG", "Hunt markers", "The mobs you're hunting, marked on their nameplates."),
]


# The FAQ, by section: (question, answer as HTML). Answers may use the LINKS
# names as %(name)s; the structured data gets the same text without tags.
FAQ = [
    ("Getting started", [
        ("What is GoldScout?",
         "A free addon for WoW Forever that answers one question: what should the character you're playing farm "
         "or craft for gold right now? It ranks farms and recipes by gold per hour for that character's level, "
         "class, faction and professions, using auction house prices and drop rates shared by players."),
        ("How do I get started?",
         "Install GoldScout from <a href=\"%(curseforge)s\">CurseForge</a> or <a href=\"%(wago)s\">Wago</a>, log "
         "in and type <code>/gscout</code>. A short checklist shows what's left to set up and ticks itself off: "
         "prices for your auction house, your recipes if you craft, and your first Hunt. <code>/gscout "
         "welcome</code> shows it again."),
        ("Is it free?",
         "Yes. Every feature is the same for everyone, with no premium version, ads or accounts."),
        ("Do I need GoldScout Companion?",
         "No. GoldScout works on its own: press <b>Scan AH</b> at any auctioneer for prices. "
         "<a href=\"/companion\">The companion</a> brings prices in every hour without scanning, and shares your "
         "drop data so the Farm tab keeps getting better."),
        ("Does it work on a Mac?",
         "Yes. The addon works like any addon, and GoldScout Companion has a Mac app, signed and checked by "
         "Apple, for Apple silicon and Intel Macs: <a href=\"%(companion_mac)s\">download it</a>, open the zip "
         "and drag GoldScout Companion into Applications. It lives in the Dock; "
         "<a href=\"%(companion_guide)s\">more about the Mac app</a>."),
    ]),
    ("Rules and safety", [
        ("Is GoldScout allowed?",
         "GoldScout only shows you information, using the same addon interface every addon uses. It never "
         "moves, targets, attacks, loots or clicks anything for you, and it skips anything the game hides from "
         "addons instead of working around it."),
        ("Does the companion touch the game?",
         "No. It reads GoldScout's saved data file and writes one small data addon, GoldScout_Prices, which the "
         "game loads at login like any other addon. It never reads or changes the running game."),
        ("Will anything pop up while I play?",
         "No. The companion's only notification says a new version is out, and it waits until World of Warcraft "
         "is closed."),
    ]),
    ("Prices", [
        ("Where do the prices come from?",
         "Three places, newest first: your own <b>Scan AH</b>, the companion's hourly copy of Blizzard's auction "
         "house snapshot for your realm, and, until you have either, regional estimates (the typical price "
         "across your region's auction houses) that ship with each release. Auction data comes from the "
         "Blizzard Entertainment Game Data API."),
        ("Which realms have prices?",
         "Realms in the US, Europe, Korea and Taiwan. Prices are kept per realm type and faction, so Alliance "
         "and Horde characters each see their own auction house. The goblin (Blackwater) auction houses show as "
         "an extra tooltip line and never replace your faction's prices."),
        ("A price looks wrong. Why?",
         "Prices are the lowest buyout listed, so one cheap listing can make an item look cheaper than it "
         "really is. The <b>Listed</b> column shows how many are up, and tooltips warn when there are only a "
         "few. A fresh <b>Scan AH</b> always wins over older prices."),
        ("I see GoldScout's prices twice in tooltips.",
         "Another addon is adding the same lines. Turn GoldScout's off in Options &gt; AddOns &gt; GoldScout, "
         "or with <code>/gscout set tooltip off</code>."),
    ]),
    ("Farms and drop rates", [
        ("Where do the drop rates come from?",
         "From players looting in game, never from Wowhead or any other site. GoldScout learns what every mob "
         "you loot really drops, and the shared data from all players ships in a release every week. "
         "<a href=\"/drop-rates\">How drop rates work</a>."),
        ("How accurate is gold per hour?",
         "It's an estimate: price after the auction house cut, times the chance per kill, times your pace. Set "
         "your own pace in Options &gt; AddOns &gt; GoldScout or with <code>/gscout set kills 80</code> (also "
         "<code>nodes</code> and <code>picks</code>). The Chance column's color shows how many kills back a "
         "rate up, and a Hunt measures what you actually earn."),
        ("Why isn't a mob or zone listed?",
         "Nobody has shared enough loot from it yet. Loot it yourself and GoldScout learns it right away; share "
         "and everyone gets it in the next release."),
    ]),
    ("Your data", [
        ("What does GoldScout share?",
         "Only drop data: creature and item IDs, kill and drop counts, levels and where you looted, plus a "
         "random ID. Never character, account or realm names. The addon itself never connects to anything; "
         "sharing happens through the companion or the <a href=\"%(share)s\">share form</a>, and only if you "
         "agree. See the <a href=\"%(privacy)s\">privacy policy</a>."),
        ("How do I stop sharing, or have my data deleted?",
         "Turn off <b>Share automatically</b> in the companion to stop uploads, or <code>/gscout set learn "
         "off</code> to stop GoldScout learning from your loot at all. To have what you've shared deleted, "
         "email <a href=\"%(contact)s\">admin@wowgoldscout.com</a> with your install ID (shown in your "
         "exports)."),
    ]),
    ("Help", [
        ("Where can I ask a question?",
         "On the <a href=\"%(discord)s\">GoldScout Discord</a>. Bugs and ideas are welcome there or in "
         "<a href=\"%(issues)s\">GitHub issues</a>; for anything private, email "
         "<a href=\"%(contact)s\">admin@wowgoldscout.com</a>."),
        ("Something isn't working. What should I send?",
         "Type <code>/gscout errors</code> to list GoldScout's recent errors and include them, along with what "
         "you were doing. The <a href=\"%(guide)s\">guide</a> covers every feature, command and setting."),
    ]),
]


def faq_page():
    """(title, description, body) for /faq, with FAQPage structured data."""
    sections, entries = [], []
    for title, questions in FAQ:
        parts = ['<h2 id="%s">%s</h2>' % (title.lower().replace(" ", "-"), html.escape(title))]
        for question, answer in questions:
            answer = answer % dict(LINKS)
            parts.append("<h3>%s</h3>\n<p>%s</p>" % (html.escape(question), answer))
            text = html.unescape(re.sub(r"<[^>]+>", "", answer))
            entries.append({"@type": "Question", "name": question,
                            "acceptedAnswer": {"@type": "Answer", "text": text}})
        sections.append("\n".join(parts))
    jsonld = data_pages.json_for_script({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": entries})
    body = """<script type="application/ld+json">%s</script>
<h1>Questions</h1>
<p class="summary">Can't find your answer? Ask on the <a href="%s">GoldScout Discord</a>.</p>
<div class="faq">
%s
</div>""" % (jsonld, LINKS["discord"], "\n".join(sections))
    return ("GoldScout FAQ: questions about the WoW Forever gold addon",
            "Answers about GoldScout: getting started, whether it's allowed, where prices and drop rates come "
            "from, what it shares, and where to get help.", body)


def git(*args):
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def stats(results, merged):
    """Numbers for the community section, from data/submissions/."""
    shown = {npc: e for npc, e in merged.items() if e["k"] + e["p"] >= 5}
    updated = iso = git("log", "-1", "--format=%cs", "--", "GoldScout/Data_Community.lua")
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
        "updated_iso": iso,
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
.next { margin: 22px 0 0; padding: 14px 16px; border: 1px solid var(--gold2); border-radius: 12px; background: rgba(242,194,85,.08); font-size: 15px; color: var(--muted); }
.next b { color: var(--text); }
.next .btn { margin-top: 10px; padding: 9px 16px; }
.faq h3 { margin: 22px 0 4px; font-size: 18px; color: var(--gold); }
.faq p { margin: 0; color: var(--muted); max-width: 46em; }
main.page { padding: 8px 0 40px; }
main.page h1 { font-size: 34px; margin: 6px 0 4px; }
main.page h2 { font-size: 22px; margin: 30px 0 10px; }
.crumbs { margin: 0; font-size: 14px; } .crumbs a { color: var(--muted); }
.facts { color: var(--muted); margin: 0 0 8px; }
table { width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--line); border-radius: 12px; overflow: hidden; font-size: 15px; }
th, td { text-align: left; padding: 9px 12px; border-bottom: 1px solid var(--line); vertical-align: top; }
th { color: var(--muted); font-weight: 600; font-size: 13px; text-transform: uppercase; letter-spacing: .4px; background: var(--bg2); }
tr:last-child td { border-bottom: none; }
.nowrap { white-space: nowrap; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.conf { display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: 12px; font-weight: 600; color: #1b1203; }
.conf.low { background: #ff8040; } .conf.fair { background: #ffd100; } .conf.good { background: #9be35a; } .conf.high { background: #40d040; }
.summary { font-size: 18px; max-width: 46em; margin: 10px 0 6px; }
ul.related { columns: 2; padding-left: 20px; margin: 0; } ul.related li { margin: 4px 0; break-inside: avoid; }
main.page .small a { color: var(--muted); }
.cta { margin-top: 34px; padding: 16px 18px; border: 1px solid var(--gold2); border-radius: 12px; background: rgba(242,194,85,.08); }
.table-wrap { overflow-x: auto; }
.pricebar { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; margin: 18px 0 8px; padding: 10px 14px; background: var(--panel); border: 1px solid var(--line); border-radius: 12px; font-size: 15px; }
.pricebar label { font-weight: 600; }
.pricebar select { margin-left: 6px; font: inherit; color: var(--text); background: var(--bg2); border: 1px solid var(--line); border-radius: 8px; padding: 4px 8px; }
.pricebar .status { color: var(--muted); }
.pricebar .source { flex-basis: 100%; color: var(--muted); font-size: 12px; }
.muted { color: var(--muted); }
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
<meta property="og:type" content="website">
<meta property="og:url" content="%(site)s/">
<meta property="og:image" content="%(site)s/logo-400.png">
<meta name="twitter:card" content="summary">
<link rel="canonical" href="%(site)s/">
<link rel="icon" href="favicon.png">
<script type="application/ld+json">%(jsonld)s</script>
<style>%(css)s</style>
</head>
<body>
<div class="wrap">
<header class="top">
  <a class="brand" href="#"><img src="logo-400.png" alt="">GoldScout</a>
  <nav><a href="#features">Features</a><a href="/farms">Farms by level</a><a href="/drop-rates">Drop rates</a><a href="/companion">Companion</a><a href="/faq">FAQ</a><a href="%(guide)s">Guide</a></nav>
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
    <div class="next"><b>Then add GoldScout Companion.</b> The free app for Windows and Mac brings auction prices into GoldScout every hour, without scanning, and shares your drop data so the Farm tab keeps getting better.<br>
      <a class="btn" href="/companion">Get the companion</a></div>
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
    <li><b>You share.</b> <a href="/companion">GoldScout Companion</a> does it automatically, or use <code>/gscout export</code> and the <a href="%(share)s">share form</a>. No character or account names, ever.</li>
    <li><b>It's checked.</b> Every submission is validated, and unusual drop rates are reviewed before they're used.</li>
    <li><b>Everyone gets it.</b> New community data ships in a release every week. Your own loot is never counted twice.</li>
  </ol>
  <p style="margin-top:22px"><a class="btn" href="/farms">Browse farms by level</a> <a class="btn" href="/drop-rates">How drop rates work</a></p>
</div></section>

<section id="companion"><div class="wrap two">
  <div>
    <h2>Prices every hour, without scanning</h2>
    <p class="sub">GoldScout Companion is a free app for Windows and Mac that keeps GoldScout up to date while you play.</p>
    <ul class="ticks">
      <li><b>Hourly auction prices.</b> Blizzard's auction house snapshot for your realm and faction, saved for GoldScout about once an hour. Your own scans still win when they're newer.</li>
      <li><b>Blackwater prices too.</b> What items go for at the goblin auction houses, as an extra tooltip line.</li>
      <li><b>Better drop rates, automatically.</b> It shares what GoldScout learns from your loot, never character or account names, so the Farm tab improves for you and everyone.</li>
      <li><b>Out of your way.</b> It sits in the system tray (the Dock on a Mac), never pops up over your game, and updates itself in one click.</li>
    </ul>
    <p style="margin-top:22px"><a class="btn primary" href="%(companion)s">Download for Windows</a> <a class="btn primary" href="%(companion_mac)s">Download for Mac</a> <a class="btn" href="/companion">How it works</a></p>
    <p class="small">Free and code-signed, so Windows and macOS show who published it.</p>
  </div>
  <div>
    <h2>Plays by the rules</h2>
    <p class="sub">GoldScout only shows information. It never moves, targets, attacks, loots or clicks anything for you, and it respects every limit Blizzard puts on addons.</p>
    <ul class="ticks">
      <li>The addon never connects to anything; sharing is always your choice.</li>
      <li>The companion never touches the running game: it reads GoldScout's saved data and writes one small data addon.</li>
      <li>Open source on <a href="%(source)s">GitHub</a>, so anyone can check what it does.</li>
      <li>Read the <a href="%(privacy)s">privacy policy</a> and <a href="%(terms)s">contributor terms</a>.</li>
    </ul>
  </div>
</div></section>

<footer><div class="wrap">
  <p><a href="/faq">FAQ</a><a href="%(discord)s">Discord</a><a href="%(source)s">GitHub</a><a href="%(guide)s">Guide</a><a href="%(issues)s">Report a bug</a><a href="%(privacy)s">Privacy</a><a href="%(terms)s">Contributor terms</a><a href="%(data_license)s">Data license</a></p>
  <p>GoldScout is a fan project, not affiliated with or endorsed by Blizzard Entertainment. World of Warcraft is a trademark of Blizzard Entertainment, Inc.</p>
</div></footer>
</body>
</html>
""" % dict(LINKS, site=SITE_URL, css=CSS, shots=shots, jsonld=home_jsonld(), updated=updated, contributors_label=contributors_label,
           contributors=format(s["contributors"], ","), mobs=format(s["mobs"], ","),
           kills=format(s["kills"], ","), drops=format(s["drops"], ","))


def home_jsonld():
    """schema.org data for the home page: the site, and the addon as free software."""
    data = [
        {"@context": "https://schema.org", "@type": "WebSite", "name": "GoldScout", "url": SITE_URL + "/"},
        {"@context": "https://schema.org", "@type": "SoftwareApplication", "name": "GoldScout",
         "applicationCategory": "GameApplication", "operatingSystem": "Windows, macOS",
         "description": "A free WoW Forever addon that ranks what each character can farm or craft for gold.",
         "url": SITE_URL + "/", "downloadUrl": LINKS["curseforge"], "image": SITE_URL + "/logo-400.png",
         "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    ]
    return data_pages.json_for_script(data)


def layout(title, description, path, body):
    """A data page: the site's header and footer around body."""
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s | GoldScout</title>
<meta name="description" content="%(description)s">
<meta property="og:title" content="%(title)s">
<meta property="og:description" content="%(description)s">
<meta property="og:type" content="website">
<meta property="og:url" content="%(site)s%(path)s">
<meta property="og:image" content="%(site)s/logo-400.png">
<meta property="og:site_name" content="GoldScout">
<meta name="twitter:card" content="summary">
<link rel="canonical" href="%(site)s%(path)s">
<link rel="icon" href="/favicon.png">
<style>%(css)s</style>
<script src="/prices.js" defer></script>
</head>
<body>
<div class="wrap">
<header class="top">
  <a class="brand" href="/"><img src="/logo-400.png" alt="">GoldScout</a>
  <nav><a href="/farms">Farms by level</a><a href="/drop-rates">Drop rates</a><a href="/companion">Companion</a><a href="/faq">FAQ</a><a href="%(curseforge)s">Get GoldScout</a></nav>
</header>
<main class="page"><div class="table-wrap">%(body)s</div></main>
</div>
<footer><div class="wrap">
  <p><a href="/">Home</a><a href="/farms">Farms by level</a><a href="/drop-rates">How drop rates work</a><a href="/faq">FAQ</a><a href="%(discord)s">Discord</a><a href="%(source)s">GitHub</a><a href="%(privacy)s">Privacy</a><a href="%(data_license)s">Data license</a></p>
  <p>Drop rates come from GoldScout players and are covered by the GoldScout Data License. GoldScout is a fan project, not affiliated with or endorsed by Blizzard Entertainment. World of Warcraft is a trademark of Blizzard Entertainment, Inc.</p>
</div></footer>
</body>
</html>
""" % dict(LINKS, site=SITE_URL, css=CSS, path=path, body=body,
           title=html.escape(title), description=html.escape(description))


def companion_page(s):
    """(title, description, body) for /companion: what the companion does and how to get it."""
    e = html.escape
    players = "%s player%s" % (format(s["contributors"], ","), "" if s["contributors"] == 1 else "s")
    body = """<h1>GoldScout Companion</h1>
<p class="summary">A free app for Windows and Mac that brings auction house prices into GoldScout every hour, without scanning, and
shares your drop data so GoldScout's Farm tab keeps getting better for everyone.</p>
<p><a class="btn primary" href="%(companion)s">Download for Windows</a> <a class="btn primary" href="%(companion_mac)s">Download for Mac</a> <a class="btn" href="%(curseforge)s">Get the GoldScout addon</a></p>
<p class="small">Free · code-signed · updates itself · Windows, and Macs with Apple silicon or Intel</p>

<h2>What you get</h2>
<div class="grid">
  <div class="card"><h3>Prices every hour</h3><p>Blizzard's auction house snapshot for your realm and faction, saved
    for GoldScout about once an hour. Farm and Craft rankings stay current without a trip to the auction house, and
    your own scans still win when they're newer.</p></div>
  <div class="card"><h3>Blackwater prices too</h3><p>What items go for at the goblin auction houses, shown as an
    extra tooltip line. They never replace your own faction's prices.</p></div>
  <div class="card"><h3>Better drop rates for everyone</h3><p>Every mob you loot teaches GoldScout what it really
    drops. The companion shares that for you, so the next release knows more mobs, for you and every other player.</p></div>
  <div class="card"><h3>Out of your way</h3><p>It sits in the system tray (the Dock on a Mac), starts when you log
    in if you like, never pops up over your game, and updates itself in one click.</p></div>
</div>

<h2>Why it matters</h2>
<p class="summary">GoldScout uses no data from Wowhead or any other site: every drop rate comes from players looting
in game. %(players)s have shared so far. Each new player fills in mobs and zones nobody has recorded yet, and
<a href="/farms">the farms</a> get more accurate with every kill.</p>

<h2>Set it up in a minute</h2>
<ol class="steps">
  <li><b>Install GoldScout</b> from <a href="%(curseforge)s">CurseForge</a> or <a href="%(wago)s">Wago</a>, if you haven't already.</li>
  <li><b>Download and launch the app.</b> On Windows there's nothing to install; on a Mac, open the zip and drag
    GoldScout Companion into Applications. It finds your WoW Forever folder by itself.</li>
  <li><b>Choose once.</b> Agree to share automatically, or choose Not now and use it just for prices.</li>
  <li><b>Play.</b> GoldScout loads new prices when you log in or <code>/reload</code>, and its window offers
    <b>Load newer prices</b> when a fresher snapshot is waiting.</li>
</ol>

<div class="faq">
<h2>Questions</h2>
<h3>Does it touch the game?</h3>
<p>No. It reads GoldScout's saved data file and writes one small data addon, GoldScout_Prices, which the game loads
at login like any other addon. It never reads or changes the running game. Auction prices come from Blizzard's
official Game Data API.</p>
<h3>What does it share?</h3>
<p>Only GoldScout's drop data: creature and item IDs, kill and drop counts, levels and where you looted, plus a
random ID. Never character, account or realm names. See the <a href="%(privacy)s">privacy policy</a> and
<a href="%(terms)s">contributor terms</a>.</p>
<h3>Do I need it?</h3>
<p>No. GoldScout works on its own: scan at the auction house, and share with <code>/gscout export</code> and the
<a href="%(share)s">share form</a>. The companion does both for you.</p>
<h3>Will it interrupt my game?</h3>
<p>No. Its only notification says a new version is out, and it waits until World of Warcraft is closed.</p>
<h3>Is it safe to run?</h3>
<p>Every release is code-signed (and checked by Apple on a Mac), so your computer shows who published it, and
the companion only installs updates that are signed the same way. The source is on <a href="%(source)s">GitHub</a>.</p>
<h3>Is there a Mac version?</h3>
<p>Yes, for Macs with Apple silicon or Intel: <a href="%(companion_mac)s">download it</a>, open the zip and drag
GoldScout Companion into Applications. On a Mac it lives in the Dock instead of a tray, and its window's
<b>Settings</b> hold sharing, auction prices, <b>Open at login</b> and updates.</p>
</div>
<p class="small" style="margin-top:28px">Auction data from the Blizzard Entertainment Game Data API. GoldScout is not
affiliated with or endorsed by Blizzard Entertainment.</p>
""" % dict(LINKS, players=e(players))
    return ("GoldScout Companion: hourly auction prices for GoldScout",
            "A free app for Windows and Mac that brings auction house prices into the GoldScout addon every hour without "
            "scanning, and shares drop data so everyone's Farm tab gets better.", body)


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "screenshots").mkdir(parents=True)
    for name, _, _ in SCREENSHOTS:
        shutil.copy2(ROOT / "docs" / "screenshots" / name, DIST / "screenshots" / name)
    shutil.copy2(ROOT / "docs" / "logo" / "goldscout-logo-400.png", DIST / "logo-400.png")
    shutil.copy2(ROOT / "companion" / "icon.png", DIST / "favicon.png")
    shutil.copy2(HERE / "prices.js", DIST / "prices.js")
    results = merge_data.load(ROOT / "data" / "submissions")
    merged = merge_data.merge([r.mobs for r in results], 1000)
    s = stats(results, merged)
    (DIST / "index.html").write_text(page(s), encoding="utf-8")

    def write(relative, title, description, body):
        target = DIST / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        url_path = "/" + relative[:-len(".html")]
        target.write_text(layout(title, description, url_path, body), encoding="utf-8")

    write("companion.html", *companion_page(s))
    write("faq.html", *faq_page())
    data = data_pages.Dataset(results, merged)
    paths = ["/", "/companion", "/faq"] + data_pages.build(data, LINKS, write)
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    lastmod = "<lastmod>%s</lastmod>" % s["updated_iso"] if s["updated_iso"] else ""
    sitemap += ["  <url><loc>%s%s</loc>%s</url>" % (SITE_URL, path, lastmod) for path in paths]
    sitemap.append("</urlset>")
    (DIST / "sitemap.xml").write_text("\n".join(sitemap) + "\n", encoding="utf-8")
    robots = ["User-agent: *", "Allow: /", "Sitemap: %s/sitemap.xml" % SITE_URL]
    (DIST / "robots.txt").write_text("\n".join(robots) + "\n", encoding="utf-8")
    (DIST / "404.html").write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex"><title>Not found: GoldScout</title>'
        '<link rel="icon" href="/favicon.png"><style>%s</style></head><body><div class="wrap">'
        '<header class="top"><a class="brand" href="/"><img src="/logo-400.png" alt="">GoldScout</a></header>'
        '<section><h2>Page not found</h2><p class="sub">That page doesn\'t exist.</p>'
        '<a class="btn primary" href="/">Go to the GoldScout home page</a></section></div></body></html>' % CSS,
        encoding="utf-8")
    (DIST / "_headers").write_text(
        "/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n"
        "  Content-Security-Policy: default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; "
        "script-src 'self'; connect-src %s; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'\n" % API_URL, encoding="utf-8")
    print("Built %s: %d contributors, %d mobs, %d kills, %d pages." % (
        DIST, s["contributors"], s["mobs"], s["kills"], len(paths)))


if __name__ == "__main__":
    main()
