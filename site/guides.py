"""Gold-making guides: the best farms right now on each realm type and faction's auction house.

One page per market (/guides/us/pvp-horde) and an index (/guides). Each ranks the mobs GoldScout players
have recorded at least data_pages.SOLID kills of by what their crafting reagents sell for there, from the
latest auction prices, fetched when the site builds (so they're in the page for search engines, not only
filled in by prices.js). The value of a kill is the add-on's: drop chance x average stack x lowest buyout,
after the auction house cut; mobs are ranked by the low end of the drop chance's range, so a lucky few kills
can't top a list. English for now: these paths aren't in data_pages.LOCAL_PAGES, so no language switch.

Trends: the server keeps each auction house's first snapshot of every day for 30 days (?ago=7), so each farm's
main item is labelled rising, steady, cooling or new against a week ago, and "What changed this week" ranks the
same farms at last week's prices to show what entered or left the top list and which prices moved most.

One odd listing can't top a guide: as the add-on values a mob's other loot (Core.lua OTHER_LOOT_PRICE_CAP), a
lowest buyout over PRICE_CAP times the item's usual price in the region (the median lowest buyout across the
region's faction auction houses, tools/bundle_prices.py) counts as that much. A single Soft Frenzy Flesh listed at
567g, where the next house sells it for 1s, made a level 15 mob the best farm on its auction house.
"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import data_pages
import farm_notes
from data_pages import P, e

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import bundle_prices  # noqa: E402

API_URL = "https://api.wowgoldscout.com"
USER_AGENT = "GoldScout-site-build/1.0 (+https://wowgoldscout.com)"
REGIONS = {"us": "US", "eu": "EU", "kr": "Korea", "tw": "Taiwan"}
AH_CUT = data_pages.addon_number("Core.lua", "AH_CUT")   # you keep this share of a sale
PRICE_CAP = data_pages.addon_number("Core.lua", "OTHER_LOOT_PRICE_CAP")   # times the region's usual price
TOP = 3                     # farms in a guide's top list, each for a different item
MINOR = 0.02                # drops worth less than this share of a farm's kill are left out of its table
FETCH_TIMEOUT = 20
WEEK = 7                    # days back for trends
RISING, COOLING = 1.15, 0.85   # a week's price change past these is "rising" or "cooling"
MOVERS = 6                  # biggest price moves listed under "What changed this week"
MOVER_FARMS = 15            # among the main items of this many top farms


# -- prices -----------------------------------------------------------------
def get_json(url, opener=urllib.request.urlopen, timeout=FETCH_TIMEOUT):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with opener(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def price_pairs(body):
    """{itemID: (copper, quantity)} from a price response, skipping anything malformed."""
    prices = {}
    for item, pair in ((body or {}).get("prices") or {}).items():
        if isinstance(pair, list) and len(pair) >= 2 and item.isdigit():
            prices[int(item)] = (int(pair[0]), int(pair[1]))
    return prices


def fetch_week(api, house, fetch):
    """The house's prices about a week ago: {day, prices}, or None (too new, or the server has none)."""
    try:
        body = fetch("%s/v1/prices/%s/%d?ago=%d" % (api, house["region"], house["house"], WEEK))
    except (OSError, ValueError, urllib.error.URLError):
        return None
    prices = price_pairs(body)
    return {"day": str(body.get("day") or ""), "prices": prices} if prices else None


