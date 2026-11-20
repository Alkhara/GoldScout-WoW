"""Blackwater flips: items that are cheaper on a realm type's Blackwater (goblin) auction house than they sell for
on a faction's own, the website's version of the add-on's Flip tab.

One page per faction auction house (/flips/us/normal-horde), paired with the Blackwater house of the same region
and realm type, and an index (/flips). The rules are the add-on's (GoldScout/Engine.lua Engine:Flips): profit
after the faction auction house's cut of at least FLIP_MIN_PROFIT and FLIP_MIN_MARGIN of the Blackwater price,
both snapshots from the last FLIP_MAX_AGE, read from the add-on's code so the two can't drift apart. The flips
at build time are in the page for search engines; site/flips.js then works them out again from the live prices.

A flip whose faction-side price is more than OTHER_LOOT_PRICE_CAP (Core.lua) times the item's regional price, the
median of the cheapest listings across the region's auction houses (tools/bundle_prices.py, as the add-on's
regional estimates), is a "long shot", listed apart under the main table, as the add-on's Long shots checkbox
does: some are real gaps between the factions (recipes only one faction's vendors sell), many are one listing
nobody will buy (Simple Wildflowers at 100g), and a snapshot can't tell which.

Item names come from site/item_names.json (tools/item_names.py, Blizzard's Game Data API), since flips can be
any item on the auction house, not only the ones players have looted. English for now, like the gold guides.
"""
import json
import re
import sys
import time
import urllib.error
from pathlib import Path

import data_pages
import guides
from data_pages import P, e

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
import bundle_prices  # noqa: E402

NAMES_FILE = HERE / "item_names.json"
REGIONS = guides.REGIONS
AH_CUT = guides.AH_CUT
TOP = 50                    # flips listed on a market's page
RETRY_AFTER = 61            # seconds to wait once if the API says too many requests (its limit is per minute)


def engine_number(name):
    """Engine.NAME from the add-on (`Engine.FLIP_MAX_AGE = 12 * 3600` reads as 43200)."""
    source = (data_pages.ADDON / "Engine.lua").read_text(encoding="utf-8")
    found = re.search(r"\bEngine\.%s = ([\d.]+)(?:\s*\*\s*([\d.]+))?" % name, source)
    return float(found.group(1)) * float(found.group(2) or 1)


MIN_PROFIT = engine_number("FLIP_MIN_PROFIT")    # copper per item
MIN_MARGIN = engine_number("FLIP_MIN_MARGIN")    # of the Blackwater price
MAX_AGE = int(engine_number("FLIP_MAX_AGE"))     # seconds
PRICE_CAP = data_pages.addon_number("Core.lua", "OTHER_LOOT_PRICE_CAP")   # times the regional price


def load_names(path=NAMES_FILE):
    """{itemID: (name, quality)} from tools/item_names.py's file, {} without it."""
    if not path.is_file():
        return {}
    return {int(item): (value[0], int(value[1])) for item, value in json.loads(path.read_text(encoding="utf-8")).items()}


# -- prices -----------------------------------------------------------------
def fetch_markets(api=guides.API_URL, fetch=guides.get_json, known=(), sleep=time.sleep):
    """Every faction auction house paired with the Blackwater house of its region and realm type:
    [{region, ruleset, faction, sell: {house, snapshot, prices}, buy: {house, snapshot, prices}, reference}],
    prices {itemID: (lowest unit buyout in copper, quantity listed)}, reference {itemID: the region's median
    lowest buyout} over every house fetched in the region. [] if the server can't be reached.
    known: guides.fetch_markets()'s markets, whose prices are used instead of asking again (the API allows
    120 requests a minute from one address, and the guides already fetched every faction house)."""
    waited = []

    def get(url):
        """fetch(url), waiting out the API's per-minute limit once if the guides' requests used it up."""
        try:
            return fetch(url)
        except urllib.error.HTTPError as error:
            if error.code != 429 or waited:
                raise
            waited.append(url)
            print("Flips: the price API asked us to slow down; waiting %d seconds." % RETRY_AFTER)
            sleep(RETRY_AFTER)
            return fetch(url)

    try:
        listing = get(api + "/v1/prices")
    except (OSError, ValueError, urllib.error.URLError) as error:
        print("Flips skipped: no auction prices (%s)." % error)
        return []
    houses = [h for h in listing.get("houses") or [] if h.get("region") in REGIONS and h.get("rulesetName")
              and h.get("items") and h.get("faction") in ("Alliance", "Horde", "Neutral")]
    blackwater = {(h["region"], h.get("ruleset")): h for h in houses if h["faction"] == "Neutral"}
    fetched = {(m["region"], m["house"]): {"house": m["house"], "snapshot": m["snapshot"], "prices": m["prices"]}
               for m in known}

    def side(house):
        key = (house["region"], house["house"])
        if key not in fetched:
            try:
                body = get("%s/v1/prices/%s/%d" % (api, house["region"], house["house"]))
                fetched[key] = {"house": house["house"], "snapshot": int(body.get("snapshot") or house.get("snapshot") or 0),
                                "prices": guides.price_pairs(body)}
            except (OSError, ValueError, urllib.error.URLError) as error:
                print("Flips skipped for %s house %s: %s" % (house["region"], house["house"], error))
                fetched[key] = None
        return fetched[key]

    markets = []
    for house in houses:
        neutral = blackwater.get((house["region"], house.get("ruleset")))
        if house["faction"] == "Neutral" or not neutral:
            continue
        sell, buy = side(house), side(neutral)
        if sell and buy:
            markets.append({"region": house["region"], "ruleset": house["rulesetName"], "faction": house["faction"],
                            "sell": sell, "buy": buy})
    references = {}
    for (region, _), found in fetched.items():
        if found:
            references.setdefault(region, {})[found["house"]] = found["prices"]
    references = {region: {item: entry[0] for item, entry in bundle_prices.region_estimates(houses).items()}
                  for region, houses in references.items()}
    for market in markets:
        market["reference"] = references.get(market["region"], {})
    markets.sort(key=lambda m: (list(REGIONS).index(m["region"]), m["ruleset"], m["faction"]))
    return markets


