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

    def test_count_all_loot_turns_on_once_for_existing_players(self):
        saved = self.lua.eval("{ schema = 3, settings = { allLoot = false } }")   # the old default, saved
        self.lua.globals().GoldScoutDB = saved
        self.fake.frame.scripts["OnEvent"](None, "ADDON_LOADED", "GoldScout")
        self.assertTrue(saved.settings.allLoot)
        saved.settings.allLoot = False                                 # turned off by choice...
        self.fake.frame.scripts["OnEvent"](None, "ADDON_LOADED", "GoldScout")
        self.assertFalse(saved.settings.allLoot)                       # ...stays off

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
class AllLootTests(unittest.TestCase):
    """Count all loot in gold per hour: the By mob view also earns the mob's other loot; an item row notes it
    (for its tooltip and MobFarms) but its gold per hour stays that item's own."""
    setUp = FarmRulesTests.setUp
    run_lua, run_file, item, drops, rows = (FarmRulesTests.run_lua, FarmRulesTests.run_file, FarmRulesTests.item,
                                            FarmRulesTests.drops, FarmRulesTests.rows)

    def mob(self, kills=15):
        self.item(5000, price=10000)                                   # the row's reagent: 9500 after the cut
        self.item(5100, price=0, sell=50, quality=0, reagent=False)    # gray trash: vendor price
        self.item(5101, price=1000, sell=5, reagent=False)             # a non-reagent drop: 950 after the cut
        self.drops(3000, kills, {5000: 2, 5100: kills})
        self.ns.db.drops[3000].i[5101] = self.lua.table_from({"d": 3, "q": 6})

    def row(self):
        return self.rows()[("Learned", 5000)]

    def test_on_by_default(self):
        self.assertTrue(self.ns.db.settings.allLoot)

    def test_off_notes_nothing(self):
        self.mob()
        self.ns.db.settings.allLoot = False
        row = self.row()
        self.assertIsNone(row.otherLoot)
        self.assertGreater(row.hour, 0)

    def test_on_notes_the_other_loot_but_the_item_row_keeps_its_own_gold_per_hour(self):
        self.mob()
        self.ns.db.settings.allLoot = False
        before = self.row()
        self.ns.db.settings.allLoot = True
        row = self.row()
        self.assertAlmostEqual(row.otherLoot, (50 * 15 + 950 * 6) / 15)    # 430 a kill; the reagent isn't counted twice
        self.assertEqual(row.otherLootKills, 15)
        self.assertAlmostEqual(row.each, before.each)
        self.assertAlmostEqual(row.hour, before.hour)

    def test_a_cheap_drop_from_a_mob_with_good_trash_doesnt_top_the_item_list(self):
        # A player's report: a 1% claw from Coyotes topped the list because Coyotes' trash pays well.
        self.item(5002, price=100)                                     # the cheap drop: 95 a kill after the cut
        self.item(5003, price=2000)                                    # a better item elsewhere: 1900
        self.item(5100, price=0, sell=5000, quality=0, reagent=False)  # trash worth 50 silver every kill
        self.drops(3000, 15, {5002: 15, 5100: 15}, name="Coyote")
        self.drops(3001, 15, {5003: 15}, name="Wolf")
        self.ns.db.settings.allLoot = True
        rows = self.rows()
        self.assertGreater(rows[("Learned", 5003)].hour, rows[("Learned", 5002)].hour)
        # By mob, the Coyote's trash still counts: it earns more per kill than the Wolf.
        mobs = {m.npc: m for m in self.ns.Engine.MobFarms(self.ns.Engine, self.ns.Engine.Farms(self.ns.Engine)).values()
                if m.npc in (3000, 3001)}
        self.assertGreater(mobs[3000].each, mobs[3001].each)

    def test_each_item_row_leaves_out_only_its_own_item(self):
        # The mob's loot is valued once per build; each of its rows then takes out its own item.
        self.mob()
        self.item(5001, price=4000)                                    # a second reagent: 3800 after the cut
        self.ns.db.drops[3000].i[5001] = self.lua.table_from({"d": 5, "q": 5})
        self.ns.db.settings.allLoot = True
        rows = self.rows()
        first, second = rows[("Learned", 5000)], rows[("Learned", 5001)]
        self.assertAlmostEqual(first.otherLoot, (50 * 15 + 950 * 6 + 3800 * 5) / 15)
        self.assertAlmostEqual(second.otherLoot, (50 * 15 + 950 * 6) / 15)   # 5000 dropped twice: under the minimum
        self.assertEqual(sorted(p.item for p in first.otherLootParts.values()), [5001, 5100, 5101])
        self.assertEqual(sorted(p.item for p in second.otherLootParts.values()), [5100, 5101])

    def test_item_values_are_only_kept_during_a_build(self):
        self.mob()
        self.ns.db.settings.allLoot = True
        self.rows()
        self.fake.prices[5101] = 3000                                  # a new price after the list was built
        self.assertAlmostEqual(self.ns.LootValue(5101)[0], 3000 * 0.95)
        self.assertIsNone(self.ns.BuildCache())
        self.assertAlmostEqual(self.row().otherLoot, (50 * 15 + 2850 * 6) / 15)

    def test_a_lucky_drop_or_two_doesnt_count(self):
        self.mob()
        self.item(5102, price=200000, reagent=False)                   # a 20g recipe, seen twice
        self.ns.db.drops[3000].i[5102] = self.lua.table_from({"d": 2, "q": 2})
        self.ns.db.settings.allLoot = True
        self.assertAlmostEqual(self.row().otherLoot, (50 * 15 + 950 * 6) / 15)

    def test_the_breakdown_lists_the_items_most_valuable_first(self):
        self.mob()
        self.ns.db.settings.allLoot = True
        parts = list(self.row().otherLootParts.values())
        self.assertEqual([(p.item, p.drops) for p in parts], [(5101, 3), (5100, 15)])
        self.assertAlmostEqual(parts[0].value, 950 * 6 / 15)
        self.assertFalse(parts[0].capped)

    def test_a_price_far_above_the_regional_estimate_is_capped(self):
        self.mob()
        # Regional estimate 100 copper: listed at 1000 here, it counts at 3 x 100.
        self.run_lua("local ns = ...; ns.Prices.Bundled = function() return { price = { [5101] = 100 } } end")
        self.ns.db.settings.allLoot = True
        row = self.row()
        self.assertAlmostEqual(row.otherLoot, (50 * 15 + 300 * 0.95 * 6) / 15)
        capped = [p for p in row.otherLootParts.values() if p.item == 5101][0]
        self.assertTrue(capped.capped)

    def test_a_price_near_the_regional_estimate_is_kept(self):
        self.mob()
        self.run_lua("local ns = ...; ns.Prices.Bundled = function() return { price = { [5101] = 400 } } end")
        self.ns.db.settings.allLoot = True
        self.assertAlmostEqual(self.row().otherLoot, (50 * 15 + 950 * 6) / 15)   # 1000 is under 3 x 400

    def test_needs_fifteen_kills_from_you_and_the_community(self):
        self.mob(kills=9)
        self.ns.db.settings.allLoot = True
        self.assertIsNone(self.row().otherLoot)
        shared = self.lua.eval("{ k = 6, i = {} }")
        shared.i[5100] = self.lua.table_from({"d": 6, "q": 6})
        self.ns.COMMUNITY[3000] = shared
        row = self.row()
        self.assertEqual(row.otherLootKills, 15)
        self.assertAlmostEqual(row.otherLoot, (50 * 15 + 950 * 6) / 15)