def fetch_markets(api=API_URL, fetch=get_json):
    """Every faction auction house with prices: [{region, house, ruleset, faction, snapshot, prices, week}],
    prices {itemID: (lowest unit buyout in copper, quantity listed)}, week the same about a week ago ({day,
    prices}, or None). The neutral Blackwater houses are left out (a guide is where your character sells).
    Returns [] if the server can't be reached, so the site still builds."""
    try:
        listing = fetch(api + "/v1/prices")
    except (OSError, ValueError, urllib.error.URLError) as error:
        print("Guides skipped: no auction prices (%s)." % error)
        return []
    markets = []
    for house in listing.get("houses") or []:
        if (house.get("region") not in REGIONS or house.get("faction") not in ("Alliance", "Horde")
                or not house.get("rulesetName") or not house.get("items")):
            continue
        try:
            body = fetch("%s/v1/prices/%s/%d" % (api, house["region"], house["house"]))
        except (OSError, ValueError, urllib.error.URLError) as error:
            print("Guide skipped for %s house %s: %s" % (house["region"], house["house"], error))
            continue
        markets.append({"region": house["region"], "house": house["house"], "ruleset": house["rulesetName"],
                        "faction": house["faction"], "snapshot": int(house.get("snapshot") or 0),
                        "prices": price_pairs(body), "week": fetch_week(api, house, fetch)})
    markets.sort(key=lambda m: (list(REGIONS).index(m["region"]), m["ruleset"], m["faction"]))
    return with_usual(markets)


def usual_prices(price_lists):
    """{itemID: usual price in copper}: the median lowest buyout over these auction houses' prices, for items
    listed on at least bundle_prices.MIN_HOUSES of them (on one house alone, nothing says what's usual)."""
    houses = dict(enumerate(price_lists))
    if len(houses) < bundle_prices.MIN_HOUSES:
        return {}
    return {item: entry[0] for item, entry in bundle_prices.region_estimates(houses).items()}


def with_usual(markets):
    """Adds each region's usual prices to its markets ("usual"), and a week ago's to their "week". In place;
    returns markets."""
    for region in {market["region"] for market in markets}:
        own = [market for market in markets if market["region"] == region]
        usual = usual_prices([market["prices"] for market in own])
        weeks = [market["week"] for market in own if market.get("week")]
        usual_then = usual_prices([week["prices"] for week in weeks])
        for market in own:
            market["usual"] = usual
        for week in weeks:
            week["usual"] = usual_then
    return markets


def counted_price(item, price, usual):
    """(the price a drop is valued at, True if that's the cap): at most PRICE_CAP times its usual price."""
    cap = (usual or {}).get(item, 0) * PRICE_CAP
    return (cap, True) if cap and price > cap else (price, False)


def slug(market):
    """us/pvp-horde, eu/roleplay-pvp-alliance."""
    return "%s/%s-%s" % (market["region"], market["ruleset"].lower().replace(" ", "-"), market["faction"].lower())


def market_name(market):
    """US PvP Horde."""
    return "%s %s %s" % (REGIONS[market["region"]], market["ruleset"], market["faction"])


# -- ranking ----------------------------------------------------------------
def farms(data, prices, usual=None):
    """The mobs worth farming on one auction house, best first: [{npc, kills, per_kill, cautious, pace, timed,
    parts}], parts [{item, rate, stack, price, listed, counted, capped, per_kill}] for each crafting reagent
    listed there, most valuable first: price is the lowest buyout, counted what it's valued at (at most
    PRICE_CAP times its price in usual, the region's usual prices). Ranked by the cautious gold an hour, at the pace players kill each mob (Dataset.kills_per_hour:
    timed kills where there are enough, else the addon's default). Only mobs with SOLID kills that players looted somewhere with a position, so not inside dungeons (the
    game gives no position there, and some bosses come with no zone at all): like the add-on's Farm list with
    Show dungeon drops off, since a boss with a lockout isn't a farm. Items nobody lists (no price) don't count."""
    found = []
    for npc, entry in data.mobs.items():
        kills = entry["k"]
        if kills < data_pages.SOLID or not entry["maps"]:
            continue
        parts, cautious = [], 0.0
        for item, rate, stack in data.best_drops(npc):
            price, listed = prices.get(item, (0, 0))
            if price <= 0 or listed <= 0:
                continue
            counted, capped = counted_price(item, price, usual)
            each = counted * AH_CUT
            parts.append({"item": item, "rate": rate, "stack": stack, "price": price, "listed": listed,
                          "counted": counted, "capped": capped, "per_kill": rate * stack * each})
            cautious += data_pages.wilson(round(rate * kills), kills)[0] * stack * each
        if not parts:
            continue
        parts.sort(key=lambda part: (-part["per_kill"], part["item"]))
        pace, timed = data.kills_per_hour(npc)
        found.append({"npc": npc, "kills": kills, "parts": parts, "cautious": cautious, "pace": pace,
                      "timed": timed, "per_kill": sum(part["per_kill"] for part in parts)})
    found.sort(key=lambda farm: (-farm["cautious"] * farm["pace"], farm["npc"]))
    return found


