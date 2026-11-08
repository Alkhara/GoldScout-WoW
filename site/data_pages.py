"""The website's data pages, built from the merged community data: one page
per mob, one per crafting reagent, and farms by level.

Names come from players' exports (@i, @m lines and mob names) and are always
HTML-escaped. Item kinds come from @q lines (export version 4): until an item
has one, it's shown under "Drops" without being sorted into reagents.
"""
import html
from collections import Counter, defaultdict

MIN_ATTEMPTS = 5                 # same threshold as the shipped community data
RARE_CLASSES = {2, 4, 9}         # weapons, armor, recipes: rare world drops
GEM_CLASS = 3
BRACKETS = [(1, 10), (11, 20), (21, 30), (31, 40), (41, 50), (51, 63)]
CONFIDENCE = [(50, "high"), (15, "good"), (5, "fair"), (0, "low")]

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
        for npc, entry in self.mobs.items():
            for item, rate, _ in self.drops(npc):
                if self.kind(item) == "reagent":
                    self.reagent_sources[item].append((npc, rate))
        for sources in self.reagent_sources.values():
            sources.sort(key=lambda pair: -pair[1])

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
        if class_id in RARE_CLASSES or class_id == GEM_CLASS:
            return "rare"
        return "reagent" if reagent else "other"

    def mob_name(self, npc):
        names = self.mobs[npc]["names"]
        return max(names.items(), key=lambda pair: (pair[1], pair[0]))[0] if names else "Mob %d" % npc

    def zone(self, npc):
        maps = self.mobs[npc]["maps"]
        if not maps:
            return ""
        map_id = max(maps.items(), key=lambda pair: (pair[1][2], pair[0]))[0]
        return self.map_names.get(map_id, "")

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

    def drops(self, npc, key="i"):
        """(item, rate, average stack) for a mob's drops (or pickpocket items), best first."""
        entry = self.mobs[npc]
        attempts = entry["k"] if key == "i" else entry["p"]
        if not attempts:
            return []
        rows = [(item, d / attempts, q / d if d else 1) for item, (d, q) in entry[key].items() if d]
        return sorted(rows, key=lambda row: -row[1])


# -- rendering -------------------------------------------------------------------
def mob_link(data, npc):
    return '<a href="/mob/%d">%s</a>' % (npc, e(data.mob_name(npc)))


def item_cell(data, item):
    name = e(data.item_name(item))
    if data.kind(item) == "reagent":
        return '<a href="/reagent/%d">%s</a>' % (item, name)
    return name


def badge(attempts):
    level = confidence(attempts)
    return '<span class="conf %s" title="%d kills recorded">%s</span>' % (level, attempts, level)


def drop_table(data, rows):
    body = "".join(
        "<tr><td>%s</td><td class=num>%s</td><td class=num>%s</td></tr>"
        % (item_cell(data, item), percent(rate), ("%.1f" % stack).rstrip("0").rstrip("."))
        for item, rate, stack in rows)
    return ("<table><thead><tr><th>Item</th><th class=num>Chance</th><th class=num>Avg. stack</th></tr></thead>"
            "<tbody>%s</tbody></table>" % body)


def cta(links):
    return ("<div class=cta><b>Help fill this in.</b> Every number here comes from players looting in game. "
            "Install <a href=\"%(curseforge)s\">GoldScout</a> and share what you loot: the "
            "<a href=\"%(companion)s\">companion app</a> does it automatically. More players, better data "
            "for everyone.</div>" % links)