def split(buy, sell, reference=None):
    """The add-on's flips between two houses' prices, best profit first, as (flips, long shots): [{item, cost,
    sell, profit, margin, stock, listed, usual}]. Buying costs no fee; selling loses the auction house's cut.
    reference: {itemID: the region's median price} (usual); a sell price over PRICE_CAP times it is a long shot."""
    reference = reference or {}
    rows, long_shots = [], []
    for item, (cost, stock) in buy.items():
        price, listed = sell.get(item, (0, 0))
        if cost <= 0 or stock <= 0 or listed <= 0 or price <= 0:
            continue
        profit = price * AH_CUT - cost
        if profit >= MIN_PROFIT and profit >= cost * MIN_MARGIN:
            usual = reference.get(item)
            row = {"item": item, "cost": cost, "sell": price, "profit": profit, "margin": profit / cost,
                   "stock": stock, "listed": listed, "usual": usual}
            (long_shots if usual and price > usual * PRICE_CAP else rows).append(row)
    for found in (rows, long_shots):
        found.sort(key=lambda row: (-row["profit"], row["item"]))
    return rows, long_shots


def flips(buy, sell, reference=None):
    """split()'s flips, without the long shots."""
    return split(buy, sell, reference)[0]


def fresh(market, now):
    """Whether both snapshots are recent enough to trust (the add-on's FLIP_MAX_AGE)."""
    return now - min(market["buy"]["snapshot"], market["sell"]["snapshot"]) <= MAX_AGE


# -- pages ------------------------------------------------------------------
def slug(market):
    return guides.slug(market)


def market_name(market):
    return guides.market_name(market)


def blackwater_name(market):
    """US Normal Blackwater."""
    return "%s %s Blackwater" % (REGIONS[market["region"]], market["ruleset"])


def item_cell(data, names, item):
    """The item's name in its quality's color, linked to its page when the site has one."""
    name, quality = names.get(item) or (data.item_name(item), 1)
    if data.has_page(item):
        return '<a class=q%d href="%s">%s</a>' % (quality, P("/item/%d" % item), e(name))
    return "<span class=q%d>%s</span>" % (quality, e(name))


def percent(fraction):
    return "%d%%" % round(fraction * 100)


def long_rows(data, names, rows):
    return "".join(
        "<tr><td>%s</td><td class=num>%s</td><td class=num>%s</td><td class=num>%s</td><td class=num><b>%s</b></td>"
        "<td class=num>%s / %s</td></tr>"
        % (item_cell(data, names, row["item"]), guides.money(row["cost"]), guides.money(row["sell"]),
           guides.money(row["usual"]), guides.money(row["profit"]), data_pages.num(row["stock"]),
           data_pages.num(row["listed"]))
        for row in rows)


def flip_rows(data, names, rows):
    return "".join(
        "<tr><td>%s</td><td class=num>%s</td><td class=num>%s</td><td class=num><b>%s</b></td><td class=num>%s</td>"
        "<td class=num>%s / %s</td></tr>"
        % (item_cell(data, names, row["item"]), guides.money(row["cost"]), guides.money(row["sell"]),
           guides.money(row["profit"]), percent(row["margin"]), data_pages.num(row["stock"]),
           data_pages.num(row["listed"]))
        for row in rows)