def top(ranked, n=TOP):
    """The best n farms, each for a different main item (three kinds of coyote are one farm)."""
    picked, items = [], set()
    for farm in ranked:
        main = farm["parts"][0]["item"]
        if main not in items:
            picked.append(farm)
            items.add(main)
        if len(picked) == n:
            break
    return picked


def by_level(data, ranked):
    """The best farm in each level range: [(bracket, farm)]."""
    best = {}
    for farm in ranked:
        best.setdefault(data.bracket(farm["npc"]), farm)
    return [(bracket, best[bracket]) for bracket in data_pages.BRACKETS if bracket in best]


# -- trends -----------------------------------------------------------------
def trend(market, item):
    """How an item's price moved in a week: ("rising" | "steady" | "cooling" | "new", change as a fraction or
    None), or None when there's no week-old snapshot to compare with (or no price now)."""
    week = market.get("week")
    if not week:
        return None
    now, _ = market["prices"].get(item, (0, 0))
    then, listed = week["prices"].get(item, (0, 0))
    if now <= 0:
        return None
    if then <= 0 or listed <= 0:
        return "new", None
    change = now / then - 1
    if now >= then * RISING:
        return "rising", change
    if now <= then * COOLING:
        return "cooling", change
    return "steady", change


def trend_badge(market, item):
    """<span class="trend rising">Rising, +18% this week</span>, or "" without a week to compare."""
    found = trend(market, item)
    if not found:
        return ""
    label, change = found
    if label == "new":
        text = "New: not listed a week ago"
    elif label == "steady":
        text = "Steady this week"
    else:
        text = "%s, %+d%% this week" % (label.capitalize(), round(change * 100))
    return '<span class="trend %s">%s</span>' % (label, text)


def week_cell(market, item):
    """+18%, -12%, new, or a dash, for a drop table's This week column."""
    found = trend(market, item)
    if not found:
        return "&ndash;"
    label, change = found
    if label == "new":
        return '<span class="trend new">new</span>'
    return '<span class="trend %s">%+d%%</span>' % (label, round(change * 100))


def places(ranked):
    """{main item: its place in the top list} (1 = best), one place per item, as top() counts them."""
    found = {}
    for farm in ranked:
        found.setdefault(farm["parts"][0]["item"], len(found) + 1)
    return found


def changes(data, market, ranked):
    """(entered, left, moves) against a week ago, or None without a week-old snapshot. entered and left are
    [(farm, place)]: farms new to the top list with their place a week ago (None if not ranked then), and farms
    that left it with their place now (None if not ranked now). moves: [(item, then, now, change)] for the top
    farms' main items that rose or cooled, biggest first. Both weeks are ranked with today's drop rates, so
    only prices differ."""
    week = market.get("week")
    if not week:
        return None
    before = farms(data, week["prices"], week.get("usual"))
    places_now, places_then = places(ranked), places(before)
    picked_now, picked_then = top(ranked), top(before)
    items_now = {farm["parts"][0]["item"] for farm in picked_now}
    items_then = {farm["parts"][0]["item"] for farm in picked_then}
    entered = [(farm, places_then.get(farm["parts"][0]["item"])) for farm in picked_now
               if farm["parts"][0]["item"] not in items_then]
    left = [(farm, places_now.get(farm["parts"][0]["item"])) for farm in picked_then
            if farm["parts"][0]["item"] not in items_now]
    moves = []
    for farm in top(ranked, MOVER_FARMS):
        item = farm["parts"][0]["item"]
        found = trend(market, item)
        if found and found[0] in ("rising", "cooling"):
            moves.append((item, week["prices"][item][0], market["prices"][item][0], found[1]))
    moves.sort(key=lambda move: (-abs(move[3]), move[0]))
    return entered, left, moves[:MOVERS]


