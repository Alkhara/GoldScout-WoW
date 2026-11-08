-- GoldScout static data: what can be farmed, where, and how often it drops.
--
-- Gathering skill requirements and spawn zones are the classic values; Forever
-- expanded some zones, so treat the zone hints as a starting point. Yields
-- marked "rough" are estimates. Mob drop rates and spawn spots come only from
-- player-collected data (Data_Community.lua) and your own loot.
local _, ns = ...

ns.SKILL = {
  ALCHEMY = 171,
  BLACKSMITHING = 164,
  COOKING = 185,
  ENCHANTING = 333,
  ENGINEERING = 202,
  FIRST_AID = 129,
  FISHING = 356,
  HERBALISM = 182,
  LEATHERWORKING = 165,
  LOCKPICKING = 633,
  MINING = 186,
  SKINNING = 393,
  TAILORING = 197,
}

ns.SKILL_NAME = {
  [171] = "Alchemy",
  [164] = "Blacksmithing",
  [185] = "Cooking",
  [333] = "Enchanting",
  [202] = "Engineering",
  [129] = "First Aid",
  [356] = "Fishing",
  [182] = "Herbalism",
  [165] = "Leatherworking",
  [633] = "Lockpicking",
  [186] = "Mining",
  [393] = "Skinning",
  [197] = "Tailoring",
}

-- Average units per node, skin or kill (rough).
ns.YIELD = {
  herb = 1.8,    -- herbs per herb node
  ore = 1.8,     -- ore per mining node
  stone = 0.6,   -- stone per mining node
  leather = 1.6, -- leather per skin
  hide = 0.06,   -- chance of a hide per skin
  cloth = 0.3,   -- cloth per humanoid kill
}

-- Herbs: item ID, Herbalism skill needed, classic spawn zones.
ns.HERBS = {
  { id = 2447, skill = 1, zones = "Starting zones, Barrens, Westfall" },              -- Peacebloom
  { id = 765, skill = 1, zones = "Starting zones, Barrens, Westfall" },               -- Silverleaf
  { id = 2449, skill = 15, zones = "Barrens, Westfall, Loch Modan, Darkshore" },      -- Earthroot
  { id = 785, skill = 50, zones = "Barrens, Silverpine, Westfall, Redridge" },        -- Mageroyal
  { id = 2450, skill = 70, zones = "Barrens, Silverpine, Redridge, Stonetalon" },     -- Briarthorn
  { id = 3820, skill = 85, zones = "Underwater on coasts: Darkshore, Westfall, Wetlands, Hillsbrad" }, -- Stranglekelp
  { id = 2453, skill = 100, zones = "Barrens, Redridge, Ashenvale, Stonetalon, Wetlands" }, -- Bruiseweed
  { id = 3355, skill = 115, zones = "Stonetalon, Ashenvale, Thousand Needles, Arathi, Wetlands" }, -- Wild Steelbloom
  { id = 3369, skill = 120, zones = "Duskwood, Desolace (Kodo Graveyard), Arathi, Wetlands" }, -- Grave Moss
  { id = 3356, skill = 125, zones = "Ashenvale, Hillsbrad, Stonetalon, Thousand Needles, Wetlands" }, -- Kingsblood
  { id = 3357, skill = 150, zones = "Riverbanks in Hillsbrad, Wetlands, Arathi, Stranglethorn" }, -- Liferoot
  { id = 3818, skill = 160, zones = "Arathi, Stranglethorn, Swamp of Sorrows, Badlands" }, -- Fadeleaf
  { id = 3821, skill = 170, zones = "Arathi, Stranglethorn, Badlands, Dustwallow, Feralas" }, -- Goldthorn
  { id = 3358, skill = 185, zones = "Arathi, Stranglethorn, Hinterlands, Dustwallow, Feralas" }, -- Khadgar's Whisker
  { id = 3819, skill = 195, zones = "Alterac Mountains" },                            -- Wintersbite
  { id = 4625, skill = 205, zones = "Searing Gorge, Blasted Lands, Tanaris" },        -- Firebloom
  { id = 8831, skill = 210, zones = "Tanaris, Feralas, Azshara, Hinterlands" },       -- Purple Lotus
  { id = 8836, skill = 220, zones = "Felwood, Plaguelands" },                         -- Arthas' Tears
  { id = 8838, skill = 230, zones = "Felwood, Hinterlands, Feralas, Un'Goro" },       -- Sungrass
  { id = 8839, skill = 235, zones = "Swamp of Sorrows, Un'Goro" },                    -- Blindweed
  { id = 8845, skill = 245, zones = "Maraudon, Hinterlands caves, Un'Goro" },         -- Ghost Mushroom
  { id = 8846, skill = 250, zones = "Felwood, Desolace, Blasted Lands" },             -- Gromsblood
  { id = 13464, skill = 260, zones = "Feralas, Azshara, Felwood, Burning Steppes" },  -- Golden Sansam
  { id = 13463, skill = 270, zones = "Un'Goro, Azshara, Felwood, Silithus" },         -- Dreamfoil
  { id = 13465, skill = 280, zones = "Winterspring, Un'Goro, Azshara, Burning Steppes" }, -- Mountain Silversage
  { id = 13466, skill = 285, zones = "Plaguelands, Felwood" },                        -- Plaguebloom
  { id = 13467, skill = 290, zones = "Winterspring" },                                -- Icecap
  { id = 13468, skill = 300, zones = "Burning Steppes, Winterspring, Silithus, Eastern Plaguelands" }, -- Black Lotus
}

