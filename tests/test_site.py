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
        self.assertIn('href="/reagent/3730"', reagents)
        self.assertIn("40%", reagents)                     # 8 of 20 kills
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

    def test_reagent_pages_and_farms(self):
        data = dataset()
        pages = {}
        paths = data_pages.build(data, LINKS, lambda path, *page: pages.__setitem__(path, page))
        self.assertIn("/reagent/3730", paths)
        self.assertNotIn("/reagent/14728", paths)           # gear isn't a reagent page
        _, _, reagent = pages["reagent/3730.html"]
        self.assertLess(reagent.index("Ashenvale Bear"), reagent.index("Laughing"))   # 40% before 20%
        _, _, farms = pages["farms.html"]
        self.assertIn("Levels 21-30", farms)

    def test_breadcrumbs_and_structured_data(self):
        data = dataset()
        _, _, body = data_pages.mob_page(data, 4054, LINKS)
        script = re.search(r'<script type="application/ld\+json">(.*?)</script>', body).group(1)
        crumbs = json.loads(script)
        self.assertEqual(crumbs["@type"], "BreadcrumbList")
        self.assertEqual([c["name"] for c in crumbs["itemListElement"]],
                         ["Home", "Farms by level", "Levels 21-30", "Laughing Sister & Co's"])
        self.assertEqual(crumbs["itemListElement"][2]["item"], "https://wowgoldscout.com/farms#levels-21-30")
        _, _, farms = data_pages.farms_page(data, LINKS)
        self.assertIn('id="levels-21-30"', farms)       # the breadcrumb's anchor exists

    def test_summaries_and_descriptions(self):
        data = dataset()
        _, description, body = data_pages.mob_page(data, 3809, LINKS)
        self.assertIn("Ashenvale Bear is a level 21-22 mob in Ashenvale in WoW Forever. GoldScout players have "
                      "recorded 20 kills. Its most common crafting reagent is Big Bear Meat (40% of kills).", body)
        self.assertIn("Big Bear Meat 40%", description)
        _, description, body = data_pages.reagent_page(data, 3730, LINKS)
        self.assertIn("looted it from 2 mobs; the most reliable is Ashenvale Bear (level 21-22, Ashenvale), "
                      "which drops it on 40% of kills.", body)
        self.assertIn("and 1 other mob in", description)
        self.assertIn('href="/reagent/3702"', body)       # other reagents the same mobs drop

    def test_zone_pages_and_links(self):
        data = dataset()
        pages = {}
        paths = data_pages.build(data, LINKS, lambda path, *page: pages.__setitem__(path, page))
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
        data_pages.build(data, LINKS, lambda path, *page: pages.__setitem__(path, page))
        _, _, mob = pages["mob/3809.html"]
        self.assertIn('id="prices-bar"', mob)
        self.assertIn('data-price="3730"', mob)
        self.assertIn('data-value="3730:0.4"', mob)            # 8 of 20 kills, stacks of 1
        self.assertIn("Blizzard Entertainment Game Data API", mob)
        _, _, farms = pages["farms.html"]
        self.assertIn("<table class=by-value>", farms)
        self.assertIn("Gold per kill", farms)
        _, _, reagent = pages["reagent/3730.html"]
        self.assertIn('data-qty="3730"', reagent)
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
        page = build.layout("t", "d", "/x", "<p>body</p>")
        self.assertIn('<script src="/prices.js" defer></script>', page)

    def test_without_item_details_everything_is_listed(self):
        v3 = "\n".join(line for line in V4.splitlines() if not line.startswith("@q"))
        data = dataset(v3.replace("export 4^", "export 3^"))
        _, _, body = data_pages.mob_page(data, 3809, LINKS)
        self.assertIn("<h2>Drops</h2>", body)
        self.assertIn("Torn Bear Pelt", body)


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
