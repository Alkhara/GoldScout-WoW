"""The website's data pages, built from the merged community data: one page
per mob, one per item players loot (everything but gray vendor trash), one
per zone, farms by level, and how the numbers work.

Pages whose numbers rest on fewer than INDEX_MIN kills are built but kept out
of search engines (noindex, left out of the sitemap) until more players loot
there: thin pages drag down how a search engine rates the whole site.

Names come from players' exports (@i, @m lines and mob names) and are always
HTML-escaped. Item kinds come from @q lines (export version 4): until an item
has one, it's shown under "Drops" without being sorted into reagents.

Every page gets breadcrumbs (visible, plus schema.org BreadcrumbList data) and
a plain-language summary a search engine can quote.

Prices aren't built in: they change every hour. Pages mark where they go
(data-price, data-qty, data-value) and site/prices.js fills them in the browser
from the GoldScout server's copy of Blizzard's auction data, for the realm type
and faction the visitor picks in the price bar.
"""
import html
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

SITE_URL = "https://wowgoldscout.com"
MIN_ATTEMPTS = 5                 # same threshold as the shipped community data
INDEX_MIN = 15                   # kills (or pickpockets) before a page is offered to search engines
RARE_CLASSES = {2, 4, 9}         # weapons, armor, recipes: rare world drops
GEM_CLASS = 3
ADDON = Path(__file__).resolve().parent.parent / "GoldScout"


def addon_gems():
    """Item IDs in the addon's ns.GEMS (Data.lua): gems that drop at random from many mobs.
    The Farm tab treats them like gear, so the site does too."""
    source = (ADDON / "Data.lua").read_text(encoding="utf-8")
    block = re.search(r"ns\.GEMS = \{(.*?)\n\}", source, re.S)
    return {int(item) for item in re.findall(r"\[(\d+)\]", block.group(1))} if block else set()


def addon_pace(setting):
    """A default pace from the addon's settings (Core.lua), so the site's gold per hour matches the Farm tab's."""
    source = (ADDON / "Core.lua").read_text(encoding="utf-8")
    return int(re.search(r"\b%s = (\d+)" % setting, source).group(1))


GEMS = addon_gems()
KILLS_PER_HOUR = addon_pace("killsPerHour")
PICKS_PER_HOUR = addon_pace("picksPerHour")


def wilson(hits, trials, z=1.96):
    """The 95% range a drop chance really lies in, given hits out of trials (Wilson score interval)."""
    if trials <= 0:
        return 0.0, 1.0
    p = hits / trials
    centre = p + z * z / (2 * trials)
    spread = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials))
    scale = 1 + z * z / trials
    return max(0.0, (centre - spread) / scale), min(1.0, (centre + spread) / scale)
BRACKETS = [(1, 10), (11, 20), (21, 30), (31, 40), (41, 50), (51, 63)]
CONFIDENCE = [(50, "high"), (15, "good"), (5, "fair"), (0, "low")]
PLAYER_CAP = 1000                # kills per mob counted from any one player
RELATED = 8                      # cross-links per list

e = html.escape


def confidence(attempts):
    for minimum, name in CONFIDENCE:
        if attempts >= minimum:
            return name
    return "low"


def percent(rate):
    if rate >= 0.1:
        return "%d%%" % round(rate * 100)
    return "%.1f%%" % (rate * 100)


def bracket_of(level):
    for low, high in BRACKETS:
        if low <= level <= high:
            return low, high
    return None


def bracket_label(bracket):
    low, high = bracket
    return "Levels %d-%d" % (low, min(high, 60))


def bracket_anchor(bracket):
    low, high = bracket
    return "levels-%d-%d" % (low, min(high, 60))