-- Ores: item ID, Mining skill needed, stone from the same vein, classic zones.
ns.ORES = {
  { id = 2770, skill = 1, stone = 2835, zones = "Starting zones, Barrens, Westfall, Loch Modan, Darkshore" }, -- Copper Ore / Rough Stone
  { id = 2771, skill = 65, stone = 2836, zones = "Redridge, Duskwood, Ashenvale, Stonetalon, Wetlands, Hillsbrad" }, -- Tin Ore / Coarse Stone
  { id = 2775, skill = 75, zones = "Rare spawn where tin is: Redridge, Ashenvale, Stonetalon, Hillsbrad" }, -- Silver Ore
  { id = 2772, skill = 125, stone = 2838, zones = "Arathi, Desolace, Thousand Needles, Stranglethorn, Badlands" }, -- Iron Ore / Heavy Stone
  { id = 2776, skill = 155, zones = "Arathi, Desolace, Stranglethorn, Badlands, Thousand Needles" }, -- Gold Ore
  { id = 3858, skill = 175, stone = 7912, zones = "Badlands, Hinterlands, Feralas, Tanaris, Searing Gorge" }, -- Mithril Ore / Solid Stone
  { id = 7911, skill = 230, zones = "Rare spawn where mithril is: Badlands, Hinterlands, Tanaris" }, -- Truesilver Ore
  { id = 10620, skill = 245, stone = 12365, zones = "Un'Goro, Silithus, Winterspring, Burning Steppes" }, -- Thorium Ore / Dense Stone
}

-- Skinning: leather and hide by beast level.
ns.SKINNING = {
  { min = 1, max = 16, leather = 2318, hide = 783 },   -- Light Leather / Light Hide
  { min = 15, max = 28, leather = 2319, hide = 4232 }, -- Medium Leather / Medium Hide
  { min = 25, max = 40, leather = 4234, hide = 4235 }, -- Heavy Leather / Heavy Hide
  { min = 35, max = 50, leather = 4304, hide = 8169 }, -- Thick Leather / Thick Hide
  { min = 45, max = 63, leather = 8170, hide = 8171 }, -- Rugged Leather / Rugged Hide
}

-- Gems from mining veins that also drop at random from many mobs. The Farm tab
-- treats them like BoE gear: shown only with the Rare drops option.
ns.GEMS = {
  [774] = true,   -- Malachite
  [818] = true,   -- Tigerseye
  [1206] = true,  -- Moss Agate
  [1210] = true,  -- Shadowgem
  [1529] = true,  -- Jade
  [1705] = true,  -- Lesser Moonstone
  [3864] = true,  -- Citrine
  [7909] = true,  -- Aquamarine
  [7910] = true,  -- Star Ruby
  [7971] = true,  -- Black Pearl
  [11754] = true, -- Black Diamond
  [12361] = true, -- Blue Sapphire
  [12363] = true, -- Arcane Crystal
  [12364] = true, -- Huge Emerald
  [12799] = true, -- Large Opal
  [12800] = true, -- Azerothian Diamond
}

-- Cloth by humanoid level (rough).
ns.CLOTH = {
  { id = 2589, min = 5, max = 18 },   -- Linen Cloth
  { id = 2592, min = 15, max = 27 },  -- Wool Cloth
  { id = 4306, min = 23, max = 38 },  -- Silk Cloth
  { id = 4338, min = 33, max = 49 },  -- Mageweave Cloth
  { id = 14047, min = 45, max = 63 }, -- Runecloth
}