# -- pages ------------------------------------------------------------------
def money(copper):
    """12g 34s, 4s 12c, 80c."""
    copper = int(round(copper))
    gold, silver, rest = copper // 10000, copper // 100 % 100, copper % 100
    if gold:
        return "%dg %ds" % (gold, silver) if silver else "%dg" % gold
    if silver:
        return "%ds %dc" % (silver, rest) if rest else "%ds" % silver
    return "%dc" % rest


def snapshot_text(snapshot):
    return time.strftime("%d %b %Y, %H:%M UTC", time.gmtime(snapshot)).lstrip("0")


def hour_range(farm):
    """What a farm earns an hour: the cautious figure (the low end of each drop chance's range, which the
    ranking uses) to the average so far: "4g 4s-4g 31s", or one figure when they round the same."""
    low, high = (money(value * farm["pace"]) for value in (farm["cautious"], farm["per_kill"]))
    return low if low == high else "%s&ndash;%s" % (low, high)


def where_figure(data, npc):
    """The zone's map with the hunting area shaded where players loot this mob, as the add-on's hunt map shows
    it in game; "" until enough loots are placed."""
    cells = data.mob_area(npc)
    if sum(cells.values()) < data_pages.AREA_MIN_LOOTS:
        return ""
    map_id, name = data.zone_id(npc), data.mob_name(npc)
    zone = data.map_name(map_id)
    art = data_pages.area_map(data, map_id, cells, "Map of %s: where players looted %s" % (zone, name),
                              lambda cell: "Around %s: looted %s here" % (data_pages.square_coords(cell),
                                                                          data_pages.num(int(cells[cell] + 0.5))))
    return ('<figure class="area-map">%s<figcaption>Brightest where players loot it most: around <b>%s</b>. '
            "Coordinates match the in-game map. %s</figcaption></figure>"
            % (art, data_pages.square_coords(data_pages.busiest(cells)), data_pages.ground_note([map_id])))


def price_cell(price, counted, capped):
    """A drop's lowest buyout, and what it's counted as when that's capped."""
    if not capped:
        return money(price)
    return '%s <span class=small title="Far above its usual price in the region">(counted as %s)</span>' % (
        money(price), money(counted))


def loot_table(data, npc, kills, prices, usual=None):
    """Everything players have looted from the mob (gray junk aside), priced on this auction house."""
    rows = []
    for item, rate, stack in data.drops(npc):
        if data.kind(item) == "gray":
            continue
        price, listed = prices.get(item, (0, 0))
        counted, capped = counted_price(item, price, usual)
        each = counted * AH_CUT if price > 0 and listed > 0 else 0
        rows.append("<tr><td>%s</td><td class=num>%s</td><td class=num>%s</td><td class=num>%s</td>"
                    "<td class=num>%s</td></tr>"
                    % (data_pages.item_link(data, item), data_pages.chance(rate, kills), data_pages.stack_text(stack),
                       price_cell(price, counted, capped) if each else "&ndash;",
                       money(rate * stack * each) if each else "&ndash;"))
    if not rows:
        return ""
    return ("<details><summary>Everything players have looted from it (%d item%s)</summary>"
            "<div class=scroll><table><thead><tr><th>Item</th><th class=num>Chance</th><th class=num>Avg. stack</th>"
            "<th class=num>Lowest buyout</th><th class=num>Per kill</th></tr></thead><tbody>%s</tbody></table></div>"
            "<p class=small>Gear, recipes and gems are random drops from many mobs, so their prices swing; the "
            "hour above counts crafting reagents only.</p></details>"
            % (len(rows), "" if len(rows) == 1 else "s", "".join(rows)))