class Dataset:
    def __init__(self, results, merged):
        self.mobs = {npc: entry for npc, entry in merged.items() if entry["k"] + entry["p"] >= MIN_ATTEMPTS}
        item_votes, map_votes, meta_votes = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
        for result in results:
            for item, name in result.item_names.items():
                item_votes[item][name] += 1
            for map_id, name in result.map_names.items():
                map_votes[map_id][name] += 1
            for item, meta in result.item_meta.items():
                meta_votes[item][meta] += 1
        self.item_names = {item: votes.most_common(1)[0][0] for item, votes in item_votes.items()}
        self.map_names = {map_id: votes.most_common(1)[0][0] for map_id, votes in map_votes.items()}
        self.item_meta = {item: votes.most_common(1)[0][0] for item, votes in meta_votes.items()}
        self.has_kinds = bool(self.item_meta)
        self.reagent_sources = defaultdict(list)
        # Every item worth a page (not gray): [(npc, rate, stack, attempts, per)], per "kill" or "pickpocket".
        self.sources = defaultdict(list)
        self.zones = defaultdict(list)
        for npc in self.mobs:
            for key, per in (("i", "kill"), ("pi", "pickpocket")):
                attempts = self.mobs[npc]["k" if key == "i" else "p"]
                for item, rate, stack in self.drops(npc, key):
                    if self.kind(item) == "gray":
                        continue
                    self.sources[item].append((npc, rate, stack, attempts, per))
                    if key == "i" and self.kind(item) == "reagent":
                        self.reagent_sources[item].append((npc, rate, stack))
            zone = self.zone_id(npc)
            if zone is not None:
                self.zones[zone].append(npc)
        for sources in self.reagent_sources.values():
            sources.sort(key=lambda pair: -pair[1])
        for sources in self.sources.values():
            sources.sort(key=lambda source: (source[3] < INDEX_MIN, -self.cautious(source), source[0]))
        for npcs in self.zones.values():
            npcs.sort(key=lambda npc: (self.mid_level(npc), self.mob_name(npc)))

    # -- names and kinds --------------------------------------------------------
    def item_name(self, item):
        return self.item_names.get(item, "Item %d" % item)

    def kind(self, item):
        meta = self.item_meta.get(item)
        if not meta:
            return "unknown"
        quality, class_id, reagent = meta
        if quality == 0:
            return "gray"
        if class_id in RARE_CLASSES or class_id == GEM_CLASS or item in GEMS:
            return "rare"
        return "reagent" if reagent else "other"

    def mob_name(self, npc):
        names = self.mobs[npc]["names"]
        return max(names.items(), key=lambda pair: (pair[1], pair[0]))[0] if names else "Mob %d" % npc

    def zone_id(self, npc):
        """The map the mob was seen on most, if players' exports named it."""
        maps = self.mobs[npc]["maps"]
        if not maps:
            return None
        map_id = max(maps.items(), key=lambda pair: (pair[1][2], pair[0]))[0]
        return map_id if map_id in self.map_names else None

    def zone(self, npc):
        map_id = self.zone_id(npc)
        return self.map_names[map_id] if map_id is not None else ""

    def levels(self, npc):
        entry = self.mobs[npc]
        if not entry["lmin"]:
            return ""
        if entry["lmin"] == entry["lmax"]:
            return str(entry["lmin"])
        return "%d-%d" % (entry["lmin"], entry["lmax"])

    def mid_level(self, npc):
        entry = self.mobs[npc]
        return (entry["lmin"] + entry["lmax"]) / 2 if entry["lmin"] else 0

    def bracket(self, npc):
        return bracket_of(self.mid_level(npc))

    def drops(self, npc, key="i"):
        """(item, rate, average stack) for a mob's drops (or pickpocket items), best first."""
        entry = self.mobs[npc]
        attempts = entry["k"] if key == "i" else entry["p"]
        if not attempts:
            return []
        rows = [(item, d / attempts, q / d if d else 1) for item, (d, q) in entry[key].items() if d]
        return sorted(rows, key=lambda row: -row[1])

    @staticmethod
    def cautious(source):
        """Items per kill (or pickpocket) at the low end of the drop chance's range. Sources are ranked by it,
        those with INDEX_MIN kills first, so a lucky few kills don't beat a mob players have pinned down."""
        _, rate, stack, attempts, _ = source
        return wilson(round(rate * attempts), attempts)[0] * stack

    def attempts(self, npc):
        return self.mobs[npc]["k"] + self.mobs[npc]["p"]

    def mob_indexed(self, npc):
        return self.attempts(npc) >= INDEX_MIN

    def item_indexed(self, item):
        return any(attempts >= INDEX_MIN for _, _, _, attempts, _ in self.sources[item])

    def best_drops(self, npc):
        """A mob's crafting reagent drops (every drop until items have kinds), best first."""
        rows = self.drops(npc)
        if self.has_kinds:
            rows = [row for row in rows if self.kind(row[0]) == "reagent"]
        return rows


