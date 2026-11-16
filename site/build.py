#!/usr/bin/env python3
"""Builds the GoldScout website into site/dist/ (static HTML, plus prices.js
for live auction prices on the data pages).

  python site/build.py

Cloudflare Pages runs this on every push to main, so the community stats on
the page always match the data in the repository.
"""
import datetime
import html
import json
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
ANALYTICS_SCRIPT = "https://static.cloudflareinsights.com"   # Cloudflare Web Analytics
ANALYTICS_REPORT = "https://cloudflareinsights.com"
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
         "you loot really drops, and the shared data from all players ships in a release every day. "
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
         "sharing happens through the companion or the <a href=\"/share\">share page</a>, and only if you "
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


# Hidden until site/search.js runs: without it the box can't do anything.
SEARCH_BOX = ('<form class="site-search" role="search" hidden>'
              '<input type="search" name="q" placeholder="Search items, mobs and zones" '
              'aria-label="Search items, mobs and zones" autocomplete="off" spellcheck="false">'
              '<ul class="results" role="listbox" hidden></ul></form>')
SEARCH_BOX_DE = (SEARCH_BOX.replace('placeholder="Search items, mobs and zones"',
                                   'placeholder="Gegenstände, Gegner, Gebiete"')
                 .replace("Search items, mobs and zones", "Gegenstände, Gegner und Gebiete suchen"))