def in_game(data, farm, links):
    """How to run the farm with the add-on: the guide hands straight over to the game."""
    item, mob = data_pages.item_html(data, farm["parts"][0]["item"]), data_pages.name_html(
        data.mob_name(farm["npc"]), data.is_local("mobs", farm["npc"]))
    return ('<div class=ingame><b>Run it in game with GoldScout.</b> On the Farm tab, pick %s and press '
            "<b>Hunt</b>: Blizzard's waypoint arrow takes you there, this area is shaded on your world map, and "
            "the hunt panel counts your kills, drops and gold per hour as you go. Target a %s and right-click its "
            'portrait for <b>Drop rates</b>: this loot table, in game. <a href="%s">Get GoldScout</a></div>'
            % (item, mob, links["curseforge"]))


def pace_text(farm):
    """At what pace a farm's gold an hour is worked out."""
    if farm["timed"]:
        return ("at %d kills an hour, how fast GoldScout players kill them (from %s timed kills, on mobs of your "
                "own level)" % (round(farm["pace"]), data_pages.num(farm["timed"])))
    return ("at %d kills an hour, an estimate until enough players have timed their kills here"
            % round(farm["pace"]))


def farm_card(data, rank, farm, market, links, note=None):
    npc, main = farm["npc"], farm["parts"][0]
    where = data_pages.zone_link(data, npc)
    levels = data.levels(npc)
    head = "%d. %s from %s" % (rank, data_pages.item_link(data, main["item"]), data_pages.mob_link(data, npc))
    place = ", ".join(part for part in (where, "level %s" % levels if levels else "") if part)
    shown = [part for part in farm["parts"] if part["per_kill"] >= MINOR * farm["per_kill"]]
    weekly = bool(market.get("week"))
    rows = "".join(
        "<tr><td>%s</td><td class=num>%s</td><td class=num>%s</td><td class=num>%s</td><td class=num>%s</td>%s</tr>"
        % (data_pages.item_link(data, part["item"]), data_pages.chance(part["rate"], farm["kills"]),
           price_cell(part["price"], part["counted"], part["capped"]), data_pages.num(part["listed"]),
           money(part["per_kill"]),
           "<td class=num>%s</td>" % week_cell(market, part["item"]) if weekly else "")
        for part in shown)
    badge = trend_badge(market, main["item"])
    return ('<section class=guide-farm><h3>%s</h3><p class=sub>%s</p><div class=cols><div>'
            '<p><b>%s an hour</b> %s. Drop chances from %s kills recorded by GoldScout players.%s</p>%s'
            '<div class=scroll><table><thead><tr><th>Drop</th><th class=num>Chance</th><th class=num>Lowest buyout'
            '</th><th class=num>Listed now</th><th class=num>Per kill</th>%s</tr></thead><tbody>%s</tbody></table>'
            '</div>%s%s<p class=small><a href="%s">Everything about %s</a></p></div>%s</div></section>'
            % (head, place, hour_range(farm), pace_text(farm), data_pages.num(farm["kills"]),
               " " + badge if badge else "", '<p class=guide-note>%s</p>' % e(note) if note else "",
               "<th class=num>This week</th>" if weekly else "", rows,
               loot_table(data, npc, farm["kills"], market["prices"], market.get("usual")),
               in_game(data, farm, links),
               P("/mob/%d" % npc), e(data.mob_name(npc)), where_figure(data, npc)))