def json_for_script(data):
    """JSON for a <script type="application/ld+json"> element."""
    text = json.dumps(data, ensure_ascii=False)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


# -- shared pieces ---------------------------------------------------------------
LOADING = "&hellip;"
SOURCE = ("Auction data from the Blizzard Entertainment Game Data API. "
          "GoldScout is not affiliated with or endorsed by Blizzard.")


def per_kill(rows):
    """data-value for prices.js: each item's chance x average stack, so price x it = gold per kill."""
    return ",".join("%d:%s" % (item, ("%.4f" % (rate * stack)).rstrip("0").rstrip("."))
                    for item, rate, stack in rows)


def price_bar():
    """Where the visitor picks a realm type and faction; prices.js fills it in."""
    return ('<div id="prices-bar" class="pricebar"><label>Auction prices for '
            '<select aria-label="Realm type and faction" hidden></select></label> '
            '<span class="status">Turn on JavaScript to see current auction prices.</span>'
            '<span class="source">%s</span></div>' % SOURCE)


def price_cell(item):
    return '<td class=num data-price="%d">%s</td>' % (item, LOADING)


def value_cell(rows):
    return '<td class=num data-value="%s">%s</td>' % (per_kill(rows), LOADING)

def crumbs(trail):
    """Visible breadcrumbs plus schema.org BreadcrumbList data. trail: [(path, label)], last is this page."""
    links = " &rsaquo; ".join('<a href="%s">%s</a>' % (path, e(label)) for path, label in trail[:-1])
    data = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": n, "name": label, "item": SITE_URL + path}
        for n, (path, label) in enumerate(trail, 1)]}
    # Inside a script element HTML escaping doesn't apply; escaping <, > and & in
    # the JSON (same value) means nothing in a name can end or break the element.
    script = json_for_script(data)
    return '<p class=crumbs>%s</p><script type="application/ld+json">%s</script>' % (links, script)


def farms_trail(data, npc=None, bracket=None):
    trail = [("/", "Home"), ("/farms", "Farms by level")]
    bracket = bracket or (data.bracket(npc) if npc is not None else None)
    if bracket:
        trail.append(("/farms#" + bracket_anchor(bracket), bracket_label(bracket)))
    return trail


def mob_link(data, npc):
    return '<a href="/mob/%d">%s</a>' % (npc, e(data.mob_name(npc)))


def zone_link(data, npc):
    map_id = data.zone_id(npc)
    if map_id is None:
        return ""
    return '<a href="/zone/%d">%s</a>' % (map_id, e(data.map_names[map_id]))


def item_link(data, item):
    name = e(data.item_name(item))
    if item in data.sources:
        return '<a href="/item/%d">%s</a>' % (item, name)
    return name


item_cell = item_link


def chance(rate, attempts):
    """A drop chance with the 95% range it really lies in, from the kills behind it."""
    low, high = wilson(round(rate * attempts), attempts)
    return ('%s <span class="range" title="95%% likely between these, from %d recorded">%s&ndash;%s</span>'
            % (percent(rate), attempts, percent(low).rstrip("%"), percent(high)))


def badge(attempts):
    level = confidence(attempts)
    return '<span class="conf %s" title="%d kills recorded">%s</span>' % (level, attempts, level)


def legend():
    return ('<p class=small>Chance is how often players got the item per kill; the small numbers are the range '
            'it is 95%% likely to be in, which narrows as more kills are recorded. Counted in WoW Forever only: '
            'no Classic Era data is mixed in. <a href="/drop-rates">How these numbers work</a></p>')


def drop_table(data, rows, attempts, per="kill"):
    body = "".join(
        "<tr><td>%s</td><td class=num>%s</td><td class=num>%s</td>%s%s</tr>"
        % (item_cell(data, item), chance(rate, attempts), ("%.1f" % stack).rstrip("0").rstrip("."),
           price_cell(item), value_cell([(item, rate, stack)]))
        for item, rate, stack in rows)
    return ("<table><thead><tr><th>Item</th><th class=num>Chance</th><th class=num>Avg. stack</th>"
            "<th class=num>Price</th><th class=num>Per %s</th></tr></thead><tbody>%s</tbody></table>" % (per, body))