@unittest.skipIf(lua51 is None, "lupa is not installed")
class FlipTests(unittest.TestCase):
    """The Flip tab: buy on the Blackwater (neutral) auction house, sell on your faction's."""
    setUp = FarmRulesTests.setUp
    run_lua, run_file = FarmRulesTests.run_lua, FarmRulesTests.run_file

    def market(self, neutral, mine, age=60):
        """Both markets' prices ({item: (copper, listed)}) as Prices:GetFor sees them, `age` seconds old."""
        self.run_lua("""
            local ns, neutral, mine, age = ...
            ns.Prices.BlackwaterKey = function() return "Realm-Neutral" end
            local markets = { ["Realm-Neutral"] = neutral, ["Realm-Horde"] = mine }
            ns.Prices.GetFor = function(_, item, key)
              local entry = markets[key] and markets[key][item]
              if entry then return entry[1], entry[2], age end
            end
            ns.Prices.MarketItemIDs = function(_, key)
              local ids = {}
              for item in pairs(markets[key] or {}) do ids[item] = true end
              return ids
            end
        """.replace("local ns, neutral, mine, age = ...", "local ns = ...; local neutral, mine, age = FLIP_N, FLIP_M, FLIP_AGE"))

    def flips(self, neutral, mine, age=60):
        g = self.lua.globals()
        g.FLIP_N = self.lua.table_from({k: self.lua.table_from(list(v)) for k, v in neutral.items()})
        g.FLIP_M = self.lua.table_from({k: self.lua.table_from(list(v)) for k, v in mine.items()})
        g.FLIP_AGE = age
        self.market(neutral, mine, age)
        return self.result()

    def result(self):
        found = self.ns.Engine.Flips(self.ns.Engine)
        rows, reason = found if isinstance(found, tuple) else (found, None)   # lupa unwraps a single return
        return list(rows.values()), reason

    def test_flips_worth_making_best_first(self):
        rows, reason = self.flips(
            {1: (1000, 5), 2: (10000, 2), 3: (1000, 9), 4: (500, 3), 5: (100, 50)},
            {1: (2000, 40), 2: (12000, 7), 3: (1100, 9), 6: (9000, 1), 5: (300, 10)})
        # 1: 1900 - 1000 = 900 (90%). 2: 11400 - 10000 = 1400 (14%: under the 15% margin).
        # 3: 1045 - 1000 = 45 (too little). 4: none listed on yours. 6: none at Blackwater. 5: 185 (185%).
        self.assertIsNone(reason)
        self.assertEqual([row.item for row in rows], [1, 5])
        first = rows[0]
        self.assertAlmostEqual(first.profit, 2000 * 0.95 - 1000)
        self.assertAlmostEqual(first.margin, 0.9)
        self.assertEqual((first.cost, first.sell, first.stock, first.listed), (1000, 2000, 5, 40))

    def test_old_prices_dont_count(self):
        rows, _ = self.flips({1: (1000, 5)}, {1: (2000, 40)}, age=13 * 3600)
        self.assertEqual(rows, [])

    def test_why_there_are_none(self):
        self.assertEqual(self.flips({}, {1: (2000, 40)})[1], "noprices")
        self.run_lua('local ns = ...; ns.Prices.BlackwaterKey = function() return ns.MarketKey() end')
        self.assertEqual(self.result()[1], "neutral")