def mob_page(data, npc, links):
    entry = data.mobs[npc]
    name = data.mob_name(npc)
    zone = data.zone(npc)
    drops = data.drops(npc)
    sections = []
    if data.has_kinds:
        reagents = [row for row in drops if data.kind(row[0]) == "reagent"]
        others = [row for row in drops if data.kind(row[0]) in ("other", "unknown", "rare")]
        if reagents:
            sections.append("<h2>Crafting reagents</h2>" + drop_table(data, reagents))
        if others:
            sections.append("<h2>Other drops</h2>" + drop_table(data, others))
    elif drops:
        sections.append("<h2>Drops</h2>" + drop_table(data, drops))
    picks = data.drops(npc, "pi")
    if picks:
        sections.append("<h2>Pickpocketing</h2><p class=sub>Chance per pickpocket, over %d attempts.</p>"
                        % entry["p"] + drop_table(data, picks))
    if not sections:
        sections.append("<p class=sub>No drops recorded yet.</p>")
    level = data.levels(npc)
    facts = ["Level %s" % e(level)] if level else []
    if zone:
        facts.append(e(zone))
    facts.append("%s kills recorded %s" % (format(entry["k"], ","), badge(entry["k"])))
    body = ('<p class=crumbs><a href="/farms">Farms by level</a></p><h1>%s</h1><p class=facts>%s</p>%s%s'
            % (e(name), " &middot; ".join(facts), "".join(sections), cta(links)))
    title = "%s drops and drop rates (WoW Forever)" % name
    description = "What %s drops in WoW Forever, with drop rates from %d kills recorded by GoldScout players." % (
        name, entry["k"])
    return title, description, body


def reagent_page(data, item, links):
    name = data.item_name(item)
    rows = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td><td class=num>%s</td><td>%s</td></tr>"
        % (mob_link(data, npc), e(data.levels(npc)), e(data.zone(npc)), percent(rate), badge(data.mobs[npc]["k"]))
        for npc, rate in data.reagent_sources[item])
    body = ('<p class=crumbs><a href="/farms">Farms by level</a></p><h1>%s</h1>'
            "<p class=facts>Crafting reagent. Where GoldScout players have looted it:</p>"
            "<table><thead><tr><th>Dropped by</th><th>Level</th><th>Zone</th><th class=num>Chance</th>"
            "<th>Confidence</th></tr></thead><tbody>%s</tbody></table>"
            "<p class=sub>Prices differ on every realm, so GoldScout ranks these by gold per hour in game, "
            "using your own auction house.</p>%s" % (e(name), rows, cta(links)))
    title = "Where to farm %s (WoW Forever)" % name
    description = "Which mobs drop %s in WoW Forever and how often, from GoldScout players' loot." % name
    return title, description, body


def farms_page(data, links):
    sections = []
    for low, high in BRACKETS:
        npcs = [npc for npc in data.mobs if low <= data.mid_level(npc) <= high]
        if not npcs:
            continue

        def best(npc):
            rows = data.drops(npc)
            if data.has_kinds:
                rows = [row for row in rows if data.kind(row[0]) == "reagent"]
            return rows

        npcs.sort(key=lambda npc: -(best(npc)[0][1] if best(npc) else 0))
        rows = "".join(
            "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
            % (mob_link(data, npc), e(data.levels(npc)), e(data.zone(npc)),
               ", ".join("%s %s" % (item_cell(data, item), percent(rate)) for item, rate, _ in best(npc)[:3])
               or '<span class=small>none yet</span>')
            for npc in npcs)
        sections.append("<h2>Levels %d-%d</h2><table><thead><tr><th>Mob</th><th>Level</th><th>Zone</th>"
                        "<th>Best reagent drops</th></tr></thead><tbody>%s</tbody></table>"
                        % (low, min(high, 60), rows))
    if not sections:
        sections.append("<p class=sub>No mobs have enough kills recorded yet.</p>")
    body = ("<h1>Farms by level</h1><p class=facts>Mobs GoldScout players have recorded at least %d kills of, "
            "with the crafting reagents they drop most often. Open a mob for every drop, or a reagent for "
            "everywhere it drops.</p>%s%s" % (MIN_ATTEMPTS, "".join(sections), cta(links)))
    return ("Gold farms by level (WoW Forever)",
            "WoW Forever mobs and the crafting reagents they drop, by level, from GoldScout players' loot.", body)


def build(data, links, write):
    """Calls write(path, title, description, body) for every data page; returns their URL paths."""
    paths = ["/farms"]
    write("farms.html", *farms_page(data, links))
    for npc in sorted(data.mobs):
        write("mob/%d.html" % npc, *mob_page(data, npc, links))
        paths.append("/mob/%d" % npc)
    for item in sorted(data.reagent_sources):
        write("reagent/%d.html" % item, *reagent_page(data, item, links))
        paths.append("/reagent/%d" % item)
    return paths