def mob_table(data, npcs, zone_column=True):
    """Mobs with their best reagent drops and gold per kill; prices.js re-sorts by gold per kill."""
    rows = "".join(
        "<tr><td>%s</td><td class=nowrap>%s</td>%s<td>%s</td>%s</tr>"
        % (mob_link(data, npc), e(data.levels(npc)),
           "<td>%s</td>" % zone_link(data, npc) if zone_column else "",
           ", ".join("%s %s" % (item_cell(data, item), percent(rate))
                     for item, rate, _ in data.best_drops(npc)[:3]) or '<span class=small>none yet</span>',
           value_cell(data.best_drops(npc)))
        for npc in npcs)
    return ("<table class=by-value><thead><tr><th>Mob</th><th>Level</th>%s<th>Best reagent drops</th>"
            "<th class=num>Gold per kill</th></tr></thead><tbody>%s</tbody></table>"
            % ("<th>Zone</th>" if zone_column else "", rows))


def link_list(items):
    return "<ul class=related>%s</ul>" % "".join("<li>%s</li>" % item for item in items)


def cta(links):
    return ("<div class=cta><b>Help fill this in.</b> Every number here comes from players looting in game. "
            "Install <a href=\"%(curseforge)s\">GoldScout</a> and add "
            "<a href=\"/companion\">GoldScout Companion</a>: it brings auction prices into the game every hour "
            "without scanning, and shares what you loot automatically. More players, better data for "
            "everyone.</div>" % links)


# -- pages -----------------------------------------------------------------------
def mob_summary(data, npc):
    """One or two plain sentences about a mob (unescaped)."""
    name, level, zone = data.mob_name(npc), data.levels(npc), data.zone(npc)
    where = " in %s" % zone if zone else ""
    what = "a level %s mob%s" % (level, where) if level else "a mob%s" % where
    kills = data.mobs[npc]["k"]
    text = "%s is %s in WoW Forever. GoldScout players have recorded %s kill%s." % (
        name, what, format(kills, ","), "" if kills == 1 else "s")
    best = data.best_drops(npc)
    if best:
        kind = "crafting reagent" if data.has_kinds else "drop"
        text += " Its most common %s is %s (%s of kills)." % (kind, data.item_name(best[0][0]), percent(best[0][1]))
    return text


def mob_page(data, npc, links):
    entry = data.mobs[npc]
    name = data.mob_name(npc)
    drops = data.drops(npc)
    sections = []
    if data.has_kinds:
        reagents = [row for row in drops if data.kind(row[0]) == "reagent"]
        others = [row for row in drops if data.kind(row[0]) in ("other", "unknown", "rare")]
        if reagents:
            sections.append("<h2>Crafting reagents</h2>" + drop_table(data, reagents, entry["k"]))
        if others:
            sections.append("<h2>Other drops</h2>" + drop_table(data, others, entry["k"]))
    elif drops:
        sections.append("<h2>Drops</h2>" + drop_table(data, drops, entry["k"]))
    picks = data.drops(npc, "pi")
    if picks:
        sections.append("<h2>Pickpocketing</h2><p class=sub>Chance per pickpocket, over %d attempts.</p>"
                        % entry["p"] + drop_table(data, picks, entry["p"], per="pickpocket"))
    if sections:
        sections.append(legend())
    else:
        sections.append("<p class=sub>No drops recorded yet.</p>")
    zone_id = data.zone_id(npc)
    if zone_id is not None:
        siblings = [other for other in data.zones[zone_id] if other != npc][:RELATED]
        if siblings:
            sections.append("<h2>More farms in %s</h2>%s" % (
                e(data.map_names[zone_id]),
                link_list("%s <span class=small>level %s</span>" % (mob_link(data, other), e(data.levels(other)))
                          for other in siblings)))
    level = data.levels(npc)
    facts = ["Level %s" % e(level)] if level else []
    if zone_id is not None:
        facts.append(zone_link(data, npc))
    facts.append("%s kills recorded %s" % (format(entry["k"], ","), badge(entry["k"])))
    best = data.best_drops(npc)
    worth = ""
    if best:
        worth = ('<p class=facts>%s are worth about <b data-value="%s">%s</b> per kill at current prices.</p>'
                 % ("Its crafting reagents" if data.has_kinds else "Its drops", per_kill(best), LOADING))
    body = ("%s<h1>%s</h1><p class=facts>%s</p><p class=summary>%s</p>%s%s%s%s"
            % (crumbs(farms_trail(data, npc) + [("/mob/%d" % npc, name)]), e(name), " &middot; ".join(facts),
               e(mob_summary(data, npc)), price_bar(), worth, "".join(sections), cta(links)))
    title = "%s drops and drop rates (WoW Forever)" % name
    best = data.best_drops(npc)[:2]
    if best:
        description = "%s drop rates in WoW Forever: %s, from %d kills recorded by GoldScout players." % (
            name, ", ".join("%s %s" % (data.item_name(item), percent(rate)) for item, rate, _ in best),
            entry["k"])
    else:
        description = "What %s drops in WoW Forever, with drop rates from %d kills recorded by GoldScout players." % (
            name, entry["k"])
    return title, description, body


