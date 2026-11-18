"""Gold-making guides: the best farms right now on each realm type and faction's auction house.

One page per market (/guides/us/pvp-horde) and an index (/guides). Each ranks the mobs GoldScout players
have recorded at least data_pages.SOLID kills of by what their crafting reagents sell for there, from the
latest auction prices, fetched when the site builds (so they're in the page for search engines, not only
filled in by prices.js). The value of a kill is the add-on's: drop chance x average stack x lowest buyout,
after the auction house cut; mobs are ranked by the low end of the drop chance's range, so a lucky few kills
can't top a list. English for now: these paths aren't in data_pages.LOCAL_PAGES, so no language switch.
"""
import json
import time
import urllib.error
import urllib.request

import data_pages
from data_pages import P, e

API_URL = "https://api.wowgoldscout.com"
USER_AGENT = "GoldScout-site-build/1.0 (+https://wowgoldscout.com)"
REGIONS = {"us": "US", "eu": "EU", "kr": "Korea", "tw": "Taiwan"}
AH_CUT = data_pages.addon_number("Core.lua", "AH_CUT")   # you keep this share of a sale
TOP = 3                     # farms in a guide's top list, each for a different item
MINOR = 0.02                # drops worth less than this share of a farm's kill are left out of its table
FETCH_TIMEOUT = 20


