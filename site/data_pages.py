"""The website's data pages, built from the merged community data: one page
per mob, one per item players loot or fish up (everything but gray vendor
trash), one per zone, one per level range, fishing by zone, and how the
numbers work.

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

German: build() runs a second time with LANG = "de" for the pages under /de/.
Every sentence goes through T() (German from site/i18n_de.py), links to data
pages through P() (which adds /de), and game names come from German players'
exports where they've recorded them; English names are kept, marked, until
then.
"""
import datetime
import html
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from i18n_de import DE, RATES_BODY as RATES_BODY_DE

SITE_URL = "https://wowgoldscout.com"
MIN_ATTEMPTS = 5                 # same threshold as the shipped community data
INDEX_MIN = 15                   # kills (or pickpockets) before a page is offered to search engines
RARE_CLASSES = {2, 4, 9}         # weapons, armor, recipes: rare world drops
GEM_CLASS = 3
ADDON = Path(__file__).resolve().parent.parent / "GoldScout"

# -- languages ------------------------------------------------------------------------
LANG = "en"                      # "de" while the German pages are built (build_language)
LANGUAGES = {"de": "deDE"}       # page language -> the game client language whose names it uses
MISSING = set()                  # texts looked up on a German page with no German yet (the tests keep it empty)
# Pages that exist in every language (and the home page, "/"). The home page, companion, share, FAQ and
# leaderboard pages are written by site/build.py; the rest by build() here.
LOCAL_PAGES = ("/item/", "/mob/", "/zone/", "/farms", "/fishing", "/data-wanted", "/drop-rates", "/search",
               "/companion", "/share", "/leaderboard", "/faq")


def T(text):
    """text in the language being built."""
    if LANG == "en":
        return text
    if text in DE:
        return DE[text]
    MISSING.add(text)
    return text


def plural(n, one, many, shown=None):
    """ "1 mob" / "3 mobs": the template for n, filled with shown (n itself by default)."""
    return T(one if n == 1 else many) % (n if shown is None else shown)


def num(n):
    """1,234 (German: 1.234)."""
    text = format(n, ",")
    return text.replace(",", ".") if LANG == "de" else text


def is_local_page(path):
    return path == "/" or any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in LOCAL_PAGES)


def P(path):
    """A link to a page, in the language being built when that page exists in it."""
    if LANG != "en" and is_local_page(path):
        return "/" + LANG + path
    return path


def addon_gems():
    """Item IDs in the addon's ns.GEMS (Data.lua): gems that drop at random from many mobs.
    The Farm tab treats them like gear, so the site does too."""
    source = (ADDON / "Data.lua").read_text(encoding="utf-8")
    block = re.search(r"ns\.GEMS = \{(.*?)\n\}", source, re.S)
    return {int(item) for item in re.findall(r"\[(\d+)\]", block.group(1))} if block else set()


def addon_number(file, name):
    """A number from the addon's code (`name = 123`), so the site's gold per hour matches the Farm tab's."""
    source = (ADDON / file).read_text(encoding="utf-8")
    return float(re.search(r"\b%s = ([\d.]+)" % name, source).group(1))


def addon_pace(setting):
    """A default pace from the addon's settings (Core.lua)."""
    return int(addon_number("Core.lua", setting))


GEMS = addon_gems()
KILLS_PER_HOUR = addon_pace("killsPerHour")
PICKS_PER_HOUR = addon_pace("picksPerHour")
CATCHES_PER_HOUR = addon_pace("catchesPerHour")
POOL_SHARE = addon_number("Engine.lua", "POOL_FISHING_SHARE")   # a pool takes finding: this share of your time fishes
AREA_GRID = int(addon_number("Learn.lua", "AREA_GRID"))   # where loot happened: squares of a grid over the zone map
AREA_MIN_SHARE = addon_number("Engine.lua", "AREA_MIN_SHARE")   # as the addon's hunt map: quieter squares are noise
AREA_MIN_LOOTS = 5               # loots placed on a map before the page draws it
AREA_ZONES = 3                   # maps on an item page
MAPS = Path(__file__).resolve().parent / "maps"   # the game's zone maps (tools/zone_maps.py), as <uiMapID>.webp
MAP_WIDTH, MAP_HEIGHT = 1002, 668   # the map area the game shows; map coordinates 0-1 cover exactly this


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
SOLID = CONFIDENCE[0][0]         # kills where a mob's rates count as solid ("high")
ALMOST = 10                      # "almost there" mobs listed per level range on /data-wanted
MILESTONES = (10, 25, 50, 75, 100)   # zone goals: % of a zone's mobs with solid rates (10: a first step in reach)
GOAL_LEFT = 6                    # mobs listed under a zone's goal, the closest to solid first

e = html.escape


def confidence(attempts):
    for minimum, name in CONFIDENCE:
        if attempts >= minimum:
            return name
    return "low"


def percent(rate):
    if rate >= 0.1:
        return "%d%%" % round(rate * 100)
    text = "%.1f%%" % (rate * 100)
    return text.replace(".", ",") if LANG == "de" else text


def bracket_of(level):
    for low, high in BRACKETS:
        if low <= level <= high:
            return low, high
    return None


def bracket_label(bracket):
    low, high = bracket
    return T("Levels %d-%d") % (low, min(high, 60))


def bracket_phrase(bracket):
    """The label inside a sentence: "levels 21-30" (German keeps its capital)."""
    low, high = bracket
    return T("levels %d-%d") % (low, min(high, 60))


def bracket_anchor(bracket):
    low, high = bracket
    return "levels-%d-%d" % (low, min(high, 60))


def vote(names):
    """{key: the name most players' exports gave it} from {key: Counter of names}."""
    return {key: votes.most_common(1)[0][0] for key, votes in names.items()}