def week_section(data, market, ranked):
    """What changed this week: farms that entered or left the top list, and the biggest price moves."""
    found = changes(data, market, ranked)
    if found is None:
        return ""
    entered, left, moves = found
    since = market["week"]["day"]
    try:
        since = time.strftime("%d %b", time.strptime(since, "%Y-%m-%d")).lstrip("0")
    except ValueError:
        pass
    lines = []
    for farm, then in entered:
        lines.append("<li><b>New in the top %d:</b> %s from %s (%s a week ago)</li>"
                     % (TOP, data_pages.item_link(data, farm["parts"][0]["item"]),
                        data_pages.mob_link(data, farm["npc"]), "#%d" % then if then else "not ranked"))
    for farm, now in left:
        lines.append("<li><b>Out of the top %d:</b> %s from %s (%s now)</li>"
                     % (TOP, data_pages.item_link(data, farm["parts"][0]["item"]),
                        data_pages.mob_link(data, farm["npc"]), "#%d" % now if now else "not listed now"))
    if not lines:
        lines.append("<li>The top %d is the same as a week ago.</li>" % TOP)
    moved = ""
    if moves:
        moved = "<h3>Biggest price moves among the top farms</h3><ul class=moves>%s</ul>" % "".join(
            '<li>%s: %s &rarr; %s <span class="trend %s">%+d%%</span></li>'
            % (data_pages.item_link(data, item), money(then), money(now), "rising" if change > 0 else "cooling",
               round(change * 100))
            for item, then, now, change in moves)
    return ("<section class=guide-week><h2>What changed this week</h2><p class=sub>Since %s, with today's drop "
            "rates both weeks, so only prices changed.</p><ul>%s</ul>%s</section>"
            % (e(since), "".join(lines), moved))


def market_page(data, market, ranked, markets, links, notes=None):
    """(title, description, body) for one market's guide."""
    name = market_name(market)
    picks = top(ranked)
    sections = []
    if picks:
        first = picks[0]
        sections.append("<h2>The top %d right now</h2>" % len(picks))
        notes = notes or (lambda farm: None)
        sections += [farm_card(data, rank, farm, market, links, notes(farm)) for rank, farm in enumerate(picks, 1)]
        sections.append(week_section(data, market, ranked))
        levels = by_level(data, ranked)
        if levels:
            rows = "".join(
                '<tr><td><a href="%s">%s</a></td><td>%s from %s</td><td>%s</td><td class=num>%s</td></tr>'
                % (P(data_pages.bracket_path(bracket)), data_pages.bracket_label(bracket),
                   data_pages.item_link(data, farm["parts"][0]["item"]), data_pages.mob_link(data, farm["npc"]),
                   data_pages.zone_link(data, farm["npc"]), hour_range(farm))
                for bracket, farm in levels)
            sections.append("<h2>Best farm for your level</h2><div class=guide-levels><table><thead><tr>"
                            "<th>Levels</th><th>Farm</th><th>Zone</th><th class=num>Per hour</th></tr></thead>"
                            "<tbody>%s</tbody></table></div>" % rows)
        summary = ("The best gold farm on %s auction houses right now is %s from %s, worth %s an hour. "
                   "Ranked from %s kills GoldScout players recorded in game and the auction house snapshot from %s."
                   % (e(name), e(data.item_name(first["parts"][0]["item"])), e(data.mob_name(first["npc"])),
                      hour_range(first), data_pages.num(sum(farm["kills"] for farm in ranked)), snapshot_text(market["snapshot"])))
    else:
        summary = ("No farm on %s auction houses has enough recorded kills and current listings to rank yet."
                   % e(name))
    sections.append(
        "<h2>How this is worked out</h2><p>Each drop chance comes from GoldScout players looting in game: only mobs "
        "with at least %d recorded kills count, and they're ranked by the low end of the chance's range, so a lucky "
        "streak can't top the list. Prices are the lowest buyout on %s auction houses, after the %d%% auction house "
        "cut. A price over %d times the item's usual price in the region (the middle of its lowest buyouts there) "
        "counts as %d times the usual price, so a single odd listing can't top the list either. Gold per hour "
        "runs from that low end to the average so far, at the pace GoldScout players kill each mob: the time from "
        "one kill to the next, as if the mobs were your own level. Looking for the next one counts, so a mob there "
        "are only a few of isn't rated like a crowded camp; a gap of over ten minutes, or over three after moving "
        "to another zone, is a break and doesn't count. Until players have timed at least %d kills of a mob, it's %d kills an hour on mobs of your "
        "own level (faster if you outlevel them). It counts crafting reagents only, not gear, coin or vendor trash. "
        "Lots of listings can mean a crowded market: check before you farm for hours.</p><p class=small>%s</p>"
        % (data_pages.SOLID, e(name), round((1 - AH_CUT) * 100), PRICE_CAP, PRICE_CAP, data_pages.PACE_MIN_KILLS,
           data_pages.KILLS_PER_HOUR, e(data_pages.SOURCE)))
    others = [other for other in markets if other is not market]
    if others:
        sections.append("<h2>Other realm types and factions</h2>" + data_pages.link_list(
            '<a href="%s">%s</a>' % (P("/guides/" + slug(other)), e(market_name(other))) for other in others))
    trail = [("/", "Home"), ("/guides", "Gold guides"), ("/guides/" + slug(market), name)]
    body = ("%s<h1>Best gold farms on %s right now</h1><p class=summary>%s</p>%s%s"
            % (data_pages.crumbs(trail), e(name), summary, "".join(sections),
               data_pages.cta(links)))
    title = "Best gold farms on %s right now (WoW Forever)" % name
    description = ("The best WoW Forever gold farms on %s auction houses right now, ranked by gold per hour from "
                   "player-recorded drop rates and the latest auction prices." % name)
    return title, description, body


