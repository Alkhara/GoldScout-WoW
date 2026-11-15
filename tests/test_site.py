"""The website's data pages: built from merged exports, with item kinds from
version 4 @q lines, names escaped, gray items hidden."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "site"))

import data_pages  # noqa: E402
import merge_data  # noqa: E402
import submission  # noqa: E402

V4 = """GoldScout-export 4^abcdefghijkl^9
3809^20^0^21^22^1440^0.5400^0.5400^20^Ashenvale Bear^3730:8:8,3702:4:4,11407:6:6,14728:1:1,2934:5:5^
4054^10^0^24^25^1440^0.5800^0.5500^10^Laughing Sister & Co's^3730:2:2,1205:3:3^
2955^3^0^9^10^1411^0.4000^0.4000^3^Plainstrider^4739:1:1^
@i^3730^Big Bear Meat
@i^3702^Bear Gall Bladder
@i^11407^Torn Bear Pelt
@i^14728^War Paint Shoulder Pads
@i^2934^Ruined Leather Scraps
@i^1205^Melon Juice
@q^3730^1:7:1
@q^3702^1:7:1
@q^11407^0:15:0
@q^14728^2:4:0
@q^2934^1:7:1
@q^1205^1:0:0
@m^1440^Ashenvale
"""
LINKS = {"curseforge": "https://cf", "companion": "https://exe"}


def dataset(text=V4):
    result = submission.parse(text)
    assert result.ok, result.errors
    return data_pages.Dataset([result], merge_data.merge([result.mobs], 1000))


class VersionFourTests(unittest.TestCase):
    def test_item_details_parse_and_round_trip(self):
        result = submission.parse(V4)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.version, 4)
        self.assertEqual(result.item_meta[3730], (1, 7, True))
        self.assertEqual(result.item_meta[11407], (0, 15, False))
        self.assertEqual(submission.parse(result.text()).text(), result.text())

    def test_bad_item_details_are_rejected(self):
        for bad in ("@q^3730^1:7:2", "@q^3730^one:7:1", "@q^3730^", "@q^3730^1:7"):
            with self.subTest(bad):
                self.assertTrue(submission.parse(V4.replace("@q^3730^1:7:1", bad)).errors)

    def test_item_details_need_version_four(self):
        v3 = V4.replace("export 4^", "export 3^")
        self.assertTrue(submission.parse(v3).errors)


class DataPagesTests(unittest.TestCase):
    def test_kinds(self):
        data = dataset()
        kinds = {item: data.kind(item) for item in (3730, 3702, 11407, 14728, 1205, 9999)}
        self.assertEqual(kinds, {3730: "reagent", 3702: "reagent", 11407: "gray", 14728: "rare",
                                 1205: "other", 9999: "unknown"})

    def test_addon_gems_are_rare_drops(self):
        self.assertIn(1206, data_pages.GEMS)                # Moss Agate, from Data.lua's ns.GEMS
        data = dataset(V4.replace("@q^1205^1:0:0", "@q^1205^1:7:1").replace("1205", "1206"))
        self.assertEqual(data.kind(1206), "rare")

    def test_only_mobs_with_enough_kills(self):
        self.assertEqual(sorted(dataset().mobs), [3809, 4054])   # Plainstrider has 3 kills

    def test_mob_page_sorts_and_hides(self):
        data = dataset()
        title, description, body = data_pages.mob_page(data, 3809, LINKS)
        self.assertIn("Ashenvale Bear", title)
        reagents, others = body.split("<h2>Other drops</h2>")
        self.assertIn("Big Bear Meat", reagents)
        self.assertIn('href="/item/3730"', reagents)
        self.assertIn("40%", reagents)                     # 8 of 20 kills
        self.assertIn("22&ndash;61%", reagents)             # the 95% range around it
        self.assertIn("War Paint Shoulder Pads", others)
        self.assertNotIn("Torn Bear Pelt", body)            # gray: hidden
        self.assertIn("Help fill this in", body)

    def test_names_are_escaped(self):
        data = dataset()
        _, _, body = data_pages.mob_page(data, 4054, LINKS)
        page = re.sub(r"<script.*?</script>", "", body)
        self.assertIn("Laughing Sister &amp; Co&#x27;s", page)
        self.assertNotIn("Co's", page)
        script = re.search(r"<script[^>]*>(.*?)</script>", body).group(1)
        self.assertNotIn("&", script)                     # escaped as \u0026 in the JSON
        self.assertEqual(json.loads(script)["itemListElement"][-1]["name"], "Laughing Sister & Co's")

    def build(self, data):
        pages, index = {}, {}

        def write(path, *page, index=True):
            pages[path] = page
            index_of[path] = index
        index_of = index
        paths = data_pages.build(data, LINKS, write)
        return paths, pages, index

    def test_item_pages_and_farms(self):
        paths, pages, _ = self.build(dataset())
        self.assertIn("/item/3730", paths)
        self.assertIn("/item/14728", paths)                 # gear gets a page too
        self.assertNotIn("item/11407.html", pages)          # gray vendor trash doesn't
        title, _, item = pages["item/3730.html"]
        self.assertEqual(title, "Where to farm Big Bear Meat (WoW Forever)")
        self.assertLess(item.index("Ashenvale Bear"), item.index("Laughing"))   # 40% before 20%
        self.assertIn("Gold per hour", item)
        _, _, farms = pages["farms.html"]
        self.assertIn("Levels 21-30", farms)

    def test_sources_rank_by_the_cautious_end_of_their_range(self):
        lucky = V4.replace("3809^20^0^21^22^1440^0.5400^0.5400^20^Ashenvale Bear^3730:8:8",
                           "3809^200^0^21^22^1440^0.5400^0.5400^200^Ashenvale Bear^3730:80:80")
        lucky = lucky.replace("^Laughing Sister & Co's^3730:2:2", "^Laughing Sister & Co's^3730:5:5")
        data = dataset(lucky)                               # 40% of 200 kills beats 50% of 10
        self.assertEqual([source[0] for source in data.sources[3730]], [3809, 4054])
        few = V4.replace("^Laughing Sister & Co's^3730:2:2", "^Laughing Sister & Co's^3730:9:9")
        data = dataset(few)                                 # 90% of 10 kills still comes after 40% of 20
        self.assertEqual([source[0] for source in data.sources[3730]], [3809, 4054])

    def test_thin_pages_stay_out_of_search(self):
        paths, pages, index = self.build(dataset())
        self.assertTrue(index["mob/3809.html"])             # 20 kills
        self.assertFalse(index["mob/4054.html"])            # 10 kills: built, but noindex and not in the sitemap
        self.assertIn("mob/4054.html", pages)
        self.assertNotIn("/mob/4054", paths)
        self.assertFalse(index["item/1205.html"])           # only from the 10-kill mob
        self.assertTrue(index["item/3730.html"])

    def test_pickpocket_sources(self):
        rogue = V4.replace("4054^10^0^24^25", "4054^10^20^24^25").replace(
            "^Laughing Sister & Co's^3730:2:2,1205:3:3^", "^Laughing Sister & Co's^3730:2:2,1205:3:3^16882:5:5")
        _, pages, _ = self.build(dataset(rogue))
        _, _, item = pages["item/16882.html"]
        self.assertIn("<h2>Pickpocketing</h2>", item)
        self.assertIn("pickpocketed it from 1 mob", item)
        self.assertIn("At %d pickpockets an hour" % data_pages.PICKS_PER_HOUR, item)

    def test_wilson_range(self):
        self.assertEqual([round(x * 100) for x in data_pages.wilson(50, 200)], [20, 31])
        self.assertEqual(data_pages.wilson(0, 0), (0.0, 1.0))
        low, high = data_pages.wilson(0, 30)
        self.assertEqual(low, 0.0)
        self.assertLess(high, 0.12)

    def test_pace_comes_from_the_addon(self):
        self.assertEqual((data_pages.KILLS_PER_HOUR, data_pages.PICKS_PER_HOUR), (70, 110))
        self.assertEqual((data_pages.CATCHES_PER_HOUR, data_pages.POOL_SHARE), (200, 0.5))

    def test_level_range_pages(self):
        paths, pages, index = self.build(dataset())
        self.assertIn("/farms/levels-21-30", paths)
        self.assertNotIn("farms/levels-1-10.html", pages)  # no mobs recorded at those levels
        title, description, body = pages["farms/levels-21-30.html"]
        self.assertEqual(title, "Best gold farms for levels 21-30 (WoW Forever)")
        self.assertIn("from 30 kills", description)
        self.assertIn('href="/mob/3809"', body)
        self.assertIn('href="/zone/1440"', body)
        self.assertIn("Gold per hour", body)
        self.assertIn('data-value="3730:28', body)        # 0.4 Big Bear Meat a kill x 70 kills an hour
        self.assertIn('<tr data-thin><td><a href="/mob/4054">', body)   # 10 kills: sorted after the rest
        self.assertIn('<tr><td><a href="/mob/3809">', body)

    def test_breadcrumbs_and_structured_data(self):
        data = dataset()
        _, _, body = data_pages.mob_page(data, 4054, LINKS)
        script = re.search(r'<script type="application/ld\+json">(.*?)</script>', body).group(1)
        crumbs = json.loads(script)
        self.assertEqual(crumbs["@type"], "BreadcrumbList")
        self.assertEqual([c["name"] for c in crumbs["itemListElement"]],
                         ["Home", "Farms by level", "Levels 21-30", "Laughing Sister & Co's"])
        self.assertEqual(crumbs["itemListElement"][2]["item"], "https://wowgoldscout.com/farms/levels-21-30")
        _, _, farms = data_pages.farms_page(data, LINKS)
        self.assertIn('id="levels-21-30"', farms)       # old /farms#levels-21-30 links still land
        self.assertIn('href="/farms/levels-21-30"', farms)

    def test_summaries_and_descriptions(self):
        data = dataset()
        _, description, body = data_pages.mob_page(data, 3809, LINKS)
        self.assertIn("Ashenvale Bear is a level 21-22 mob in Ashenvale in WoW Forever. GoldScout players have "
                      "recorded 20 kills. Its most common crafting reagent is Big Bear Meat (40% of kills).", body)
        self.assertIn("Big Bear Meat 40%", description)
        _, description, body = data_pages.item_page(data, 3730, LINKS)
        self.assertIn("Big Bear Meat is a crafting reagent in WoW Forever. GoldScout players have looted it from "
                      "2 mobs; the best source is Ashenvale Bear (level 21-22, Ashenvale), "
                      "which gave it on 40% of 20 kills.", body)
        self.assertIn("and 1 other mob in", description)
        self.assertIn('href="/item/3702"', body)          # other items the same mobs drop

    def test_zone_pages_and_links(self):
        data = dataset()
        pages = {}
        paths = data_pages.build(data, LINKS, lambda path, *page, **_: pages.__setitem__(path, page))
        self.assertIn("/zone/1440", paths)
        self.assertIn("/drop-rates", paths)
        title, _, zone = pages["zone/1440.html"]
        self.assertEqual(title, "Where to farm gold in Ashenvale (WoW Forever)")
        self.assertIn('href="/mob/3809"', zone)
        self.assertIn('href="/mob/4054"', zone)
        self.assertIn("2 level 21-25 mobs in Ashenvale", zone)
        _, _, mob = pages["mob/3809.html"]
        self.assertIn('<a href="/zone/1440">Ashenvale</a>', mob)
        self.assertIn("More farms in Ashenvale", mob)
        self.assertIn('href="/drop-rates"', mob)
        _, _, rates = pages["drop-rates.html"]
        self.assertIn("1,000 kills per mob", rates)

    def test_price_placeholders_for_prices_js(self):
        data = dataset()
        pages = {}
        data_pages.build(data, LINKS, lambda path, *page, **_: pages.__setitem__(path, page))
        _, _, mob = pages["mob/3809.html"]
        self.assertIn('id="prices-bar"', mob)
        self.assertIn('data-price="3730"', mob)
        self.assertIn('data-value="3730:0.4"', mob)            # 8 of 20 kills, stacks of 1
        self.assertIn("Blizzard Entertainment Game Data API", mob)
        _, _, farms = pages["farms.html"]
        self.assertIn("<table class=by-value>", farms)
        self.assertIn("Gold per kill", farms)
        _, _, item = pages["item/3730.html"]
        self.assertIn('data-qty="3730"', item)
        self.assertIn('data-value="3730:28"', item)             # gold per hour: 0.4 a kill x 70 kills
        _, _, rates = pages["drop-rates.html"]
        self.assertIn("Blizzard Entertainment Game Data API", rates)
        self.assertNotIn("prices-bar", rates)

    def test_per_kill_values(self):
        self.assertEqual(data_pages.per_kill([(10, 0.5, 2.0), (11, 0.12345, 1.0)]), "10:1,11:0.1235")
        self.assertEqual(data_pages.per_kill([]), "")

    def test_prices_script_and_policy_agree_on_the_server(self):
        # By path: other tests put companion/ on sys.path, whose build/ folder would win.
        import importlib.util
        spec = importlib.util.spec_from_file_location("site_build", ROOT / "site" / "build.py")
        build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build)
        script =(ROOT / "site" / "prices.js").read_text(encoding="utf-8")
        self.assertIn('var API = "%s";' % build.API_URL, script)
        self.assertNotIn("innerHTML", script)                  # server data only ever goes in as text
        search = (ROOT / "site" / "search.js").read_text(encoding="utf-8")
        self.assertNotIn("innerHTML", search)                  # search results only ever go in as text
        page = build.layout("t", "d", "/x", "<p>body</p>")
        self.assertIn('<script src="/prices.js" defer></script>', page)
        self.assertIn('class="site-search" role="search" hidden', page)   # shown by search.js
        self.assertIn('<script src="/search.js" defer></script>', page)
        self.assertNotIn("noindex", page)
        self.assertIn('<meta name="robots" content="noindex, follow">', build.layout("t", "d", "/x", "", index=False))

    def test_without_item_details_everything_is_listed(self):
        v3 = "\n".join(line for line in V4.splitlines() if not line.startswith("@q"))
        data = dataset(v3.replace("export 4^", "export 3^"))
        _, _, body = data_pages.mob_page(data, 3809, LINKS)
        self.assertIn("<h2>Drops</h2>", body)
        self.assertIn("Torn Bear Pelt", body)


FISH = """GoldScout-export 5^abcdefghijkl^1
@f^1444^0^40^226^6359:12:12,6358:8:8,3670:30:30^
@f^1444^180750^10^240^13422:6:12^
@f^1440^0^4^100^6359:1:1^
@i^6359^Firefin Snapper
@i^6358^Oily Blackmouth
@i^3670^Large Slimy Bone
@i^13422^Stonescale Eel
@q^6359^1:7:1
@q^6358^1:7:1
@q^3670^0:15:0
@q^13422^1:7:1
@m^1444^Feralas
@m^1440^Ashenvale
@l^0^enUS
"""


class FishingPagesTests(unittest.TestCase):
    def setUp(self):
        fish = submission.parse(FISH)
        assert fish.ok, fish.errors
        mobs = submission.parse(V4)
        results = [mobs, fish]
        self.data = data_pages.Dataset(results, merge_data.merge([mobs.mobs], 1000),
                                       merge_data.merge_fish([fish.fishing], 1000))
        self.pages, self.index = {}, {}

        def write(path, *page, index=True):
            self.pages[path] = page
            self.index[path] = index
        self.paths = data_pages.build(self.data, LINKS, write)

    def test_zone_page_lists_each_spot(self):
        self.assertIn("/fishing/1444", self.paths)
        title, description, body = self.pages["fishing/1444.html"]
        self.assertEqual(title, "Fishing in Feralas: catches and gold per hour (WoW Forever)")
        self.assertIn("<h2>Open water</h2>", body)
        self.assertIn("<h2>Fishing pool</h2>", body)
        self.assertIn("lowest skill seen 226", body)
        self.assertIn("Firefin Snapper on 30% of catches", body)
        self.assertNotIn("Large Slimy Bone", body)            # gray junk left out
        self.assertIn('data-value="6359:60,6358:40"', body)    # an hour of open water: 200 catches
        self.assertIn('data-value="13422:120"', body)          # pools: half the pace, stacks of 2
        self.assertNotIn("fishing/1440.html", self.pages)      # 4 catches: under the minimum

    def test_overview_ranks_every_spot(self):
        title, _, body = self.pages["fishing.html"]
        self.assertEqual(title, "Best fishing spots for gold (WoW Forever)")
        self.assertIn("<table class=by-value>", body)
        self.assertEqual(body.count('href="/fishing/1444"'), 2)  # open water and the pool

    def test_fish_get_item_pages(self):
        title, description, body = self.pages["item/6359.html"]
        self.assertEqual(title, "Where to fish Firefin Snapper (WoW Forever)")
        self.assertIn("fished it up in 1 zone; the best spot is open water in Feralas, which gave it on 30% "
                      "of 40 catches.", body)
        self.assertIn("<h2>Fishing</h2>", body)
        self.assertTrue(self.index["item/6359.html"])          # 40 catches
        self.assertFalse(self.index["item/13422.html"])        # 10 catches at the pool
        self.assertNotIn("item/3670.html", self.pages)

    def test_search_index_covers_every_kind_of_page(self):
        index = {path: (name, detail) for name, path, detail, _ in data_pages.search_index(self.data)}
        self.assertEqual(index["/item/3730"], ("Big Bear Meat", "Crafting reagent · 2 sources"))
        self.assertEqual(index["/item/6359"], ("Firefin Snapper", "Crafting reagent · 1 source · fished up"))
        self.assertEqual(index["/mob/3809"], ("Ashenvale Bear", "Mob · level 21-22 · Ashenvale"))
        self.assertEqual(index["/zone/1440"][0], "Ashenvale")
        self.assertEqual(index["/fishing/1444"][0], "Fishing in Feralas")
        self.assertEqual(index["/farms/levels-21-30"][0], "Gold farms for levels 21-30")
        self.assertNotIn("/item/3670", index)                   # gray: no page, so not searchable
        for path in index:                                      # every result is a page the build makes
            self.assertIn(path.lstrip("/") + ".html", self.pages)


AREAS = V4.replace("export 4^", "export 5^") + "@a^3809^210:12,211:6,250:1\n@a^4054^100:4\n"
FISH_AREAS = """GoldScout-export 5^mnopqrstuvwx^1
@f^1444^0^40^226^6359:12:12^205:30,206:2
@i^6359^Firefin Snapper
@q^6359^1:7:1
@m^1444^Feralas
"""


class AreaMapTests(unittest.TestCase):
    """Where on the zone map: a grid with the game's coordinates, drawn from players' area squares."""

    def setUp(self):
        mobs, fish = submission.parse(AREAS), submission.parse(FISH_AREAS)
        assert mobs.ok and fish.ok, (mobs.errors, fish.errors)
        self.data = data_pages.Dataset([mobs, fish], merge_data.merge([mobs.mobs], 1000),
                                       merge_data.merge_fish([fish.fishing], 1000))

    def test_square_coordinates_match_the_game_map(self):
        self.assertEqual(data_pages.square_coords(0), "2.5, 2.5")
        self.assertEqual(data_pages.square_coords(210), "52.5, 52.5")   # row 10, column 10
        self.assertEqual(data_pages.square_coords(399), "97.5, 97.5")

    def test_quiet_squares_are_left_out_as_in_the_addon(self):
        self.assertEqual(data_pages.area_squares({210: 12, 211: 6, 250: 1}), {210: 1.0, 211: 0.5})

    def test_mob_page_draws_where_it_was_looted(self):
        _, _, body = data_pages.mob_page(self.data, 3809, LINKS)
        self.assertIn("<h2>Where to find it</h2>", body)
        self.assertIn("around <b>52.5, 52.5</b>", body)
        self.assertIn('aria-label="Map grid of Ashenvale: where players looted Ashenvale Bear"', body)
        self.assertEqual(body.count('class="h"'), 2)              # 250 is under a tenth of the busiest
        self.assertIn('class="g"', body)                          # the other mob's square: the zone's outline
        self.assertIn("<title>Around 52.5, 52.5: looted 12 here</title>", body)

    def test_too_few_loots_draw_no_map(self):
        _, _, body = data_pages.mob_page(self.data, 4054, LINKS)   # 4 loots placed
        self.assertNotIn("<svg", body)
        self.assertNotIn("Where to find it", body)
        self.assertEqual(data_pages.mob_page(dataset(), 3809, LINKS)[2].count("<svg"), 0)   # a version 4 export

    def test_item_page_weighs_squares_by_drop_chance(self):
        (map_id, cells, loots), = self.data.item_areas(3730)       # Big Bear Meat: two Ashenvale mobs
        self.assertEqual((map_id, loots), (1440, 23))
        self.assertAlmostEqual(cells[210], 12 * 0.4)
        self.assertAlmostEqual(cells[100], 4 * 0.2)
        _, _, body = data_pages.item_page(self.data, 3730, LINKS)
        self.assertIn("<h2>Where on the map</h2>", body)
        self.assertIn('<figcaption class="zone">Ashenvale</figcaption>', body)
        self.assertIn("Most around <b>52.5, 52.5</b>", body)

    def test_fishing_spots_are_drawn_too(self):
        _, _, body = data_pages.item_page(self.data, 6359, LINKS)
        self.assertIn('<figcaption class="zone">Feralas</figcaption>', body)
        self.assertIn("Most around <b>27.5, 52.5</b>", body)

    def test_names_in_the_map_are_escaped(self):
        self.data.mobs[4054]["areas"][1440][100] = 20
        _, _, body = data_pages.mob_page(self.data, 4054, LINKS)
        self.assertIn("looted Laughing Sister &amp; Co&#x27;s", body)


class FaqTests(unittest.TestCase):
    def test_every_question_is_on_the_page_and_in_the_structured_data(self):
        import build
        _, _, body = build.faq_page()
        data = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', body, re.S).group(1))
        self.assertEqual(data["@type"], "FAQPage")
        questions = [q for _, section in build.FAQ for q, _ in section]
        self.assertEqual([entry["name"] for entry in data["mainEntity"]], questions)
        for entry in data["mainEntity"]:
            self.assertNotIn("<", entry["acceptedAnswer"]["text"])       # plain text, links resolved
            self.assertNotIn("%(", entry["acceptedAnswer"]["text"])
        self.assertIn('href="https://discord.gg/rJdZcuepzN"', body)
        self.assertIn('href="mailto:admin@wowgoldscout.com"', body)


if __name__ == "__main__":
    unittest.main()
