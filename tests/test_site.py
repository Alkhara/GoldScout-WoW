"""The website's data pages: built from merged exports, with item kinds from
version 4 @q lines, names escaped, gray items hidden."""
import datetime
import importlib.util
import json
import re
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "site"))

import data_pages  # noqa: E402
import merge_data  # noqa: E402
import submission  # noqa: E402


def site_build():
    """site/build.py, loaded by its path: companion/build.py has the same module name, and other test modules
    put companion/ first on sys.path."""
    if "site_build" not in sys.modules:
        spec = importlib.util.spec_from_file_location("site_build", ROOT / "site" / "build.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules["site_build"] = module
        spec.loader.exec_module(module)
    return sys.modules["site_build"]

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

    def maps(self, *map_ids):
        """Point the pages at a folder holding these zones' map art (and only these)."""
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        for map_id in map_ids:
            (Path(folder.name) / ("%d.webp" % map_id)).write_bytes(b"")
        patcher = mock.patch.object(data_pages, "MAPS", Path(folder.name))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_mob_page_draws_where_it_was_looted(self):
        self.maps()                                                # no map art: our own grid
        _, _, body = data_pages.mob_page(self.data, 3809, LINKS)
        self.assertIn("<h2>Where to find it</h2>", body)
        self.assertIn("around <b>52.5, 52.5</b>", body)
        self.assertIn('aria-label="Map of Ashenvale: where players looted Ashenvale Bear"', body)
        self.assertEqual(body.count('class="h"'), 2)              # 250 is under a tenth of the busiest
        self.assertIn('class="g"', body)                          # the other mob's square: the zone's outline
        self.assertIn("<title>Around 52.5, 52.5: looted 12 here</title>", body)
        self.assertIn("Faint squares", body)

    def test_the_zones_own_map_when_we_have_it(self):
        self.maps(1440)
        _, _, body = data_pages.mob_page(self.data, 3809, LINKS)
        self.assertIn('<img src="/maps/1440.webp" width="1002" height="668" loading="lazy"', body)
        self.assertIn('alt="Map of Ashenvale: where players looted Ashenvale Bear"', body)
        self.assertIn('<svg viewBox="0 0 1002 668"', body)
        # Square 210 is row 10, column 10: half way across and down the map's 1002x668.
        self.assertIn('<rect x="501.0" y="334.0" width="50.1" height="33.4" fill-opacity="0.70">', body)
        self.assertEqual(body.count("<rect"), 2)                  # no outline squares over real art
        self.assertIn("Map art &copy; Blizzard Entertainment.", body)
        self.assertNotIn("Faint squares", body)

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


class CommunityTargetsTests(unittest.TestCase):
    """The community's targets on the home page and /data-wanted: players, kills, solid mobs, by a date."""

    def setUp(self):
        self.data = dataset()   # 1 player, 30 kills of 2 mobs, none solid
        self.before = data_pages.TARGETS_DATE - datetime.timedelta(days=12)

    def tearDown(self):
        data_pages.LANG = "en"

    def test_progress_and_days_left(self):
        box = data_pages.targets_section(self.data, self.before)
        self.assertIn("<h2>Community goals</h2>", box)
        self.assertIn("by %s (12 days left)" % data_pages.day_text(data_pages.TARGETS_DATE), box)
        self.assertIn("Players sharing data</span>", box)
        self.assertIn('<span class=target-num><b>1</b> of 50</span>', box)
        self.assertIn('<span class=target-num><b>33</b> of 30,000</span>', box)   # every kill, thin mobs too
        self.assertIn("Mobs with solid drop rates (50+ kills)", box)
        self.assertIn('aria-label="0 of 300"><span style="width:0%"></span>', box)

    def test_last_day_and_after(self):
        box = data_pages.targets_section(self.data, data_pages.TARGETS_DATE - datetime.timedelta(days=1))
        self.assertIn("(1 day left)", box)
        self.assertIn("(today)", data_pages.targets_section(self.data, data_pages.TARGETS_DATE))
        box = data_pages.targets_section(self.data, data_pages.TARGETS_DATE + datetime.timedelta(days=1))
        self.assertIn("The goals for %s, and how far everyone got." % data_pages.day_text(data_pages.TARGETS_DATE),
                      box)
        self.assertNotIn("left)", box)

    def test_reached(self):
        self.data.contributors, self.data.kills = 60, 40000
        for npc in range(300):
            self.data.mobs[50000 + npc] = dict(self.data.mobs[3809], k=50)
        box = data_pages.targets_section(self.data, self.before)
        self.assertIn("Every goal for", box)
        self.assertIn('<span class=target-num><b class=done>60</b> of 50</span>', box)
        self.assertIn('style="width:100%"', box)                     # past the target, the bar stays full
        self.assertNotIn('style="width:120%"', box)

    def test_on_the_pages(self):
        pages = {}

        def write(path, *page, index=True):
            pages[path] = page
        data_pages.build(self.data, LINKS, write)
        self.assertIn("<section class=targets>", pages["data-wanted.html"][2])
        build = site_build()
        s = dict(build.stats([], {}), targets=data_pages.targets_section(self.data, self.before))
        self.assertIn("<section class=targets>", build.page(s))

    def test_german(self):
        data_pages.LANG = "de"
        data_pages.MISSING.clear()
        for day in (self.before, data_pages.TARGETS_DATE - datetime.timedelta(days=1), data_pages.TARGETS_DATE,
                    data_pages.TARGETS_DATE + datetime.timedelta(days=1)):
            box = data_pages.targets_section(self.data, day)
        self.data.contributors, self.data.kills = 60, 40000
        for npc in range(300):
            self.data.mobs[50000 + npc] = dict(self.data.mobs[3809], k=50)
        box = data_pages.targets_section(self.data, self.before)
        self.assertEqual(data_pages.MISSING, set())
        self.assertIn("<h2>Gemeinschaftsziele</h2>", box)
        self.assertIn("40.000", box)
        self.assertEqual(data_pages.day_text(datetime.date(2026, 3, 1)), "1. März")


class SharePageTests(unittest.TestCase):
    """/share: paste a /gscout export and send it to the upload service, as the companion does."""

    def test_page(self):
        build = site_build()
        title, description, body = build.share_page()
        self.assertEqual(title, "Share your GoldScout drop data")
        self.assertIn('<form id="share-form" class="share-form" hidden>', body)   # shown by share.js
        self.assertIn('<script src="/share.js" defer></script>', body)
        self.assertIn('href="%s"' % build.LINKS["share"], body)                  # the GitHub form, for no JS
        self.assertIn('href="%s"' % build.LINKS["terms"], body)
        # The same two promises as the GitHub form.
        for consent in ("I collected this data myself by playing World of\n  Warcraft with GoldScout.",
                        "including the license they grant for this data."):
            self.assertIn(consent, body)

    def test_script_matches_the_server(self):
        script = (ROOT / "site" / "share.js").read_text(encoding="utf-8")
        server = (ROOT / "server" / "src" / "index.js").read_text(encoding="utf-8")
        terms = re.search(r'var TERMS = "([0-9-]+)"', script).group(1)
        self.assertIn('"%s"' % terms, re.search(r"const TERMS_VERSIONS = new Set\(\[(.*?)\]\)", server).group(1))
        self.assertIn("const MAX_BYTES = %s;" % re.search(r"var MAX_BYTES = (\d+);", script).group(1), server)
        header = re.search(r"var HEADER = (/.*/);", script).group(1)
        self.assertIn("const HEADER = %s;" % header, server)
        self.assertIn("textContent", script)
        self.assertNotIn("innerHTML", script)

    def test_leaderboard_box(self):
        # The same box on both pages (share.js finds it by these ids), and the same name rule as the server.
        build = site_build()
        english, german = build.share_page()[2], build.share_page_de()[2]
        ids = re.compile(r'id="(board-[^"]+|share-board)"')
        self.assertEqual(set(ids.findall(english)), {"share-board", "board-rank", "board-public", "board-name",
                                                     "board-save", "board-status"})
        self.assertEqual(ids.findall(english), ids.findall(german))
        self.assertIn('<section id="share-board" class="share-board" hidden>', english)
        script = (ROOT / "site" / "share.js").read_text(encoding="utf-8")
        server = (ROOT / "server" / "src" / "leaderboard.js").read_text(encoding="utf-8")
        for element in set(ids.findall(english)):
            self.assertIn('getElementById("%s")' % element, script)
        self.assertEqual(re.search(r"var NAME = (/.*/u);", script).group(1),
                         re.search(r"const NAME = (/.*/u);", server).group(1))

    def test_pages_point_to_it(self):
        build = site_build()
        self.assertIn('href="/share"', build.page(dict(build.stats([], {}), targets="")))
        self.assertIn('href="/share"', build.faq_page()[2])
        self.assertIn('href="/share"', build.leaderboard_page()[2])
        self.assertTrue(any(entry[1] == "/share" for entry in build.STATIC_SEARCH))


class GermanJoinPagesTests(unittest.TestCase):
    """/de/companion and /de/share: German visitors who want to help don't land on English pages."""

    def setUp(self):
        self.build = site_build()

    def test_pages(self):
        title, _, body = self.build.companion_page_de({"contributors": 1234})
        self.assertEqual(title, "GoldScout Companion: stündliche Auktionspreise für GoldScout")
        self.assertIn("1.234 Spieler haben bisher geteilt", body)
        self.assertIn('href="%s"' % self.build.LINKS["companion"], body)
        self.assertIn('href="/de/share"', body)
        title, _, body = self.build.share_page_de()
        self.assertEqual(title, "Teile deine GoldScout-Dropdaten")
        self.assertIn('<form id="share-form" class="share-form" hidden>', body)
        self.assertIn('<script src="/share.js" defer></script>', body)
        self.assertIn('href="/de/companion"', body)
        self.assertIn('href="%s"' % self.build.LINKS["share"], body)
        for page in (self.build.companion_page_de({"contributors": 1})[2], body):
            self.assertNotIn("kostenlos", page.lower())

    def test_same_form_as_english(self):
        english, german = self.build.share_page()[2], self.build.share_page_de()[2]
        pick = re.compile(r'id="[^"]+"|name="[^"]+"|type="[^"]+"')
        self.assertEqual(pick.findall(english), pick.findall(german))

    def test_language_links(self):
        for path in ("/companion", "/share"):
            self.assertTrue(data_pages.is_local_page(path))
            alternates, other = self.build.language_links(path, "en")
            self.assertEqual(other, "/de" + path)
            self.assertIn('hreflang="de" href="https://wowgoldscout.com/de%s"' % path, alternates)
        self.assertIn('href="/de/companion"', self.build.CHROME["de"]["nav"])
        self.assertIn('href="/de/share"', self.build.CHROME["de"]["footer"])
        self.assertTrue(all(not entry[1].startswith("/companion") and not entry[1].startswith("/share")
                            for entry in self.build.STATIC_SEARCH_DE))

    def test_script_speaks_both(self):
        script = (ROOT / "site" / "share.js").read_text(encoding="utf-8")
        german, english = re.search(r'lang === "de" \? \{(.*?)\} : \{(.*?)\};', script, re.S).groups()
        keys = re.compile(r"^\s+(\w+):", re.M)
        self.assertEqual(keys.findall(german), keys.findall(english))
        self.assertGreater(len(keys.findall(german)), 10)


class GermanSitePagesTests(unittest.TestCase):
    """/de/, /de/faq and /de/leaderboard: the rest of the site in German."""

    def setUp(self):
        self.build = site_build()

    def test_faq_matches_english(self):
        self.assertEqual([len(questions) for _, questions in self.build.FAQ_DE],
                         [len(questions) for _, questions in self.build.FAQ])
        _, _, english = self.build.faq_page()
        title, _, german = self.build.faq_page("de")
        self.assertEqual(title, "GoldScout-FAQ: Fragen zum Gold-Addon für WoW Forever")
        anchors = re.compile(r'<h2 id="([^"]+)"')
        self.assertEqual(anchors.findall(english), anchors.findall(german))   # /faq#prices works on /de/faq
        self.assertIn('"@type": "FAQPage"', german.replace('":"', '": "'))
        self.assertIn('href="/de/share"', german)
        self.assertNotIn("kostenlos", german.lower())

    def test_home_page(self):
        s = {"contributors": 1234, "mobs": 888, "kills": 20420, "drops": 18234, "updated": "x",
             "updated_iso": "2026-11-16", "targets_de": "<section class=targets>T</section>"}
        home = self.build.page_de(s)
        self.assertIn('<html lang="de">', home)
        self.assertIn('<link rel="canonical" href="https://wowgoldscout.com/de/">', home)
        self.assertIn('hreflang="en" href="https://wowgoldscout.com/"', home)
        self.assertIn('class="lang-switch" href="/"', home)
        self.assertIn("<b>1.234</b><span>Mitwirkende</span>", home)
        self.assertIn("Zuletzt aktualisiert am 16. November 2026.", home)
        self.assertIn("<section class=targets>T</section>", home)
        self.assertIn('placeholder="Gegenstände, Gegner, Gebiete"', home)
        self.assertNotIn("kostenlos", home.lower())
        english = self.build.page(dict(s, targets=""))
        self.assertIn('class="lang-switch" href="/de/"', english)
        self.assertIn('hreflang="de" href="https://wowgoldscout.com/de/"', english)
        # The same sections and screenshots as the English home page.
        sections = re.compile(r'<section id="([^"]+)"|src="/?screenshots/([^"]+)"')
        self.assertEqual(sections.findall(english), sections.findall(home))

    def test_leaderboard(self):
        title, _, body = self.build.leaderboard_page_de()
        self.assertEqual(title, "Bestenliste der Mitwirkenden")
        for marker in ('id="leaderboard-status"', '<table id="leaderboard" hidden>', '<script src="/leaderboard.js"'):
            self.assertIn(marker, body)
        script = (ROOT / "site" / "leaderboard.js").read_text(encoding="utf-8")
        german, english = re.search(r'GERMAN \? \{(.*?)\} : \{(.*?)\};', script, re.S).groups()
        keys = re.compile(r"^\s+(\w+):", re.M)
        self.assertEqual(keys.findall(german), keys.findall(english))
        self.assertNotIn("innerHTML", script)

    def test_german_links_stay_german(self):
        chrome = self.build.CHROME["de"]
        for path in ("/de/leaderboard", "/de/faq", "/de/"):
            self.assertIn('href="%s"' % path, chrome["nav"] + chrome["footer"])
        self.assertNotIn('lang="en">Leaderboard', chrome["nav"] + chrome["footer"])
        self.assertTrue(data_pages.is_local_page("/"))
        self.assertFalse(data_pages.is_local_page("/not-translated"))
        data_pages.LANG = "de"
        try:
            self.assertEqual(data_pages.P("/"), "/de/")
            self.assertEqual(data_pages.P("/leaderboard"), "/de/leaderboard")
        finally:
            data_pages.LANG = "en"


class ChampionsScriptTests(unittest.TestCase):
    def test_writes_text_only(self):
        script = (ROOT / "site" / "champions.js").read_text(encoding="utf-8")
        self.assertNotIn("innerHTML", script)
        self.assertIn("textContent", script)
        self.assertIn('"/v1/leaderboard/zones"', script)


GERMAN = """GoldScout-export 5^dededededede^1
3809^12^0^21^22^1440^0.5400^0.5400^12^Eschentalbär^3730:5:5^
1000^6^0^30^31^1413^0.5000^0.5000^6^Fieser Kerl^3730:1:1^
@i^3730^Großes Bärenfleisch
@m^1440^Eschental
@m^1413^Das Brachland
@l^0^deDE
"""


class GermanPagesTests(unittest.TestCase):
    """The German pages under /de/: German text, German names where German players recorded them."""

    def setUp(self):
        english, german = submission.parse(V4 + "@m^1413^The Barrens\n"), submission.parse(GERMAN)
        assert english.ok and german.ok, (english.errors, german.errors)
        results = [submission.keep_english_names(english), submission.keep_english_names(german)]
        self.data = data_pages.Dataset(results, merge_data.merge([english.mobs, german.mobs], 1000))
        data_pages.MISSING.clear()
        self.pages = {}

        def write(path, *page, index=True):
            self.pages[path] = page
        self.paths = data_pages.build_language("de", self.data, LINKS, write)

    def test_german_names_are_kept_apart_from_the_shared_data(self):
        german = submission.keep_english_names(submission.parse(GERMAN))
        self.assertEqual(german.item_names, {})                       # the shared data stays English
        self.assertEqual(german.local_names["items"], {3730: "Großes Bärenfleisch"})
        self.assertEqual(german.local_names["maps"], {1440: "Eschental", 1413: "Das Brachland"})
        self.assertEqual(german.local_names["mobs"], {3809: "Eschentalbär", 1000: "Fieser Kerl"})
        self.assertEqual(submission.keep_english_names(submission.parse(V4)).local_names, {})

    def test_every_text_on_the_german_pages_is_translated(self):
        data_pages.LANG = "de"
        try:
            data_pages.search_index(self.data)
        finally:
            data_pages.LANG = "en"
        self.assertEqual(data_pages.MISSING, set())
        self.assertEqual(data_pages.LANG, "en")                       # building German leaves English as it was

    def test_mob_page(self):
        title, description, body = self.pages["mob/3809.html"]
        self.assertEqual(title, "Eschentalbär: Drops und Dropraten (WoW Forever)")
        self.assertIn("<h1>Eschentalbär</h1>", body)
        self.assertIn("Eschentalbär ist ein Gegner der Stufe 21-22 in Eschental in WoW Forever. "
                      "GoldScout-Spieler haben 32 Kills erfasst.", body)
        self.assertIn('<a href="/de/item/3730">Großes Bärenfleisch</a>', body)
        self.assertIn('<a href="/de/zone/1440">Eschental</a>', body)
        self.assertIn('href="/de/drop-rates"', body)
        self.assertIn('href="/de/companion"', body)                    # the companion page has a German version
        # A name no German player recorded keeps its English name, marked.
        self.assertIn('<span class=en-name lang=en title="Noch kein deutscher Name erfasst">Bear Gall Bladder</span>',
                      body)
        self.assertNotIn("Ashenvale", body)

    def test_numbers_and_percent(self):
        _, _, body = self.pages["item/3730.html"]
        self.assertIn("Großes Bärenfleisch ist ein Handwerksmaterial in WoW Forever.", body)
        data_pages.LANG = "de"
        try:
            self.assertEqual((data_pages.num(12668), data_pages.percent(0.047)), ("12.668", "4,7%"))
        finally:
            data_pages.LANG = "en"
        self.assertEqual((data_pages.num(12668), data_pages.percent(0.047)), ("12,668", "4.7%"))

    def test_zone_names_with_an_article(self):
        title, _, body = self.pages["zone/1413.html"]
        self.assertEqual(title, "Wo du im Brachland Gold farmst (WoW Forever)")
        self.assertIn("<h1>Farmen im Brachland</h1>", body)
        data_pages.LANG = "de"
        try:
            self.assertEqual(data_pages.grammar('Karte von <a href="/de/zone/1">Das Brachland</a>, in Die Sümpfe'),
                             'Karte vom <a href="/de/zone/1">Brachland</a>, in der Sümpfe')
        finally:
            data_pages.LANG = "en"
        self.assertEqual(data_pages.grammar("in Das Brachland"), "in Das Brachland")   # English pages: as is

    def test_the_same_pages_as_english(self):
        english = {}
        data_pages.build(self.data, LINKS, lambda path, *page, index=True: english.update({path: index}))
        self.assertEqual(sorted(english), sorted(self.pages))

    def test_search_index_has_german_and_english_names(self):
        data_pages.LANG = "de"
        try:
            index = {(name, path) for name, path, _, _ in data_pages.search_index(self.data)}
        finally:
            data_pages.LANG = "en"
        self.assertIn(("Großes Bärenfleisch", "/de/item/3730"), index)
        self.assertIn(("Big Bear Meat", "/de/item/3730"), index)        # the English name finds it too
        self.assertIn(("Eschental", "/de/zone/1440"), index)
        self.assertIn(("Eschentalbär", "/de/mob/3809"), index)


class LayoutLanguageTests(unittest.TestCase):
    def test_alternates_and_switch(self):
        build = site_build()
        page = build.layout("T", "D", "/item/3730", "<p>x</p>")
        self.assertIn('<html lang="en">', page)
        self.assertIn('<link rel="alternate" hreflang="de" href="https://wowgoldscout.com/de/item/3730">', page)
        self.assertIn('<link rel="alternate" hreflang="x-default" href="https://wowgoldscout.com/item/3730">', page)
        self.assertIn('<a class="lang-switch" href="/de/item/3730" hreflang="de" lang="de">Deutsch</a>', page)
        german = build.layout("T", "D", "/de/item/3730", "<p>x</p>", lang="de")
        self.assertIn('<html lang="de">', german)
        self.assertIn('<link rel="canonical" href="https://wowgoldscout.com/de/item/3730">', german)
        self.assertIn('<a class="lang-switch" href="/item/3730" hreflang="en" lang="en">English</a>', german)
        self.assertIn('<a href="/de/farms">Farmen nach Stufe</a>', german)
        self.assertIn("Gegenstände, Gegner und Gebiete suchen", german)
        # English-only pages have no German version to point to.
        english_only = build.layout("Elsewhere", "D", "/not-translated", "<p>x</p>")   # no German version
        self.assertNotIn("hreflang", english_only)
        self.assertNotIn('class="lang-switch"', english_only)

    def test_scripts_know_german(self):
        for name in ("prices.js", "search.js", "champions.js"):
            with self.subTest(name):
                script = (ROOT / "site" / name).read_text(encoding="utf-8")
                self.assertIn('document.documentElement.lang === "de"', script)
                self.assertNotIn("innerHTML", script)
        self.assertIn('"/search-de.json"', (ROOT / "site" / "search.js").read_text(encoding="utf-8"))


class LegendTests(unittest.TestCase):
    def test_no_doubled_percent_signs(self):
        # The legend isn't %-formatted, so "%%" would show as is (it did, 2026-11-15).
        self.assertIn("95% likely", data_pages.legend())
        self.assertNotIn("%%", data_pages.legend())


class DataWantedTests(unittest.TestCase):
    """Phase 2: show where the data is thin, and ask for it on thin pages."""

    def setUp(self):
        self.data = dataset()   # Ashenvale Bear 20 kills (21-22), Laughing Sister 10 kills (24-25)

    def test_thin_pages_say_how_far_from_solid(self):
        _, _, body = data_pages.mob_page(self.data, 3809, LINKS)
        self.assertIn("Ashenvale Bear has 20 kills recorded so far, so the ranges are wide; 30 more and its rates "
                      "are solid.", body)
        self.assertIn('href="/data-wanted"', body)
        _, _, body = data_pages.item_page(self.data, 3730, LINKS)
        self.assertIn("Its best source, Ashenvale Bear, has 20 kills", body)

    def test_solid_pages_dont_ask(self):
        self.data.mobs[3809]["k"] = 50
        _, _, body = data_pages.mob_page(self.data, 3809, LINKS)
        self.assertNotIn("recorded so far", body)
        self.assertIn('href="/data-wanted"', body)

    def test_names_in_the_ask_are_escaped(self):
        _, _, body = data_pages.mob_page(self.data, 4054, LINKS)
        self.assertIn("Laughing Sister &amp; Co&#x27;s has 10 kills", body)

    def test_coverage_page(self):
        pages = {}

        def write(path, *page, index=True):
            pages[path] = page
        paths = data_pages.build(self.data, LINKS, write)
        self.assertIn("/data-wanted", paths)
        title, _, body = pages["data-wanted.html"]
        self.assertEqual(title, "Where GoldScout needs drop data (WoW Forever)")
        self.assertIn("33 kills so far, 2 mobs with drop rates, 0 of them with the 50+ kills", body)
        self.assertIn('<a href="/farms/levels-21-30">Levels 21-30</a></td><td class=num>2</td><td class=num>30</td>'
                      '<td class=num>1 <span class=range>50%</span>', body)
        self.assertIn("<tr><td>Levels 51-60</td><td class=num>0</td>", body)   # nobody's been: still listed
        self.assertIn("nobody yet", body)
        self.assertIn('<a href="/zone/1440">Ashenvale</a> <span class=small>21-25</span>', body)
        # Almost there: the closest to solid first.
        self.assertLess(body.index("/mob/3809"), body.index("/mob/4054"))
        self.assertIn("20 kills, <b>30 to go</b>", body)
        # Zone goals: Ashenvale's two mobs, neither solid yet.
        self.assertIn("0 of 1 zones complete, 0 past a milestone", body)
        self.assertIn('aria-label="0 of 2 mobs solid"', body)
        self.assertIn("1 more mob to 10%", body)


class ZoneGoalTests(unittest.TestCase):
    """A zone's community goal: every mob recorded there with solid rates, with milestones."""

    def setUp(self):
        self.data = dataset()   # Ashenvale: Ashenvale Bear 20 kills, Laughing Sister 10

    def goal(self, *kills):
        """Ashenvale with mobs of these kill counts."""
        self.data.zones[1440] = []
        for i, k in enumerate(kills):
            npc = 9000 + i
            self.data.mobs[npc] = dict(self.data.mobs[3809], k=k)
            self.data.zones[1440].append(npc)
        return data_pages.zone_goal(self.data, 1440)

    def test_milestones(self):
        goal = self.goal(50, 60, 10, 49, 0, 5, 5, 5, 5, 5)          # 2 of 10 solid: 20%
        self.assertEqual((goal["solid"], goal["total"], goal["reached"], goal["next"], goal["needed"]),
                         (2, 10, 10, 25, 1))                       # 25% of 10 rounds up to 3 mobs
        self.assertEqual(goal["left"][:2], [9003, 9002])           # the closest to solid first
        self.assertEqual(data_pages.goal_next(goal), "1 more mob to 25%")

    def test_nothing_solid_yet(self):
        goal = self.goal(10, 20)
        self.assertEqual((goal["reached"], goal["next"], goal["needed"]), (0, 10, 1))

    def test_complete(self):
        goal = self.goal(50, 80)
        self.assertEqual((goal["reached"], goal["next"], goal["needed"], goal["left"]), (100, None, 0, []))
        self.assertIn("Complete", data_pages.goal_next(goal))

    def test_zone_page_shows_the_goal(self):
        _, _, body = data_pages.zone_page(self.data, 1440, LINKS)
        self.assertIn("<h2>Zone goal</h2>", body)
        self.assertIn("<b>0 of 2</b> so far. Next milestone: 1 more mob to 10%.", body)
        self.assertIn("20 kills, <b>30 to go</b>", body)
        self.assertLess(body.index("Zone goal"), body.index("<h2>Mobs</h2>"))
        # Zone champions come from the server, filled in by champions.js; hidden until then.
        self.assertIn('<div id=zone-champions data-zone="1440" hidden>', body)
        self.assertIn('<script src="/champions.js" defer></script>', body)
        self.data.mobs[3809]["k"] = self.data.mobs[4054]["k"] = 50
        _, _, body = data_pages.zone_page(self.data, 1440, LINKS)
        self.assertIn("<b>Goal reached:</b> every mob players have recorded in Ashenvale", body)
        self.assertNotIn("Closest to solid", body)


class FaqTests(unittest.TestCase):
    def test_every_question_is_on_the_page_and_in_the_structured_data(self):
        build = site_build()
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