KIND_TEXT = {"reagent": "a crafting reagent", "rare": "a rare world drop", "other": "an item",
             "unknown": "an item"}


def source_where(data, npc):
    """'level 21-22, Ashenvale' for a summary, or ''."""
    bits = []
    if data.levels(npc):
        bits.append("level %s" % data.levels(npc))
    if data.zone(npc):
        bits.append(data.zone(npc))
    return ", ".join(bits)


def source_table(data, item, sources, per):
    """Where an item comes from, best first, with gold per kill and per hour at the visitor's prices."""
    pace = KILLS_PER_HOUR if per == "kill" else PICKS_PER_HOUR
    noun = "Kills" if per == "kill" else "Pickpockets"
    rows = "".join(
        "<tr><td>%s</td><td class=nowrap>%s</td><td>%s</td><td class=num>%s</td><td class=num>%s %s</td>%s%s</tr>"
        % (mob_link(data, npc), e(data.levels(npc)), zone_link(data, npc), chance(rate, attempts),
           format(attempts, ","), badge(attempts), value_cell([(item, rate, stack)]),
           value_cell([(item, rate * pace, stack)]))
        for npc, rate, stack, attempts, _ in sources)
    return ("<table><thead><tr><th>%s</th><th>Level</th><th>Zone</th><th class=num>Chance</th>"
            "<th class=num>%s</th><th class=num>Gold per %s</th><th class=num>Gold per hour*</th></tr></thead>"
            "<tbody>%s</tbody></table><p class=small>* At %d %s an hour. In game, GoldScout works it out for your "
            "character, at your own pace and level.</p>"
            % ("Dropped by" if per == "kill" else "Pickpocketed from", noun, per, rows, pace,
               "kills" if per == "kill" else "pickpockets"))


def item_page(data, item, links):
    """'Where to farm X': every mob players have looted (or pickpocketed) it from, most reliable first."""
    name = data.item_name(item)
    sources = data.sources[item]
    kills = [source for source in sources if source[4] == "kill"]
    picks = [source for source in sources if source[4] == "pickpocket"]
    top_npc, top_rate, _, top_attempts, top_per = sources[0]
    where = source_where(data, top_npc)
    count = len({source[0] for source in sources})
    looted = "looted it from" if kills else "pickpocketed it from"
    summary = ("%s is %s in WoW Forever. GoldScout players have %s %d mob%s; the best source is %s%s, "
               "which gave it on %s of %s %s." % (
                   name, KIND_TEXT[data.kind(item)], looted, count, "" if count == 1 else "s",
                   data.mob_name(top_npc), " (%s)" % where if where else "", percent(top_rate),
                   format(top_attempts, ","), "kills" if top_per == "kill" else "pickpockets"))
    sections = []
    if kills:
        sections.append("<h2>Where it drops</h2>" + source_table(data, item, kills, "kill"))
    if picks:
        sections.append("<h2>Pickpocketing</h2>" + source_table(data, item, picks, "pickpocket"))
    sections.append(legend())
    related, seen = [], {item}
    for npc, _, _, _, _ in sources:
        for other, _, _ in data.drops(npc):
            if other not in seen and other in data.sources and data.kind(other) != "gray":
                seen.add(other)
                related.append(other)
    related.sort(key=lambda other: (data.kind(other) != "reagent", data.item_name(other)))
    if related:
        sections.append("<h2>Farm these at the same time</h2><p class=sub>Other items the same mobs drop.</p>%s"
                        % link_list(item_link(data, other) for other in related[:RELATED]))
    trail = [("/", "Home"), ("/farms", "Farms by level"), ("/item/%d" % item, name)]
    price = ('<p class=facts>Lowest price: <b data-price="%d">%s</b> <span class=small data-qty="%d"></span></p>'
             % (item, LOADING, item))
    body = ("%s<h1>%s</h1><p class=summary>%s</p>%s%s%s%s"
            % (crumbs(trail), e(name), e(summary), price_bar(), price, "".join(sections), cta(links)))
    title = "Where to farm %s (WoW Forever)" % name
    others = count - 1
    description = "%s %s from %s (%s)%s in WoW Forever. Drop rates counted from GoldScout players' loot." % (
        name, "drops" if top_per == "kill" else "is pickpocketed", data.mob_name(top_npc), percent(top_rate),
        " and %d other mob%s" % (others, "" if others == 1 else "s") if others else "")
    return title, description, body