class Dataset:
    def __init__(self, results, merged, fish=None):
        self.mobs = {npc: entry for npc, entry in merged.items() if entry["k"] + entry["p"] >= MIN_ATTEMPTS}
        self.contributors = len(results)
        self.kills = sum(entry["k"] for entry in merged.values())   # every kill, as on the home page
        item_votes, map_votes, meta_votes = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
        local_votes = {lang: {kind: defaultdict(Counter) for kind in ("items", "maps", "mobs")} for lang in LANGUAGES}
        for result in results:
            for item, name in result.item_names.items():
                item_votes[item][name] += 1
            for map_id, name in result.map_names.items():
                map_votes[map_id][name] += 1
            for item, meta in result.item_meta.items():
                meta_votes[item][meta] += 1
            for lang, locale in LANGUAGES.items():
                if getattr(result, "locale", None) == locale:
                    for kind, names in getattr(result, "local_names", {}).items():
                        for key, name in names.items():
                            local_votes[lang][kind][key][name] += 1
        self.item_names = vote(item_votes)
        self.map_names = vote(map_votes)
        self.item_meta = vote(meta_votes)
        # Names in each page language, from players whose game runs in it: {lang: {kind: {key: name}}}.
        self.local_names = {lang: {kind: vote(names) for kind, names in kinds.items()}
                            for lang, kinds in local_votes.items()}
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
        # Fishing, per zone and spot (0 open water, else a kind of pool), with enough catches and a zone name.
        self.fish = {key: entry for key, entry in (fish or {}).items()
                     if entry["n"] >= MIN_ATTEMPTS and key[0] in self.map_names}
        self.fish_sources = defaultdict(list)   # item: [(map, spot, rate, stack, catches)]
        self.fish_zones = defaultdict(list)     # map: [spot], open water first
        for (map_id, spot), entry in sorted(self.fish.items()):
            self.fish_zones[map_id].append(spot)
            for item, rate, stack in self.catches(map_id, spot):
                if self.kind(item) != "gray":
                    self.fish_sources[item].append((map_id, spot, rate, stack, entry["n"]))
        for sources in self.fish_sources.values():
            sources.sort(key=lambda source: (source[4] < INDEX_MIN, -self.cautious(
                (None, source[2], source[3], source[4], None)), source[0], source[1]))
        self.items = sorted(set(self.sources) | set(self.fish_sources))
        # Every square anyone has looted or fished in, per map: a rough outline of each zone for the page maps.
        self.ground = defaultdict(set)
        for entry in self.mobs.values():
            for map_id, cells in entry.get("areas", {}).items():
                self.ground[map_id].update(cell for cell, n in cells.items() if n > 0)
        for (map_id, _), entry in self.fish.items():
            self.ground[map_id].update(cell for cell, n in entry.get("a", {}).items() if n > 0)
        for npcs in self.zones.values():
            npcs.sort(key=lambda npc: (self.mid_level(npc), self.english_mob_name(npc)))

    # -- names and kinds --------------------------------------------------------
    def local(self, kind, key):
        """The name in the page language, or None (always None on English pages)."""
        return self.local_names[LANG][kind].get(key) if LANG != "en" else None

    def is_local(self, kind, key):
        """Whether a name shows in the page language (English pages: always)."""
        return LANG == "en" or self.local(kind, key) is not None

    def item_name(self, item):
        return self.local("items", item) or self.item_names.get(item, T("Item %d") % item)

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

    def english_mob_name(self, npc):
        names = self.mobs[npc]["names"]
        return max(names.items(), key=lambda pair: (pair[1], pair[0]))[0] if names else "Mob %d" % npc

    def mob_name(self, npc):
        local = self.local("mobs", npc)
        if local:
            return local
        return self.english_mob_name(npc) if self.mobs[npc]["names"] else T("Mob %d") % npc

    def map_name(self, map_id):
        return self.local("maps", map_id) or self.map_names[map_id]

    def zone_id(self, npc):
        """The map the mob was seen on most, if players' exports named it."""
        maps = self.mobs[npc]["maps"]
        if not maps:
            return None
        map_id = max(maps.items(), key=lambda pair: (pair[1][2], pair[0]))[0]
        return map_id if map_id in self.map_names else None

    def zone(self, npc):
        map_id = self.zone_id(npc)
        return self.map_name(map_id) if map_id is not None else ""

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
        return (any(attempts >= INDEX_MIN for _, _, _, attempts, _ in self.sources.get(item, ()))
                or any(catches >= INDEX_MIN for _, _, _, _, catches in self.fish_sources.get(item, ())))

    def has_page(self, item):
        return item in self.sources or item in self.fish_sources

    def catches(self, map_id, spot):
        """(item, rate per catch, average stack) for one fishing spot, best first."""
        entry = self.fish[(map_id, spot)]
        rows = [(item, d / entry["n"], q / d) for item, (d, q) in entry["i"].items() if d]
        return sorted(rows, key=lambda row: (-row[1], row[0]))

    def spot_name(self, map_id, spot):
        if spot == 0:
            return T("Open water")
        pools = [other for other in self.fish_zones[map_id] if other != 0]
        return T("Fishing pool") if len(pools) == 1 else T("Fishing pool %d") % (pools.index(spot) + 1)

    def mob_area(self, npc):
        """{square: loots} where players looted a mob, on the map it's seen on most."""
        map_id = self.zone_id(npc)
        if map_id is None:
            return {}
        return {cell: n for cell, n in self.mobs[npc].get("areas", {}).get(map_id, {}).items() if n > 0}

    def item_areas(self, item):
        """[(map, {square: items}, loots)], most items first: where an item turns up. Each square counts
        the loots there times the chance and stack, so a mob that drops it more weighs more."""
        maps = defaultdict(lambda: defaultdict(float))
        loots = defaultdict(float)
        placed = [(self.mobs[npc].get("areas", {}), rate * stack) for npc, rate, stack, _, _ in self.sources.get(item, ())]
        placed += [({map_id: self.fish[(map_id, spot)].get("a", {})}, rate * stack)
                   for map_id, spot, rate, stack, _ in self.fish_sources.get(item, ())]
        for areas, per in placed:
            for map_id, cells in areas.items():
                for cell, n in cells.items():
                    maps[map_id][cell] += n * per
                    loots[map_id] += n
        found = [(map_id, dict(cells), loots[map_id]) for map_id, cells in maps.items()
                 if map_id in self.map_names and loots[map_id] >= AREA_MIN_LOOTS and any(cells.values())]
        return sorted(found, key=lambda area: (-sum(area[1].values()), area[0]))

    def bracket_mobs(self, bracket):
        npcs = [npc for npc in self.mobs if self.bracket(npc) == bracket]
        npcs.sort(key=lambda npc: (-(self.best_drops(npc)[0][1] if self.best_drops(npc) else 0), npc))
        return npcs

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


def name_html(text, local=True):
    """A game name for HTML. On a translated page, one players haven't recorded in its language yet keeps
    its English name, marked."""
    if local or LANG == "en":
        return e(text)
    return '<span class=en-name lang=en title="%s">%s</span>' % (e(T("No German name recorded yet")), e(text))


def per_kill(rows):
    """data-value for prices.js: each item's chance x average stack, so price x it = gold per kill."""
    return ",".join("%d:%s" % (item, ("%.4f" % (rate * stack)).rstrip("0").rstrip("."))
                    for item, rate, stack in rows)


def price_bar():
    """Where the visitor picks a realm type and faction; prices.js fills it in."""
    return ('<div id="prices-bar" class="pricebar"><label>%s '
            '<select aria-label="%s" hidden></select></label> '
            '<span class="status">%s</span>'
            '<span class="source">%s</span></div>'
            % (T("Auction prices for"), T("Realm type and faction"),
               T("Turn on JavaScript to see current auction prices."), T(SOURCE)))


def price_cell(item):
    return '<td class=num data-price="%d">%s</td>' % (item, LOADING)


def value_cell(rows):
    return '<td class=num data-value="%s">%s</td>' % (per_kill(rows), LOADING)

def crumbs(trail):
    """Visible breadcrumbs plus schema.org BreadcrumbList data. trail: [(path, label)], last is this page.
    Paths are as on English pages; P() adds the language."""
    links = " &rsaquo; ".join('<a href="%s">%s</a>' % (P(path), e(label)) for path, label in trail[:-1])
    data = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": n, "name": label, "item": SITE_URL + P(path)}
        for n, (path, label) in enumerate(trail, 1)]}
    # Inside a script element HTML escaping doesn't apply; escaping <, > and & in
    # the JSON (same value) means nothing in a name can end or break the element.
    script = json_for_script(data)
    return '<p class=crumbs>%s</p><script type="application/ld+json">%s</script>' % (links, script)


def bracket_path(bracket):
    return "/farms/" + bracket_anchor(bracket)


def farms_trail(data, npc=None, bracket=None):
    trail = [("/", T("Home")), ("/farms", T("Farms by level"))]
    bracket = bracket or (data.bracket(npc) if npc is not None else None)
    if bracket:
        trail.append((bracket_path(bracket), bracket_label(bracket)))
    return trail


def mob_link(data, npc):
    return '<a href="%s">%s</a>' % (P("/mob/%d" % npc), name_html(data.mob_name(npc), data.is_local("mobs", npc)))


def zone_html(data, map_id):
    return name_html(data.map_name(map_id), data.is_local("maps", map_id))


def zone_link(data, npc):
    map_id = data.zone_id(npc)
    if map_id is None:
        return ""
    return '<a href="%s">%s</a>' % (P("/zone/%d" % map_id), zone_html(data, map_id))


def item_html(data, item):
    return name_html(data.item_name(item), data.is_local("items", item))


def item_link(data, item):
    name = item_html(data, item)
    if data.has_page(item):
        return '<a href="%s">%s</a>' % (P("/item/%d" % item), name)
    return name


item_cell = item_link


def chance(rate, attempts):
    """A drop chance with the 95% range it really lies in, from the kills behind it."""
    low, high = wilson(round(rate * attempts), attempts)
    return ('%s <span class="range" title="%s">%s&ndash;%s</span>'
            % (percent(rate), T("95%% likely between these, from %d recorded") % attempts,
               percent(low).rstrip("%"), percent(high)))


def badge(attempts):
    level = confidence(attempts)
    return '<span class="conf %s" title="%s">%s</span>' % (level, T("%d kills recorded") % attempts, T(level))


def legend(per="kill"):
    if per == "catch":
        text = T("Chance is how often players got the item per catch; the small numbers are the range it is 95% "
                 "likely to be in, which narrows as more catches are recorded. Counted in WoW Forever only: no "
                 "Classic Era data is mixed in.")
    else:
        text = T("Chance is how often players got the item per kill; the small numbers are the range it is 95% "
                 "likely to be in, which narrows as more kills are recorded. Counted in WoW Forever only: no "
                 "Classic Era data is mixed in.")
    return '<p class=small>%s <a href="%s">%s</a></p>' % (text, P("/drop-rates"), T("How these numbers work"))


def drop_table(data, rows, attempts, per="kill"):
    body = "".join(
        "<tr><td>%s</td><td class=num>%s</td><td class=num>%s</td>%s%s</tr>"
        % (item_cell(data, item), chance(rate, attempts), stack_text(stack),
           price_cell(item), value_cell([(item, rate, stack)]))
        for item, rate, stack in rows)
    return ("<table><thead><tr><th>%s</th><th class=num>%s</th><th class=num>%s</th>"
            "<th class=num>%s</th><th class=num>%s</th></tr></thead><tbody>%s</tbody></table>"
            % (T("Item"), T("Chance"), T("Avg. stack"), T("Price"),
               T("Per kill") if per == "kill" else T("Per pickpocket"), body))


def stack_text(stack):
    text = ("%.1f" % stack).rstrip("0").rstrip(".")
    return text.replace(".", ",") if LANG == "de" else text