@unittest.skipIf(lua51 is None, "lupa is not installed")
class MobViewTests(unittest.TestCase):
    """The Farm tab's By mob view: one row per mob, adding up its farms."""
    setUp = FarmRulesTests.setUp
    run_lua, run_file, item, drops, rows = (FarmRulesTests.run_lua, FarmRulesTests.run_file, FarmRulesTests.item,
                                            FarmRulesTests.drops, FarmRulesTests.rows)

    def mobs(self):
        farms = self.ns.Engine.Farms(self.ns.Engine)
        return list(self.ns.Engine.MobFarms(self.ns.Engine, farms).values())

    def two_reagent_mob(self):
        self.item(5000, price=10000)
        self.item(5001, price=4000)
        self.drops(3000, 20, {5000: 4, 5001: 10}, name="Ghoul")

    def test_a_mob_with_several_farms_is_one_row_adding_them_up(self):
        self.two_reagent_mob()
        rows = self.rows()
        first, second = rows[("Learned", 5000)], rows[("Learned", 5001)]
        mobs = [m for m in self.mobs() if m.npc == 3000]
        self.assertEqual(len(mobs), 1)
        mob = mobs[0]
        self.assertEqual((mob.kind, mob.source, mob.mobKey), ("Mob", "Ghoul", "Mob:3000"))
        self.assertEqual(len(mob["items"]), 2)
        self.assertAlmostEqual(mob.each, first.each + second.each)
        self.assertAlmostEqual(mob.hour, first.hour + second.hour)
        self.assertEqual(mob["items"][1].item, max((first, second), key=lambda r: r.hour).item)  # best first
        self.assertEqual(mob.hunt.key, "Mob:3000")
        self.assertNotEqual(mob["items"][1].hunt.key, "Mob:3000")   # its farms keep their own hunts

    def test_a_mob_with_one_farm_is_that_farm(self):
        self.item(5000, price=10000)
        self.drops(3000, 20, {5000: 4})
        mob = [m for m in self.mobs() if m.npc == 3000][0]
        self.assertEqual(mob.kind, "Learned")
        self.assertIsNone(mob["items"])

    def test_market_items_without_a_mob_are_left_out(self):
        self.item(5002, ilvl=25)                                    # a Market row nobody has seen drop
        self.assertEqual([m for m in self.mobs() if m.item == 5002], [])
        self.assertEqual(self.kinds(5002), ["Market"])

    def test_other_loot_counts_once_and_leaves_out_every_farmed_item(self):
        self.two_reagent_mob()
        self.item(5100, price=0, sell=50, quality=0, reagent=False)   # gray trash: 50 a kill
        self.ns.db.drops[3000].i[5100] = self.lua.table_from({"d": 20, "q": 20})
        self.ns.db.settings.allLoot = True
        mob = [m for m in self.mobs() if m.npc == 3000][0]
        self.assertAlmostEqual(mob.otherLoot, 50)
        items = list(mob["items"].values())
        self.assertAlmostEqual(mob.each, sum(item.each for item in items) + 50)   # Each includes it
        self.assertAlmostEqual(mob.hour, mob.each * mob.perHour)
        # The lines under the mob add up to its total: each item's own share plus the other loot.
        other = mob.otherRow
        self.assertEqual((other.kind, other.each), ("OtherLoot", 50))
        self.assertAlmostEqual(sum(item.each * item.perHour for item in items) + other.hour, mob.hour)

    def test_a_one_farm_mob_with_other_loot_is_a_group_too(self):
        self.item(5000, price=10000)
        self.item(5100, price=0, sell=50, quality=0, reagent=False)
        self.drops(3000, 20, {5000: 4, 5100: 20})
        self.ns.db.settings.allLoot = True
        mob = [m for m in self.mobs() if m.npc == 3000][0]
        self.assertEqual((mob.kind, len(mob["items"])), ("Mob", 1))
        self.assertAlmostEqual(mob.otherRow.each, 50)

    kinds = FarmRulesTests.kinds


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