# The data pages' header and footer in each language (data_pages.LOCAL_PAGES exist in both; the rest is
# English, so German pages link there in English).
CHROME = {
    "en": {
        "nav": '<a href="/farms">Farms by level</a><a href="/fishing">Fishing</a><a href="/drop-rates">Drop rates</a>'
               '<a href="/companion">Companion</a><a href="/leaderboard">Leaderboard</a><a href="/faq">FAQ</a>'
               '<a href="%(curseforge)s">Get GoldScout</a>',
        "footer": '<a href="/">Home</a><a href="/farms">Farms by level</a><a href="/fishing">Fishing</a>'
                  '<a href="/drop-rates">How drop rates work</a><a href="/leaderboard">Leaderboard</a>'
                  '<a href="/data-wanted">Data wanted</a><a href="/faq">FAQ</a><a href="%(discord)s">Discord</a>'
                  '<a href="%(source)s">GitHub</a><a href="%(privacy)s">Privacy</a>'
                  '<a href="%(data_license)s">Data license</a>',
        "notice": "Drop rates come from GoldScout players and are covered by the GoldScout Data License. GoldScout is "
                  "a fan project, not affiliated with or endorsed by Blizzard Entertainment. World of Warcraft is a "
                  "trademark of Blizzard Entertainment, Inc.",
        "switch": ("de", "Deutsch"),
        "search": SEARCH_BOX,
    },
    "de": {
        "nav": '<a href="/de/farms">Farmen nach Stufe</a><a href="/de/fishing">Angeln</a>'
               '<a href="/de/drop-rates">Dropraten</a><a href="/de/companion">Companion</a>'
               '<a href="/leaderboard" lang="en">Leaderboard</a><a href="/faq" lang="en">FAQ</a>'
               '<a href="%(curseforge)s">GoldScout holen</a>',
        "footer": '<a href="/" lang="en">Home</a><a href="/de/farms">Farmen nach Stufe</a><a href="/de/fishing">Angeln</a>'
                  '<a href="/de/drop-rates">So funktionieren Dropraten</a><a href="/leaderboard" lang="en">Leaderboard</a>'
                  '<a href="/de/data-wanted">Daten gesucht</a><a href="/de/share">Daten teilen</a>'
                  '<a href="/faq" lang="en">FAQ</a>'
                  '<a href="%(discord)s">Discord</a><a href="%(source)s">GitHub</a>'
                  '<a href="%(privacy)s" lang="en">Privacy</a><a href="%(data_license)s" lang="en">Data license</a>',
        "notice": "Die Dropraten stammen von GoldScout-Spielern und stehen unter der GoldScout Data License. "
                  "Spielnamen, die noch kein deutscher Spieler erfasst hat, stehen kursiv auf Englisch. GoldScout ist "
                  "ein Fanprojekt, nicht mit Blizzard Entertainment verbunden und nicht von Blizzard unterstützt. "
                  "World of Warcraft ist eine Marke von Blizzard Entertainment, Inc.",
        "switch": ("en", "English"),
        "search": SEARCH_BOX_DE,
    },
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
.range { font-size: 12px; color: var(--muted); white-space: nowrap; }
.en-name { font-style: italic; }
a.lang-switch { color: var(--muted); text-decoration: none; font-size: 14px; margin-left: 18px; border: 1px solid var(--line); border-radius: 8px; padding: 2px 8px; white-space: nowrap; }
a.lang-switch:hover { color: var(--text); }
td.bar { width: 120px; }
td.bar { background: none; }
.goal-bar { position: relative; display: block; height: 10px; min-width: 110px; border-radius: 5px; background: var(--line); overflow: hidden; }
.goal-bar > span { display: block; height: 100%; min-width: 2px; background: var(--gold); }
.goal-bar i { position: absolute; top: 0; bottom: 0; width: 2px; margin-left: -1px; background: var(--bg2); opacity: .8; }
.zone-goal { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 4px 18px 10px; margin: 18px 0; }
.zone-goal .goal-bar { height: 14px; border-radius: 7px; margin: 4px 0 2px; }
.targets { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 4px 18px 12px; margin: 18px 0; }
.targets h2 { margin: 12px 0 4px; }
.target { display: grid; grid-template-columns: minmax(0, 17em) 1fr 7.5em; gap: 4px 14px; align-items: center; margin: 9px 0; }
.target .goal-bar { height: 12px; border-radius: 6px; }
.target-num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; color: var(--muted); }
.target-num b { color: var(--text); }
.target-num b.done { color: #40ff40; }
@media (max-width: 620px) { .target { grid-template-columns: 1fr auto; } .target .goal-bar { grid-column: 1 / -1; grid-row: 2; } }
b.done { color: #40ff40; }
ol.champions { margin: 4px 0 6px; padding-left: 24px; }
ol.champions li { margin: 3px 0; }
.champion.anon { color: var(--muted); }
td.bar .track { display: block; height: 8px; border-radius: 4px; background: var(--line); }
td.bar .good { display: block; height: 8px; min-width: 2px; border-radius: 4px; background: rgba(242,194,85,.4); }
td.bar .solid { display: block; height: 8px; border-radius: 4px; background: var(--gold); }
th.bar-head { width: 120px; }
.share-form { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 16px 18px; margin: 18px 0; display: grid; gap: 10px; }
.share-form[hidden] { display: none; }
.share-form textarea { width: 100%; box-sizing: border-box; min-height: 150px; resize: vertical; background: var(--bg2); color: var(--text); border: 1px solid var(--line); border-radius: 8px; padding: 10px; font: 13px/1.4 ui-monospace, Consolas, monospace; }
.share-form label.check { display: flex; gap: 10px; align-items: flex-start; color: var(--muted); }
.share-form label.check input { margin-top: 5px; flex: none; }
.share-form button { justify-self: start; cursor: pointer; }
.share-form button:disabled { opacity: .6; cursor: wait; }
.share-status { margin: 0; min-height: 1.4em; }
.share-board { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 4px 18px 16px; margin: 18px 0; display: grid; gap: 10px; }
.share-board[hidden] { display: none; }
.share-board h2 { margin: 12px 0 0; }
.share-board .sub { margin: 0; }
.share-board label.check { display: flex; gap: 10px; align-items: flex-start; }
.share-board label.check input { margin-top: 5px; flex: none; }
.share-board input[type=text] { max-width: 260px; background: var(--bg2); color: var(--text); border: 1px solid var(--line); border-radius: 8px; padding: 7px 10px; font: inherit; }
.share-board input[type=text]:disabled { opacity: .5; }
.share-board .small { margin: 0; }
.share-board button { justify-self: start; cursor: pointer; }
.share-status.good { color: #40ff40; }
.share-status.bad { color: #ff8a7a; }
.area-maps { display: flex; flex-wrap: wrap; gap: 0 28px; }
figure.area-map { margin: 10px 0 22px; width: 100%; max-width: 380px; }
figure.area-map:has(.area-art) { max-width: 640px; }
.area-maps figure.area-map:has(.area-art) { max-width: 480px; }
figure.area-map figcaption { color: var(--muted); font-size: 14px; margin-top: 6px; }
figure.area-map figcaption.zone { color: var(--text); font-weight: 600; margin: 0 0 4px; }
svg.area { display: block; width: 100%; height: auto; }
.area-art { position: relative; border-radius: 10px; overflow: hidden; border: 1px solid var(--line); background: var(--bg2); }
.area-art img { display: block; width: 100%; height: auto; }
.area-art svg { position: absolute; inset: 0; width: 100%; height: 100%; }
.area-art rect { fill: #2bff5e; stroke: #04310f; stroke-width: 2; }
svg.area .bg { fill: var(--bg2); stroke: var(--line); stroke-width: 1; }
svg.area .g { fill: var(--line); fill-opacity: .6; }
svg.area .l { stroke: var(--line); stroke-width: .6; }
svg.area .h { fill: var(--gold); stroke: var(--bg2); stroke-width: .6; }
svg.area text { fill: var(--muted); font-size: 9px; font-family: inherit; }
.conf.low { background: #ff8040; } .conf.fair { background: #ffd100; } .conf.good { background: #9be35a; } .conf.high { background: #40d040; }
.summary { font-size: 18px; max-width: 46em; margin: 10px 0 6px; }
ul.related { columns: 2; padding-left: 20px; margin: 0; } ul.related li { margin: 4px 0; break-inside: avoid; }
main.page .small a { color: var(--muted); }
.cta { margin-top: 34px; padding: 16px 18px; border: 1px solid var(--gold2); border-radius: 12px; background: rgba(242,194,85,.08); }
.table-wrap { overflow-x: auto; }
td.anon { color: var(--muted); font-style: italic; }
.pricebar { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; margin: 18px 0 8px; padding: 10px 14px; background: var(--panel); border: 1px solid var(--line); border-radius: 12px; font-size: 15px; }
.pricebar label { font-weight: 600; }
.pricebar select { margin-left: 6px; font: inherit; color: var(--text); background: var(--bg2); border: 1px solid var(--line); border-radius: 8px; padding: 4px 8px; }
.pricebar .status { color: var(--muted); }
.pricebar .source { flex-basis: 100%; color: var(--muted); font-size: 12px; }
.muted { color: var(--muted); }
[hidden] { display: none !important; }
.site-search { position: relative; max-width: 460px; margin: 0 0 8px; }
.site-search input { width: 100%; font: inherit; font-size: 16px; color: var(--text); background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 9px 14px; }
.site-search input:focus { outline: none; border-color: var(--gold2); }
.site-search .results { position: absolute; left: 0; right: 0; top: calc(100% + 4px); z-index: 10; list-style: none; margin: 0; padding: 4px; background: var(--bg2); border: 1px solid var(--line); border-radius: 10px; box-shadow: 0 12px 30px rgba(0,0,0,.5); max-height: 70vh; overflow-y: auto; }
.site-search .results a, ul.search-list a { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; padding: 7px 10px; border-radius: 7px; text-decoration: none; color: var(--text); }
.site-search .results a.active, .site-search .results a:hover, ul.search-list a:hover { background: var(--panel); }
.site-search .detail, ul.search-list .detail { color: var(--muted); font-size: 13px; text-align: right; }
.site-search .results li.none { padding: 8px 10px; color: var(--muted); font-size: 14px; }
ul.search-list { list-style: none; padding: 0; margin: 12px 0; max-width: 680px; }
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
<script src="/search.js" defer></script>
</head>
<body>
<div class="wrap">
<header class="top">
  <a class="brand" href="#"><img src="logo-400.png" alt="">GoldScout</a>
  <nav><a href="#features">Features</a><a href="/farms">Farms by level</a><a href="/fishing">Fishing</a><a href="/drop-rates">Drop rates</a><a href="/companion">Companion</a><a href="/faq">FAQ</a><a href="%(guide)s">Guide</a></nav>
</header>
%(search)s

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
  %(targets)s
  <ol class="steps">
    <li><b>You play.</b> GoldScout learns what every mob you loot really drops, on all your characters.</li>
    <li><b>You share.</b> <a href="/companion">GoldScout Companion</a> does it automatically, or use <code>/gscout export</code> and the <a href="/share">share page</a>. No character or account names, ever.</li>
    <li><b>It's checked.</b> Every submission is validated, and unusual drop rates are reviewed before they're used.</li>
    <li><b>Everyone gets it.</b> New community data ships in a release every day. Your own loot is never counted twice.</li>
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
""" % dict(LINKS, site=SITE_URL, css=CSS, shots=shots, jsonld=home_jsonld(), search=SEARCH_BOX, updated=updated, contributors_label=contributors_label, targets=s.get("targets", ""),
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


def language_links(path, lang):
    """hreflang alternates and the other language's address for a page that exists in every language,
    or ("", None). path is the page's own path (/de/... for German)."""
    english = path[len("/" + lang):] if lang != "en" else path
    if not data_pages.is_local_page(english):
        return "", None
    links = ['<link rel="alternate" hreflang="en" href="%s%s">' % (SITE_URL, english)]
    links += ['<link rel="alternate" hreflang="%s" href="%s/%s%s">' % (other, SITE_URL, other, english)
              for other in data_pages.LANGUAGES]
    links.append('<link rel="alternate" hreflang="x-default" href="%s%s">' % (SITE_URL, english))
    target, _ = CHROME[lang]["switch"]
    return "\n" + "\n".join(links), english if target == "en" else "/" + target + english


def layout(title, description, path, body, index=True, lang="en"):
    """A data page: the site's header and footer around body. index=False keeps it out of search engines.
    lang: the page's language (German pages live under /de/)."""
    chrome = CHROME[lang]
    alternates, other = language_links(path, lang)
    switch = ""
    if other:
        target, label = chrome["switch"]
        switch = '<a class="lang-switch" href="%s" hreflang="%s" lang="%s">%s</a>' % (other, target, target, label)
    return """<!doctype html>
<html lang="%(lang)s">
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
<link rel="canonical" href="%(site)s%(path)s">%(robots)s%(alternates)s
<link rel="icon" href="/favicon.png">
<style>%(css)s</style>
<script src="/prices.js" defer></script>
<script src="/search.js" defer></script>
</head>
<body>
<div class="wrap">
<header class="top">
  <a class="brand" href="/"><img src="/logo-400.png" alt="">GoldScout</a>
  <nav>%(nav)s</nav>%(switch)s
</header>
%(search)s
<main class="page"><div class="table-wrap">%(body)s</div></main>
</div>
<footer><div class="wrap">
  <p>%(footer)s</p>
  <p>%(notice)s</p>
</div></footer>
</body>
</html>
""" % dict(LINKS, site=SITE_URL, css=CSS, path=path, body=body, search=chrome["search"], lang=lang,
           nav=chrome["nav"] % LINKS, footer=chrome["footer"] % LINKS, notice=chrome["notice"],
           switch=switch, alternates=alternates,
           robots="" if index else '\n<meta name="robots" content="noindex, follow">',
           title=html.escape(title), description=html.escape(description))


TOP = 10 ** 9   # the site's own pages win ties with data pages ("fishing" finds Fishing for gold first)
STATIC_SEARCH = [
    ["Farms by level", "/farms", "The best gold farms for every level range", TOP],
    ["Fishing for gold", "/fishing", "Every zone players have fished, by gold per hour", TOP],
    ["How drop rates work", "/drop-rates", "Chance, ranges and how the data is checked", TOP],
    ["GoldScout Companion", "/companion", "Free app: hourly auction prices, shares your drops", TOP],
    ["Contributor leaderboard", "/leaderboard", "Who's shared the most drop data", TOP],
    ["Where data is needed", "/data-wanted", "Level ranges, zones and mobs with the least drop data", TOP],
    ["Share your drop data", "/share", "Paste your /gscout export to add it to the community data", TOP],
    ["FAQ", "/faq", "Questions about GoldScout", TOP],
]


def search_page_de():
    """/de/search, as search_page()."""
    body = """<h1>Suche</h1>
<p class="small" id="search-status">Suche läuft...</p>
<ul class="search-list" id="search-page-results"></ul>
<noscript><p class="small">Die Suche braucht JavaScript. <a href="/de/farms">Farmen nach Stufe</a> durchsehen.</p></noscript>
"""
    return ("Suche", "Gegenstände, Gegner, Gebiete und Angelplätze aus WoW Forever bei GoldScout suchen.", body)


def search_page():
    """(title, description, body) for /search; site/search.js lists the results for ?q=."""
    body = """<h1>Search</h1>
<p class="small" id="search-status">Searching...</p>
<ul class="search-list" id="search-page-results"></ul>
<noscript><p class="small">Search needs JavaScript. <a href="/farms">Browse farms by level</a> instead.</p></noscript>
"""
    return ("Search", "Search GoldScout's WoW Forever items, mobs, zones and fishing spots.", body)


STATIC_SEARCH_DE = [
    ["Farmen nach Stufe", "/de/farms", "Die besten Goldfarmen für jede Stufe", TOP],
    ["Angeln für Gold", "/de/fishing", "Jedes Gebiet, in dem Spieler geangelt haben, nach Gold pro Stunde", TOP],
    ["So funktionieren Dropraten", "/de/drop-rates", "Chance, Bereiche und wie die Daten geprüft werden", TOP],
    ["Wo GoldScout Daten braucht", "/de/data-wanted", "Stufen, Gebiete und Gegner mit den wenigsten Dropdaten", TOP],
    ["GoldScout Companion", "/de/companion", "App für Windows und Mac: stündliche Auktionspreise", TOP],
    ["Dropdaten teilen", "/de/share", "Füge deinen /gscout-Export ein und teile ihn", TOP],
    ["Bestenliste der Mitwirkenden", "/leaderboard", "Wer die meisten Dropdaten geteilt hat (auf Englisch)", TOP],
    ["FAQ", "/faq", "Fragen zu GoldScout (auf Englisch)", TOP],
]


def leaderboard_page():
    """(title, description, body) for /leaderboard; site/leaderboard.js fills the table in."""
    body = """<h1>Contributor leaderboard</h1>
<p class="summary">Every drop rate in GoldScout comes from players who share their loot. These are the players who've
shared the most, ranked by their kills that count in the community data.</p>
<p class="small" id="leaderboard-status">Loading the leaderboard...</p>
<table id="leaderboard" hidden>
<thead><tr><th class="num">Rank</th><th>Contributor</th><th class="num">Kills</th><th class="num">Mobs</th></tr></thead>
<tbody></tbody>
</table>
<noscript><p class="small">The leaderboard needs JavaScript.</p></noscript>

<div class="faq">
<h2>How it works</h2>
<h3>Who's on it?</h3>
<p>Everyone who shares drop data with <a href="/companion">GoldScout Companion</a> or the
<a href="/share">share page</a> is ranked, and
everyone is anonymous unless they choose otherwise. Each zone's page also lists its zone champions: the top three by
kills of the mobs there.</p>
<h3>How do I put my name on it?</h3>
<p>In GoldScout Companion, press <b>Leaderboard...</b> under Your data and tick <b>Show me on the public
leaderboard and zone pages</b>. If you share on the <a href="/share">share page</a>, the same choice appears there
after you share. You're shown under a name GoldScout makes up, or under a name of your own once it's approved.
Only your copy of the companion, or the browser you shared from, can change your entry. With the companion, your
rank also shows on GoldScout's minimap button.</p>
<h3>What counts?</h3>
<p>Kills that are in the community data: your export has to pass the data checks, and as in the data itself, at most
1,000 kills of any one mob count from one player. Scores update every hour.</p>
<h3>Can I leave?</h3>
<p>Untick <b>Show me on the public leaderboard and zone pages</b> any time and you're anonymous again. To remove your data
altogether, see the <a href="%(privacy)s">privacy policy</a>.</p>
</div>
<script src="/leaderboard.js" defer></script>
""" % LINKS
    return ("Contributor leaderboard",
            "The GoldScout players who've shared the most loot data, ranked by their kills in the community data.",
            body)


def share_page():
    """(title, description, body) for /share: paste a /gscout export and send it (site/share.js), as the companion
    does; the GitHub form stays as the other way."""
    body = """<h1>Share your drop data</h1>
<p class="summary">Every drop rate in GoldScout comes from players' loot. Paste your GoldScout export here and it
joins the community data, after the same checks as everything else, at the next hourly update. Each kill helps the
<a href="/data-wanted">community goals</a> and fills in the rates for everyone.</p>
<p><a href="/companion">GoldScout Companion</a> does this by itself every time you log out or /reload, along with
bringing in auction prices. No companion? This page works from any browser.</p>

<ol class="steps">
  <li><b>Export.</b> In game, type <code>/gscout export</code>. GoldScout opens a window with your data, already
  selected: press <b>Ctrl+C</b> to copy it.</li>
  <li><b>Paste.</b> Paste it below, tick the two boxes and press <b>Share</b>.</li>
</ol>

<form id="share-form" class="share-form" hidden>
  <label for="share-export">Your /gscout export</label>
  <textarea id="share-export" name="export" rows="8" spellcheck="false" autocomplete="off"
    placeholder="GoldScout-export 5^..."></textarea>
  <label class="check"><input type="checkbox" name="mine"> I collected this data myself by playing World of
  Warcraft with GoldScout.</label>
  <label class="check"><input type="checkbox" name="terms"> I agree to the <a href="%(terms)s">GoldScout
  Contributor Terms</a>, including the license they grant for this data.</label>
  <button class="btn primary" type="submit">Share</button>
  <p id="share-status" class="share-status" role="status" aria-live="polite"></p>
</form>
<section id="share-board" class="share-board" hidden>
  <h2>Your leaderboard entry</h2>
  <p id="board-rank" class="sub"></p>
  <label class="check"><input type="checkbox" id="board-public"> Show me on the public leaderboard and zone
  pages</label>
  <label for="board-name">Name (optional)</label>
  <input id="board-name" type="text" maxlength="20" autocomplete="off" spellcheck="false">
  <p class="small">Leave it empty to be shown under a name GoldScout makes up, like Patient Boar. A name of your
  own shows once it's approved. Your character or account name would tell others who you are. Turn this off any
  time to be anonymous again.</p>
  <button class="btn" type="button" id="board-save">Save</button>
  <p id="board-status" class="share-status" role="status" aria-live="polite"></p>
</section>
<noscript><p class="small">This form needs JavaScript. You can share through the
<a href="%(share)s">GitHub form</a> instead.</p></noscript>

<div class="faq">
<h2>Questions</h2>
<h3>What does the export contain?</h3>
<p>Only drop data: creature and item IDs, kill and drop counts, levels and where you looted, plus a random ID for
your WoW account's GoldScout data. Never character, account or realm names. See the
<a href="%(privacy)s">privacy policy</a>.</p>
<h3>Is it checked?</h3>
<p>Yes. Every export is validated, and if some of its drop rates are far off what other players see, it waits for a
person to review it before it's used. Accepted exports are added to the public
<a href="%(source)s">GitHub repository</a> under their random ID, like everyone's.</p>
<h3>Can I share again later?</h3>
<p>Yes, as often as you like: the newest export of your data replaces the last. This browser remembers a key for
your data, the way the companion does, so only it can update your data. If you also run the companion, it already
shares for you.</p>
<h3>Can I show my name on the leaderboard?</h3>
<p>Everyone who shares is on the <a href="/leaderboard">leaderboard</a> and the zone pages, anonymously unless they
choose otherwise. After you share, <b>Your leaderboard entry</b> appears on this page, in this browser: your rank,
and whether to be shown, under a name GoldScout makes up or one of your own.</p>
<h3>Prefer GitHub?</h3>
<p>The <a href="%(share)s">GitHub share form</a> still works. It posts your export as a public issue under your
GitHub account.</p>
</div>
<script src="/share.js" defer></script>
""" % LINKS
    return ("Share your GoldScout drop data",
            "Paste your /gscout export to add your loot to GoldScout's community drop rates for WoW Forever.",
            body)


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
<a href="/farms">the farms</a> get more accurate with every kill. The <a href="/leaderboard">contributor
leaderboard</a> ranks who's shared the most; you're anonymous on it unless you choose a name.</p>

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
<a href="/share">share page</a>. The companion does both for you.</p>
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


def companion_page_de(s):
    """/de/companion: companion_page() in German. Download links, privacy policy and terms stay the English
    originals (marked lang="en" where the link text is English)."""
    players = "%s Spieler" % format(s["contributors"], ",").replace(",", ".")
    body = """<h1>GoldScout Companion</h1>
<p class="summary">Eine App für Windows und Mac, die stündlich Auktionshauspreise in GoldScout bringt, ohne dass du
scannen musst, und deine Dropdaten teilt, damit der Farmen-Tab von GoldScout für alle immer besser wird.</p>
<p><a class="btn primary" href="%(companion)s">Für Windows herunterladen</a> <a class="btn primary" href="%(companion_mac)s">Für Mac herunterladen</a> <a class="btn" href="%(curseforge)s">Das GoldScout-Addon holen</a></p>
<p class="small">Code-signiert · aktualisiert sich selbst · Windows, und Macs mit Apple Silicon oder Intel · die App selbst ist auf Englisch</p>

<h2>Was du bekommst</h2>
<div class="grid">
  <div class="card"><h3>Stündlich Preise</h3><p>Blizzards Auktionshaus-Snapshot für deinen Realm und deine Fraktion,
    etwa einmal pro Stunde für GoldScout gespeichert. Die Ranglisten unter Farmen und Herstellen bleiben aktuell,
    ohne Gang zum Auktionshaus, und deine eigenen Scans gewinnen weiterhin, wenn sie neuer sind.</p></div>
  <div class="card"><h3>Auch Preise aus Blackwater</h3><p>Was Gegenstände in den Goblin-Auktionshäusern kosten, als
    zusätzliche Zeile im Tooltip. Sie ersetzen nie die Preise deiner eigenen Fraktion.</p></div>
  <div class="card"><h3>Bessere Dropraten für alle</h3><p>Jeder Gegner, den du lootest, zeigt GoldScout, was er
    wirklich fallen lässt. Die Companion-App teilt das für dich, damit das nächste Update mehr Gegner kennt, für dich
    und alle anderen Spieler.</p></div>
  <div class="card"><h3>Stört nicht</h3><p>Sie sitzt im Infobereich der Taskleiste (auf dem Mac im Dock), startet auf
    Wunsch bei der Anmeldung, erscheint nie über deinem Spiel und aktualisiert sich mit einem Klick.</p></div>
</div>

<h2>Warum das zählt</h2>
<p class="summary">GoldScout nutzt keine Daten von Wowhead oder einer anderen Seite: Jede Droprate stammt von
Spielern, die im Spiel looten. %(players)s haben bisher geteilt. Jeder neue Spieler füllt Gegner und Gebiete, die
noch niemand erfasst hat, und <a href="/de/farms">die Farmen</a> werden mit jedem Kill genauer. Die
<a href="/de/data-wanted">Gemeinschaftsziele</a> zeigen, wie weit wir sind; die
<a href="/leaderboard" lang="en">Bestenliste</a> (auf Englisch) zeigt, wer am meisten geteilt hat. Dort bist du
anonym, außer du wählst einen Namen.</p>

<h2>In einer Minute eingerichtet</h2>
<ol class="steps">
  <li><b>Installiere GoldScout</b> von <a href="%(curseforge)s">CurseForge</a> oder <a href="%(wago)s">Wago</a>, falls noch nicht geschehen.</li>
  <li><b>Lade die App herunter und starte sie.</b> Unter Windows musst du nichts installieren; auf dem Mac öffnest du
    die ZIP-Datei und ziehst GoldScout Companion in den Ordner Programme. Sie findet deinen WoW-Forever-Ordner selbst.</li>
  <li><b>Einmal entscheiden.</b> Stimme dem automatischen Teilen zu oder wähle <span lang="en">Not now</span> und
    nutze sie nur für Preise.</li>
  <li><b>Spielen.</b> GoldScout lädt neue Preise, wenn du dich einloggst oder <code>/reload</code> eingibst, und sein
    Fenster bietet <b>Load newer prices</b> an, sobald ein frischerer Snapshot bereitliegt.</li>
</ol>

<div class="faq">
<h2>Fragen</h2>
<h3>Greift sie ins Spiel ein?</h3>
<p>Nein. Sie liest die gespeicherte Datendatei von GoldScout und schreibt ein kleines Daten-Addon, GoldScout_Prices,
das das Spiel beim Einloggen wie jedes andere Addon lädt. Das laufende Spiel liest oder verändert sie nie. Die
Auktionspreise stammen aus Blizzards offizieller Game Data API.</p>
<h3>Was teilt sie?</h3>
<p>Nur die Dropdaten von GoldScout: IDs von Gegnern und Gegenständen, Kill- und Dropzahlen, Stufen und wo du gelootet
hast, dazu eine zufällige ID. Nie Namen von Charakteren, Accounts oder Realms. Siehe die
<a href="%(privacy)s" lang="en">Privacy Policy</a> und die <a href="%(terms)s" lang="en">Contributor Terms</a>
(auf Englisch).</p>
<h3>Brauche ich sie?</h3>
<p>Nein. GoldScout funktioniert auch allein: Scanne im Auktionshaus und teile mit <code>/gscout export</code> und der
<a href="/de/share">Teilen-Seite</a>. Die Companion-App macht beides für dich.</p>
<h3>Unterbricht sie mein Spiel?</h3>
<p>Nein. Ihre einzige Benachrichtigung meldet eine neue Version, und sie wartet damit, bis World of Warcraft
geschlossen ist.</p>
<h3>Ist sie sicher?</h3>
<p>Jede Version ist code-signiert (auf dem Mac zusätzlich von Apple geprüft), daher zeigt dein Computer, wer sie
veröffentlicht hat, und die App installiert nur Updates, die genauso signiert sind. Der Quellcode liegt auf
<a href="%(source)s">GitHub</a>.</p>
<h3>Gibt es eine Mac-Version?</h3>
<p>Ja, für Macs mit Apple Silicon oder Intel: <a href="%(companion_mac)s">herunterladen</a>, die ZIP-Datei öffnen und
GoldScout Companion in den Ordner Programme ziehen. Auf dem Mac lebt sie im Dock statt im Infobereich, und unter
<b>Settings</b> in ihrem Fenster findest du Teilen, Auktionspreise, <b>Open at login</b> und Updates.</p>
</div>
<p class="small" style="margin-top:28px">Auktionsdaten aus der Game Data API von Blizzard Entertainment. GoldScout ist
nicht mit Blizzard Entertainment verbunden und wird nicht von Blizzard unterstützt.</p>
""" % dict(LINKS, players=html.escape(players))
    return ("GoldScout Companion: stündliche Auktionspreise für GoldScout",
            "Eine App für Windows und Mac, die stündlich Auktionshauspreise ins GoldScout-Addon bringt, ohne zu "
            "scannen, und Dropdaten teilt, damit der Farmen-Tab für alle besser wird.", body)


def share_page_de():
    """/de/share: share_page() in German (site/share.js answers in German on <html lang="de">)."""
    body = """<h1>Teile deine Dropdaten</h1>
<p class="summary">Jede Droprate in GoldScout stammt aus der Beute von Spielern. Füge hier deinen GoldScout-Export ein,
und er fließt nach denselben Prüfungen wie alles andere beim nächsten stündlichen Update in die Gemeinschaftsdaten.
Jeder Kill hilft bei den <a href="/de/data-wanted">Gemeinschaftszielen</a> und macht die Raten für alle genauer.</p>
<p><a href="/de/companion">GoldScout Companion</a> macht das von selbst, jedes Mal wenn du dich ausloggst oder
<code>/reload</code> eingibst, und bringt dazu Auktionspreise ins Spiel. Keine Companion-App? Diese Seite
funktioniert in jedem Browser.</p>

<ol class="steps">
  <li><b>Exportieren.</b> Gib im Spiel <code>/gscout export</code> ein. GoldScout öffnet ein Fenster mit deinen Daten,
  schon markiert: Drücke <b>Strg+C</b>, um sie zu kopieren.</li>
  <li><b>Einfügen.</b> Füge sie unten ein, setze die beiden Haken und drücke <b>Teilen</b>.</li>
</ol>

<form id="share-form" class="share-form" hidden>
  <label for="share-export">Dein /gscout-Export</label>
  <textarea id="share-export" name="export" rows="8" spellcheck="false" autocomplete="off"
    placeholder="GoldScout-export 5^..."></textarea>
  <label class="check"><input type="checkbox" name="mine"> Ich habe diese Daten selbst gesammelt, beim Spielen von
  World of Warcraft mit GoldScout.</label>
  <label class="check"><input type="checkbox" name="terms"> Ich stimme den
  <a href="%(terms)s" lang="en">GoldScout Contributor Terms</a> (auf Englisch) zu, einschließlich der Lizenz, die sie für
  diese Daten erteilen.</label>
  <button class="btn primary" type="submit">Teilen</button>
  <p id="share-status" class="share-status" role="status" aria-live="polite"></p>
</form>
<section id="share-board" class="share-board" hidden>
  <h2>Dein Eintrag in der Bestenliste</h2>
  <p id="board-rank" class="sub"></p>
  <label class="check"><input type="checkbox" id="board-public"> Zeig mich in der öffentlichen Bestenliste und auf
  den Gebietsseiten</label>
  <label for="board-name">Name (optional)</label>
  <input id="board-name" type="text" maxlength="20" autocomplete="off" spellcheck="false">
  <p class="small">Lass ihn leer, dann erscheinst du unter einem Namen, den GoldScout erfindet, etwa Patient Boar.
  Ein eigener Name erscheint, sobald er freigegeben ist. Dein Charakter- oder Accountname würde anderen verraten,
  wer du bist. Schalte das jederzeit ab, um wieder anonym zu sein.</p>
  <button class="btn" type="button" id="board-save">Speichern</button>
  <p id="board-status" class="share-status" role="status" aria-live="polite"></p>
</section>
<noscript><p class="small">Dieses Formular braucht JavaScript. Du kannst stattdessen über das
<a href="%(share)s">GitHub-Formular</a> teilen.</p></noscript>

<div class="faq">
<h2>Fragen</h2>
<h3>Was steht im Export?</h3>
<p>Nur Dropdaten: IDs von Gegnern und Gegenständen, Kill- und Dropzahlen, Stufen und wo du gelootet hast, dazu eine
zufällige ID für die GoldScout-Daten deines WoW-Accounts. Nie Namen von Charakteren, Accounts oder Realms. Siehe die
<a href="%(privacy)s" lang="en">Privacy Policy</a> (auf Englisch).</p>
<h3>Wird er geprüft?</h3>
<p>Ja. Jeder Export wird geprüft, und wenn einige seiner Dropraten weit von dem abweichen, was andere Spieler sehen,
wartet er auf eine Prüfung durch einen Menschen, bevor er verwendet wird. Angenommene Exporte landen unter ihrer
zufälligen ID im öffentlichen <a href="%(source)s">GitHub-Repository</a>, wie die aller anderen.</p>
<h3>Kann ich später wieder teilen?</h3>
<p>Ja, so oft du willst: Der neueste Export deiner Daten ersetzt den letzten. Dieser Browser merkt sich einen
Schlüssel für deine Daten, so wie die Companion-App, damit nur er sie aktualisieren kann. Wenn du auch die
Companion-App nutzt, teilt sie bereits für dich.</p>
<h3>Kann ich meinen Namen in der Bestenliste zeigen?</h3>
<p>Alle, die teilen, stehen in der <a href="/leaderboard" lang="en">Bestenliste</a> und auf den Gebietsseiten,
anonym, außer sie wählen etwas anderes. Nach dem Teilen erscheint auf dieser Seite, in diesem Browser,
<b>Dein Eintrag in der Bestenliste</b>: dein Rang und ob du gezeigt wirst, unter einem von GoldScout erfundenen
oder einem eigenen Namen.</p>
<h3>Lieber über GitHub?</h3>
<p>Das <a href="%(share)s">GitHub-Formular</a> funktioniert weiterhin (auf Englisch). Es veröffentlicht deinen Export
als öffentliches Issue unter deinem GitHub-Konto.</p>
</div>
<script src="/share.js" defer></script>
""" % LINKS
    return ("Teile deine GoldScout-Dropdaten",
            "Füge deinen /gscout-Export ein, um deine Beute zu den Gemeinschafts-Dropraten von GoldScout für WoW Forever "
            "beizutragen.", body)


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "screenshots").mkdir(parents=True)
    for name, _, _ in SCREENSHOTS:
        shutil.copy2(ROOT / "docs" / "screenshots" / name, DIST / "screenshots" / name)
    shutil.copy2(ROOT / "docs" / "logo" / "goldscout-logo-400.png", DIST / "logo-400.png")
    shutil.copy2(ROOT / "companion" / "icon.png", DIST / "favicon.png")
    shutil.copy2(HERE / "prices.js", DIST / "prices.js")
    shutil.copy2(HERE / "leaderboard.js", DIST / "leaderboard.js")
    shutil.copy2(HERE / "search.js", DIST / "search.js")
    shutil.copy2(HERE / "champions.js", DIST / "champions.js")
    shutil.copy2(HERE / "share.js", DIST / "share.js")
    if (HERE / "maps").is_dir():   # the game's zone maps (tools/zone_maps.py)
        shutil.copytree(HERE / "maps", DIST / "maps", dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.md"))
    results = merge_data.load(ROOT / "data" / "submissions")
    merged = merge_data.merge([r.mobs for r in results], 1000)
    s = stats(results, merged)
    data = data_pages.Dataset(results, merged, merge_data.merge_fish([r.fishing for r in results], 1000))
    s["targets"] = data_pages.targets_section(data)
    (DIST / "index.html").write_text(page(s), encoding="utf-8")

    def write(relative, title, description, body, index=True, lang="en"):
        target = DIST / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        url_path = "/" + relative[:-len(".html")]
        target.write_text(layout(title, description, url_path, body, index, lang), encoding="utf-8")

    def write_de(relative, title, description, body, index=True):
        write("de/" + relative, title, description, body, index, "de")

    write("companion.html", *companion_page(s))
    write("faq.html", *faq_page())
    write("leaderboard.html", *leaderboard_page())
    write("share.html", *share_page())
    paths = ["/", "/companion", "/leaderboard", "/faq", "/share"] + data_pages.build(data, LINKS, write)
    write("search.html", *search_page(), index=False)   # results for one visitor's words: not for search engines
    index = data_pages.search_index(data) + STATIC_SEARCH
    (DIST / "search.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    # German: the same data pages under /de/, with German names where German players have recorded them.
    paths += ["/de" + path for path in data_pages.build_language("de", data, LINKS, write_de)]
    write_de("search.html", *search_page_de(), index=False)
    write_de("companion.html", *companion_page_de(s))
    write_de("share.html", *share_page_de())
    paths += ["/de/companion", "/de/share"]
    data_pages.LANG = "de"
    try:
        index_de = data_pages.search_index(data) + STATIC_SEARCH_DE
    finally:
        data_pages.LANG = "en"
    (DIST / "search-de.json").write_text(json.dumps(index_de, ensure_ascii=False, separators=(",", ":")),
                                         encoding="utf-8")
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
        '<link rel="icon" href="/favicon.png"><style>%s</style><script src="/search.js" defer></script></head>'
        '<body><div class="wrap">'
        '<header class="top"><a class="brand" href="/"><img src="/logo-400.png" alt="">GoldScout</a></header>'
        '<section><h2>Page not found</h2><p class="sub">That page doesn\'t exist. Search for what you were after, '
        'or start from the home page.</p>%s'
        '<a class="btn primary" href="/">Go to the GoldScout home page</a></section></div></body></html>'
        % (CSS, SEARCH_BOX),
        encoding="utf-8")
    # Item pages replaced the reagent-only pages (2026-11-14); keep old links and search results working.
    (DIST / "_redirects").write_text("/reagent/:id /item/:id 301\n", encoding="utf-8")
    # Cloudflare injects its Web Analytics beacon into every page: the script comes from
    # static.cloudflareinsights.com and reports to cloudflareinsights.com.
    (DIST / "_headers").write_text(
        "/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n"
        "  Content-Security-Policy: default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; "
        "script-src 'self' %s; connect-src 'self' %s %s; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'\n"
        # Zone maps only change when tools/zone_maps.py is rerun, so browsers keep them a week
        # instead of asking again on every page.
        "/maps/*\n  Cache-Control: public, max-age=604800\n"
        % (ANALYTICS_SCRIPT, API_URL, ANALYTICS_REPORT), encoding="utf-8")
    print("Built %s: %d contributors, %d mobs, %d kills, %d pages." % (
        DIST, s["contributors"], s["mobs"], s["kills"], len(paths)))


if __name__ == "__main__":
    main()