-- Trade goods that players make rather than loot from mobs, so the Farm tab
-- never suggests hunting them. Whole categories that are always crafted
-- (engineering parts, bars, enchanting materials) are filtered by subclass in
-- Engine.lua; this list covers crafted items in the mixed categories.
ns.CRAFTED_TRADE_GOODS = {
  [2996] = true,  -- Bolt of Linen Cloth
  [2997] = true,  -- Bolt of Woolen Cloth
  [4305] = true,  -- Bolt of Silk Cloth
  [4339] = true,  -- Bolt of Mageweave
  [14048] = true, -- Bolt of Runecloth
  [14342] = true, -- Mooncloth
  [4231] = true,  -- Cured Light Hide
  [4233] = true,  -- Cured Medium Hide
  [4236] = true,  -- Cured Heavy Hide
  [8172] = true,  -- Cured Thick Hide
  [15407] = true, -- Cured Rugged Hide
  [3470] = true,  -- Rough Grinding Stone
  [3478] = true,  -- Coarse Grinding Stone
  [3486] = true,  -- Heavy Grinding Stone
  [7966] = true,  -- Solid Grinding Stone
  [12644] = true, -- Dense Grinding Stone
  [12810] = true, -- Enchanted Leather
}

-- Crafting reagents sold by vendors. Until you visit a vendor that sells one,
-- its cost is estimated at four times its vendor sell price.
ns.VENDOR_REAGENTS = {
  [159] = true,   -- Refreshing Spring Water
  [1179] = true,  -- Ice Cold Milk
  [2320] = true,  -- Coarse Thread
  [2321] = true,  -- Fine Thread
  [2324] = true,  -- Bleach
  [2325] = true,  -- Black Dye
  [2604] = true,  -- Red Dye
  [2605] = true,  -- Green Dye
  [2678] = true,  -- Mild Spices
  [2692] = true,  -- Hot Spices
  [2880] = true,  -- Weak Flux
  [2928] = true,  -- Dust of Decay
  [2930] = true,  -- Essence of Pain
  [3371] = true,  -- Empty Vial
  [3372] = true,  -- Leaded Vial
  [3466] = true,  -- Strong Flux
  [3713] = true,  -- Soothing Spices
  [3857] = true,  -- Coal
  [4289] = true,  -- Salt
  [4291] = true,  -- Silken Thread
  [4340] = true,  -- Gray Dye
  [4341] = true,  -- Yellow Dye
  [4342] = true,  -- Purple Dye
  [4399] = true,  -- Wooden Stock
  [4400] = true,  -- Heavy Stock
  [4470] = true,  -- Simple Wood
  [5140] = true,  -- Flash Powder
  [5173] = true,  -- Deathweed
  [6217] = true,  -- Copper Rod
  [6260] = true,  -- Blue Dye
  [6261] = true,  -- Orange Dye
  [8343] = true,  -- Heavy Silken Thread
  [8923] = true,  -- Essence of Agony
  [8924] = true,  -- Dust of Deterioration
  [8925] = true,  -- Crystal Vial
  [10290] = true, -- Pink Dye
  [10647] = true, -- Engineer's Ink
  [10648] = true, -- Blank Parchment
  [11291] = true, -- Star Wood
  [14341] = true, -- Rune Thread
  [18256] = true, -- Imbued Vial
}

-- Hand-listed farm tables (mob drops, pickpocket targets, junkbox contents).
-- Empty for now: every entry needs a source players collected in game.
ns.MOB_DROPS = ns.MOB_DROPS or {}
ns.PICKPOCKET = ns.PICKPOCKET or {}
ns.JUNKBOXES = ns.JUNKBOXES or {}
-- Player-collected drop data, filled by Data_Community.lua (built by tools/merge_data.py).
ns.COMMUNITY = ns.COMMUNITY or {}

-- The farm tables indexed by creature ID, for mob tooltips and hunt markers.
ns.FARMS_BY_NPC = {}
local function IndexFarm(npcID, kind, entry)
  local list = ns.FARMS_BY_NPC[npcID]
  if not list then
    list = {}
    ns.FARMS_BY_NPC[npcID] = list
  end
  list[#list + 1] = { kind = kind, entry = entry }
end
ns.Listen("DB_READY", function()
  for _, drop in ipairs(ns.MOB_DROPS) do
    IndexFarm(drop.npc, "Drop", drop)
  end
  for _, target in ipairs(ns.PICKPOCKET) do
    IndexFarm(target.npc, "Pickpocket", target)
  end
end)