@unittest.skipIf(lua51 is None, "lupa is not installed")
class WantedMobsTests(unittest.TestCase):
    """The Farm tab's Data wanted view (Engine:WantedMobs): mobs whose drop rates still need kills."""
    setUp = FarmRulesTests.setUp
    run_lua, run_file, item, drops = (FarmRulesTests.run_lua, FarmRulesTests.run_file,
                                      FarmRulesTests.item, FarmRulesTests.drops)

    def shared(self, npc, kills, items, levels=(24, 25), map_id=1440):
        entry = self.lua.eval("{ k = %d, p = 0, lmin = %d, lmax = %d, m = %d, i = {}, pi = {} }"
                              % ((kills,) + tuple(levels) + (map_id,)))
        for item_id, times in items.items():
            entry.i[item_id] = self.lua.table_from({"d": times, "q": times})
        self.ns.COMMUNITY[npc] = entry

    def wanted(self):
        rows = self.ns.Engine.WantedMobs(self.ns.Engine)
        return [rows[i] for i in range(1, len(rows) + 1)]

    def test_your_kills_and_other_players_add_up(self):
        self.item(5000)
        self.drops(3000, 12, {5000: 6})
        self.shared(3000, 20, {5000: 9})
        (row,) = self.wanted()
        self.assertEqual((row.kind, row.npc, row.kills, row.needed, row.zone), ("Wanted", 3000, 32, 18, "Ashenvale"))
        self.assertEqual(row.item, 5000)
        self.assertAlmostEqual(row.chance, 15 / 32)
        self.assertEqual(row.hunt.key, "Wanted:3000")
        self.assertTrue(row.hunt.npcs[3000])

    def test_solid_mobs_are_left_out(self):
        self.shared(3000, 50, {})
        self.shared(3001, 49, {})
        self.assertEqual([row.npc for row in self.wanted()], [3001])

    def test_far_above_your_level_needs_all_levels(self):
        self.shared(3000, 10, {}, levels=(28, 29))   # you're 25: 3 above
        self.shared(3001, 10, {}, levels=(27, 28))
        self.assertEqual([row.npc for row in self.wanted()], [3001])
        self.settings.showAllLevels = True
        self.assertEqual(sorted(row.npc for row in self.wanted()), [3000, 3001])

    def test_your_zone_first_then_closest_to_solid(self):
        self.fake.maps[1441] = "Thousand Needles"
        self.shared(3000, 40, {})
        self.shared(3001, 10, {}, map_id=1441)
        self.shared(3002, 45, {})
        self.assertEqual([row.npc for row in self.wanted()], [3002, 3000, 3001])
        self.run_lua("C_Map.GetBestMapForUnit = function() return 1441 end")
        self.assertEqual([row.npc for row in self.wanted()], [3001, 3002, 3000])
        self.assertTrue(self.wanted()[0].here)

    def test_the_hunt_tracks_its_most_common_drop_but_not_vendor_trash(self):
        self.item(5000)
        self.item(5001, quality=0)
        self.shared(3000, 20, {5000: 4, 5001: 15})
        (row,) = self.wanted()
        self.assertEqual(row.item, 5000)
        self.shared(3000, 20, {5001: 15})
        (row,) = self.wanted()
        self.assertIsNone(row.item)
        self.assertIsNone(row.hunt)                  # nothing to track: can't be hunted

    def test_mobs_without_a_known_zone_or_level_are_left_out(self):
        self.shared(3000, 10, {}, map_id=9999)        # a map the game doesn't name
        self.shared(3001, 10, {}, levels=(0, 0))
        self.assertEqual(self.wanted(), [])


