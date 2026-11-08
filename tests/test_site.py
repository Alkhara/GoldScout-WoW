"""The website's data pages: built from merged exports, with item kinds from
version 4 @q lines, names escaped, gray items hidden."""
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
        self.assertIn("Laughing Sister &amp; Co&#x27;s", body)
        self.assertNotIn("Co's", body)

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

    def test_without_item_details_everything_is_listed(self):
        v3 = "\n".join(line for line in V4.splitlines() if not line.startswith("@q"))
        data = dataset(v3.replace("export 4^", "export 3^"))
        _, _, body = data_pages.mob_page(data, 3809, LINKS)
        self.assertIn("<h2>Drops</h2>", body)
        self.assertIn("Torn Bear Pelt", body)


if __name__ == "__main__":
    unittest.main()