def mob_table(data, npcs, zone_column=True):
    """Mobs with their best reagent drops, gold per kill and per hour; prices.js re-sorts by value."""
    rows = "".join(
        "<tr%s><td>%s</td><td class=nowrap>%s</td>%s<td>%s</td><td class=num>%s %s</td>%s%s</tr>"
        % (thin(data.mobs[npc]["k"]), mob_link(data, npc), e(data.levels(npc)),
           "<td>%s</td>" % zone_link(data, npc) if zone_column else "",
           ", ".join("%s %s" % (item_cell(data, item), percent(rate))
                     for item, rate, _ in data.best_drops(npc)[:3]) or '<span class=small>%s</span>' % T("none yet"),
           num(data.mobs[npc]["k"]), badge(data.mobs[npc]["k"]),
           value_cell(data.best_drops(npc)),
           value_cell([(item, rate * KILLS_PER_HOUR, stack) for item, rate, stack in data.best_drops(npc)]))
        for npc in npcs)
    return ("<table class=by-value><thead><tr><th>%s</th><th>%s</th>%s<th>%s</th>"
            "<th class=num>%s</th><th class=num>%s</th><th class=num>%s*</th></tr></thead>"
            "<tbody>%s</tbody></table><p class=small>* %s</p>"
            % (T("Mob"), T("Level"), "<th>%s</th>" % T("Zone") if zone_column else "", T("Best reagent drops"),
               T("Kills"), T("Gold per kill"), T("Gold per hour"), rows,
               T("Crafting reagents only, at %d kills an hour. In game, GoldScout works it out for your character, "
                 "at your own pace.") % KILLS_PER_HOUR))


def fishing_link(data, map_id):
    return '<a href="%s">%s</a>' % (P("/fishing/%d" % map_id), zone_html(data, map_id))


def fish_pace(spot):
    return CATCHES_PER_HOUR * (POOL_SHARE if spot else 1)


def area_squares(cells):
    """{square: strength 0-1} to draw: as the addon's hunt map, squares under AREA_MIN_SHARE of the busiest
    are left out (a stray loot or two isn't where to go)."""
    most = max(cells.values(), default=0)
    return {cell: n / most for cell, n in cells.items() if most and n >= most * AREA_MIN_SHARE}


def square_coords(cell):
    """The middle of a square in the game's map coordinates (0-100), e.g. "32.5, 47.5"."""
    row, column = divmod(cell, AREA_GRID)
    size = 100 / AREA_GRID
    return "%g, %g" % ((column + 0.5) * size, (row + 0.5) * size)


AREA_SIZE = 10   # SVG units per square


def area_svg(data, map_id, cells, label, tip):
    """A zone as a grid with the game's map coordinates: faint squares wherever GoldScout players have looted
    or fished there (all we know of the zone's shape: the game's map art isn't ours), bright ones in `cells`.
    tip(cell) is each bright square's tooltip."""
    shown = area_squares(cells)
    side = AREA_SIZE * AREA_GRID

    def square(cell, extra=""):
        row, column = divmod(cell, AREA_GRID)
        return '<rect x="%d" y="%d" width="%d" height="%d"%s' % (
            column * AREA_SIZE, row * AREA_SIZE, AREA_SIZE, AREA_SIZE, extra)

    parts = ['<rect class="bg" x="0" y="0" width="%d" height="%d"/>' % (side, side)]
    parts += [square(cell, ' class="g"/>') for cell in sorted(data.ground.get(map_id, ())) if cell not in shown]
    for step in range(0, 5):
        at = side * step // 4
        coordinate = 25 * step
        if 0 < step < 4:
            parts.append('<line class="l" x1="%d" y1="0" x2="%d" y2="%d"/>' % (at, at, side))
            parts.append('<line class="l" x1="0" y1="%d" x2="%d" y2="%d"/>' % (at, side, at))
        parts.append('<text x="%d" y="%d" text-anchor="middle">%d</text>' % (at, side + 13, coordinate))
        parts.append('<text x="-5" y="%d" text-anchor="end" dominant-baseline="middle">%d</text>' % (at, coordinate))
    parts += [square(cell, ' class="h" fill-opacity="%.2f"><title>%s</title></rect>'
                     % (0.3 + 0.7 * strength, e(tip(cell))))
              for cell, strength in sorted(shown.items())]
    return ('<svg class="area" viewBox="-24 -6 230 226" role="img" aria-label="%s">%s</svg>'
            % (e(label), "".join(parts)))


def has_map_art(map_id):
    return (MAPS / ("%d.webp" % map_id)).exists()


def area_art(map_id, cells, label, tip):
    """The zone's own map with the squares drawn over it in the addon's hunt-map green."""
    shown = area_squares(cells)
    width, height = MAP_WIDTH / AREA_GRID, MAP_HEIGHT / AREA_GRID
    squares = "".join(
        '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill-opacity="%.2f"><title>%s</title></rect>'
        % (column * width, row * height, width, height, 0.22 + 0.48 * strength, e(tip(cell)))
        for cell, strength in sorted(shown.items()) for row, column in [divmod(cell, AREA_GRID)])
    return ('<div class="area-art"><img src="/maps/%d.webp" width="%d" height="%d" loading="lazy" decoding="async" '
            'alt="%s"><svg viewBox="0 0 %d %d" preserveAspectRatio="none">%s</svg></div>'
            % (map_id, MAP_WIDTH, MAP_HEIGHT, e(label), MAP_WIDTH, MAP_HEIGHT, squares))


def area_map(data, map_id, cells, label, tip):
    """The zone's map if we have its art, else our own grid."""
    if has_map_art(map_id):
        return area_art(map_id, cells, label, tip)
    return area_svg(data, map_id, cells, label, tip)


def ground_note(map_ids):
    """The grid's faint squares need explaining; the real map doesn't have them."""
    if all(has_map_art(map_id) for map_id in map_ids):
        return T("Map art &copy; Blizzard Entertainment.")
    return T("Faint squares on a grid are where players have looted anything else in the zone.")


def busiest(cells):
    return max(sorted(cells), key=lambda cell: cells[cell])


def mob_area_section(data, npc):
    """Where players looted a mob, on its zone's grid, or "" until enough loots are placed."""
    cells = data.mob_area(npc)
    if sum(cells.values()) < AREA_MIN_LOOTS:
        return ""
    name, zone = data.mob_name(npc), data.map_name(data.zone_id(npc))
    svg = area_map(data, data.zone_id(npc), cells, T("Map of %s: where players looted %s") % (zone, name),
                   lambda cell: T("Around %s: looted %s here") % (square_coords(cell), num(int(cells[cell] + 0.5))))
    return ('<h2>%s</h2><figure class="area-map">%s<figcaption>%s %s</figcaption></figure>'
            % (T("Where to find it"), svg,
               T("Brightest where players loot %s most: around <b>%s</b> in %s. Coordinates match the in-game map.")
               % (name_html(name, data.is_local("mobs", npc)), square_coords(busiest(cells)), zone_link(data, npc)),
               ground_note([data.zone_id(npc)])))


def item_area_section(data, item):
    """Where an item turns up, one grid per zone (up to AREA_ZONES), or ""."""
    areas = data.item_areas(item)[:AREA_ZONES]
    if not areas:
        return ""
    name = data.item_name(item)
    figures = []
    for map_id, cells, _ in areas:
        zone = data.map_name(map_id)
        svg = area_map(data, map_id, cells, T("Map of %s: where players found %s") % (zone, name),
                       lambda cell: T("Around %s") % square_coords(cell))
        figures.append('<figure class="area-map"><figcaption class="zone">%s</figcaption>%s<figcaption>%s'
                       '</figcaption></figure>' % (zone_html(data, map_id), svg,
                                                   T("Most around <b>%s</b>.") % square_coords(busiest(cells))))
    return ('<h2>%s</h2><p class=sub>%s %s</p><div class="area-maps">%s</div>'
            % (T("Where on the map"),
               T("Brightest where the most %s turned up: squares where players looted or fished more of it. "
                 "Coordinates match the in-game map.") % item_html(data, item),
               ground_note([map_id for map_id, _, _ in areas]), "".join(figures)))


def thin(attempts):
    """Marks a ranked table row with too few kills (or catches) to trust: prices.js sorts those last."""
    return " data-thin" if attempts < INDEX_MIN else ""


def link_list(items):
    return "<ul class=related>%s</ul>" % "".join("<li>%s</li>" % item for item in items)


def cta(links, need=""):
    """The "help fill this in" box. need: a sentence on how thin this page's data is, or ""."""
    return ("<div class=cta><b>%s</b> %s%s</div>"
            % (T("Help fill this in."), need + " " if need else "",
               T("Every number here comes from players looting in game. Install <a href=\"%s\">GoldScout</a> and "
                 "add <a href=\"%s\">GoldScout Companion</a>: it brings auction prices into the game every "
                 "hour without scanning, and shares what you loot automatically. More players, better data for "
                 "everyone. <a href=\"%s\">See where data is needed most</a>.") % (links["curseforge"],
                                                                                  P("/companion"),
                                                                                  P("/data-wanted"))))


def kills_needed(name, attempts, noun="kills"):
    """A sentence for cta(): how far a thin mob, item or spot is from solid rates, or "" once it's there."""
    if attempts >= SOLID:
        return ""
    return e(T("%s has %s %s recorded so far, so the ranges are wide; %d more and its rates are solid.")
             % (name, num(attempts), T(noun), SOLID - attempts))