@unittest.skipIf(lua51 is None, "lupa is not installed")
class HuntAreaTests(unittest.TestCase):
    """The hunting area a hunt shades on the world map (Engine.HuntArea, Hunt.AreaSquares)."""
    setUp_farm = FarmRulesTests.setUp
    run_lua, run_file, item, drops, rows = (FarmRulesTests.run_lua, FarmRulesTests.run_file,
                                            FarmRulesTests.item, FarmRulesTests.drops, FarmRulesTests.rows)

    def setUp(self):
        self.setUp_farm()
        self.run_file("Hunt.lua")

    def area(self, hunt):
        area = self.ns.Engine.HuntArea(hunt)
        if area is None:
            return None
        return {m: dict(cells.items()) for m, cells in area.items()}

    def shared(self, npc, map_id, cells):
        self.ns.COMMUNITY[npc] = self.lua.eval("{ k = 10, i = {}, m = %d, a = %s }" % (map_id, cells))

    def test_a_mob_hunt_adds_your_loots_to_other_players(self):
        self.item(5000)
        self.drops(3000, 12, {5000: 6})
        self.ns.db.drops[3000].a = self.lua.eval("{ [206] = 3, [300] = 1 }")
        self.shared(3000, 1440, "{ [205] = 20, [206] = 7 }")
        hunt = self.rows()[("Learned", 5000)].hunt
        # 205: 20, 206: 7 + 3, 300: 1 (under a tenth of the busiest square, so left out)
        self.assertEqual(self.area(hunt), {1440: {205: 1.0, 206: 0.5}})

    def test_each_map_keeps_its_own_squares(self):
        self.drops(3000, 5, {})
        self.ns.db.drops[3000].m = 1441
        self.ns.db.drops[3000].a = self.lua.eval("{ [10] = 4 }")
        self.shared(3000, 1440, "{ [205] = 2 }")
        hunt = self.lua.eval("{ npcs = { [3000] = true } }")
        self.assertEqual(self.area(hunt), {1440: {205: 1.0}, 1441: {10: 1.0}})

    def test_a_fishing_hunt_uses_its_catches(self):
        hunt = self.lua.eval("{ npcs = {}, area = { [1440] = { [10] = 4, [11] = 1 } } }")
        self.assertEqual(self.area(hunt), {1440: {10: 1.0, 11: 0.25}})

    def test_nothing_known_no_area(self):
        self.assertIsNone(self.area(self.lua.eval("{ npcs = { [3999] = true } }")))
        self.assertIsNone(self.area(self.lua.eval("{ npcs = {} }")))

    def test_squares_sit_on_the_grid(self):
        squares = self.ns.Hunt.AreaSquares(self.lua.eval("{ [45] = 1 }"))   # row 2, column 5
        square = squares[1]
        self.assertAlmostEqual(square.left, 0.25)
        self.assertAlmostEqual(square.top, 0.10)
        self.assertAlmostEqual(square.size, 0.05)
        self.assertAlmostEqual(square.alpha, 0.55)

    def test_the_outline_runs_around_the_area(self):
        # 45 and 46 side by side, 0 in the map's corner
        squares = self.ns.Hunt.AreaSquares(self.lua.eval("{ [45] = 1, [46] = 0.5, [0] = 0.2 }"))
        edges = {}
        for square in squares.values():
            cell = round(square.top * 20) * 20 + round(square.left * 20)
            edges[cell] = sorted(side for side, on in square.edges.items() if on)
        self.assertEqual(edges, {45: ["bottom", "left", "top"], 46: ["bottom", "right", "top"],
                                 0: ["bottom", "left", "right", "top"]})

    def test_a_hunt_splits_the_hunted_item_from_other_loot_and_coin(self):
        # A player's report: hunting one item, the tracker's loot and gold per hour counted the trash too.
        self.item(5000, price=10000)                                   # the hunted item: 9500 after the cut
        self.item(5100, price=0, sell=50, quality=0, reagent=False)    # gray trash: 50
        self.run_lua("GetMoney = function() return 1300 end")         # 300 copper of coin since the start
        session = self.lua.eval("""{ started = -2600, startMoney = 1000, kills = 4, picks = 0, nodes = 0,
          catches = 0, hits = 2, gained = { [5000] = 2, [5100] = 6 },
          target = { item = 5000, label = "Mob", zone = "Zone", per = "kill" } }""")   # an hour (time() is 1000)
        summary = self.ns.Hunt.Summarize(session)
        self.assertEqual((summary.count, summary.targetValue, summary.otherValue, summary.coin, summary.total),
                         (2, 19000, 300, 300, 19600))
        self.assertAlmostEqual(summary.targetPerHour, 19000)
        self.assertAlmostEqual(summary.perHour, 19600)
        self.assertEqual(summary.value, 19300)                        # all loot, as hunt history keeps it
        session.gained = self.lua.eval("{ [5100] = 6 }")              # nothing of the hunted item yet
        summary = self.ns.Hunt.Summarize(session)
        self.assertEqual((summary.targetValue, summary.otherValue, summary.total), (0, 300, 600))

    # OpenMap's stitched map: zone 1441 sits just right of 1440 on the world, at half its size.
    OPEN_MAP = """{
      WorldFromMap = function(zone, x, y)
        if zone == 1440 then return x * 0.2, y * 0.2 end
        if zone == 1441 then return 0.2 + x * 0.1, y * 0.1 end
      end,
      MapFromWorld = function(zone, u, v)
        if zone == 1440 then return u / 0.2, v / 0.2 end
      end,
    }"""

    def place(self, open_map, zone, canvas_map, left, top, size):
        api = self.lua.eval(self.OPEN_MAP) if open_map else None
        packed = self.lua.eval("function(h, ...) return { h.PlaceSquare(...) } end")
        return list(packed(self.ns.Hunt, api, zone, canvas_map, left, top, size).values())

    def test_squares_on_blizzards_map_stay_on_their_own_zone(self):
        self.assertEqual([round(n, 6) for n in self.place(False, 1440, 1440, 0.25, 0.1, 0.05)], [0.25, 0.1, 0.3, 0.15])
        self.assertEqual(self.place(False, 1441, 1440, 0.25, 0.1, 0.05), [])   # another zone: not drawn

    def test_openmap_places_a_neighbouring_zones_squares_beside_the_map(self):
        left, top, right, bottom = self.place(True, 1441, 1440, 0.5, 0.0, 0.05)
        # 1441's x = 0.5 is world u = 0.25, which is 1.25 across 1440 (past its right edge)
        self.assertAlmostEqual(left, 1.25)
        self.assertAlmostEqual(top, 0.0)
        self.assertAlmostEqual(right - left, 0.025)   # half the size: 1441 is half as big
        self.assertAlmostEqual(bottom - top, 0.025)
        self.assertEqual(self.place(True, 1442, 1440, 0.5, 0.0, 0.05), [])   # a zone OpenMap doesn't have