# -- prices -----------------------------------------------------------------
def get_json(url, opener=urllib.request.urlopen, timeout=FETCH_TIMEOUT):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with opener(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_markets(api=API_URL, fetch=get_json):
    """Every faction auction house with prices: [{region, house, ruleset, faction, snapshot, prices}], prices
    {itemID: (lowest unit buyout in copper, quantity listed)}. The neutral Blackwater houses are left out (a
    guide is where your character sells). Returns [] if the server can't be reached, so the site still builds."""
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
        prices = {}
        for item, pair in (body.get("prices") or {}).items():
            if isinstance(pair, list) and len(pair) >= 2 and item.isdigit():
                prices[int(item)] = (int(pair[0]), int(pair[1]))
        markets.append({"region": house["region"], "house": house["house"], "ruleset": house["rulesetName"],
                        "faction": house["faction"], "snapshot": int(house.get("snapshot") or 0), "prices": prices})
    markets.sort(key=lambda m: (list(REGIONS).index(m["region"]), m["ruleset"], m["faction"]))
    return markets


def slug(market):
    """us/pvp-horde, eu/roleplay-pvp-alliance."""
    return "%s/%s-%s" % (market["region"], market["ruleset"].lower().replace(" ", "-"), market["faction"].lower())


def market_name(market):
    """US PvP Horde."""
    return "%s %s %s" % (REGIONS[market["region"]], market["ruleset"], market["faction"])


# -- ranking ----------------------------------------------------------------
def farms(data, prices):
    """The mobs worth farming on one auction house, best first: [{npc, kills, per_kill, cautious, parts}],
    parts [{item, rate, stack, price, listed, per_kill}] for each crafting reagent listed there, most valuable
    first. Only mobs with SOLID kills; items nobody lists (no price) don't count."""
    found = []
    for npc, entry in data.mobs.items():
        kills = entry["k"]
        if kills < data_pages.SOLID:
            continue
        parts, cautious = [], 0.0
        for item, rate, stack in data.best_drops(npc):
            price, listed = prices.get(item, (0, 0))
            if price <= 0 or listed <= 0:
                continue
            each = price * AH_CUT
            parts.append({"item": item, "rate": rate, "stack": stack, "price": price, "listed": listed,
                          "per_kill": rate * stack * each})
            cautious += data_pages.wilson(round(rate * kills), kills)[0] * stack * each
        if not parts:
            continue
        parts.sort(key=lambda part: (-part["per_kill"], part["item"]))
        found.append({"npc": npc, "kills": kills, "parts": parts, "cautious": cautious,
                      "per_kill": sum(part["per_kill"] for part in parts)})
    found.sort(key=lambda farm: (-farm["cautious"], farm["npc"]))
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
    low, high = (money(value * data_pages.KILLS_PER_HOUR) for value in (farm["cautious"], farm["per_kill"]))
    return low if low == high else "%s&ndash;%s" % (low, high)


def farm_card(data, rank, farm):
    npc, main = farm["npc"], farm["parts"][0]
    where = data_pages.zone_link(data, npc)
    levels = data.levels(npc)
    head = "%d. %s from %s" % (rank, data_pages.item_link(data, main["item"]), data_pages.mob_link(data, npc))
    place = ", ".join(part for part in (where, "level %s" % levels if levels else "") if part)
    shown = [part for part in farm["parts"] if part["per_kill"] >= MINOR * farm["per_kill"]]
    rows = "".join(
        "<tr><td>%s</td><td class=num>%s</td><td class=num>%s</td><td class=num>%s</td><td class=num>%s</td></tr>"
        % (data_pages.item_link(data, part["item"]), data_pages.chance(part["rate"], farm["kills"]),
           money(part["price"]), data_pages.num(part["listed"]), money(part["per_kill"]))
        for part in shown)
    minor = len(farm["parts"]) - len(shown)
    more = (" Plus %d minor drop%s worth under %d%% of a kill." % (minor, "" if minor == 1 else "s", MINOR * 100)
            if minor else "")
    return ('<section class=guide-farm><h3>%s</h3><p class=sub>%s</p>'
            '<p><b>%s an hour</b> at %d kills an hour, from %s kills recorded by GoldScout players.</p>'
            '<table><thead><tr><th>Drop</th><th class=num>Chance</th><th class=num>Lowest buyout</th>'
            '<th class=num>Listed now</th><th class=num>Per kill</th></tr></thead><tbody>%s</tbody></table>'
            '<p class=small>%s<a href="%s">Where to find it, and everything it drops</a></p></section>'
            % (head, place, hour_range(farm), data_pages.KILLS_PER_HOUR, data_pages.num(farm["kills"]), rows,
               e(more.strip()) + " " if more else "", P("/mob/%d" % npc)))


def market_page(data, market, ranked, markets, links):
    """(title, description, body) for one market's guide."""
    name = market_name(market)
    picks = top(ranked)
    sections = []
    if picks:
        first = picks[0]
        sections.append("<h2>The top %d right now</h2>" % len(picks))
        sections += [farm_card(data, rank, farm) for rank, farm in enumerate(picks, 1)]
        levels = by_level(data, ranked)
        if levels:
            sections.append("<h2>Best farm for your level</h2><table><thead><tr><th>Levels</th><th>Farm</th>"
                            "<th>Zone</th><th class=num>Per hour</th></tr></thead><tbody>%s</tbody></table>"
                            % "".join("<tr><td><a href=\"%s\">%s</a></td><td>%s from %s</td><td>%s</td>"
                                      "<td class=num>%s</td></tr>"
                                      % (P(data_pages.bracket_path(bracket)), data_pages.bracket_label(bracket),
                                         data_pages.item_link(data, farm["parts"][0]["item"]),
                                         data_pages.mob_link(data, farm["npc"]), data_pages.zone_link(data, farm["npc"]),
                                         hour_range(farm))
                                      for bracket, farm in levels))
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
        "cut. Gold per hour runs from that low end to the average so far, at %d kills an hour on mobs of your own "
        "level (faster if you outlevel them), and counts crafting reagents only, not gear, coin or vendor trash. "
        "Lots of listings can mean a crowded market: check before you farm for hours.</p><p class=small>%s</p>"
        % (data_pages.SOLID, e(name), round((1 - AH_CUT) * 100), data_pages.KILLS_PER_HOUR, e(data_pages.SOURCE)))
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
        best = ("%s from %s, %s an hour" % (data_pages.item_link(data, picks[0]["parts"][0]["item"]),
                                           data_pages.mob_link(data, picks[0]["npc"]), hour_range(picks[0]))
                if picks else "not enough data yet")
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


def build(data, links, write, markets):
    """Writes /guides and each market's guide; returns their URL paths."""
    ranked = {slug(market): farms(data, market["prices"]) for market in markets}
    write("guides.html", *index_page(data, markets, ranked))
    paths = ["/guides"]
    for market in markets:
        write("guides/%s.html" % slug(market), *market_page(data, market, ranked[slug(market)], markets, links))
        paths.append("/guides/" + slug(market))
    return paths