# -- pages -----------------------------------------------------------------------
def mob_summary(data, npc):
    """One or two plain sentences about a mob (unescaped)."""
    name, level, zone = data.mob_name(npc), data.levels(npc), data.zone(npc)
    kills = data.mobs[npc]["k"]
    if level and zone:
        what = T("%s is a level %s mob in %s in WoW Forever.") % (name, level, zone)
    elif level:
        what = T("%s is a level %s mob in WoW Forever.") % (name, level)
    elif zone:
        what = T("%s is a mob in %s in WoW Forever.") % (name, zone)
    else:
        what = T("%s is a mob in WoW Forever.") % name
    text = what + " " + plural(kills, "GoldScout players have recorded %s kill.",
                               "GoldScout players have recorded %s kills.", num(kills))
    best = data.best_drops(npc)
    if best:
        sentence = (T("Its most common crafting reagent is %s (%s of kills).") if data.has_kinds
                    else T("Its most common drop is %s (%s of kills)."))
        text += " " + sentence % (data.item_name(best[0][0]), percent(best[0][1]))
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
            sections.append("<h2>%s</h2>" % T("Crafting reagents") + drop_table(data, reagents, entry["k"]))
        if others:
            sections.append("<h2>%s</h2>" % T("Other drops") + drop_table(data, others, entry["k"]))
    elif drops:
        sections.append("<h2>%s</h2>" % T("Drops") + drop_table(data, drops, entry["k"]))
    picks = data.drops(npc, "pi")
    if picks:
        sections.append("<h2>%s</h2><p class=sub>%s</p>" % (
            T("Pickpocketing"), T("Chance per pickpocket, over %d attempts.") % entry["p"])
            + drop_table(data, picks, entry["p"], per="pickpocket"))
    if sections:
        sections.append(legend())
    else:
        sections.append("<p class=sub>%s</p>" % T("No drops recorded yet."))
    sections.append(mob_area_section(data, npc))
    zone_id = data.zone_id(npc)
    if zone_id is not None:
        siblings = [other for other in data.zones[zone_id] if other != npc][:RELATED]
        if siblings:
            sections.append("<h2>%s</h2>%s" % (
                T("More farms in %s") % zone_html(data, zone_id),
                link_list("%s <span class=small>%s</span>" % (mob_link(data, other),
                                                               T("level %s") % e(data.levels(other)))
                          for other in siblings)))
    level = data.levels(npc)
    facts = [T("Level %s") % e(level)] if level else []
    if zone_id is not None:
        facts.append(zone_link(data, npc))
    facts.append(T("%s kills recorded %s") % (num(entry["k"]), badge(entry["k"])))
    best = data.best_drops(npc)
    worth = ""
    if best:
        worth = ('<p class=facts>%s</p>'
                 % ((T("Its crafting reagents are worth about <b data-value=\"%s\">%s</b> per kill at current prices.")
                     if data.has_kinds else
                     T("Its drops are worth about <b data-value=\"%s\">%s</b> per kill at current prices."))
                    % (per_kill(best), LOADING)))
    body = ("%s<h1>%s</h1><p class=facts>%s</p><p class=summary>%s</p>%s%s%s%s"
            % (crumbs(farms_trail(data, npc) + [("/mob/%d" % npc, name)]),
               name_html(name, data.is_local("mobs", npc)), " &middot; ".join(facts),
               e(mob_summary(data, npc)), price_bar(), worth, "".join(sections),
               cta(links, kills_needed(name, entry["k"]))))
    title = T("%s drops and drop rates (WoW Forever)") % name
    best = data.best_drops(npc)[:2]
    if best:
        description = T("%s drop rates in WoW Forever: %s, from %d kills recorded by GoldScout players.") % (
            name, ", ".join("%s %s" % (data.item_name(item), percent(rate)) for item, rate, _ in best),
            entry["k"])
    else:
        description = T("What %s drops in WoW Forever, with drop rates from %d kills recorded by GoldScout "
                        "players.") % (name, entry["k"])
    return title, description, body


KIND_TEXT = {"reagent": "a crafting reagent", "rare": "a rare world drop", "other": "an item",
             "unknown": "an item"}


def source_where(data, npc):
    """'level 21-22, Ashenvale' for a summary, or ''."""
    bits = []
    if data.levels(npc):
        bits.append(T("level %s") % data.levels(npc))
    if data.zone(npc):
        bits.append(data.zone(npc))
    return ", ".join(bits)


def source_table(data, item, sources, per):
    """Where an item comes from, best first, with gold per kill and per hour at the visitor's prices."""
    pace = KILLS_PER_HOUR if per == "kill" else PICKS_PER_HOUR
    rows = "".join(
        "<tr><td>%s</td><td class=nowrap>%s</td><td>%s</td><td class=num>%s</td><td class=num>%s %s</td>%s%s</tr>"
        % (mob_link(data, npc), e(data.levels(npc)), zone_link(data, npc), chance(rate, attempts),
           num(attempts), badge(attempts), value_cell([(item, rate, stack)]),
           value_cell([(item, rate * pace, stack)]))
        for npc, rate, stack, attempts, _ in sources)
    if per == "kill":
        head = (T("Dropped by"), T("Kills"), T("Gold per kill"))
        note = T("At %d kills an hour. In game, GoldScout works it out for your character, at your own pace and "
                 "level.") % pace
    else:
        head = (T("Pickpocketed from"), T("Pickpockets"), T("Gold per pickpocket"))
        note = T("At %d pickpockets an hour. In game, GoldScout works it out for your character, at your own pace "
                 "and level.") % pace
    return ("<table><thead><tr><th>%s</th><th>%s</th><th>%s</th><th class=num>%s</th>"
            "<th class=num>%s</th><th class=num>%s</th><th class=num>%s*</th></tr></thead>"
            "<tbody>%s</tbody></table><p class=small>* %s</p>"
            % (head[0], T("Level"), T("Zone"), T("Chance"), head[1], head[2], T("Gold per hour"), rows, note))


def fish_source_table(data, item, sources):
    """Where an item is fished up, best first, with gold per catch and per hour."""
    rows = "".join(
        "<tr><td>%s</td><td>%s</td><td class=num>%s</td><td class=num>%s %s</td>%s%s</tr>"
        % (fishing_link(data, map_id), e(data.spot_name(map_id, spot)), chance(rate, catches),
           num(catches), badge(catches), value_cell([(item, rate, stack)]),
           value_cell([(item, rate * fish_pace(spot), stack)]))
        for map_id, spot, rate, stack, catches in sources)
    return ("<table><thead><tr><th>%s</th><th>%s</th><th class=num>%s</th><th class=num>%s</th>"
            "<th class=num>%s</th><th class=num>%s*</th></tr></thead><tbody>%s</tbody></table>"
            "<p class=small>* %s</p>"
            % (T("Zone"), T("Where"), T("Chance"), T("Catches"), T("Gold per catch"), T("Gold per hour"), rows,
               T("At %d catches an hour in open water, half that at pools (finding the next one takes time).")
               % CATCHES_PER_HOUR))


def item_need(data, item):
    """cta() sentence for an item whose best source is still thin."""
    sources, fishing = data.sources.get(item, []), data.fish_sources.get(item, [])
    if sources:
        npc, _, _, attempts, per = sources[0]
        return kills_needed(T("Its best source, %s,") % data.mob_name(npc), attempts,
                            "kills" if per == "kill" else "pickpockets")
    map_id, spot, _, _, catches = fishing[0]
    return kills_needed(T("Its best spot, %s in %s,") % (spot_phrase(data, map_id, spot), data.map_name(map_id)),
                        catches, "catches")


def spot_phrase(data, map_id, spot):
    """A spot's name inside a sentence: "open water" (German nouns keep their capital)."""
    name = data.spot_name(map_id, spot)
    return name if LANG == "de" else name.lower()