@unittest.skipIf(lua51 is None, "lupa is not installed")
class ScannerTests(unittest.TestCase):
    """The price scan (Scanner.lua) and Blizzard's Sell tab, which errors when a request goes out while the
    item it holds has no deposit yet: scan requests wait while it's open."""
    setUp_farm = FarmRulesTests.setUp
    run_lua, run_file = FarmRulesTests.run_lua, FarmRulesTests.run_file

    def setUp(self):
        self.setUp_farm()
        self.run_lua("""local ns = ...
          SENT, PRINTED, SELL_SHOWN = 0, {}, false
          C_Timer.NewTicker = function(_, fn) TICK = fn return { Cancel = function() end } end
          C_Timer.After = function() end                     -- no page timeouts here
          wipe = wipe or function(t) for k in pairs(t) do t[k] = nil end return t end
          C_AuctionHouse = { IsThrottledMessageSystemReady = function() return true end,
            SendBrowseQuery = function() SENT = SENT + 1 end, RequestMoreBrowseResults = function() SENT = SENT + 1 end }
          AuctionHouseFrame = { ItemSellFrame = { IsVisible = function() return SELL_SHOWN end } }
          ns.Print = function(text) PRINTED[#PRINTED + 1] = text end""")
        self.run_file("Scanner.lua")
        self.g = self.lua.globals()

    def test_requests_wait_while_the_sell_tab_is_open(self):
        self.g.SELL_SHOWN = True
        self.ns.Scanner.ahOpen = True
        self.assertTrue(self.ns.Scanner.Start(self.ns.Scanner, "test"))
        self.assertEqual(self.g.SENT, 0)                      # the first query waits
        self.g.TICK()
        self.g.TICK()
        self.assertEqual(self.g.SENT, 0)
        self.assertEqual(len(self.g.PRINTED), 1)             # said once
        self.assertIn("Sell tab", self.g.PRINTED[1])
        self.g.SELL_SHOWN = False                            # back to Browse: it carries on
        self.g.TICK()
        self.assertEqual(self.g.SENT, 1)

    def test_no_sell_tab_no_wait(self):
        self.ns.Scanner.ahOpen = True
        self.ns.Scanner.Start(self.ns.Scanner, "test")
        self.assertEqual(self.g.SENT, 1)
        self.assertEqual(len(self.g.PRINTED), 0)


@unittest.skipIf(lua51 is None, "lupa is not installed")
class ContributorRankTests(unittest.TestCase):
    """The minimap tooltip's leaderboard line, from what GoldScout Companion wrote into GoldScout_Prices."""
    setUp = FarmRulesTests.setUp
    run_lua, run_file = FarmRulesTests.run_lua, FarmRulesTests.run_file

    def rank(self):
        entry = self.ns.ContributorRank()
        return None if entry is None else (entry.rank, entry.of, entry.kills)

    def test_this_accounts_rank_only(self):
        self.ns.db.installID = "abcdefghijkl"
        self.lua.execute('''GoldScoutPricesData = { markets = {}, contributors = {
          ["abcdefghijkl"] = { rank = 3, of = 40, kills = 1200 },
          ["otheraccount"] = { rank = 1, of = 40, kills = 9000 } } }''')
        self.assertEqual(self.rank(), (3, 40, 1200))
        self.ns.db.installID = "notrankedyet"
        self.assertIsNone(self.rank())

    def test_nothing_without_a_companion_or_ranks(self):
        self.ns.db.installID = "abcdefghijkl"
        self.lua.execute("GoldScoutPricesData = nil")
        self.assertIsNone(self.rank())
        self.lua.execute("GoldScoutPricesData = { markets = {} }")
        self.assertIsNone(self.rank())
        self.lua.execute('GoldScoutPricesData = { contributors = { ["abcdefghijkl"] = "junk" } }')
        self.assertIsNone(self.rank())