def index_page(data, markets, ranked):
    """(title, description, body) for /guides: every market's guide, with its best farm."""
    rows = []
    for market in markets:
        picks = top(ranked[slug(market)], 1)
        if picks:
            badge = trend_badge(market, picks[0]["parts"][0]["item"])
            best = "%s from %s, %s an hour%s" % (data_pages.item_link(data, picks[0]["parts"][0]["item"]),
                                                data_pages.mob_link(data, picks[0]["npc"]), hour_range(picks[0]),
                                                " " + badge if badge else "")
        else:
            best = "not enough data yet"
        rows.append('<tr><td><a href="%s">%s</a></td><td>%s</td></tr>'
                    % (P("/guides/" + slug(market)), e(market_name(market)), best))
    if rows:
        listing = ("<table><thead><tr><th>Realm type and faction</th><th>Best farm right now</th></tr></thead>"
                   "<tbody>%s</tbody></table>" % "".join(rows))
    else:
        listing = "<p class=sub>Auction prices weren't available when this page was built. Try again soon.</p>"
    trail = [("/", "Home"), ("/guides", "Gold guides")]
    body = ("%s<h1>WoW Forever gold guides</h1><p class=summary>What's worth farming for gold right now, on each "
            "realm type and faction's auction house: the top farms from drop rates GoldScout players recorded in game, "
            "priced at the latest auction house snapshot.</p>%s<p class=small>%s</p>"
            % (data_pages.crumbs(trail), listing, e(data_pages.SOURCE)))
    return ("WoW Forever gold guides: the best farms right now",
            "The best WoW Forever gold farms right now for every realm type and faction, from player-recorded drop "
            "rates and the latest auction prices.", body)


def build(data, links, write, markets, notes_file=farm_notes.NOTES_FILE):
    """Writes /guides and each market's guide; returns their URL paths."""
    if any("usual" not in market for market in markets):
        with_usual(markets)
    ranked = {slug(market): farms(data, market["prices"], market["usual"]) for market in markets}
    written = farm_notes.load(notes_file)
    known = farm_notes.known_name_words(data) if written else set()

    def notes(farm):
        return farm_notes.note_for(data, farm, written, known)
    write("guides.html", *index_page(data, markets, ranked))
    paths = ["/guides"]
    for market in markets:
        write("guides/%s.html" % slug(market),
              *market_page(data, market, ranked[slug(market)], markets, links, notes))
        paths.append("/guides/" + slug(market))
    return paths