def how_it_works(market=None):
    faction = market["faction"] if market else "your faction"
    return (
        "<h2>How Blackwater flipping works</h2><p>The Blackwater auction houses in Booty Bay, Gadgetzan and Everlook "
        "are shared by Alliance and Horde, so prices there often differ from %s's own auction house. Buy an item "
        "there, list it on %s's auction house for the price shown, and the profit is what's left after the %d%% "
        "auction house cut. Buying costs no fee; the deposit you pay to list comes back when it sells.</p>"
        "<p>Only flips worth at least %s and %d%% of what you pay are listed, from auction house snapshots no more "
        "than %d hours old. A price is the cheapest auction: only the first few may be that cheap, so check how many "
        "are listed on each side (Blackwater / %s) before you buy a stack, and remember someone else may be flipping "
        "the same item. Flips that sell for more than %d times the item's usual price on %s's auction house are "
        "long shots, listed apart: one listing nobody buys isn't a price you can sell at, but a real gap between "
        "the factions is.</p>"
        % (e(faction), e(faction), round((1 - AH_CUT) * 100), guides.money(MIN_PROFIT), round(MIN_MARGIN * 100),
           MAX_AGE // 3600, e(faction), PRICE_CAP, e(faction)))


def in_game(links):
    return ("<div class=ingame>The GoldScout add-on's <b>Flip</b> tab finds these on your own realm while you play, "
            "next to your farms and crafts. <a href=\"%s\">Get GoldScout</a>, and add <a href=\"%s\">GoldScout "
            "Companion</a> to bring both auction houses' prices into the game every hour without scanning.</div>"
            % (links["curseforge"], P("/companion")))


def market_page(data, names, market, markets, links, now):
    """(title, description, body) for one faction auction house's flips."""
    name, faction = market_name(market), market["faction"]
    rows, long_shots = (split(market["buy"]["prices"], market["sell"]["prices"], market.get("reference"))
                        if fresh(market, now) else ([], []))
    shown = rows[:TOP]
    if not fresh(market, now):
        summary = ("The auction house snapshots for %s were more than %d hours old when this page was built. "
                   "The table fills in from the latest prices when the page loads." % (e(name), MAX_AGE // 3600))
    elif rows:
        best = rows[0]
        summary = ("%s items are cheaper on the %s auction house than they sell for on the %s auction house right "
                   "now. The best: %s, bought for %s and sold for %s, earns %s each after the auction house cut."
                   % (data_pages.num(len(rows)), e(blackwater_name(market)), e(faction),
                      e((names.get(best["item"]) or (data.item_name(best["item"]),))[0]), guides.money(best["cost"]),
                      guides.money(best["sell"]), guides.money(best["profit"])))
    else:
        summary = ("Nothing on the %s auction house sells for enough more on the %s auction house right now."
                   % (e(blackwater_name(market)), e(faction)))
    attributes = ('data-region="%s" data-buy="%d" data-sell="%d" data-cut="%s" data-min-profit="%d" '
                  'data-min-margin="%s" data-max-age="%d" data-top="%d" data-cap="%s" data-faction="%s"'
                  % (market["region"], market["buy"]["house"], market["sell"]["house"], AH_CUT, MIN_PROFIT,
                     MIN_MARGIN, MAX_AGE, TOP, PRICE_CAP, e(faction)))
    status = ("Prices from the auction house snapshots of %s (Blackwater) and %s (%s)."
              % (guides.snapshot_text(market["buy"]["snapshot"]), guides.snapshot_text(market["sell"]["snapshot"]),
                 e(faction)))
    table = ("<p class=small id=flips-status>%s</p><div class=scroll><table id=flips class=flips %s><thead><tr>"
             "<th>Item</th><th class=num>Buy on Blackwater</th><th class=num>Sell on %s</th><th class=num>Profit each"
             "</th><th class=num>Margin</th><th class=num>Listed (Blackwater / %s)</th></tr></thead><tbody>%s</tbody>"
             "</table></div><p class=small id=flips-more>%s</p>"
             % (status, attributes, e(faction), e(faction), flip_rows(data, names, shown) or
                "<tr><td colspan=6 class=small>No flips right now.</td></tr>",
                "The top %d of %s." % (TOP, data_pages.num(len(rows))) if len(rows) > TOP else ""))
    region = REGIONS[market["region"]]
    table += (
        "<details class=long-shots id=long-shots%s><summary>Long shots: <span id=long-count>%s</span> more flips "
        "priced far above usual. Check before buying.</summary><p class=small>These sell on %s's auction house for "
        "more than %d times the item's usual price in %s (the middle of its cheapest prices across the region's "
        "auction houses). Some are real gaps between the factions, like recipes only one faction's vendors sell; "
        "many are one listing nobody will pay. One listed far above the usual price is the riskiest.</p>"
        "<div class=scroll><table id=flips-long class=flips><thead><tr><th>Item</th><th class=num>Buy on Blackwater"
        "</th><th class=num>Sell on %s</th><th class=num>Usual in %s</th><th class=num>Profit each</th>"
        "<th class=num>Listed (Blackwater / %s)</th></tr></thead><tbody>%s</tbody></table></div>"
        "<p class=small id=flips-long-more>%s</p></details>"
        % ("" if long_shots else " hidden", data_pages.num(len(long_shots)), e(faction), PRICE_CAP, e(region),
           e(faction), e(region), e(faction), long_rows(data, names, long_shots[:TOP]),
           "The top %d of %s." % (TOP, data_pages.num(len(long_shots))) if len(long_shots) > TOP else ""))
    others = [other for other in markets if other is not market]
    related = ("<h2>Other realm types and factions</h2>" + data_pages.link_list(
        '<a href="%s">%s</a>' % (P("/flips/" + slug(other)), e(market_name(other))) for other in others)
        if others else "")
    trail = [("/", "Home"), ("/flips", "Blackwater flips"), ("/flips/" + slug(market), name)]
    body = ("%s<h1>Blackwater flips for %s</h1><p class=summary>%s</p>%s%s%s<p class=small>%s</p>%s"
            % (data_pages.crumbs(trail), e(name), summary, table, in_game(links), how_it_works(market),
               e(data_pages.SOURCE), related))
    title = "Blackwater auction house flips for %s (WoW Forever)" % name
    description = ("What to buy on the %s auction house and sell on the %s auction house for profit right now, from "
                   "the latest WoW Forever auction prices." % (blackwater_name(market), faction))
    return title, description, body + '<script src="/flips.js" defer></script>'


def index_page(data, names, markets, links, now):
    """(title, description, body) for /flips: every faction auction house, with its best flip."""
    rows = []
    for market in markets:
        found = (flips(market["buy"]["prices"], market["sell"]["prices"], market.get("reference"))
                 if fresh(market, now) else None)
        if found is None:
            best, count = "prices too old", "-"
        elif found:
            best = "%s, %s each" % (item_cell(data, names, found[0]["item"]), guides.money(found[0]["profit"]))
            count = data_pages.num(len(found))
        else:
            best, count = "none right now", "0"
        rows.append('<tr><td><a href="%s">%s</a></td><td class=num>%s</td><td>%s</td></tr>'
                    % (P("/flips/" + slug(market)), e(market_name(market)), count, best))
    if rows:
        listing = ("<div class=scroll><table><thead><tr><th>Realm type and faction</th><th class=num>Flips</th>"
                   "<th>Best flip when this page was built</th></tr></thead><tbody>%s</tbody></table></div>"
                   % "".join(rows))
    else:
        listing = "<p class=sub>Auction prices weren't available when this page was built. Try again soon.</p>"
    trail = [("/", "Home"), ("/flips", "Blackwater flips")]
    body = ("%s<h1>Blackwater auction house flips</h1><p class=summary>Items that are cheaper on the goblin "
            "auction houses than on your faction's: buy on Blackwater, list at home, keep the difference. Pick your "
            "realm type and faction for the full list, worked out from the latest auction prices whenever you open "
            "it.</p>%s%s%s<p class=small>%s</p>"
            % (data_pages.crumbs(trail), listing, in_game(links), how_it_works(), e(data_pages.SOURCE)))
    return ("Blackwater auction house flips (WoW Forever)",
            "What to buy on WoW Forever's Blackwater auction houses and sell on the Alliance or Horde auction house "
            "for profit, for every realm type, from the latest auction prices.", body)


def names_json(data, names):
    """The names site/flips.js needs for live flips: {itemID: [name, quality, 1 if the site has its page]}, from
    Blizzard's names, then the community data's for items Blizzard doesn't know (new in Forever)."""
    out = {str(item): [name, 1, 1 if data.has_page(item) else 0] for item, name in data.item_names.items()}
    out.update({str(item): [name, quality, 1 if data.has_page(item) else 0] for item, (name, quality) in names.items()})
    return json.dumps(out, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def reference_json(markets, region):
    """The region's median prices site/flips.js caps sell prices with ({itemID: copper}), for the items listed on
    any of its Blackwater houses (the only ones that can flip)."""
    reference, items = {}, set()
    for market in markets:
        if market["region"] == region:
            reference = market["reference"]
            items.update(market["buy"]["prices"])
    return json.dumps({str(item): reference[item] for item in sorted(items) if item in reference},
                      separators=(",", ":"))


def build(data, links, write, markets, names=None, now=None):
    """Writes /flips and each faction auction house's flips; returns their URL paths."""
    names = load_names() if names is None else names
    now = int(time.time()) if now is None else now
    write("flips.html", *index_page(data, names, markets, links, now))
    paths = ["/flips"]
    for market in markets:
        write("flips/%s.html" % slug(market), *market_page(data, names, market, markets, links, now))
        paths.append("/flips/" + slug(market))
    return paths