def zone_page(data, map_id, links):
    zone = data.map_names[map_id]
    npcs = data.zones[map_id]
    reagents = {}
    for npc in npcs:
        for item, rate, _ in data.best_drops(npc):
            if item in data.reagent_sources and rate > reagents.get(item, (None, 0))[1]:
                reagents[item] = (npc, rate)
    levels = [data.mobs[npc]["lmin"] for npc in npcs if data.mobs[npc]["lmin"]] + \
             [data.mobs[npc]["lmax"] for npc in npcs if data.mobs[npc]["lmax"]]
    span = ""
    if levels:
        span = " level %d" % min(levels) if min(levels) == max(levels) else " level %d-%d" % (min(levels), max(levels))
    summary = "GoldScout players have recorded %d%s mob%s in %s with enough kills for reliable drop rates%s." % (
        len(npcs), span, "" if len(npcs) == 1 else "s", zone,
        ", dropping %d crafting reagent%s" % (len(reagents), "" if len(reagents) == 1 else "s") if reagents else "")
    sections = ["<h2>Mobs</h2>" + mob_table(data, npcs, zone_column=False)]
    if reagents:
        ordered = sorted(reagents.items(), key=lambda pair: -pair[1][1])
        sections.append("<h2>Crafting reagents in %s</h2><table><thead><tr><th>Reagent</th><th>Best source</th>"
                        "<th class=num>Chance</th><th class=num>Price</th></tr></thead><tbody>%s</tbody></table>"
                        % (e(zone), "".join(
                            "<tr><td>%s</td><td>%s</td><td class=num>%s</td>%s</tr>"
                            % (item_cell(data, item), mob_link(data, npc), percent(rate), price_cell(item))
                            for item, (npc, rate) in ordered)))
    sections.append(legend())
    trail = [("/", "Home"), ("/farms", "Farms by level"), ("/zone/%d" % map_id, zone)]
    body = "%s<h1>Farming in %s</h1><p class=summary>%s</p>%s%s%s" % (
        crumbs(trail), e(zone), e(summary), price_bar(), "".join(sections), cta(links))
    title = "Where to farm gold in %s (WoW Forever)" % zone
    description = "Mobs to farm in %s, WoW Forever, and the crafting reagents they drop, from GoldScout players' loot." % zone
    return title, description, body


def farms_page(data, links):
    sections = []
    for bracket in BRACKETS:
        npcs = [npc for npc in data.mobs if data.bracket(npc) == bracket]
        if not npcs:
            continue
        npcs.sort(key=lambda npc: -(data.best_drops(npc)[0][1] if data.best_drops(npc) else 0))
        sections.append('<h2 id="%s">%s</h2>%s' % (bracket_anchor(bracket), bracket_label(bracket),
                                                   mob_table(data, npcs)))
    if not sections:
        sections.append("<p class=sub>No mobs have enough kills recorded yet.</p>")
    else:
        sections.append(legend())
    if data.zones:
        zones = sorted(data.zones, key=lambda map_id: data.map_names[map_id])
        sections.append("<h2>By zone</h2>" + link_list(
            '<a href="/zone/%d">%s</a> <span class=small>%d mob%s</span>'
            % (map_id, e(data.map_names[map_id]), len(data.zones[map_id]), "" if len(data.zones[map_id]) == 1 else "s")
            for map_id in zones))
    trail = [("/", "Home"), ("/farms", "Farms by level")]
    body = ("%s<h1>Farms by level</h1><p class=facts>Mobs GoldScout players have recorded at least %d kills of, "
            "with the crafting reagents they drop most often, ranked by gold per kill at current auction prices. "
            "Open a mob for every drop, or a reagent for everywhere it drops.</p>%s%s%s"
            % (crumbs(trail), MIN_ATTEMPTS, price_bar(), "".join(sections), cta(links)))
    return ("Gold farms by level (WoW Forever)",
            "WoW Forever mobs and the crafting reagents they drop, by level, from GoldScout players' loot.", body)