@unittest.skipIf(lua51 is None, "lupa is not installed")
class MobDropsTests(unittest.TestCase):
    """The drop rates window (MobDrops.lua): every item players have looted from one mob, and the
    entry it adds to the target portrait's right-click menu."""
    setUp_farm = FarmRulesTests.setUp
    run_lua, run_file, item, drops = (FarmRulesTests.run_lua, FarmRulesTests.run_file,
                                      FarmRulesTests.item, FarmRulesTests.drops)

    def setUp(self):
        self.setUp_farm()
        self.run_lua(r"""
        FAKE.units, FAKE.menus = {}, {}
        UnitExists = function(unit) return FAKE.units[unit] ~= nil end
        UnitIsPlayer = function(unit) return FAKE.units[unit] and FAKE.units[unit]:find("^Player") ~= nil end
        UnitGUID = function(unit) return FAKE.units[unit] end
        Menu = { ModifyMenu = function(tag, fn) FAKE.menus[tag] = fn end }
        """)
        self.run_file("MobDrops.lua")
        self.drop_rows = self.ns.MobDrops.Rows

    def shared(self, npc, kills, items, picks=0, picked=None):
        entry = self.lua.eval("{ k = %d, p = %d, i = {}, pi = {} }" % (kills, picks))
        for item_id, (times, quantity) in items.items():
            entry.i[item_id] = self.lua.table_from({"d": times, "q": quantity})
        for item_id, (times, quantity) in (picked or {}).items():
            entry.pi[item_id] = self.lua.table_from({"d": times, "q": quantity})
        self.ns.COMMUNITY[npc] = entry

    def rows(self, npc):
        rows, kills, picks = self.drop_rows(npc)
        return [dict(row) for row in rows.values()], kills, picks

    def target(self, guid):
        self.lua.globals().FAKE.units.target = guid

    def test_your_loot_and_the_communitys_add_up(self):
        self.shared(3000, 90, {5001: (30, 60), 5002: (9, 9)})
        self.drops(3000, kills=10, items={5001: 5, 5003: 1})
        rows, kills, picks = self.rows(3000)
        self.assertEqual((kills, picks), (100, 0))
        self.assertEqual([row["item"] for row in rows], [5001, 5002, 5003])   # most often dropped first
        first = rows[0]
        self.assertEqual((first["drops"], first["quantity"], first["attempts"]), (35, 65, 100))
        self.assertAlmostEqual(first["rate"], 0.35)
        self.assertAlmostEqual(first["stack"], 65 / 35)

    def test_pickpocketing_has_its_own_heading_and_attempts(self):
        self.shared(3000, 20, {5001: (4, 4)}, picks=50, picked={5010: (10, 10)})
        rows, kills, picks = self.rows(3000)
        self.assertEqual((kills, picks), (20, 50))
        self.assertEqual(rows[0]["attempts"], 20)
        self.assertIn("50", rows[1]["heading"])
        self.assertEqual((rows[2]["item"], rows[2]["attempts"], rows[2]["pick"]), (5010, 50, True))
        self.assertAlmostEqual(rows[2]["rate"], 0.2)

    def test_a_mob_nobody_has_looted_has_no_rows(self):
        self.assertEqual(self.rows(4242), ([], 0, 0))

    def test_drop_list_ignores_missing_records(self):
        # pick = true reads only picks: a record with kills but no picks has nothing.
        attempts, items = self.ns.Community.DropList(True, None, self.lua.eval("{ k = 5, i = { [1] = { d = 2, q = 2 } } }"))
        self.assertEqual((attempts, len(items)), (0, 0))

    def test_only_creatures_are_mobs(self):
        npc_of = self.ns.MobDrops.NpcOf
        self.target("Creature-0-1-2-3-3809-0000ABCDEF")
        self.assertEqual(npc_of("target"), 3809)
        self.target("Player-1234-00ABCDEF")
        self.assertIsNone(npc_of("target"))
        self.target("Pet-0-1-2-3-416-0000ABCDEF")
        self.assertIsNone(npc_of("target"))
        self.target(None)
        self.assertIsNone(npc_of("target"))

    def menu_buttons(self, tag="MENU_UNIT_TARGET", unit="target"):
        root = self.lua.eval("""{ buttons = {},
          CreateDivider = function() end, CreateTitle = function() end,
          CreateButton = function(self, text, fn) self.buttons[#self.buttons + 1] = { text = text, fn = fn } end }""")
        self.lua.globals().FAKE.menus[tag](None, root, self.lua.table_from({"unit": unit}))
        return list(root.buttons.values())

    def test_target_and_focus_menus_get_a_drop_rates_entry_for_mobs(self):
        self.target("Creature-0-1-2-3-3809-0000ABCDEF")
        buttons = self.menu_buttons()
        self.assertEqual([button.text for button in buttons], ["Drop rates"])
        self.assertIsNotNone(self.lua.globals().FAKE.menus["MENU_UNIT_FOCUS"])
        self.target("Player-1234-00ABCDEF")
        self.assertEqual(self.menu_buttons(), [])

    def open_window(self, npc):
        """Opens the window with a stand-in for the game's frames; returns every text it set."""
        self.run_lua(r"""
        FAKE.texts = {}
        local function Widget()
          return setmetatable({}, { __index = function(_, key)
            return function(self, value)
              if key == "SetText" then FAKE.texts[#FAKE.texts + 1] = tostring(value) end
              if key == "Show" then rawset(self, "shown", true) end
              if key == "Hide" then rawset(self, "shown", false) end
              if key == "IsShown" then return rawget(self, "shown") end
              if key == "CreateFontString" or key == "CreateTexture" then return Widget() end
            end
          end })
        end
        CreateFrame = function() return Widget() end
        UISpecialFrames = {}
        """)
        self.ns.MobDrops.Show(self.ns.MobDrops, npc)
        return "\n".join(self.lua.globals().FAKE.texts.values())

    def test_window_shows_the_mob_and_its_drops(self):
        self.item(5001, price=1000, name="Gooey Spider Leg")
        self.shared(3000, 40, {5001: (10, 20)}, picks=8, picked={5010: (2, 2)})
        self.drops(3000, kills=5, items={5001: 2}, name="Webwood Spider")
        texts = self.open_window(3000)
        self.assertIn("Webwood Spider", texts)
        self.assertIn("45 kills recorded by GoldScout players, 5 of them yours.", texts)
        self.assertIn("Gooey Spider Leg", texts)
        self.assertIn("27%", texts)                      # 12 of 45 kills
        self.assertIn("Pickpocketing: 8 picks", texts)
        self.assertIn("wowgoldscout.com/mob/3000", texts)
        self.assertEqual(list(self.ns.db.errors.values()), [])

    def test_window_for_a_mob_nobody_has_looted(self):
        texts = self.open_window(4242)
        self.assertIn("Nobody has recorded loot from this mob yet.", texts)
        self.assertNotIn("wowgoldscout.com", texts)       # no page on the website for it

    def test_a_menu_error_is_recorded_not_raised(self):
        self.target("Creature-0-1-2-3-3809-0000ABCDEF")
        broken = self.lua.eval("{ CreateButton = function() error('menu changed') end }")
        self.lua.globals().FAKE.menus["MENU_UNIT_TARGET"](None, broken, self.lua.table_from({"unit": "target"}))
        self.assertIn("menu changed", self.ns.db.errors[1].m)


