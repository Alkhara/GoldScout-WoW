"""The gold guides' written farm notes: fact sheets, the checker that keeps a note to its facts, the weekly
writer (with a stand-in for Claude) and the guide pages showing them."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "site"))
sys.path.insert(0, str(ROOT / "tests"))

import farm_notes  # noqa: E402
import guides  # noqa: E402
import write_farm_notes  # noqa: E402
from test_guides import LINKS, PRICES, dataset  # noqa: E402

GOOD = ("Coyotes roam Westfall at levels 10-11, and every one you kill has a fair shot at Coyote Meat for the "
        "cooks on your auction house. Work the area around 52.5, 47.5 where players loot them most, and pick up "
        "the Ruined Leather Scraps too. Press Hunt in GoldScout to mark them and shade the hunting area on your map.")


class FactTests(unittest.TestCase):
    def setUp(self):
        self.data = dataset()
        self.coyote = guides.farms(self.data, PRICES)[0]
        self.sheet = farm_notes.facts(self.data, self.coyote)
        self.known = farm_notes.known_name_words(self.data)

    def test_fact_sheet(self):
        self.assertEqual(farm_notes.key(self.coyote), "1109:2673")
        self.assertEqual((self.sheet["mob"], self.sheet["item"], self.sheet["zone"], self.sheet["levels"]),
                         ("Coyote", "Coyote Meat", "Westfall", "10-11"))
        self.assertEqual(self.sheet["other_drops"], ["Ruined Leather Scraps"])
        self.assertTrue(self.sheet["item_is_crafting_reagent"])

    def checked(self, text, sheet=None):
        sheet = dict(sheet or self.sheet, busiest_spot="52.5, 47.5", other_spots=["52.5, 47.5"])
        return farm_notes.check(text, sheet, self.known)

    def test_a_note_keeping_to_its_facts_passes(self):
        self.assertEqual(self.checked(GOOD), [])

    def test_numbers_and_prices_not_in_the_facts(self):
        self.assertTrue(any("the number 12" in p for p in self.checked(GOOD.replace("10-11", "10-12"))))
        problems = self.checked(GOOD.replace("fair shot", "40% chance"))
        self.assertTrue(any("percentages" in p for p in problems))
        self.assertTrue(any("prices" in p for p in self.checked(GOOD.replace("the cooks", "a 5g sale for the cooks"))))

    def test_names_not_in_the_facts(self):
        problems = self.checked(GOOD.replace("Ruined Leather Scraps", "Big Bear Meat"))
        self.assertTrue(any("'Bear'" in p for p in problems), problems)
        # An ordinary word may start a sentence; a name from elsewhere in the data may not.
        self.assertEqual(self.checked(GOOD.replace("Press Hunt", "Then press Hunt")), [])
        problems = self.checked(GOOD + " Ashenvale is close by.")
        self.assertTrue(any("'Ashenvale'" in p for p in problems), problems)

    def test_plurals_and_possessives_of_allowed_names(self):
        text = GOOD.replace("Press Hunt in GoldScout", "Kill the Coyotes and press Hunt in GoldScout's window")
        self.assertEqual(self.checked(text), [])

    def test_claims_about_the_game(self):
        problems = self.checked(GOOD.replace("roam Westfall", "respawn quickly in Westfall"))
        self.assertTrue(any("respawn" in p for p in problems))

    def test_length(self):
        self.assertTrue(any("words" in p for p in self.checked("Kill Coyotes in Westfall.")))

    def test_shown_only_while_it_matches_the_current_facts(self):
        sheet = farm_notes.facts(self.data, self.coyote)
        text = GOOD.replace("Work the area around 52.5, 47.5 where players loot them most, and pick",
                            "Pick").replace("Pick up the", "Pick up the")
        self.assertEqual(farm_notes.check(text, sheet, self.known), [])
        notes = {"1109:2673": {"text": text, "written": "2026-11-18"}}
        self.assertEqual(farm_notes.note_for(self.data, self.coyote, notes, self.known), text)
        self.data.mobs[1109]["lmax"] = 13                    # the mob's levels changed: "10-11" is stale
        self.assertIsNone(farm_notes.note_for(self.data, self.coyote, notes, self.known))
        self.assertIsNone(farm_notes.note_for(self.data, self.coyote, {}, self.known))


class FakeClient:
    """Answers each request with the next note in line, recording what it was asked."""
    def __init__(self, *notes, refuse=False):
        self.notes, self.refuse, self.asked = list(notes), refuse, []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **request):
        self.asked.append(request)
        if self.refuse:
            return SimpleNamespace(stop_reason="refusal", content=[])
        text = json.dumps({"note": self.notes.pop(0)})
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=text)])


class WriterTests(unittest.TestCase):
    def setUp(self):
        self.data = dataset()
        self.coyote = guides.farms(self.data, PRICES)[0]
        self.sheet = dict(farm_notes.facts(self.data, self.coyote), busiest_spot="52.5, 47.5",
                          other_spots=["52.5, 47.5"])
        self.known = farm_notes.known_name_words(self.data)

    def test_a_good_note_first_time(self):
        client = FakeClient(GOOD)
        self.assertEqual(write_farm_notes.write_note(client, self.sheet, self.known), (GOOD, []))
        request = client.asked[0]
        self.assertEqual(request["model"], "claude-opus-5-5")
        self.assertEqual(request["fallbacks"], "default")
        self.assertIn('"mob": "Coyote"', request["messages"][0]["content"])

    def test_a_broken_note_gets_one_retry_with_its_problems(self):
        client = FakeClient(GOOD.replace("fair shot", "40% chance"), GOOD)
        self.assertEqual(write_farm_notes.write_note(client, self.sheet, self.known), (GOOD, []))
        self.assertIn("percentages", client.asked[1]["messages"][0]["content"])
        client = FakeClient(GOOD + " They respawn fast.", GOOD + " They respawn fast.")
        note, problems = write_farm_notes.write_note(client, self.sheet, self.known)
        self.assertIsNone(note)
        self.assertTrue(problems)

    def test_a_refusal_writes_nothing(self):
        self.assertEqual(write_farm_notes.write_note(FakeClient(refuse=True), self.sheet, self.known),
                         (None, ["declined"]))

    def test_unnamed_mobs_get_no_note(self):
        market = {"prices": PRICES}
        self.data.mobs[1109]["names"] = {}
        found = write_farm_notes.farms_to_note(self.data, [market])
        self.assertNotIn("1109:2673", found)
        self.assertIn("3809:3702", found)


class PageTests(unittest.TestCase):
    def test_the_guide_shows_a_note_that_still_matches(self):
        data = dataset()
        coyote = guides.farms(data, PRICES)[0]
        text = farm_notes.facts(data, coyote)
        note = ("Coyotes in Westfall at levels 10-11 are a steady source of Coyote Meat, a crafting reagent cooks "
                "keep buying. Pick up the Ruined Leather Scraps they drop as well, and press Hunt in GoldScout to "
                "mark every Coyote around you and shade the hunting area on your world map.")
        self.assertEqual(farm_notes.check(note, text, farm_notes.known_name_words(data)), [])
        market = {"region": "us", "house": 113, "ruleset": "PvP", "faction": "Horde", "snapshot": 1794986707,
                  "prices": PRICES}
        pages = {}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "notes.json"
            farm_notes.save({"1109:2673": {"text": note, "written": "2026-11-18"},
                             "3809:3702": {"text": "Kill bears for 5g an hour.", "written": "2026-11-18"}}, path)
            guides.build(data, LINKS, lambda p, t, d, b, index=True: pages.__setitem__(p, b), [market], path)
        body = pages["guides/us/pvp-horde.html"]
        self.assertIn('<p class=guide-note>Coyotes in Westfall', body)
        self.assertNotIn("5g an hour", body)                 # the bear's note breaks the rules: not shown


if __name__ == "__main__":
    unittest.main()
