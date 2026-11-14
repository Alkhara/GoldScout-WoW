-- GoldScout engine: turns prices, recipes and farm data into ranked lists.
local _, ns = ...
local L = ns.L

local Engine = {}
ns.Engine = Engine

local TRIVIAL = (Enum.TradeskillRelativeDifficulty and Enum.TradeskillRelativeDifficulty.Trivial) or 3

-- How many of your own kills it takes before your loot outweighs the database rate.
local PRIOR_WEIGHT = 30
-- Kills of an unlisted mob before it shows up on the Farm tab as "Learned".
-- Low counts are shown with a low confidence and a cautious rate (below).
local LEARNED_MIN_KILLS = 1
-- Kills of a mob (yours plus the community's) before its other loot counts
-- toward a row's gold per hour (the allLoot setting); fewer is mostly luck.
local OTHER_LOOT_MIN_KILLS = 10
-- Gold per hour from player data uses drops / (attempts + this), so a lucky
-- first drop doesn't top the list; it fades out as attempts add up.
local CAUTION_ATTEMPTS = 2
-- How far above your level Market rows still show (dimmed past the usual window).
local MARKET_ABOVE_LEVELS = 10

-- Confidence in a drop rate by how many kills (or picks) back it up.
local CONFIDENCE = {
  { min = 50, key = "high", text = L["high"], color = "|cff40ff40" },
  { min = 15, key = "good", text = L["good"], color = "|cff9be35a" },
  { min = 5, key = "fair", text = L["fair"], color = "|cffffd100" },
  { min = 0, key = "low", text = L["low"], color = "|cffff8040" },
}

function Engine.Confidence(attempts)
  for _, tier in ipairs(CONFIDENCE) do
    if (attempts or 0) >= tier.min then
      return tier
    end
  end
  return CONFIDENCE[#CONFIDENCE]
end
-- Once players have recorded this many attempts on a mob, a hand-listed
-- starting rate is ignored entirely and only player data counts.
local STARTING_RATE_RETIRE_ATTEMPTS = 200
-- Player loot positions needed before a community spawn spot is trusted.
local COMMUNITY_SPOT_MIN = 10
-- Item class for trade goods (meat, cloth, parts, elemental...).
local TRADE_GOODS = (Enum.ItemClass and Enum.ItemClass.Tradegoods) or 7
-- Trade goods subclasses players make rather than loot: engineering parts,
-- explosives and devices, metal bars (ore and stone have their own Mining
-- rows) and enchanting materials from disenchanting.
local CRAFTED_SUBCLASSES = { [1] = true, [2] = true, [3] = true, [7] = true, [12] = true }

Engine.DIFFICULTY_TEXT = {
  [0] = "|cffff8040orange|r",
  [1] = "|cffffff00yellow|r",
  [2] = "|cff40c040green|r",
  [3] = "|cff808080gray|r",
}

-- What you would actually receive selling one unit on the auction house.
local function NetPrice(itemID)
  local price, listed, age = ns.Prices:Get(itemID)
  if not price then
    return nil, listed, age
  end
  return price * ns.AH_CUT, listed, age
end

local function LevelText(minLevel, maxLevel)
  if minLevel == maxLevel then
    return tostring(minLevel)
  end
  return minLevel .. "-" .. maxLevel
end

local function MapName(mapID)
  local info = mapID and C_Map and C_Map.GetMapInfo and C_Map.GetMapInfo(mapID)
  return info and info.name
end

-- Rough kills per hour: mobs well below your level die much faster.
local function KillsPerHour(playerLevel, mobLevel, base)
  local diff = playerLevel - mobLevel
  if diff >= 10 then
    return base * 2
  elseif diff >= 6 then
    return base * 1.6
  elseif diff >= 3 then
    return base * 1.25
  elseif diff >= 0 then
    return base
  elseif diff >= -2 then
    return base * 0.8
  end
  return base * 0.6
end

-- Highest beast level you can skin with this Skinning skill.
local function MaxSkinnableLevel(rank)
  if rank >= 100 then
    return math.floor(rank / 5)
  end
  return 10 + math.floor(rank / 10)
end

-- Highest gathering skill a character of this level can train up to.
local function SkillCapForLevel(level)
  if level >= 35 then
    return 300
  elseif level >= 20 then
    return 225
  elseif level >= 10 then
    return 150
  end
  return 75
end

-- Highest mob level that is gray (gives no experience) at your level, using
-- the classic rule.
local function GrayLevel(level)
  if level <= 5 then
    return 0
  elseif level < 40 then
    return level - math.floor(level / 10) - 5
  elseif level < 60 then
    return level - math.floor(level / 5) - 1
  end
  return level - 9
end

local MAX_LEVEL = 60

-- "full" if every mob in the level range gives you XP, "some" if only the top
-- of the range does, "none" if all are gray. nil when it doesn't apply (no mob
-- levels, or you're at max level).
local function XpStatus(level, lvlText)
  if level >= MAX_LEVEL or type(lvlText) ~= "string" then
    return nil
  end
  local low, high = lvlText:match("^(%d+)%-(%d+)$")
  low = tonumber(low or lvlText:match("^(%d+)$"))
  high = tonumber(high) or low
  if not low then
    return nil
  end
  local gray = GrayLevel(level)
  if low > gray then
    return "full"
  elseif high > gray then
    return "some"
  end
  return "none"
end

-- Sort helper: larger values first, rows without a value last.
local function ByValue(field, tiebreak)
  return function(a, b)
    local va, vb = a[field], b[field]
    if va and vb then
      if va ~= vb then
        return va > vb
      end
    elseif va then
      return true
    elseif vb then
      return false
    end
    return (a[tiebreak] or "") < (b[tiebreak] or "")
  end
end

-- Mixes a listed starting chance with what players (community data plus you)
-- have recorded. With enough attempts the starting chance stops counting.
local function BlendedChance(prior, npcID, itemID, pick)
  local drops, attempts = ns.Learn:Evidence(npcID, itemID, pick)
  if attempts == 0 then
    return prior, nil, 0
  end
  local weight = (attempts >= STARTING_RATE_RETIRE_ATTEMPTS) and 0 or PRIOR_WEIGHT
  return (prior * weight + drops) / (weight + attempts), drops / attempts, attempts
end

-- Spawn spots: the community's spot once enough players have looted there,
-- otherwise listed hotspots, otherwise where you've looted it yourself.
local function SpotsFor(npcID, spots)
  local shared = ns.COMMUNITY[npcID]
  if shared and shared.m and shared.x and (shared.c or 0) >= COMMUNITY_SPOT_MIN then
    return { { shared.m, shared.x * 100, shared.y * 100 } }
  end
  if spots then
    return spots
  end
  local map, x, y = ns.Learn:Spot(npcID)
  if map then
    return { { map, x, y } }
  end
  return nil
end

-- Items the cloth, herb, ore and skinning farms already cover, so market rows
-- don't repeat them (or bring back professions you've chosen to hide).
local gatheredItems
local function GatheredItems()
  if not gatheredItems then
    gatheredItems = {}
    for _, cloth in ipairs(ns.CLOTH) do
      gatheredItems[cloth.id] = true
    end
    for _, list in ipairs({ ns.HERBS, ns.ORES }) do
      for _, entry in ipairs(list) do
        gatheredItems[entry.id] = true
        if entry.stone then
          gatheredItems[entry.stone] = true
        end
      end
    end
    for _, band in ipairs(ns.SKINNING) do
      gatheredItems[band.leather] = true
      if band.hide then
        gatheredItems[band.hide] = true
      end
    end
  end
  return gatheredItems
end

-- Weapons, armor and recipes: rare world drops that can come from many mobs,
-- so a rate tied to one mob says little. Learned rows hide them unless the
-- Rare drops option is on.
local RARE_DROP_CLASSES = { [2] = true, [4] = true, [9] = true }
local GEM_CLASS = (Enum.ItemClass and Enum.ItemClass.Gem) or 3

-- Item classes that are never crafting reagents, skipped without loading the
-- item: containers, weapons, armor, recipes, quest items.
local NEVER_REAGENT_CLASSES = { [1] = true, [2] = true, [4] = true, [9] = true, [12] = true }

-- Item level of each crafting reagent once the game has told us, or false for
-- items that aren't sellable reagents worth farming. Remembered for the session
-- so the list doesn't change when the client drops items from its cache.
local reagentFacts = {}

local function ReagentFacts(itemID)
  local facts = reagentFacts[itemID]
  if facts ~= nil then
    return facts
  end
  local _, _, _, _, _, classID, subclassID = ns.GetItemInfoInstant(itemID)
  if not classID or NEVER_REAGENT_CLASSES[classID] then
    reagentFacts[itemID] = false
    return false
  end
  local info = { ns.GetItemInfo(itemID) }
  local quality, itemLevel, bindType = info[3], info[4], info[14]
  if not itemLevel then
    ns.RequestItem(itemID) -- the list refreshes once the item loads
    return nil
  end
  -- The "Crafting Reagent" flag the game shows in item tooltips. If this client
  -- doesn't report it, fall back to the trade goods category.
  local isReagent = ns.Plain(info[17])
  if type(isReagent) ~= "boolean" then
    isReagent = classID == TRADE_GOODS
  end
  -- Reagents are never used directly: anything with a "Use:" effect (crates,
  -- food, scrolls) isn't one, whatever its flag says.
  local useSpell = C_Item and C_Item.GetItemSpell and ns.Plain(C_Item.GetItemSpell(itemID))
  -- Bound, quest and gray (vendor trash) items aren't worth farming for the AH.
  if not isReagent or useSpell or bindType == 1 or bindType == 4 or quality == ns.QUALITY_POOR then
    facts = false
  else
    local craftedCategory = classID == TRADE_GOODS and CRAFTED_SUBCLASSES[subclassID]
    facts = {
      level = itemLevel,
      crafted = craftedCategory or ns.CRAFTED_TRADE_GOODS[itemID],
      -- Gems drop at random from many mobs (and come from mining), like gear.
      gem = classID == GEM_CLASS or ns.GEMS[itemID] or nil,
    }
  end
  reagentFacts[itemID] = facts
  return facts
end

-- The mob players have seen drop an item most often per kill, even with too
-- few kills to rank it yet. Returns npcID, drops, kills, or nil.
local function BestSighting(itemID)
  local bestNpc, bestDrops, bestKills, bestRate
  local function Check(npcID, entry)
    local stat = entry and entry.i and entry.i[itemID]
    if stat and (entry.k or 0) > 0 then
      local drops, kills = ns.Learn:Evidence(npcID, itemID, false)
      local rate = (kills > 0) and drops / kills or 0
      if not bestRate or rate > bestRate then
        bestNpc, bestDrops, bestKills, bestRate = npcID, drops, kills, rate
      end
    end
  end
  for npcID, entry in pairs(ns.db.drops or {}) do
    Check(npcID, entry)
  end
  for npcID, entry in pairs(ns.COMMUNITY) do
    Check(npcID, entry)
  end
  return bestNpc, bestDrops, bestKills
end

---------------------------------------------------------------------------
-- Hunt targets: what the Hunt button tracks for each Farm row
---------------------------------------------------------------------------

-- A drop hunt covers every listed mob that drops the same item on the same map.
local function DropHunt(drop)
  local map = drop.spots and drop.spots[1] and drop.spots[1][1]
  local npcs, names, spots = {}, {}, {}
  for _, other in ipairs(ns.MOB_DROPS) do
    local otherMap = other.spots and other.spots[1] and other.spots[1][1]
    if other.item == drop.item and (other == drop or (map ~= nil and otherMap == map)) then
      npcs[other.npc] = true
      names[#names + 1] = ns.MobName(other.npc, nil, other.mob)
      for _, spot in ipairs(SpotsFor(other.npc, other.spots) or {}) do
        spots[#spots + 1] = spot
      end
    end
  end
  return {
    key = "Drop:" .. drop.item .. ":" .. drop.npc,
    kind = "Drop", per = "kill", item = drop.item, chance = drop.chance,
    label = table.concat(names, ", "), zone = drop.zone, npcs = npcs,
    spots = (#spots > 0) and spots or nil,
  }
end

local function MobHunt(key, per, itemID, chance, mob, zone, npcID, spots)
  return {
    key = key, kind = per == "pick" and "Pickpocket" or "Drop", per = per, item = itemID, chance = chance,
    label = mob, zone = zone, npcs = { [npcID] = true }, spots = SpotsFor(npcID, spots),
  }
end

-- A hunt marks every mob on the Farm list that drops the same item in the same
-- zone (Coyote and Coyote Packleader both drop Coyote Meat), not
-- only the row's own mob. Each row keeps its own key, and its own spots first
-- so the waypoint still leads to that mob.
local UNKNOWN_ZONE = L["where players loot it"]

local function ShareHunts(rows)
  local places = {}
  for _, row in ipairs(rows) do
    local hunt = row.hunt
    -- Same zone: the map of the mob's first known spot, else the zone's name.
    local map = hunt and hunt.spots and hunt.spots[1] and hunt.spots[1][1]
    local zone = map or (hunt and hunt.zone ~= UNKNOWN_ZONE and hunt.zone)
    if hunt and hunt.per == "kill" and hunt.npcs and next(hunt.npcs) and zone then
      local place = hunt.item .. "|" .. tostring(zone)
      places[place] = places[place] or {}
      table.insert(places[place], row)
    end
  end
  for _, list in pairs(places) do
    if #list > 1 then
      local npcs, own = {}, {}
      for i, row in ipairs(list) do
        own[i] = row.hunt   -- the rows' own hunts, before any is replaced
        for npcID in pairs(row.hunt.npcs) do
          npcs[npcID] = true
        end
      end
      for i, row in ipairs(list) do
        -- This row's mobs first in the label, then the others.
        local names, seen = {}, {}
        local function AddNames(label)
          for name in ((label or "") .. ", "):gmatch("(.-), ") do
            if name ~= "" and not seen[name] then
              seen[name] = true
              names[#names + 1] = name
            end
          end
        end
        AddNames(own[i].label)
        for j = 1, #list do
          AddNames(own[j].label)
        end
        local shared = {}
        for field, value in pairs(own[i]) do
          shared[field] = value
        end
        local spots = {}
        for j = 0, #list do
          local hunt = own[j == 0 and i or j]
          if j == 0 or j ~= i then
            for _, spot in ipairs(hunt.spots or {}) do
              spots[#spots + 1] = spot
            end
          end
        end
        shared.npcs, shared.label = npcs, table.concat(names, ", ")
        shared.spots = (#spots > 0) and spots or nil
        row.hunt = shared
      end
    end
  end
end

-- Gathering and cloth hunts have no single mob or spot; they just track loot.
local function LootHunt(key, per, itemID, label, zone)
  return { key = key, kind = "Loot", per = per, item = itemID, label = label, zone = zone, npcs = {} }
end

---------------------------------------------------------------------------
-- Fishing
---------------------------------------------------------------------------

-- A fishing pool takes finding; this share of your time is spent fishing it.
local POOL_FISHING_SHARE = 0.5
-- Grid squares (Learn.lua's 20x20 AreaCell) where most catches were, as
-- waypoint spots in map percent: up to this many.
local FISH_SPOTS = 3

-- Every zone and spot fished, community data plus your own:
-- { { map, spot, n, s, i = { [itemID] = { d, q } }, a = { [cell] = count } } }.
local function FishSpots()
  local spots, index = {}, {}
  local function Add(fishing)
    for map, zone in pairs(fishing or {}) do
      for spot, entry in pairs(zone) do
        local key = map .. ":" .. spot
        local merged = index[key]
        if not merged then
          merged = { map = map, spot = spot, n = 0, i = {}, a = {} }
          index[key] = merged
          spots[#spots + 1] = merged
        end
        merged.n = merged.n + (entry.n or 0)
        if (entry.s or 0) > 0 then
          merged.s = math.min(merged.s or entry.s, entry.s)
        end
        for itemID, stat in pairs(entry.i or {}) do
          local item = merged.i[itemID] or { d = 0, q = 0 }
          merged.i[itemID] = item
          item.d, item.q = item.d + (stat.d or 0), item.q + (stat.q or 0)
        end
        for cell, count in pairs(entry.a or {}) do
          merged.a[cell] = (merged.a[cell] or 0) + count
        end
      end
    end
  end
  Add(ns.COMMUNITY_FISH)
  Add(ns.Learn:Fish())
  return spots
end

-- What one fished-up item is worth to you: the AH price after the cut, or the
-- vendor price for gray items and anything without an AH price.
local function CatchValue(itemID)
  local sell = ns.ItemSellPrice(itemID) or 0
  local net, listed, age = NetPrice(itemID)
  if net and not ns.IsPoorQuality(itemID) then
    return math.max(net, sell), listed, age
  end
  return sell > 0 and sell or nil
end

-- The busiest grid squares, as { map, x%, y% } spots for the hunt waypoint.
local function CellSpots(map, cells)
  local list = {}
  for cell, count in pairs(cells) do
    list[#list + 1] = { cell = cell, count = count }
  end
  table.sort(list, function(a, b)
    if a.count ~= b.count then
      return a.count > b.count
    end
    return a.cell < b.cell
  end)
  local spots = {}
  for i = 1, math.min(FISH_SPOTS, #list) do
    local cell = list[i].cell
    spots[i] = { map, (cell % 20 + 0.5) * 5, (math.floor(cell / 20) + 0.5) * 5 }
  end
  return (#spots > 0) and spots or nil
end

-- One Farm row per zone and spot (open water, or a kind of fishing pool),
-- valued per catch from everything players have fished up there.
local function FishRows(rows, settings, skills)
  local fishing = skills[ns.SKILL.FISHING]
  if not fishing and not settings.showOtherProfs then
    return
  end
  local rank = fishing and ns.Plain(fishing.rank)
  for _, place in ipairs(FishSpots()) do
    if place.n > 0 then
      local each, best, bestValue, bestRate, catch = 0, nil, nil, nil, {}
      local bestListed, bestAge
      for itemID, stat in pairs(place.i) do
        local value, listed, age = CatchValue(itemID)
        local rate = stat.d / place.n
        catch[#catch + 1] = { item = itemID, rate = rate }
        if value then
          local worth = value * stat.q / place.n
          each = each + worth
          if not bestValue or worth > bestValue then
            best, bestValue, bestRate, bestListed, bestAge = itemID, worth, rate, listed, age
          end
        end
      end
      if best then
        table.sort(catch, function(a, b)
          if a.rate ~= b.rate then
            return a.rate > b.rate
          end
          return a.item < b.item
        end)
        local pool = place.spot ~= 0
        local cautious = each * place.n / (place.n + CAUTION_ATTEMPTS)
        local perHour = settings.catchesPerHour * (pool and POOL_FISHING_SHARE or 1)
        local zone = MapName(place.map) or L["where players loot it"]
        local source = pool and L["Fishing pool"] or L["Open water"]
        local tooLow = type(rank) == "number" and place.s and rank < place.s
        local note = (L["%d catches recorded by GoldScout players."]):format(place.n)
        if place.s then
          note = note .. (L[" Lowest Fishing skill seen catching here: %d."]):format(place.s)
        end
        if pool then
          note = note .. L[" Pools assume half your time goes to finding the next one."]
        end
        rows[#rows + 1] = {
          kind = "Fish", item = best, source = source, zone = zone, lvl = "-",
          chance = bestRate, per = "catch", seenRate = bestRate, seenTrials = place.n,
          confidence = Engine.Confidence(place.n), catch = catch,
          each = cautious, hour = cautious * perHour,
          listed = bestListed, age = bestAge, needsProfession = not fishing or tooLow or nil, note = note,
          hunt = {
            key = "Fish:" .. place.map .. ":" .. place.spot, kind = "Fish", per = "catch", item = best,
            chance = bestRate, label = source, zone = zone, npcs = {}, spots = CellSpots(place.map, place.a),
          },
        }
      end
    end
  end
end

---------------------------------------------------------------------------
-- Crafting
---------------------------------------------------------------------------

-- Cheapest known cost of one unit of a reagent, and where that price came from.
function Engine:UnitCost(itemID)
  local vendor = ns.db.vendor[itemID]
  if vendor then
    return vendor, "vendor"
  end
  local ahPrice = ns.Prices:Get(itemID)
  if ns.VENDOR_REAGENTS[itemID] then
    local sellPrice = ns.ItemSellPrice(itemID)
    if sellPrice and sellPrice > 0 then
      local estimate = sellPrice * 4
      if not ahPrice or estimate <= ahPrice then
        return estimate, "vendor~"
      end
    end
  end
  if ahPrice then
    return ahPrice, "ah"
  end
  return nil, "none"
end

function Engine:Crafts()
  local settings = ns.db.settings
  local rows = {}
  for _, profession in pairs(ns.cdb.recipes) do
    for recipeID, recipe in pairs(profession.list or {}) do
      local output = recipe.out
      if output then
        local bindType = ns.ItemBindType(output)
        local bound = (bindType == 1 or bindType == 4)
        local trivial = (recipe.diff == TRIVIAL)
        if (settings.showBound or not bound) and (settings.showTrivial or not trivial) then
          local quantity = ((recipe.qmin or 1) + (recipe.qmax or recipe.qmin or 1)) / 2
          local sellPrice, listed, age = ns.Prices:Get(output)
          local cost, missing, estimated = 0, false, false
          local parts = {}
          for _, reagent in ipairs(recipe.reagents or {}) do
            local itemID, needed = reagent[1], reagent[2]
            local unit, source = self:UnitCost(itemID)
            parts[#parts + 1] = { id = itemID, count = needed, unit = unit, source = source }
            if unit then
              cost = cost + unit * needed
            else
              missing = true
            end
            if source == "vendor~" then
              estimated = true
            end
          end
          local revenue = sellPrice and math.floor(sellPrice * quantity * ns.AH_CUT)
          local profit = (revenue and not missing) and (revenue - cost) or nil
          rows[#rows + 1] = {
            kind = "craft",
            recipeID = recipeID,
            profession = profession.name,
            name = recipe.name,
            item = output,
            quantity = quantity,
            sell = sellPrice and sellPrice * quantity,
            revenue = revenue,
            listed = listed,
            age = age,
            cost = (not missing) and cost or nil,
            profit = profit,
            parts = parts,
            estimated = estimated,
            missing = missing,
            diff = recipe.diff,
            bound = bound,
          }
        end
      end
    end
  end
  table.sort(rows, ByValue("profit", "name"))
  return rows
end

function Engine:HasRecipes()
  return ns.cdb ~= nil and next(ns.cdb.recipes) ~= nil
end

---------------------------------------------------------------------------
-- Farming
---------------------------------------------------------------------------

-- Expected value of one junkbox: contents at the better of AH or vendor price.
function Engine:JunkboxValue(boxID)
  local box = ns.JUNKBOXES[boxID]
  if not box then
    return nil
  end
  local total, unpriced = 0, false
  for _, content in ipairs(box.contents) do
    local value = ns.ItemSellPrice(content.id) or 0
    if not content.vendorTrash then
      local net = NetPrice(content.id)
      if net then
        value = math.max(value, net)
      else
        unpriced = true
      end
    end
    total = total + value * content.chance
  end
  return total, unpriced
end

function Engine:Farms()
  local settings = ns.db.settings
  local level = UnitLevel("player") or 1
  local _, class = UnitClass("player")
  local faction = UnitFactionGroup("player")
  local skills = ns.Professions:Skills()
  local yield = ns.YIELD
  local rows = {}

  -- Anything up to 4 levels above you (stealth makes those workable). Lower
  -- levels are never hidden: low-level materials can still pay best, and they
  -- rank higher on their own because those mobs die faster (KillsPerHour).
  local function InWindow(minLevel, maxLevel)
    return settings.showAllLevels or minLevel <= level + 4
  end

  -- Typical level of what you'd fight in a band, never above your own.
  local function BandLevel(minLevel, maxLevel)
    return math.min(level, (minLevel + maxLevel) / 2)
  end

  local function Kills(mobLevel)
    return KillsPerHour(level, mobLevel, settings.killsPerHour)
  end

  -- With "Count all loot" on, a mob row also earns everything else that mob
  -- drops (vendor trash, other items) per kill, from your loot and the
  -- community's. Sets row.otherLoot and adds it to row.hour.
  local function AddOtherLoot(row, npcID, kills)
    if not settings.allLoot or not row.each or not npcID then
      return row
    end
    local value, seen = ns.KillLootValue(row.item, ns.Learn:Entry(npcID), ns.COMMUNITY[npcID])
    if seen >= OTHER_LOOT_MIN_KILLS and value > 0 then
      row.otherLoot, row.otherLootKills = value, seen
      row.hour = (row.each + value) * kills
    end
    return row
  end

  -- Specific mobs with valuable drops
  for _, drop in ipairs(ns.MOB_DROPS) do
    if InWindow(drop.min, drop.max) and (not drop.faction or drop.faction == faction) then
      local net, listed, age = NetPrice(drop.item)
      local chance, seenRate, seenTrials = BlendedChance(drop.chance, drop.npc, drop.item, false)
      local each = net and net * chance
      local kills = Kills((drop.min + drop.max) / 2)
      rows[#rows + 1] = AddOtherLoot({
        kind = "Drop", item = drop.item, source = ns.MobName(drop.npc, nil, drop.mob), zone = drop.zone,
        lvl = LevelText(drop.min, drop.max), chance = chance, baseChance = drop.chance, per = "kill",
        seenRate = seenRate, seenTrials = seenTrials, npc = drop.npc, perHour = kills,
        each = each, hour = each and each * kills,
        listed = listed, age = age, note = drop.note, hunt = DropHunt(drop),
      }, drop.npc, kills)
    end
  end

  -- Cloth from any humanoid in range (a rough guess, so only on request)
  for _, cloth in ipairs(settings.showCloth and ns.CLOTH or {}) do
    if InWindow(cloth.min, cloth.max) then
      local net, listed, age = NetPrice(cloth.id)
      local each = net and net * yield.cloth
      local zone = L["Humanoids level "] .. LevelText(cloth.min, cloth.max)
      rows[#rows + 1] = {
        kind = "Cloth", item = cloth.id, source = L["Any humanoid"], zone = zone,
        lvl = LevelText(cloth.min, cloth.max), chanceText = "~" .. yield.cloth, per = "kill",
        each = each, hour = each and each * Kills(BandLevel(cloth.min, cloth.max)),
        listed = listed, age = age, note = L["Cloth per kill is a rough average."],
        hunt = LootHunt("Cloth:" .. cloth.id, "kill", cloth.id, L["Any humanoid"], zone),
      }
    end
  end

  -- Pickpocketing (rogues only)
  if class == "ROGUE" then
    for _, target in ipairs(ns.PICKPOCKET) do
      if InWindow(target.min, target.max) and (not target.faction or target.faction == faction) then
        local boxValue, unpriced = self:JunkboxValue(target.box)
        local chance, seenRate, seenTrials = BlendedChance(target.chance, target.npc, target.box, true)
        local each = boxValue and boxValue * chance
        local note = L["Chance is per pickpocket. Value counts what's in the box, not coin."]
        if unpriced then
          note = note .. L[" Some contents have no AH price yet."]
        end
        rows[#rows + 1] = {
          kind = "Pickpocket", item = target.box, source = ns.MobName(target.npc, nil, target.mob), zone = target.zone,
          lvl = LevelText(target.min, target.max), chance = chance, baseChance = target.chance, per = "pick",
          seenRate = seenRate, seenTrials = seenTrials, npc = target.npc, perHour = settings.picksPerHour,
          each = each, hour = each and each * settings.picksPerHour,
          bound = true, note = note,
          hunt = MobHunt("Pickpocket:" .. target.npc, "pick", target.box, target.chance,
            ns.MobName(target.npc, nil, target.mob),
            target.zone, target.npc, target.spots),
        }
      end
    end
  end

  -- Mobs players have looted (community data plus you) that the list above
  -- doesn't cover
  local gathered = GatheredItems()
  local mobs = {}
  for npcID in pairs(ns.db.drops or {}) do
    mobs[npcID] = true
  end
  for npcID in pairs(ns.COMMUNITY) do
    mobs[npcID] = true
  end
  for npcID in pairs(mobs) do
    local own, shared = ns.Learn:Entry(npcID), ns.COMMUNITY[npcID]
    local kills = ((own and own.k) or 0) + ((shared and shared.k) or 0)
    if kills >= LEARNED_MIN_KILLS and not ns.FARMS_BY_NPC[npcID] then
      local minLevel = (own and own.lmin) or (shared and shared.lmin) or level
      local maxLevel = (own and own.lmax) or (shared and shared.lmax) or minLevel
      if InWindow(minLevel, maxLevel) then
        local zone = MapName((shared and shared.m) or (own and own.m)) or L["where players loot it"]
        local mob = ns.MobName(npcID, own and own.n, shared and shared.n)
        local items = {}
        for itemID in pairs((own and own.i) or {}) do
          items[itemID] = true
        end
        for itemID in pairs((shared and shared.i) or {}) do
          items[itemID] = true
        end
        for itemID in pairs(items) do
          local drops, attempts, perDrop = ns.Learn:Evidence(npcID, itemID, false)
          local bindType = ns.ItemBindType(itemID)
          local _, _, _, _, _, itemClass = ns.GetItemInfoInstant(itemID)
          local rareDrop = RARE_DROP_CLASSES[itemClass] ~= nil
          -- Worth farming: crafting reagents (not food, scrolls or vendor junk),
          -- minus cloth, herbs, ore and leather, which have their own rows; plus
          -- BoE gear and recipes when Rare drops is on.
          local wanted
          if rareDrop then
            wanted = settings.showRareDrops and bindType ~= 1 and bindType ~= 4 and not ns.IsPoorQuality(itemID)
          else
            local facts = ReagentFacts(itemID)
            wanted = facts and not gathered[itemID] and (settings.showRareDrops or not facts.gem)
          end
          if drops >= 1 and wanted then
            local net, listed, age = NetPrice(itemID)
            if net then
              local rate = drops / attempts
              local cautious = drops / (attempts + CAUTION_ATTEMPTS)
              local each = net * cautious * perDrop
              local confidence = Engine.Confidence(attempts)
              local note = (L["Seen %d times in %d kills by GoldScout players."]):format(drops, attempts)
              if confidence.min < 15 then
                note = note .. L[" Gold per hour uses a cautious rate until more kills are recorded."]
              end
              local kills = Kills((minLevel + maxLevel) / 2)
              rows[#rows + 1] = AddOtherLoot({
                kind = "Learned", item = itemID, source = mob, zone = zone,
                lvl = LevelText(minLevel, maxLevel), chance = rate, per = "kill",
                seenRate = rate, seenTrials = attempts, confidence = confidence,
                each = each, hour = each * kills, npc = npcID, perHour = kills,
                listed = listed, age = age,
                note = note,
                hunt = MobHunt("Learned:" .. npcID .. ":" .. itemID, "kill", itemID, rate, mob, zone, npcID, nil),
              }, npcID, kills)
            end
          end
        end
      end
    end
  end

  -- Gathering professions. Without the profession, show what you could gather
  -- at the highest skill your level allows.
  local levelCap = SkillCapForLevel(level)
  local reach = settings.showAllLevels and 300 or math.min(300, (level + 15) * 5)

  local herbalism = skills[ns.SKILL.HERBALISM]
  if herbalism or settings.showOtherProfs then
    local rank = herbalism and herbalism.rank or levelCap
    for _, herb in ipairs(ns.HERBS) do
      if herb.skill <= rank and herb.skill <= reach then
        local net, listed, age = NetPrice(herb.id)
        local each = net and net * yield.herb
        rows[#rows + 1] = {
          kind = "Herb", item = herb.id,
          source = (herbalism and (L["Herbalism"] .. " ") or L["Needs Herbalism "]) .. herb.skill,
          zone = herb.zones, lvl = "-", chanceText = "node", per = "node",
          each = each, hour = each and each * settings.nodesPerHour,
          listed = listed, age = age, needsProfession = not herbalism,
          hunt = LootHunt("Herb:" .. herb.id, "node", herb.id, L["Herb nodes"], herb.zones),
        }
      end
    end
  end

  local mining = skills[ns.SKILL.MINING]
  if mining or settings.showOtherProfs then
    local rank = mining and mining.rank or levelCap
    for _, ore in ipairs(ns.ORES) do
      if ore.skill <= rank and ore.skill <= reach then
        local net, listed, age = NetPrice(ore.id)
        local stoneNet = ore.stone and NetPrice(ore.stone)
        local each = net and (net * yield.ore + (stoneNet or 0) * yield.stone)
        rows[#rows + 1] = {
          kind = "Ore", item = ore.id,
          source = (mining and (L["Mining"] .. " ") or L["Needs Mining "]) .. ore.skill,
          zone = ore.zones, lvl = "-", chanceText = "node", per = "node",
          each = each, hour = each and each * settings.nodesPerHour,
          listed = listed, age = age, needsProfession = not mining,
          note = ore.stone and (L["Includes stone: "] .. ns.ItemName(ore.stone) .. ".") or nil,
          hunt = LootHunt("Ore:" .. ore.id, "node", ore.id, L["Mining nodes"], ore.zones),
        }
      end
    end
  end

  local skinning = skills[ns.SKILL.SKINNING]
  if skinning or settings.showOtherProfs then
    local rank = skinning and skinning.rank or levelCap
    local maxLevel = MaxSkinnableLevel(rank)
    for _, band in ipairs(ns.SKINNING) do
      local top = math.min(band.max, maxLevel)
      if band.min <= maxLevel and InWindow(band.min, top) then
        local net, listed, age = NetPrice(band.leather)
        local hideNet = band.hide and NetPrice(band.hide)
        local each = net and (net * yield.leather + (hideNet or 0) * yield.hide)
        local zone = L["Beasts level "] .. LevelText(band.min, top)
        rows[#rows + 1] = {
          kind = "Skin", item = band.leather,
          source = (skinning and "" or L["Needs Skinning: "]) .. L["skin beasts"],
          zone = zone, lvl = LevelText(band.min, top), chanceText = "skin", per = "skin",
          each = each, hour = each and each * Kills(BandLevel(band.min, top)),
          listed = listed, age = age, needsProfession = not skinning,
          note = L["Skins stack on top of whatever the beast drops."],
          hunt = LootHunt("Skin:" .. band.leather, "skin", band.leather, L["Skinning"], zone),
        }
      end
    end
  end

  FishRows(rows, settings, skills)

  -- Crafting reagents selling on your auction house that no farm above covers.
  -- Without a drop rate there's no hourly estimate, so they rank by price per
  -- item below the farms that have one. Looting them teaches the drop rate.
  if not settings.knownRatesOnly then
    local covered = {}
    for _, row in ipairs(rows) do
      covered[row.item] = true
    end
    -- What any recipe makes counts as crafted too: every recipe output your
    -- characters have seen in a profession window (db.crafted), plus this
    -- character's known recipes.
    local madeByYou = ns.db.crafted or {}
    for _, profession in pairs(ns.cdb.recipes) do
      for _, recipe in pairs(profession.list or {}) do
        if recipe.out then
          madeByYou[recipe.out] = true
        end
      end
    end
    for itemID in pairs(ns.Prices:ItemIDs()) do
      if not covered[itemID] and not gathered[itemID] then
        local facts = ReagentFacts(itemID)
        local itemLevel = facts and facts.level
        -- Crafted and vendor items aren't world drops, unless players have
        -- actually looted one from a mob.
        local notDropped = facts and (facts.crafted or madeByYou[itemID]
          or (ns.COMMUNITY_CRAFTED and ns.COMMUNITY_CRAFTED[itemID])
          or ns.VENDOR_REAGENTS[itemID] or ns.db.vendor[itemID] ~= nil)
        if itemLevel and not (notDropped and not BestSighting(itemID))
            and (settings.showRareDrops or not facts.gem) then
          local above = not InWindow(itemLevel, itemLevel) and not settings.showAllLevels
            and itemLevel > level and itemLevel <= level + MARKET_ABOVE_LEVELS
          if InWindow(itemLevel, itemLevel) or above then
            local net, listed, age = NetPrice(itemID)
            if net then
              local row = {
                kind = "Market", item = itemID, unknownRate = true, itemLevel = itemLevel, above = above,
                source = L["Source unknown"], lvl = "-", chanceText = "?", per = "item",
                each = net, listed = listed, age = age,
                note = L["A crafting reagent that professions need. No drop data yet, so this ranks by price "
                  .. "alone. Loot it (or Hunt it) "
                  .. "and GoldScout learns which mobs drop it and how often."],
                hunt = LootHunt("Market:" .. itemID, "kill", itemID, L["Any source"], L["Wherever it drops"]),
              }
              local npcID, drops, kills = BestSighting(itemID)
              if npcID then
                local own, shared = ns.Learn:Entry(npcID), ns.COMMUNITY[npcID]
                local mob = ns.MobName(npcID, own and own.n, shared and shared.n)
                local zone = MapName((shared and shared.m) or (own and own.m))
                local minLevel = (own and own.lmin) or (shared and shared.lmin)
                row.source = mob
                row.zone = zone
                row.npc = npcID
                if minLevel then
                  row.lvl = LevelText(minLevel, (own and own.lmax) or (shared and shared.lmax) or minLevel)
                end
                row.note = (L["Seen %d times in %d kills of %s."]):format(drops, kills, mob)
                row.hunt = MobHunt("Market:" .. itemID, "kill", itemID, nil, mob, zone, npcID, nil)
              end
              if above then
                row.note = (row.note .. L[" Item level %d: the mobs that drop it are likely above "
                  .. "your level, so this may be a tougher farm."]):format(itemLevel)
              end
              rows[#rows + 1] = row
            end
          end
        end
      end
    end
  end

  ShareHunts(rows)

  -- Mark (and optionally hide) farms by whether their mobs still give experience.
  local shown = {}
  for _, row in ipairs(rows) do
    row.xp = XpStatus(level, row.lvl)
    if not (settings.xpOnly and row.xp == "none") then
      shown[#shown + 1] = row
    end
  end

  -- Farms with an hourly estimate first, then market-only items by price.
  table.sort(shown, function(a, b)
    if a.hour or b.hour then
      if a.hour and b.hour and a.hour ~= b.hour then
        return a.hour > b.hour
      elseif not (a.hour and b.hour) then
        return a.hour ~= nil
      end
    elseif a.each ~= b.each then
      return (a.each or 0) > (b.each or 0)
    end
    return (a.source or "") < (b.source or "")
  end)
  return shown
end

-- The Farm tab's By mob view: the same farms, one row per mob you'd fight,
-- adding up everything worth farming that it drops. Pickpocketing a mob is a
-- row of its own. Farms without a mob (gathering, fishing, cloth) keep their
-- own rows; market items nobody has seen drop are left out. A mob with one
-- farm is just that farm's row. A mob with more gets a group row: kind
-- "Mob", items = its farms best first, each = value per kill (or pick) of
-- all of them, hour = that times kills per hour. `rows` is Farms() output,
-- sorted best first.
function Engine:MobFarms(rows)
  local groups, order = {}, {}
  for _, row in ipairs(rows) do
    local key
    if row.npc then
      key = (row.per == "pick" and "Pick:" or "Mob:") .. row.npc
    elseif row.kind ~= "Market" then
      key = row
    end
    if key then
      local group = groups[key]
      if not group then
        group = {}
        groups[key] = group
        order[#order + 1] = { key = key, rows = group }
      end
      group[#group + 1] = row
    end
  end
  local list = {}
  for _, entry in ipairs(order) do
    local items = entry.rows
    if #items == 1 then
      list[#list + 1] = items[1]
    else
      local first = items[1]
      local each, perHour, skip, otherLoot = 0, nil, {}, nil
      for _, row in ipairs(items) do
        if row.each and not row.unknownRate then
          each = each + row.each
          perHour = perHour or row.perHour
          skip[row.item] = true
          otherLoot = otherLoot or row.otherLoot
        end
      end
      local group = {
        kind = "Mob", mobKey = entry.key, items = items, npc = first.npc, item = first.item, source = first.source,
        zone = first.zone, lvl = first.lvl, xp = first.xp, per = first.per, best = first.each,
      }
      if perHour then
        if otherLoot then
          -- The mob's other loot once, leaving out every item counted above.
          local value, seen = ns.KillLootValue(skip, ns.Learn:Entry(first.npc), ns.COMMUNITY[first.npc])
          if value > 0 then
            group.otherLoot, group.otherLootKills = value, seen
          end
        end
        group.each = each
        group.hour = (each + (group.otherLoot or 0)) * perHour
      else
        group.unknownRate = true
      end
      local hunt = {}
      for field, value in pairs(first.hunt or {}) do
        hunt[field] = value
      end
      hunt.key = entry.key
      group.hunt = first.hunt and hunt or nil
      list[#list + 1] = group
    end
  end
  table.sort(list, function(a, b)
    if a.hour or b.hour then
      if a.hour and b.hour and a.hour ~= b.hour then
        return a.hour > b.hour
      elseif not (a.hour and b.hour) then
        return a.hour ~= nil
      end
    else
      local x, y = a.best or a.each or 0, b.best or b.each or 0
      if x ~= y then
        return x > y
      end
    end
    return (a.source or "") < (b.source or "")
  end)
  return list
end