def item_page(data, item, links):
    """'Where to farm X': every mob players have looted (or pickpocketed) it from and everywhere it's been
    fished up, most reliable first."""
    name = data.item_name(item)
    sources = data.sources.get(item, [])
    fishing = data.fish_sources.get(item, [])
    kills = [source for source in sources if source[4] == "kill"]
    picks = [source for source in sources if source[4] == "pickpocket"]
    kind = T(KIND_TEXT[data.kind(item)])
    fish_zones = len({source[0] for source in fishing})
    if sources:
        top_npc, top_rate, _, top_attempts, top_per = sources[0]
        where = source_where(data, top_npc)
        count = len({source[0] for source in sources})
        looted = (plural(count, "GoldScout players have looted it from %d mob;",
                         "GoldScout players have looted it from %d mobs;") if kills else
                  plural(count, "GoldScout players have pickpocketed it from %d mob;",
                         "GoldScout players have pickpocketed it from %d mobs;"))
        summary = (T("%s is %s in WoW Forever.") % (name, kind) + " " + looted + " "
                   + (T("the best source is %s%s, which gave it on %s of %s kills.") if top_per == "kill" else
                      T("the best source is %s%s, which gave it on %s of %s pickpockets."))
                   % (data.mob_name(top_npc), " (%s)" % where if where else "", percent(top_rate),
                      num(top_attempts)))
        if fishing:
            summary += " " + plural(fish_zones, "It's also fished up in %d zone.", "It's also fished up in %d zones.")
        others = count - 1
        description = ((T("%s drops from %s (%s)%s in WoW Forever. Drop rates counted from GoldScout players' loot.")
                        if top_per == "kill" else
                        T("%s is pickpocketed from %s (%s)%s in WoW Forever. Drop rates counted from GoldScout "
                          "players' loot."))
                       % (name, data.mob_name(top_npc), percent(top_rate),
                          plural(others, " and %d other mob", " and %d other mobs") if others else ""))
    else:
        top_map, top_spot, top_rate, _, top_catches = fishing[0]
        spot = spot_phrase(data, top_map, top_spot)
        summary = (T("%s is %s in WoW Forever.") % (name, kind) + " "
                   + plural(fish_zones, "GoldScout players have fished it up in %d zone;",
                            "GoldScout players have fished it up in %d zones;") + " "
                   + T("the best spot is %s in %s, which gave it on %s of %s catches.")
                   % (spot, data.map_name(top_map), percent(top_rate), num(top_catches)))
        description = T("Where to fish %s in WoW Forever: %s in %s (%s of catches)%s. Counted from GoldScout "
                        "players' catches.") % (
            name, spot, data.map_name(top_map), percent(top_rate),
            plural(fish_zones - 1, ", and %d other zone", ", and %d other zones") if fish_zones > 1 else "")
    sections = []
    if kills:
        sections.append("<h2>%s</h2>" % T("Where it drops") + source_table(data, item, kills, "kill"))
    if picks:
        sections.append("<h2>%s</h2>" % T("Pickpocketing") + source_table(data, item, picks, "pickpocket"))
    if fishing:
        sections.append("<h2>%s</h2>" % T("Fishing") + fish_source_table(data, item, fishing))
    sections.append(legend())
    sections.append(item_area_section(data, item))
    related, seen = [], {item}
    nearby = [row for npc, _, _, _, _ in sources for row in data.drops(npc)]
    nearby += [row for map_id, spot, _, _, _ in fishing for row in data.catches(map_id, spot)]
    for other, _, _ in nearby:
        if other not in seen and data.has_page(other):
            seen.add(other)
            related.append(other)
    related.sort(key=lambda other: (data.kind(other) != "reagent", data.item_name(other)))
    if related:
        sections.append("<h2>%s</h2><p class=sub>%s</p>%s" % (
            T("Farm these at the same time"), T("Other items from the same mobs and fishing spots."),
            link_list(item_link(data, other) for other in related[:RELATED])))
    trail = [("/", T("Home")), ("/fishing" if not sources else "/farms",
                                T("Fishing") if not sources else T("Farms by level")), ("/item/%d" % item, name)]
    price = ('<p class=facts>%s <b data-price="%d">%s</b> <span class=small data-qty="%d"></span></p>'
             % (T("Lowest price:"), item, LOADING, item))
    body = ("%s<h1>%s</h1><p class=summary>%s</p>%s%s%s%s"
            % (crumbs(trail), item_html(data, item), e(summary), price_bar(), price, "".join(sections),
               cta(links, item_need(data, item))))
    title = (T("Where to farm %s (WoW Forever)") if sources else T("Where to fish %s (WoW Forever)")) % name
    return title, description, body