def rates_page(data, links):
    levels = "".join("<li>%s: %s</li>" % (badge(minimum), text) for minimum, text in [
        (0, "fewer than 5 kills. A first look; expect it to change."),
        (5, "5 to 14 kills. Common drops are roughly right."),
        (15, "15 to 49 kills. Good for most drops."),
        (50, "50 kills or more. Reliable, even for uncommon drops.")])
    trail = [("/", "Home"), ("/drop-rates", "How drop rates work")]
    body = """%s<h1>How GoldScout drop rates work</h1>
<p class=summary>Every number on this site comes from GoldScout players looting in WoW Forever. Nothing is copied from Wowhead or any other database.</p>
<h2>Chance</h2>
<p>The chance for an item is how many kills dropped it, divided by the kills recorded. A mob recorded 200 times that dropped an item 50 times shows 25%%. Average stack is how many of the item came in each drop. For pickpocketing, the chance is per pickpocket instead of per kill.</p>
<p>Next to each chance is the range the real chance is 95%% likely to be in, given the kills behind it: 25%% from 200 kills is 20&ndash;31%%, from 20 kills it's 11&ndash;47%%. Where an item drops from several mobs, they're ranked by the low end of that range, so a few lucky kills don't outrank a mob hundreds of kills have pinned down.</p>
<p>Everything is counted in WoW Forever. No Classic Era numbers are mixed in, so Forever's own drop rates show as they are.</p>
<h2>Confidence</h2>
<p>The more kills recorded, the closer the chance is to the real one. Each mob shows how sure the numbers are:</p>
<ul class=ticks>%s</ul>
<p>Pages are only made for mobs with at least %d kills recorded. In game, GoldScout ranks farms with a cautious estimate for mobs with few kills, so a lucky streak doesn't put a mob at the top.</p>
<h2>Keeping the data honest</h2>
<ul class=ticks>
<li>At most %s kills per mob count from any one player, so no single player decides a mob's numbers.</li>
<li>Every upload is checked, and unusual drop rates are reviewed before they're used.</li>
<li>Skinning, mining and herb gathering a corpse don't count as kills. Kills where the corpse had no loot do.</li>
<li>Gray items are vendor trash and aren't shown. Gear, recipes and gems are rare world drops, listed under other drops.</li>
</ul>
<h2>Prices and gold per kill</h2>
<p>Prices are the lowest buyout on the auction house for the realm type and faction you pick, from Blizzard's auction data, refreshed about every hour. Gold per kill adds up each crafting reagent's chance times its average stack times that price. It leaves out gear, recipes and gems (their prices swing too much) and how long a kill takes.</p>
<p>The GoldScout addon turns this into gold per hour for your character, using your own auction house scans when they're newer.</p>
<p class=small>%s</p>
%s""" % (crumbs(trail), levels, MIN_ATTEMPTS, format(PLAYER_CAP, ","), SOURCE, cta(links))
    return ("How GoldScout drop rates work",
            "Where GoldScout's WoW Forever drop rates come from, what the chance and confidence mean, and how the data is checked.",
            body)


def build(data, links, write):
    """Calls write(path, title, description, body, index=...) for every data page; returns the URL paths
    search engines should see (the sitemap's), leaving out the thin pages built with index=False."""
    paths = ["/farms", "/drop-rates"]
    write("farms.html", *farms_page(data, links))
    write("drop-rates.html", *rates_page(data, links))

    def page(path, built, index=True):
        write(path + ".html", *built, index=index)
        if index:
            paths.append("/" + path)

    for npc in sorted(data.mobs):
        page("mob/%d" % npc, mob_page(data, npc, links), data.mob_indexed(npc))
    for item in sorted(data.sources):
        page("item/%d" % item, item_page(data, item, links), data.item_indexed(item))
    for map_id in sorted(data.zones):
        page("zone/%d" % map_id, zone_page(data, map_id, links))
    return paths
