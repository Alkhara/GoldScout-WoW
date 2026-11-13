"""Farm tab rules: runs the addon's real Core, Data, Community, Learn and Engine
code in Lua 5.1 (via lupa) against a fake item catalog and auction house, and
checks which rows the Farm tab shows. Every filtering rule lives here so later
changes can't quietly bring junk back.

Skipped when lupa isn't installed:  pip install lupa
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

try:
    from lupa import lua51
except ImportError:  # pragma: no cover
    lua51 = None

# A fake client: just enough of the WoW API for the files above to load and
# for Engine:Farms() to run.
CLIENT = r"""
local ns = ...
Enum = { LootSlotType = { Item = 1 }, ItemClass = { Tradegoods = 7, Gem = 3 }, ItemQuality = { Poor = 0 } }
FAKE = { level = 25, class = "ROGUE", items = {}, prices = {}, maps = { [1440] = "Ashenvale" } }
local frame = { scripts = {} }
function frame:RegisterEvent() end
function frame:UnregisterEvent() end
function frame:SetScript(name, fn) self.scripts[name] = fn end
CreateFrame = function() return frame end
FAKE.frame = frame
C_Timer = { After = function(_, fn) fn() end }
time = function() return 1000 end
GetTime = function() return 1000 end
print = function() end
date = function() return "" end
strsplit = function(sep, text)
  local parts = {}
  for part in (text .. sep):gmatch("(.-)%" .. sep) do parts[#parts + 1] = part end
  return unpack(parts)
end
geterrorhandler = function() return function() end end
seterrorhandler = function(fn) FAKE.errorhandler = fn end
debugstack = function() return FAKE.stack or "" end
UnitLevel = function() return FAKE.level end
UnitClass = function() return "Rogue", FAKE.class end
UnitFactionGroup = function() return "Horde" end
GetRealmName = function() return "Realm" end
UnitName = function() return "Mob" end
C_Map = { GetMapInfo = function(id) return FAKE.maps[id] and { name = FAKE.maps[id] } end }
-- item = { name, quality, ilvl, class, subclass, bind, reagent, spell, sell }
local function Item(id) return FAKE.items[id] end
C_Item = {
  GetItemInfo = function(id)
    local i = Item(id)
    if not i then return nil end
    return i.name, "|Hitem:" .. id .. "|h", i.quality or 1, i.ilvl or 20, 0, "", "", 20, "", 0, i.sell or 5,
      i.class or 7, i.subclass or 0, i.bind or 0, 0, nil, i.reagent
  end,
  GetItemInfoInstant = function(id)
    local i = Item(id)
    if not i then return nil end
    return id, "", "", "", 0, i.class or 7, i.subclass or 0
  end,
  GetItemSpell = function(id) local i = Item(id); if i and i.spell then return "Use", 1 end end,
  GetItemQualityByID = function(id) local i = Item(id); return i and (i.quality or 1) end,
  GetItemNameByID = function(id) local i = Item(id); return i and i.name end,
  RequestLoadItemDataByID = function() end,
}
"""

STUBS_AFTER_CORE = r"""
local ns = ...
-- Prices: a fake auction house (copper per unit).
ns.Prices = {
  Get = function(_, id) local p = FAKE.prices[id]; if p then return p, 50, 60 end end,
  Market = function() local items = {}; for id, p in pairs(FAKE.prices) do items[id] = { p = p } end; return { items = items } end,
  ItemIDs = function() local ids = {}; for id in pairs(FAKE.prices) do ids[id] = true end; return ids end,
}
ns.Professions = { Skills = function() return {} end }
"""


@unittest.skipIf(lua51 is None, "lupa is not installed")
class FarmRulesTests(unittest.TestCase):
    def setUp(self):
        self.lua = lua51.LuaRuntime(unpack_returned_tuples=True)
        self.ns = self.lua.table()
        self.run_lua(CLIENT)
        for name in ("Locale.lua", "Core.lua", "Data.lua", "Data_Community.lua", "Community.lua"):
            self.run_file(name)
        self.run_lua(STUBS_AFTER_CORE)
        for name in ("Learn.lua", "Engine.lua"):
            self.run_file(name)
        self.fake = self.lua.globals().FAKE
        self.ns.COMMUNITY = self.lua.table()
        self.ns.COMMUNITY_FISH = self.lua.table()   # not the shipped data
        self.ns.COMMUNITY_CRAFTED = self.lua.table()
        # Load saved data as the game would.
        self.lua.globals().GoldScoutDB = self.lua.table()
        self.lua.globals().GoldScoutCharDB = self.lua.table()
        self.fake.frame.scripts["OnEvent"](None, "ADDON_LOADED", "GoldScout")
        self.settings = self.ns.db.settings

    def run_lua(self, code):
        self.lua.execute("return loadstring(...)", code)(self.ns)

    def run_file(self, name):
        source = (ROOT / "GoldScout" / name).read_text(encoding="utf-8")
        self.lua.execute("return loadstring(...)", source)("GoldScout", self.ns)

    def item(self, item_id, price=10000, **fields):
        fields.setdefault("name", "Item %d" % item_id)
        fields.setdefault("reagent", True)
        if "class_" in fields:
            fields["class"] = fields.pop("class_")
        self.fake["items"][item_id] = self.lua.table_from(fields)
        if price:
            self.fake.prices[item_id] = price

    def drops(self, npc, kills, items, name="Mob", levels=(24, 25)):
        entry = self.lua.eval("{ k = %d, p = 0, lmin = %d, lmax = %d, m = 1440, sx = 0.5, sy = 0.5, c = 1, i = {}, pi = {} }"
                              % ((kills,) + tuple(levels)))
        entry.n = name
        for item_id, times in items.items():
            entry.i[item_id] = self.lua.table_from({"d": times, "q": times})
        self.ns.db.drops[npc] = entry

    def rows(self):
        farms = self.ns.Engine.Farms(self.ns.Engine)
        return {(row.kind, row.item): row for row in farms.values()}

    def kinds(self, item_id):
        return sorted(kind for kind, item in self.rows() if item == item_id)

    # -- Market rows ---------------------------------------------------------
    def test_crafting_reagent_on_the_ah_is_a_market_row(self):
        self.item(5000, ilvl=25)
        self.assertEqual(self.kinds(5000), ["Market"])

    def test_market_leaves_out_non_reagents(self):
        self.item(5001, ilvl=25, quality=0)                           # gray
        self.item(5002, ilvl=25, class_=0, reagent=False, spell=True)  # food
        self.item(5003, ilvl=25, reagent=False)                        # trade good no recipe uses
        self.item(5004, ilvl=25, spell=True)                           # crate with a Use: effect
        self.item(5005, ilvl=25, bind=1)                               # soulbound
        self.item(2320, ilvl=25)                                       # Coarse Thread: sold by vendors
        for item_id in (5001, 5002, 5003, 5004, 5005, 2320):
            with self.subTest(item_id):
                self.assertEqual(self.kinds(item_id), [])

    def test_market_leaves_out_crafted_items(self):
        self.item(5010, ilvl=25)
        self.item(5011, ilvl=25)
        self.ns.db.crafted[5010] = True
        self.ns.COMMUNITY_CRAFTED[5011] = True
        self.assertEqual((self.kinds(5010), self.kinds(5011)), ([], []))

    def test_gems_need_rare_drops(self):
        self.item(1206, ilvl=25, name="Moss Agate")
        self.assertEqual(self.kinds(1206), [])
        self.settings.showRareDrops = True
        self.assertEqual(self.kinds(1206), ["Market"])

    def test_market_level_window(self):
        self.item(5020, ilvl=33)   # 8 above level 25: shown, marked above
        self.item(5021, ilvl=40)   # 15 above: hidden
        self.item(5022, ilvl=10)   # 15 below: shown (low-level materials can still pay best)
        rows = self.rows()
        self.assertTrue(rows[("Market", 5020)].above)
        self.assertNotIn(("Market", 5021), rows)
        self.assertIn(("Market", 5022), rows)
        self.assertFalse(rows[("Market", 5022)].above)
        self.settings.showAllLevels = True
        self.assertIn(("Market", 5021), self.rows())

    def test_low_level_drops_stay_listed_and_rank_by_gold_per_hour(self):
        self.fake.level = 45
        self.item(2673, price=30000, ilvl=20, name="Crawler Meat")
        self.drops(3812, kills=40, items={2673: 18}, name="Clattering Crawler", levels=(19, 20))
        self.item(3731, price=30000, ilvl=40, name="Lion Meat")
        self.drops(2384, kills=40, items={3731: 18}, name="Starving Mountain Lion", levels=(44, 45))
        rows = self.rows()
        low, near = rows[("Learned", 2673)], rows[("Learned", 3731)]
        self.assertGreater(low.hour, near.hour)       # same rate and price; low mobs die faster
        self.item(9000, ilvl=55, name="Too high")
        self.drops(9001, kills=40, items={9000: 18}, levels=(55, 56))
        self.assertNotIn(("Learned", 9000), self.rows())   # more than 4 above: still hidden

    def test_known_rates_hides_market_rows(self):
        self.item(5000, ilvl=25)
        self.settings.knownRatesOnly = True
        self.assertEqual(self.kinds(5000), [])

    # -- Learned rows ----------------------------------------------------------
    def test_reagent_drop_is_a_learned_row_with_a_cautious_rate(self):
        self.item(3730, price=10000, ilvl=22, name="Big Bear Meat")
        self.drops(3809, kills=10, items={3730: 4})
        row = self.rows()[("Learned", 3730)]
        self.assertAlmostEqual(row.chance, 0.4)
        self.assertEqual(row.confidence.key, "fair")
        self.assertAlmostEqual(row.each, 10000 * 0.95 * 4 / 12)   # drops / (kills + 2)
        self.assertNotIn(("Market", 3730), self.rows())             # covered, no duplicate

    def test_hunting_an_item_marks_every_mob_dropping_it_in_the_zone(self):
        self.item(2673, price=30000, ilvl=12, name="Coyote Meat")
        self.drops(833, kills=40, items={2673: 16}, name="Coyote Packleader", levels=(11, 12))
        self.drops(1109, kills=40, items={2673: 12}, name="Coyote", levels=(10, 11))
        self.drops(1110, kills=40, items={2673: 12}, name="Far Coyote", levels=(10, 11))
        self.ns.db.drops[1110].m = 1411                          # another zone: not marked
        farms = self.ns.Engine.Farms(self.ns.Engine)
        hunts = {row.source: row.hunt for row in farms.values() if row.item == 2673}
        best = hunts["Coyote Packleader"]
        self.assertEqual(sorted(best.npcs.keys()), [833, 1109])
        self.assertEqual(best.label, "Coyote Packleader, Coyote")
        self.assertEqual(best.key, "Learned:833:2673")          # its own key: hunt history stays per farm
        self.assertEqual(sorted(hunts["Coyote"].npcs.keys()), [833, 1109])
        self.assertEqual(sorted(hunts["Far Coyote"].npcs.keys()), [1110])

    def test_learned_leaves_out_junk(self):
        self.item(4001, ilvl=22, quality=0)                        # gray
        self.item(4002, ilvl=22, class_=0, reagent=False, spell=True)  # food/scroll
        self.item(11407, ilvl=22, reagent=False, name="Torn Bear Pelt")
        self.item(2592, ilvl=22, name="Wool Cloth")                # has its own cloth rows
        self.drops(3809, kills=10, items={4001: 3, 4002: 3, 11407: 5, 2592: 2})
        rows = self.rows()
        for item_id in (4001, 4002, 11407, 2592):
            with self.subTest(item_id):
                self.assertNotIn(("Learned", item_id), rows)

    def test_gear_recipes_and_gems_need_rare_drops(self):
        self.item(14728, ilvl=22, class_=4, reagent=False, name="War Paint Shoulder Pads")
        self.item(250182, ilvl=22, class_=9, reagent=False, name="Recipe: Bear Brisket")
        self.item(1206, ilvl=22, name="Moss Agate")
        self.drops(3809, kills=10, items={14728: 1, 250182: 1, 1206: 1})
        hidden = self.rows()
        self.settings.showRareDrops = True
        shown = self.rows()
        for item_id in (14728, 250182, 1206):
            with self.subTest(item_id):
                self.assertNotIn(("Learned", item_id), hidden)
                self.assertIn(("Learned", item_id), shown)

    def test_confidence_tiers(self):
        tiers = [self.ns.Engine.Confidence(n).key for n in (1, 4, 5, 14, 15, 49, 50, 500)]
        self.assertEqual(tiers, ["low", "low", "fair", "fair", "good", "good", "high", "high"])

    # -- Cloth -------------------------------------------------------------------
    def test_cloth_rows_only_on_request(self):
        self.item(2592, ilvl=15, name="Wool Cloth")
        self.assertEqual(self.kinds(2592), [])
        self.settings.showCloth = True
        self.assertEqual(self.kinds(2592), ["Cloth"])


@unittest.skipIf(lua51 is None, "lupa is not installed")
class ErrorLogTests(FarmRulesTests.__bases__[0]):
    def setUp(self):
        FarmRulesTests.setUp(self)

    run_lua = FarmRulesTests.run_lua
    run_file = FarmRulesTests.run_file

    def test_goldscout_errors_are_recorded_once_with_counts(self):
        handler = self.fake.errorhandler
        self.fake.stack = "Interface/AddOns/GoldScout/UI.lua:120: in function"
        handler("Interface/AddOns/GoldScout/UI.lua:120: attempt to index nil")
        handler("Interface/AddOns/GoldScout/UI.lua:120: attempt to index nil")
        self.fake.stack = "Interface/AddOns/OtherAddon/x.lua:1"
        handler("Interface/AddOns/OtherAddon/x.lua:1: boom")      # not ours: ignored
        errors = self.ns.db.errors
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[1].n, 2)
        self.assertIn("attempt to index nil", errors[1].m)

    def test_other_addons_errors_are_not_recorded_because_goldscout_caught_them(self):
        # Real stacks: Core.lua's handler is on the stack whenever it runs, so
        # only the frames below it may decide whose error it is.
        self.lua.execute("FAKE.stack = nil; debugstack = function(start) return debug.traceback('', start + 1) end")
        source = (ROOT / "GoldScout" / "Core.lua").read_text(encoding="utf-8")
        self.lua.execute("return loadstring(...)", source, "@Interface/AddOns/GoldScout/Core.lua")("GoldScout", self.ns)
        handler = self.fake.errorhandler

        def fail_in(path, message):
            code = "local handler, message = ...; handler(message)"
            self.lua.execute("return loadstring(...)", code, "@Interface/AddOns/" + path)(handler, message)

        fail_in("Questie/Modules/Auras.lua", "GetAuraDataByIndex(): Auras cannot be accessed when secret")
        self.assertEqual(len(self.ns.db.errors), 0)
        fail_in("GoldScout/UI.lua", "attempt to call a nil value")     # the message alone doesn't name GoldScout
        self.assertEqual(len(self.ns.db.errors), 1)
        self.assertIn("GoldScout/UI.lua", self.ns.db.errors[1].s)
        self.assertNotIn("GoldScout/Core.lua", self.ns.db.errors[1].s)

    def test_auction_house_scans_are_manual_after_the_settings_upgrade(self):
        self.assertFalse(self.ns.db.settings.autoScan)                # new players
        self.assertEqual(self.ns.db.schema, self.ns.SCHEMA)
        self.assertTrue(self.ns.db.settings.minimap)
        saved = self.lua.eval("{ settings = { autoScan = true, killsPerHour = 90 } }")   # an existing player
        self.lua.globals().GoldScoutDB = saved
        self.fake.frame.scripts["OnEvent"](None, "ADDON_LOADED", "GoldScout")
        self.assertFalse(saved.settings.autoScan)
        self.assertEqual(saved.settings.killsPerHour, 90)              # other settings kept
        saved.settings.autoScan = True                                 # turned back on by choice...
        self.fake.frame.scripts["OnEvent"](None, "ADDON_LOADED", "GoldScout")
        self.assertTrue(saved.settings.autoScan)                       # ...stays on

    # -- The Farm tab's filter row (Core.lua ns.FitRow) ---------------------------
    def fit(self, widths, room):
        gap, cap = self.ns.FitRow(self.lua.table(*widths), 26, room, 14, 4)
        used = sum(26 + (min(w, cap) if cap is not None else w) for w in widths) + gap * (len(widths) - 1)
        return gap, cap, used

    def test_filter_row_keeps_full_gaps_when_there_is_room(self):
        self.assertEqual(self.fit([50, 60, 45, 60, 55], 500)[:2], (14, None))

    def test_filter_row_squeezes_gaps_before_cutting_labels(self):
        gap, cap, used = self.fit([50, 60, 45, 60, 55], 420)
        self.assertEqual(cap, None)
        self.assertLess(gap, 14)
        self.assertLessEqual(used, 420)

    def test_filter_row_cuts_only_the_longest_labels_when_it_must(self):
        gap, cap, used = self.fit([40, 120, 45, 110, 50], 400)
        self.assertEqual(gap, 4)
        self.assertGreater(cap, 50)                                    # short labels stay whole
        self.assertLess(cap, 110)
        self.assertLessEqual(used, 400)

    # -- Saved data versions (Core.lua ns.UpgradeSavedData) ----------------------
    def load_saved(self, saved, char=None):
        self.lua.globals().GoldScoutDB = saved
        self.lua.globals().GoldScoutCharDB = char
        self.fake.frame.scripts["OnEvent"](None, "ADDON_LOADED", "GoldScout")
        return self.lua.globals().GoldScoutDB

    def test_new_saved_data_starts_current(self):
        db = self.load_saved(None)
        self.assertEqual((db.schema, self.ns.savedData), (self.ns.SCHEMA, "fresh"))
        self.assertEqual(self.lua.globals().GoldScoutCharDB.schema, self.ns.CHAR_SCHEMA)
        self.assertIsNone(db.seenIntro)                                # new players get the welcome

    def test_data_from_before_schemas_is_upgraded_once(self):
        db = self.load_saved(self.lua.eval("{ settingsVersion = 2, settings = { autoScan = true } }"))
        self.assertEqual((db.schema, db.settingsVersion), (self.ns.SCHEMA, None))   # the old marker is replaced
        self.assertTrue(db.settings.autoScan)                          # version 2's step already ran once
        self.assertTrue(db.seenIntro)                                  # existing players skip the welcome
        self.assertEqual(self.ns.savedData, "upgraded")
        self.load_saved(db)
        self.assertEqual(self.ns.savedData, "current")                 # and it happens once

    def test_newer_saved_data_is_left_alone(self):
        db = self.load_saved(self.lua.eval("{ schema = 99, settings = {}, futureThing = { kept = true } }"))
        self.assertEqual((db.schema, self.ns.savedData), (99, "newer"))
        self.assertTrue(db.futureThing.kept)

    def test_a_failing_step_stops_and_is_retried(self):
        upgrade = self.ns.UpgradeSavedData
        steps = self.lua.eval("""{
          [2] = function(db) db.two = (db.two or 0) + 1 end,
          [3] = function(db) if not db.ready then error("not yet") end db.three = true end,
        }""")
        store = self.lua.eval("{ schema = 1 }")
        self.assertEqual(upgrade(store, 3, steps, False), "failed")
        self.assertEqual((store.schema, store.two, store.three), (2, 1, None))
        self.assertTrue(any("version 3 failed" in entry.m for entry in self.ns.db.errors.values()))
        store.ready = True
        self.assertEqual(upgrade(store, 3, steps, False), "upgraded")   # next login: only step 3 runs again
        self.assertEqual((store.schema, store.two, store.three), (3, 1, True))
        self.assertEqual(upgrade(store, 3, steps, False), "current")

    def test_every_version_has_a_step(self):
        for version in range(2, self.ns.SCHEMA + 1):
            self.assertIsNotNone(self.ns.UPGRADES[version], version)

    def test_blocked_actions_are_recorded(self):
        self.fake.frame.scripts["OnEvent"](None, "ADDON_ACTION_BLOCKED", "GoldScout", "HideUIPanel()")
        self.fake.frame.scripts["OnEvent"](None, "ADDON_ACTION_BLOCKED", "OtherAddon", "Foo()")
        messages = [e.m for e in self.ns.db.errors.values()]
        self.assertEqual(messages, ["Blocked action: HideUIPanel()"])


@unittest.skipIf(lua51 is None, "lupa is not installed")
class UnitTooltipTests(unittest.TestCase):
    """The lines GoldScout adds to a mob's tooltip (Hunt.lua)."""
    setUp_farm = FarmRulesTests.setUp
    run_lua, run_file, item, drops = (FarmRulesTests.run_lua, FarmRulesTests.run_file,
                                      FarmRulesTests.item, FarmRulesTests.drops)

    def setUp(self):
        self.setUp_farm()
        self.run_file("Hunt.lua")

    def shared(self, npc, kills, items):
        entry = self.lua.eval("{ k = %d, i = {} }" % kills)
        for item_id, (times, quantity) in items.items():
            entry.i[item_id] = self.lua.table_from({"d": times, "q": quantity})
        self.ns.COMMUNITY[npc] = entry

    def lines(self, npc):
        return list(self.ns.Hunt.UnitLines(self.ns.Hunt, npc).values())

    def test_community_loots_and_average_kill_value(self):
        self.item(5001, price=1000)                          # 950 after the AH cut
        self.item(5002, price=900, sell=7, quality=0)        # gray: its vendor price, whatever it lists for
        self.shared(3000, 10, {5001: (3, 6), 5002: (10, 10)})
        line = self.lines(3000)[-1]
        self.assertIn("Other players have looted 10 of these", line)
        self.assertIn("5|cffc7c7cfs|r 77", line)             # (950 * 6 + 7 * 10) / 10 = 577 copper

    def test_no_value_known_shows_only_the_count(self):
        self.shared(3001, 4, {5999: (1, 1)})                 # an item the game hasn't loaded
        self.assertEqual(self.lines(3001), ["Other players have looted 4 of these."])

    def test_no_community_data_no_line(self):
        self.drops(3002, 5, {})
        self.assertEqual(self.lines(3002), ["You've looted 5 of these."])


if __name__ == "__main__":
    unittest.main()