def zone_goal(data, map_id):
    """A zone's community goal: every mob recorded there with solid rates (SOLID+ kills).
    {solid, total, percent, reached (last milestone passed, 0 if none), next (milestone or None),
    needed (more solid mobs to reach it), left (mobs not yet solid, the closest first)}."""
    npcs = data.zones[map_id]
    solid = sum(1 for npc in npcs if data.mobs[npc]["k"] >= SOLID)
    total = len(npcs)
    share = 100 * solid / total if total else 0
    reached = max([milestone for milestone in MILESTONES if share >= milestone], default=0)
    upcoming = next((milestone for milestone in MILESTONES if share < milestone), None)
    needed = -(-upcoming * total // 100) - solid if upcoming else 0
    left = sorted((npc for npc in npcs if data.mobs[npc]["k"] < SOLID), key=lambda npc: (-data.mobs[npc]["k"], npc))
    return {"solid": solid, "total": total, "percent": share, "reached": reached, "next": upcoming,
            "needed": needed, "left": left}


def goal_bar(goal):
    """The share of solid mobs, with a tick at each milestone."""
    ticks = "".join('<i style="left:%d%%"></i>' % milestone for milestone in MILESTONES[:-1])
    return ('<span class=goal-bar role=img aria-label="%s"><span style="width:%d%%"></span>%s</span>'
            % (T("%d of %d mobs solid") % (goal["solid"], goal["total"]), round(goal["percent"]), ticks))


def goal_next(goal):
    """ "2 more mobs to 25%" or "complete"."""
    if not goal["next"]:
        return "<b class=done>%s</b>" % T("Complete")
    return T("%d more mob to %d%%" if goal["needed"] == 1 else "%d more mobs to %d%%") % (goal["needed"], goal["next"])


def zone_goal_section(data, map_id):
    goal = zone_goal(data, map_id)
    if not goal["next"]:
        text = ("<p>%s</p>" % T("<b>Goal reached:</b> every mob players have recorded in %s has solid drop rates. "
                                "New mobs recorded here join the goal.") % zone_html(data, map_id))
    else:
        text = "<p>%s</p>" % ((T("Every mob here with solid drop rates (%d+ kills): <b>%d of %d</b> so far, past %d%%. "
                                 "Next milestone: %s.") % (SOLID, goal["solid"], goal["total"], goal["reached"],
                                                           goal_next(goal)))
                              if goal["reached"] else
                              (T("Every mob here with solid drop rates (%d+ kills): <b>%d of %d</b> so far. Next "
                                 "milestone: %s.") % (SOLID, goal["solid"], goal["total"], goal_next(goal))))
    left = ""
    if goal["left"]:
        left = "<p class=sub>%s</p>" % T("Closest to solid:") + link_list(
            "%s <span class=small>%s &middot; %s</span>"
            % (mob_link(data, npc), T("level %s") % e(data.levels(npc)) if data.levels(npc) else "",
               T("%d kills, <b>%d to go</b>") % (data.mobs[npc]["k"], SOLID - data.mobs[npc]["k"]))
            for npc in goal["left"][:GOAL_LEFT])
    # Zone champions: filled in by site/champions.js from the server's leaderboard (hidden until then).
    champions = ('<div id=zone-champions data-zone="%d" hidden><p class=sub>%s</p><ol class=champions></ol>'
                 '<p class=small>%s <a href="%s">%s</a></p></div>'
                 '<script src="/champions.js" defer></script>'
                 % (map_id, T("Zone champions: the players with the most kills here."),
                    T("Named only if they choose it in GoldScout Companion."), P("/leaderboard"),
                    T("Contributor leaderboard")))
    return '<section class=zone-goal><h2>%s</h2>%s%s%s%s</section>' % (T("Zone goal"), goal_bar(goal), text, left,
                                                                       champions)


def zone_page(data, map_id, links):
    zone = data.map_name(map_id)
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
        span = (T(" level %d") % min(levels) if min(levels) == max(levels)
                else T(" level %d-%d") % (min(levels), max(levels)))
    summary = (plural(len(npcs), "GoldScout players have recorded %d%s mob in %s with enough kills for reliable drop "
                                 "rates", "GoldScout players have recorded %d%s mobs in %s with enough kills for "
                                          "reliable drop rates", (len(npcs), span, zone))
               + (plural(len(reagents), ", dropping %d crafting reagent", ", dropping %d crafting reagents")
                  if reagents else "") + ".")
    sections = [zone_goal_section(data, map_id), "<h2>%s</h2>" % T("Mobs") + mob_table(data, npcs, zone_column=False)]
    if reagents:
        ordered = sorted(reagents.items(), key=lambda pair: -pair[1][1])
        sections.append("<h2>%s</h2><table><thead><tr><th>%s</th><th>%s</th>"
                        "<th class=num>%s</th><th class=num>%s</th></tr></thead><tbody>%s</tbody></table>"
                        % (T("Crafting reagents in %s") % zone_html(data, map_id), T("Reagent"), T("Best source"),
                           T("Chance"), T("Price"), "".join(
                               "<tr><td>%s</td><td>%s</td><td class=num>%s</td>%s</tr>"
                               % (item_cell(data, item), mob_link(data, npc), percent(rate), price_cell(item))
                               for item, (npc, rate) in ordered)))
    if map_id in data.fish_zones:
        sections.append('<p>%s</p>' % T('Fishing here too: see <a href="%s">what players catch in %s</a>.')
                        % (P("/fishing/%d" % map_id), zone_html(data, map_id)))
    sections.append(legend())
    trail = [("/", T("Home")), ("/farms", T("Farms by level")), ("/zone/%d" % map_id, zone)]
    body = "%s<h1>%s</h1><p class=summary>%s</p>%s%s%s" % (
        crumbs(trail), T("Farming in %s") % zone_html(data, map_id), e(summary), price_bar(), "".join(sections),
        cta(links))
    title = T("Where to farm gold in %s (WoW Forever)") % zone
    description = T("Mobs to farm in %s, WoW Forever, and the crafting reagents they drop, from GoldScout players' "
                    "loot.") % zone
    return title, description, body


FARMS_PREVIEW = 5   # mobs per level range on the /farms overview


def farms_page(data, links):
    """The overview: each level range's top mobs, linking to its own page."""
    sections = []
    for bracket in BRACKETS:
        npcs = data.bracket_mobs(bracket)
        if not npcs:
            continue
        sections.append('<h2 id="%s"><a href="%s">%s</a></h2>%s<p><a href="%s">%s</a></p>'
                        % (bracket_anchor(bracket), P(bracket_path(bracket)), bracket_label(bracket),
                           mob_table(data, npcs[:FARMS_PREVIEW]), P(bracket_path(bracket)),
                           plural(len(npcs), "All %d farm for %s", "All %d farms for %s",
                                  (len(npcs), bracket_phrase(bracket)))))
    if not sections:
        sections.append("<p class=sub>%s</p>" % T("No mobs have enough kills recorded yet."))
    else:
        sections.append(legend())
    if data.fish:
        sections.append('<h2>%s</h2><p>%s</p>' % (T("Fishing"), T('<a href="%s">The best fishing spots for gold</a>, '
                                                                  'by zone.') % P("/fishing")))
    if data.zones:
        zones = sorted(data.zones, key=lambda map_id: data.map_name(map_id))
        sections.append("<h2>%s</h2>" % T("By zone") + link_list(
            '<a href="%s">%s</a> <span class=small>%s</span>'
            % (P("/zone/%d" % map_id), zone_html(data, map_id), plural(len(data.zones[map_id]), "%d mob", "%d mobs"))
            for map_id in zones))
    trail = [("/", T("Home")), ("/farms", T("Farms by level"))]
    body = ("%s<h1>%s</h1><p class=facts>%s</p>%s%s%s"
            % (crumbs(trail), T("Farms by level"),
               T("Mobs GoldScout players have recorded at least %d kills of, with the crafting reagents they drop "
                 "most often, ranked by gold per hour at current auction prices. Open a level range for every farm "
                 "in it, a mob for every drop, or an item for everywhere it drops.") % MIN_ATTEMPTS,
               price_bar(), "".join(sections), cta(links)))
    return (T("Gold farms by level (WoW Forever)"),
            T("The best WoW Forever gold farms for every level range, ranked by gold per hour at current auction "
              "prices, from GoldScout players' loot."), body)


def bracket_page(data, bracket, links):
    """Every mob in one level range, ranked by gold per hour at the visitor's prices."""
    npcs = data.bracket_mobs(bracket)
    kills = sum(data.mobs[npc]["k"] for npc in npcs)
    zones = sorted({data.zone_id(npc) for npc in npcs} - {None}, key=lambda map_id: data.map_name(map_id))
    summary = (T("%d mobs at %s that GoldScout players have recorded, from %s kills, ranked by what their crafting "
                 "reagents are worth an hour at current auction prices. Pick your realm type and faction for your "
                 "prices.") % (len(npcs), bracket_phrase(bracket), num(kills)))
    sections = ["<h2>%s</h2>" % T("Mobs") + mob_table(data, npcs), legend()]
    if zones:
        sections.append("<h2>%s</h2>" % T("Zones at these levels") + link_list(
            '<a href="%s">%s</a>' % (P("/zone/%d" % map_id), zone_html(data, map_id)) for map_id in zones))
    others = [other for other in BRACKETS if other != bracket and data.bracket_mobs(other)]
    if others:
        sections.append("<h2>%s</h2>" % T("Other levels") + link_list(
            '<a href="%s">%s</a>' % (P(bracket_path(other)), bracket_label(other)) for other in others))
    body = ("%s<h1>%s</h1><p class=summary>%s</p>%s%s%s"
            % (crumbs(farms_trail(data, bracket=bracket)), T("Gold farms for %s") % bracket_phrase(bracket),
               e(summary), price_bar(), "".join(sections), cta(links)))
    return (T("Best gold farms for %s (WoW Forever)") % bracket_phrase(bracket),
            T("The WoW Forever mobs worth farming at %s, ranked by gold per hour at current auction prices, from %s "
              "kills recorded by GoldScout players.") % (bracket_phrase(bracket), num(kills)), body)


def catch_table(data, map_id, spot):
    entry = data.fish[(map_id, spot)]
    body = "".join(
        "<tr><td>%s</td><td class=num>%s</td><td class=num>%s</td>%s%s</tr>"
        % (item_link(data, item), chance(rate, entry["n"]), stack_text(stack),
           price_cell(item), value_cell([(item, rate, stack)]))
        for item, rate, stack in data.catches(map_id, spot) if data.kind(item) != "gray")
    return ("<table><thead><tr><th>%s</th><th class=num>%s</th><th class=num>%s</th>"
            "<th class=num>%s</th><th class=num>%s</th></tr></thead><tbody>%s</tbody></table>"
            % (T("Catch"), T("Chance"), T("Avg. stack"), T("Price"), T("Per catch"), body))


def spot_rows_value(data, map_id, spot, per_hour=False, tag="td"):
    """What a spot's catch (gray junk left out) is worth per catch, or per hour, for prices.js to fill in."""
    pace = fish_pace(spot) if per_hour else 1
    rows = [(item, rate * pace, stack) for item, rate, stack in data.catches(map_id, spot) if data.kind(item) != "gray"]
    if tag == "td":
        return value_cell(rows)
    return '<%s data-value="%s">%s</%s>' % (tag, per_kill(rows), LOADING, tag)


def spot_value(data, map_id, spot, per_hour=False):
    return spot_rows_value(data, map_id, spot, per_hour)


def fishing_zone_indexed(data, map_id):
    return any(data.fish[(map_id, spot)]["n"] >= INDEX_MIN for spot in data.fish_zones[map_id])


def fishing_zone_page(data, map_id, links):
    zone = data.map_name(map_id)
    spots = data.fish_zones[map_id]
    catches = sum(data.fish[(map_id, spot)]["n"] for spot in spots)
    skills = [data.fish[(map_id, spot)]["s"] for spot in spots if data.fish[(map_id, spot)]["s"]]
    first = data.catches(map_id, spots[0])
    top = [(item, rate) for item, rate, _ in first if data.kind(item) != "gray"][:2]
    summary = T("GoldScout players have recorded %s catches fishing in %s, WoW Forever.") % (num(catches), zone)
    if skills:
        summary += " " + T("The lowest Fishing skill seen catching here is %d.") % min(skills)
    if top:
        summary += " " + T("%s gives %s.") % (data.spot_name(map_id, spots[0]), T(" and ").join(
            T("%s on %s of catches") % (data.item_name(item), percent(rate)) for item, rate in top))
    sections = []
    for spot in spots:
        entry = data.fish[(map_id, spot)]
        facts = [T("%s catches %s") % (num(entry["n"]), badge(entry["n"]))]
        if entry["s"]:
            facts.append(T("lowest skill seen %d") % entry["s"])
        sections.append('<h2>%s</h2><p class=facts>%s &middot; %s</p>%s'
                        % (e(data.spot_name(map_id, spot)), " &middot; ".join(facts),
                           T("about %s a catch, %s an hour*") % (spot_rows_value(data, map_id, spot, tag="b"),
                                                                 spot_rows_value(data, map_id, spot, True, tag="b")),
                           catch_table(data, map_id, spot)))
    sections.append("<p class=small>* %s</p>" % (T("At %d catches an hour in open water, half that at pools. Gray "
                                                   "junk is left out.") % CATCHES_PER_HOUR))
    sections.append(legend("catch"))
    if map_id in data.zones:
        sections.append('<p>%s</p>' % T('Mobs to farm here too: see <a href="%s">farming in %s</a>.')
                        % (P("/zone/%d" % map_id), zone_html(data, map_id)))
    others = [other for other in sorted(data.fish_zones, key=lambda m: data.map_name(m)) if other != map_id]
    if others:
        sections.append("<h2>%s</h2>" % T("Fishing elsewhere") + link_list(fishing_link(data, other)
                                                                          for other in others))
    trail = [("/", T("Home")), ("/fishing", T("Fishing")), ("/fishing/%d" % map_id, zone)]
    body = "%s<h1>%s</h1><p class=summary>%s</p>%s%s%s" % (
        crumbs(trail), T("Fishing in %s") % zone_html(data, map_id), e(summary), price_bar(), "".join(sections),
        cta(links))
    description = T("What you catch fishing in %s, WoW Forever%s, from %s catches recorded by GoldScout players.") % (
        zone, ": " + ", ".join("%s %s" % (data.item_name(item), percent(rate)) for item, rate in top) if top else "",
        num(catches))
    return T("Fishing in %s: catches and gold per hour (WoW Forever)") % zone, description, body


def fishing_page(data, links):
    """Every zone and spot players have fished, ranked by gold per hour at the visitor's prices."""
    rows = []
    for map_id in data.fish_zones:
        for spot in data.fish_zones[map_id]:
            entry = data.fish[(map_id, spot)]
            top = [(item, rate) for item, rate, _ in data.catches(map_id, spot) if data.kind(item) != "gray"][:2]
            rows.append("<tr%s><td>%s</td><td>%s</td><td class=num>%s %s</td><td class=num>%s</td><td>%s</td>%s%s</tr>"
                        % (thin(entry["n"]), fishing_link(data, map_id), e(data.spot_name(map_id, spot)),
                           num(entry["n"]), badge(entry["n"]), entry["s"] or "", ", ".join(
                               "%s %s" % (item_link(data, item), percent(rate)) for item, rate in top),
                           spot_value(data, map_id, spot), spot_value(data, map_id, spot, True)))
    table = ("<table class=by-value><thead><tr><th>%s</th><th>%s</th><th class=num>%s</th>"
             "<th class=num>%s</th><th>%s</th><th class=num>%s</th>"
             "<th class=num>%s*</th></tr></thead><tbody>%s</tbody></table>"
             "<p class=small>* %s</p>"
             % (T("Zone"), T("Where"), T("Catches"), T("Lowest skill"), T("Best catches"), T("Gold per catch"),
                T("Gold per hour"), "".join(rows),
                T("At %d catches an hour in open water, half that at pools. Lowest skill is the lowest Fishing skill "
                  "a player has caught there with.") % CATCHES_PER_HOUR))
    catches = sum(entry["n"] for entry in data.fish.values())
    summary = (T("Every zone GoldScout players have fished in WoW Forever, from %s catches, ranked by what the catch "
                 "is worth an hour at current auction prices. Pick your realm type and faction for your prices.")
               % num(catches))
    trail = [("/", T("Home")), ("/fishing", T("Fishing"))]
    body = "%s<h1>%s</h1><p class=summary>%s</p>%s%s%s%s" % (
        crumbs(trail), T("Fishing for gold"), e(summary), price_bar(),
        table if rows else "<p class=sub>%s</p>" % T("No fishing recorded yet."), legend("catch"), cta(links))
    return (T("Best fishing spots for gold (WoW Forever)"),
            T("Where to fish for gold in WoW Forever: every zone ranked by gold per hour at current auction prices, "
              "from %s catches recorded by GoldScout players.") % num(catches), body)


RATES_LEVELS = [
    (0, "fewer than 5 kills. A first look; expect it to change."),
    (5, "5 to 14 kills. Common drops are roughly right."),
    (15, "15 to 49 kills. Good for most drops."),
    (50, "50 kills or more. Reliable, even for uncommon drops.")]
RATES_BODY = """<h1>How GoldScout drop rates work</h1>
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
"""
DE[RATES_BODY] = RATES_BODY_DE


def rates_page(data, links):
    levels = "".join("<li>%s: %s</li>" % (badge(minimum), T(text)) for minimum, text in RATES_LEVELS)
    trail = [("/", T("Home")), ("/drop-rates", T("How drop rates work"))]
    body = crumbs(trail) + T(RATES_BODY) % (levels, MIN_ATTEMPTS, num(PLAYER_CAP), T(SOURCE)) + cta(links)
    return (T("How GoldScout drop rates work"),
            T("Where GoldScout's WoW Forever drop rates come from, what the chance and confidence mean, and how the "
              "data is checked."), body)


def coverage(data, npcs):
    """(mobs, kills, mobs with INDEX_MIN+ kills, mobs with SOLID+) for a set of mobs."""
    kills = [data.mobs[npc]["k"] for npc in npcs]
    return len(kills), sum(kills), sum(1 for k in kills if k >= INDEX_MIN), sum(1 for k in kills if k >= SOLID)


def coverage_row(label, npcs, data):
    """A row with a bar: the share of mobs with INDEX_MIN+ kills, the solid ones brighter inside it."""
    mobs, kills, good, solid = coverage(data, npcs)
    if not mobs:
        return ("<tr><td>%s</td><td class=num>0</td><td class=num>0</td><td class=num>0</td><td class=num>0</td>"
                "<td class=small>%s</td></tr>" % (label, T("nobody yet")))
    return ("<tr><td>%s</td><td class=num>%d</td><td class=num>%s</td><td class=num>%d <span class=range>%d%%</span>"
            "</td><td class=num>%d</td><td class=bar><span class=track><span class=good style=\"width:%d%%\"><span "
            "class=solid style=\"width:%d%%\"></span></span></span></td></tr>"
            % (label, mobs, num(kills), good, round(100 * good / mobs), solid, round(100 * good / mobs),
               round(100 * solid / good) if good else 0))


def zone_levels(data, map_id):
    levels = [level for npc in data.zones[map_id] for level in (data.mobs[npc]["lmin"], data.mobs[npc]["lmax"]) if level]
    if not levels:
        return ""
    return "%d-%d" % (min(levels), max(levels)) if min(levels) != max(levels) else str(min(levels))


def data_wanted_page(data, links):
    """/data-wanted: the level ranges and zones with the least data, and mobs a few kills from solid rates."""
    head = ("<table><thead><tr><th>%s</th><th class=num>%s</th><th class=num>%s</th><th class=num>%s</th>"
            "<th class=num>%s</th><th class=bar-head>%s</th></tr></thead><tbody>"
            % (T("Levels"), T("Mobs"), T("Kills"), T("%d+ kills") % INDEX_MIN, T("%d+ kills") % SOLID,
               T("Recorded")))
    by_level = "".join(coverage_row(('<a href="%s">%s</a>' % (P(bracket_path(bracket)), bracket_label(bracket))
                                     if data.bracket_mobs(bracket) else bracket_label(bracket)),
                                    data.bracket_mobs(bracket), data) for bracket in BRACKETS)
    brackets = [bracket for bracket in BRACKETS if data.bracket_mobs(bracket)]
    zones = sorted(data.zones, key=lambda map_id: (coverage(data, data.zones[map_id])[1], data.map_names[map_id]))
    goals = {map_id: zone_goal(data, map_id) for map_id in zones}
    by_zone = "".join(
        "<tr><td>%s</td><td class=num>%d</td><td class=num>%s</td><td class=num>%d</td><td class=bar>%s</td>"
        "<td class=small>%s</td></tr>"
        % ('<a href="%s">%s</a> <span class=small>%s</span>'
           % (P("/zone/%d" % map_id), zone_html(data, map_id), e(zone_levels(data, map_id))),
           goals[map_id]["total"], num(coverage(data, data.zones[map_id])[1]), goals[map_id]["solid"],
           goal_bar(goals[map_id]), goal_next(goals[map_id]))
        for map_id in zones)
    complete = sum(1 for goal in goals.values() if not goal["next"])
    started = sum(1 for goal in goals.values() if goal["reached"])
    almost = []
    for bracket in brackets:
        npcs = [npc for npc in data.bracket_mobs(bracket) if data.mobs[npc]["k"] < SOLID]
        npcs.sort(key=lambda npc: (-data.mobs[npc]["k"], npc))
        if npcs:
            almost.append("<h3>%s</h3>%s" % (bracket_label(bracket), link_list(
                "%s <span class=small>%s%s &middot; %s</span>"
                % (mob_link(data, npc), T("level %s") % e(data.levels(npc)) if data.levels(npc) else "",
                   ", %s" % zone_html(data, data.zone_id(npc)) if data.zone(npc) else "",
                   T("%d kills, <b>%d to go</b>") % (data.mobs[npc]["k"], SOLID - data.mobs[npc]["k"]))
                for npc in npcs[:ALMOST])))
    mobs, _, _, solid = coverage(data, list(data.mobs))
    trail = [("/", T("Home")), ("/farms", T("Farms by level")), ("/data-wanted", T("Where data is needed"))]
    body = ("%s<h1>%s</h1><p class=facts>%s</p>"
            "%s<h2>%s</h2><p class=sub>%s</p>%s%s</tbody></table>"
            "<h2>%s</h2><p class=sub>%s</p>"
            "<table><thead><tr><th>%s</th><th class=num>%s</th><th class=num>%s</th><th class=num>%s</th>"
            "<th class=bar-head>%s</th><th>%s</th></tr></thead><tbody>%s</tbody></table>"
            "<h2>%s</h2><p class=sub>%s</p>%s%s"
            % (crumbs(trail), T("Where GoldScout needs data"),
               T("Every drop rate on this site comes from GoldScout players' loot: %s kills so far, %d mobs with drop "
                 "rates, %d of them with the %d+ kills that make a rate solid. Here's where it's thin. Farming any of these with "
                 "GoldScout and the companion running fills it in for everyone.") % (num(data.kills), mobs, solid, SOLID),
               targets_section(data), T("By level"),
               T("The bar shows the share of mobs with %d+ kills (rated good); the brighter part has %d+ (rated high: "
                 "solid).") % (INDEX_MIN, SOLID), head, by_level,
               T("Zone goals"),
               T("Each zone's goal: every mob players have recorded there with solid drop rates (%d+ kills), with "
                 "milestones at 10%%, 25%%, 50%% and 75%%. %d of %d zones complete, %d past a milestone. Least "
                 "recorded first; zones nobody has looted in yet aren't listed.")
               % (SOLID, complete, len(goals), started),
               T("Zone"), T("Mobs"), T("Kills"), T("Solid"), T("Goal"), T("Next"), by_zone,
               T("Almost there"), T("Mobs a few kills from solid rates, the closest first."), "".join(almost),
               cta(links)))
    return (T("Where GoldScout needs drop data (WoW Forever)"),
            T("The WoW Forever level ranges, zones and mobs with the least drop data recorded by GoldScout players, "
              "and how to help fill them in."), body)


# The community's targets (notes/WEBSITE-PLAN.md, Phase 2) on the home page and /data-wanted. When they're
# reached or the date passes, set new ones here (and the German text, if it names them).
TARGETS_DATE = datetime.date(2026, 12, 15)
TARGETS = (("contributors", 50), ("kills", 30000), ("solid", 150))
MONTHS = {"en": ("January", "February", "March", "April", "May", "June", "July", "August", "September",
                 "October", "November", "December"),
          "de": ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
                 "November", "Dezember")}