@unittest.skipIf(lua51 is None, "lupa is not installed")
class BagCoinTests(unittest.TestCase):
    """Bags.lua: a coin on bag items worth listing on the auction house instead of vendoring."""
    setUp_farm = FarmRulesTests.setUp
    run_lua, run_file, item = FarmRulesTests.run_lua, FarmRulesTests.run_file, FarmRulesTests.item

    def setUp(self):
        self.setUp_farm()
        self.run_lua(r"""
        FAKE.hooks = {}
        hooksecurefunc = function(target, name, fn)
          if type(target) == "string" then target, name, fn = _G, target, name end
          local original = target[name]
          target[name] = function(...) local r = { original(...) }; fn(...); return unpack(r) end
          FAKE.hooks[#FAKE.hooks + 1] = name
        end
        Bagnon = { Item = { Update = function() end } }
        local function Texture()
          local t = { shown = true }
          function t:SetTexture() end function t:SetSize() end function t:SetPoint() end function t:SetVertexColor() end
          function t:SetShown(v) self.shown = v end
          return t
        end
        function FAKE.Slot(itemID, bound)
          local slot = { info = { itemID = itemID, isBound = bound } }
          function slot:CreateTexture() return Texture() end
          function slot:IsVisible() return true end
          return slot
        end
        """)
        self.run_file("Bags.lua")
        self.bags = self.ns.Bags

    def worth(self, item_id, bound=False):
        return self.bags.Worth(self.bags, item_id, bound)

    def test_reagents_and_green_items_at_double_the_vendor_price(self):
        self.item(6000, price=1000, sell=400, reagent=True)                    # 950 after the cut >= 800
        self.item(6001, price=700, sell=400, reagent=True)                     # 665 < 800
        self.item(6002, price=30000, sell=5000, quality=2, class_=4, reagent=False)   # green gear
        self.item(6003, price=2000, sell=0, quality=3, class_=2, reagent=False)       # vendors won't buy it
        self.assertIsNotNone(self.worth(6000))
        self.assertIsNone(self.worth(6001))
        self.assertIsNotNone(self.worth(6002))
        self.assertEqual(self.worth(6003), (2000 * 0.95, 0))

    def test_never_junk_white_quest_or_bound(self):
        self.item(6010, price=10000, sell=5, reagent=False)                    # white, not a reagent
        self.item(6011, price=10000, sell=5, quality=0)                        # gray
        self.item(6012, price=10000, sell=5, quality=2, bind=1, reagent=False) # binds on pickup
        self.item(6013, price=10000, sell=5, bind=4)                           # quest item
        self.item(6014, price=10000, sell=5, quality=2, reagent=False)         # fine, but this copy is bound
        for item_id in (6010, 6011, 6012, 6013):
            with self.subTest(item_id):
                self.assertIsNone(self.worth(item_id))
        self.assertIsNone(self.worth(6014, bound=True))
        self.assertIsNotNone(self.worth(6014))

    def test_needs_real_prices_not_the_regional_estimate(self):
        self.item(6020, price=1000, sell=100, reagent=True)
        self.run_lua('local ns = ...; ns.Prices.Get = function(_, id) return 1000, 5, 60, "estimate" end')
        self.assertIsNone(self.worth(6020))

    def test_the_setting_turns_it_off(self):
        self.item(6030, price=1000, sell=100, reagent=True)
        self.ns.db.settings.bagCoins = False
        self.assertIsNone(self.worth(6030))

    def test_bagnon_slots_get_a_coin_that_follows_the_price(self):
        self.assertIn("Update", list(self.lua.globals().FAKE.hooks.values()))   # Bagnon's Item:Update is hooked
        self.item(6040, price=1000, sell=100, reagent=True)
        slot = self.lua.globals().FAKE.Slot(6040, False)
        self.lua.globals().Bagnon.Item.Update(slot)
        self.assertTrue(slot.GoldScoutCoin.shown)
        self.lua.globals().FAKE.prices[6040] = 150                             # the price falls under double
        self.bags.Refresh(self.bags)
        self.assertFalse(slot.GoldScoutCoin.shown)
        plain = self.lua.globals().FAKE.Slot(6041, False)                      # nothing worth listing: no coin made
        self.bags.Mark(plain)
        self.assertIsNone(plain.GoldScoutCoin)

    def test_tooltip_says_why(self):
        self.item(6050, price=1000, sell=100, reagent=True)
        slot = self.lua.globals().FAKE.Slot(6050, False)
        tooltip = self.lua.eval("function(owner) return { GetOwner = function() return owner end } end")(slot)
        self.assertIn("on the auction house", self.bags.TooltipLine(self.bags, tooltip))
        elsewhere = self.lua.eval("{ GetOwner = function() return {} end }")    # not a bag slot: no line
        self.assertIsNone(self.bags.TooltipLine(self.bags, elsewhere))


if __name__ == "__main__":
    unittest.main()