def day_text(day):
    """ "December 15" (German: "15. Dezember")."""
    month = MONTHS[LANG if LANG in MONTHS else "en"][day.month - 1]
    return "%d. %s" % (day.day, month) if LANG == "de" else "%s %d" % (month, day.day)


def community_targets(data):
    """[(label, have, target)] for TARGETS."""
    have = {"contributors": data.contributors, "kills": data.kills,
            "solid": sum(1 for entry in data.mobs.values() if entry["k"] >= SOLID)}
    labels = {"contributors": T("Players sharing data"), "kills": T("Kills recorded"),
              "solid": T("Mobs with solid drop rates (%d+ kills)") % SOLID}
    return [(labels[key], have[key], target) for key, target in TARGETS]


def targets_section(data, today=None):
    """The community's progress toward TARGETS: a bar each, and how long is left."""
    today = today or datetime.date.today()
    targets = community_targets(data)
    day = day_text(TARGETS_DATE)
    if all(have >= target for _, have, target in targets):
        text = T("Every goal for %s reached. Thank you, everyone who shares!") % day
    elif today > TARGETS_DATE:
        text = T("The goals for %s, and how far everyone got.") % day
    else:
        left = (TARGETS_DATE - today).days
        text = (T("Goals for everyone sharing data, by %s (%s). Every player who adds the companion and every kill "
                  "moves them.") % (day, plural(left, "%d day left", "%d days left") if left else T("today")))
    rows = "".join(
        '<div class=target><span class=target-label>%s</span>'
        '<span class=goal-bar role=img aria-label="%s"><span style="width:%d%%"></span></span>'
        '<span class=target-num>%s</span></div>'
        % (label, T("%s of %s") % (num(have), num(target)), min(100, round(100 * have / target)),
           (T("<b class=done>%s</b> of %s") if have >= target else T("<b>%s</b> of %s")) % (num(have), num(target)))
        for label, have, target in targets)
    return '<section class=targets><h2>%s</h2><p class=sub>%s</p>%s</section>' % (T("Community goals"), text, rows)


def build(data, links, write):
    """Calls write(path, title, description, body, index=...) for every data page in the language being built
    (LANG; paths as on English pages); returns the URL paths search engines should see (the sitemap's),
    leaving out the thin pages built with index=False."""
    paths = ["/farms", "/drop-rates", "/data-wanted"]
    write("farms.html", *farms_page(data, links))
    write("drop-rates.html", *rates_page(data, links))
    write("data-wanted.html", *data_wanted_page(data, links))

    def page(path, built, index=True):
        write(path + ".html", *built, index=index)
        if index:
            paths.append("/" + path)

    for bracket in BRACKETS:
        if data.bracket_mobs(bracket):
            page(bracket_path(bracket)[1:], bracket_page(data, bracket, links))
    for npc in sorted(data.mobs):
        page("mob/%d" % npc, mob_page(data, npc, links), data.mob_indexed(npc))
    for item in data.items:
        page("item/%d" % item, item_page(data, item, links), data.item_indexed(item))
    for map_id in sorted(data.zones):
        page("zone/%d" % map_id, zone_page(data, map_id, links))
    if data.fish:
        page("fishing", fishing_page(data, links))
        for map_id in sorted(data.fish_zones):
            page("fishing/%d" % map_id, fishing_zone_page(data, map_id, links), fishing_zone_indexed(data, map_id))
    return paths


def build_language(lang, data, links, write):
    """build() with every page in another language: write gets the same paths as English, and P() links
    point inside that language."""
    global LANG
    previous, LANG = LANG, lang

    def written(path, title, description, body, index=True):
        write(path, grammar(title), grammar(description), grammar(body), index=index)
    try:
        return build(data, links, written)
    finally:
        LANG = previous


# German zone names with an article ("Das Brachland") after "in" and "von": "im Brachland", "vom Brachland",
# "in der ...". The name may sit inside a link or an English-name mark.
GERMAN_ARTICLES = [
    (re.compile(r"\b([Ii])n ((?:<[^>]+>)*)D(?:as|er) "), r"\1m \2"),
    (re.compile(r"\b([Ii])n ((?:<[^>]+>)*)Die "), r"\1n der \2"),
    (re.compile(r"\b([Vv])on ((?:<[^>]+>)*)D(?:as|er) "), r"\1om \2"),
    (re.compile(r"\b([Vv])on ((?:<[^>]+>)*)Die "), r"\1on der \2"),
]


def grammar(text):
    """Fixes what filling names into sentences breaks in the language being built (German articles)."""
    if LANG == "de":
        for pattern, replacement in GERMAN_ARTICLES:
            text = pattern.sub(replacement, text)
    return text


# -- site search -------------------------------------------------------------------
KIND_LABEL = {"reagent": "Crafting reagent", "rare": "Rare drop", "other": "Item", "unknown": "Item"}


def search_index(data):
    """[name, path, detail, weight] for every data page, for the site search (site/search.js). Weight
    (kills, catches) breaks ties between equally good matches. Mobs and items players' exports didn't
    name are left out: nobody searches for "Mob 3637". In another language (LANG), names are that
    language's where players have recorded them, with the English name as a second entry."""
    entries = []

    def add(name, english, path, detail, weight):
        entries.append([name, P(path), detail, weight])
        if english and english != name:
            entries.append([english, P(path), detail, weight])

    for bracket in BRACKETS:
        npcs = data.bracket_mobs(bracket)
        if npcs:
            add(T("Gold farms for %s") % bracket_phrase(bracket), None, bracket_path(bracket),
                T("Farms by level · %d mobs") % len(npcs), sum(data.mobs[npc]["k"] for npc in npcs))
    for map_id, npcs in data.zones.items():
        add(data.map_name(map_id), data.map_names[map_id], "/zone/%d" % map_id,
            plural(len(npcs), "Zone · %d mob", "Zone · %d mobs"), sum(data.attempts(npc) for npc in npcs))
    for map_id, spots in data.fish_zones.items():
        catches = sum(data.fish[(map_id, spot)]["n"] for spot in spots)
        add(T("Fishing in %s") % data.map_name(map_id), T("Fishing in %s") % data.map_names[map_id],
            "/fishing/%d" % map_id, T("Fishing · %s catches") % num(catches), catches)
    for npc in data.mobs:
        if not data.mobs[npc]["names"]:
            continue
        bits = [T("Mob")]
        if data.levels(npc):
            bits.append(T("level %s") % data.levels(npc))
        if data.zone(npc):
            bits.append(data.zone(npc))
        add(data.mob_name(npc), data.english_mob_name(npc), "/mob/%d" % npc, " · ".join(bits), data.attempts(npc))
    for item in data.items:
        if item not in data.item_names:
            continue
        sources = data.sources.get(item, [])
        fishing = data.fish_sources.get(item, [])
        count = len(sources) + len(fishing)
        detail = T(KIND_LABEL[data.kind(item)]) + " · " + plural(count, "%d source", "%d sources")
        if fishing:
            detail += " · " + T("fished up")
        add(data.item_name(item), data.item_names[item], "/item/%d" % item, detail,
            sum(source[3] for source in sources) + sum(source[4] for source in fishing))
    for entry in entries:
        entry[0], entry[2] = grammar(entry[0]), grammar(entry[2])
    entries.sort(key=lambda entry: (entry[0].lower(), entry[1]))
    return entries
