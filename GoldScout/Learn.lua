-- GoldScout loot learning: records what each mob actually drops for you, on
-- every character, so farm rankings improve the more you play.
--
-- It only reads the loot window after you open it yourself. GoldScout never
-- loots, targets or clicks anything for you, and it skips any value the game
-- marks as secret.
local _, ns = ...

local Learn = {}
ns.Learn = Learn

local ITEM_SLOT = (Enum.LootSlotType and Enum.LootSlotType.Item) or 1

-- Export format. Version 5 adds the game's language (@l, so shared names stay
-- English) and where mobs were looted (@a). GoldScout Companion before 0.10.0
-- refuses version 5, and leaves its version out of the GoldScout_Prices file it
-- writes; for a player with such a companion GoldScout keeps writing version 4
-- until it's updated. Nothing is lost meanwhile: every export holds everything
-- learned so far. Companions from 0.10.0 on share any newer format as it is.
local EXPORT_VERSION = 5
local COMPANION_FOR_V5 = { 0, 10, 0 }

local function ExportVersion()
  local data = GoldScoutPricesData
  if type(data) ~= "table" or type(data.markets) ~= "table" then
    return EXPORT_VERSION     -- no companion writing prices here (or the share form)
  end
  local major, minor, patch = tostring(data.companion or ""):match("^(%d+)%.(%d+)%.(%d+)")
  local version = { tonumber(major) or 0, tonumber(minor) or 0, tonumber(patch) or 0 }
  for i = 1, 3 do
    if version[i] ~= COMPANION_FOR_V5[i] then
      return version[i] > COMPANION_FOR_V5[i] and EXPORT_VERSION or 4
    end
  end
  return EXPORT_VERSION
end

-- Where a mob is looted, as squares of a 20x20 grid over its zone map (each
-- square is 5% of the map's width and height): enough to draw the area a hunt
-- covers on the world map, without keeping exact positions. Cell = row * 20 + column.
local AREA_GRID = 20

local function AreaCell(x, y)
  local column = math.min(AREA_GRID - 1, math.max(0, math.floor(x * AREA_GRID)))
  local row = math.min(AREA_GRID - 1, math.max(0, math.floor(y * AREA_GRID)))
  return row * AREA_GRID + column
end

-- Fishing: a loot window from fishing names its source as the bobber you cast
-- (open water, spot 0) or the fishing pool the bobber landed in (that pool's
-- object ID, so each kind of pool is its own spot). Catches are kept per zone
-- and spot in GoldScoutDB.fish, with what came up and where you stood.
local FISHING_BOBBER = 35591
local OPEN_WATER = 0
local MAX_EXPORT_CATCHES = 5000   -- tools/submission.py's limit per spot

-- GUIDs stay stable for a play session, so each corpse, pickpocket or node is
-- counted once even if you reopen its loot (or skin it afterwards).
local counted = {}
local window -- the loot window that is open right now

-- Kills counted when the mob died, before (or without) its loot window. If you
-- do loot the corpse, its drops still count but the kill isn't counted twice.
local pendingDrops = {}
local judgedDeaths = {}

-- When you last cast Skinning, Herb Gathering or Mining: a corpse's loot
-- window that opens right after is gathering, not the mob's drops. (Some
-- creatures can be herb-gathered or mined, not only skinned.)
local GATHER_SPELLS = {
  [8613] = true,  -- Skinning
  [2366] = true,  -- Herb Gathering
  [2575] = true,  -- Mining
}
local GATHER_SECONDS = 3
local lastGatherCast = -math.huge

-- What gathering gives: leather, hides and scraps, herbs, ore and stone. A
-- creature loot window with nothing else in it is gathering, even if the cast
-- went unseen.
local gatherProducts
local function IsGatherProduct(itemID)
  if not gatherProducts then
    gatherProducts = { [2934] = true } -- Ruined Leather Scraps
    for _, band in ipairs(ns.SKINNING or {}) do
      gatherProducts[band.leather] = true
      if band.hide then
        gatherProducts[band.hide] = true
      end
    end
    for _, herb in ipairs(ns.HERBS or {}) do
      gatherProducts[herb.id] = true
    end
    for _, ore in ipairs(ns.ORES or {}) do
      gatherProducts[ore.id] = true
      if ore.stone then
        gatherProducts[ore.stone] = true
      end
    end
  end
  return gatherProducts[itemID] == true
end

-- "Creature-0-server-instance-zone-npcID-spawn" -> "Creature", npcID
function ns.ParseGUID(guid)
  guid = ns.Plain(guid)
  if type(guid) ~= "string" then
    return nil
  end
  local kind, _, _, _, _, id = strsplit("-", guid)
  return kind, tonumber(id)
end

local function Entry(npcID, create)
  local drops = ns.db and ns.db.drops
  if not drops or not npcID then
    return nil
  end
  local entry = drops[npcID]
  if not entry and create then
    entry = { k = 0, p = 0, i = {}, pi = {} }
    drops[npcID] = entry
  end
  return entry
end

function Learn:Entry(npcID)
  return Entry(npcID, false)
end

-- Your own drop rate for an item from a mob: rate, attempts, average stack.
-- Pass pick = true for pickpocket results instead of corpse loot.
function Learn:Rate(npcID, itemID, pick)
  local entry = Entry(npcID, false)
  if not entry then
    return nil, 0
  end
  local attempts = (pick and entry.p or entry.k) or 0
  if attempts == 0 then
    return nil, 0
  end
  local stat = (pick and entry.pi or entry.i)[itemID]
  local drops = stat and stat.d or 0
  local perDrop = (drops > 0) and stat.q / drops or 1
  return drops / attempts, attempts, perDrop
end

-- Everything players have recorded for an item from a mob: the shipped
-- community data plus your own loot. Returns drops, attempts, average stack.
function Learn:Evidence(npcID, itemID, pick)
  local drops, attempts, quantity = 0, 0, 0
  local function Add(entry)
    if not entry then
      return
    end
    attempts = attempts + ((pick and entry.p or entry.k) or 0)
    local items = pick and entry.pi or entry.i
    local stat = items and items[itemID]
    if stat then
      drops = drops + (stat.d or 0)
      quantity = quantity + (stat.q or 0)
    end
  end
  Add(Entry(npcID, false))
  Add(ns.COMMUNITY[npcID])
  return drops, attempts, (drops > 0) and quantity / drops or 1
end

-- Your learned data as text for /gscout export. One line per mob:
-- npcID^kills^picks^minLevel^maxLevel^uiMapID^x^y^positions^name^drops^pickDrops
-- where drops are "itemID:times:quantity" joined by commas. No character names.
-- Mob names keep letters (including accented ones), digits, spaces and a few
-- punctuation marks; anything else would make the data bot reject the export.
local function Clean(text)
  text = tostring(text or ""):gsub("[^%w '%-%.%(%)!%?&\128-\255]", " ")
  return (text:gsub("%s+", " "):gsub("^ ", ""):gsub(" $", ""))
end

-- Item and zone names can also hold colons and commas ("Pattern: Hillman's
-- Cloak"); only the field separator, escapes and line breaks are dropped.
local function CleanName(text)
  text = tostring(text or ""):gsub("[^%w '%-%.%(%)!%?&:,\128-\255]", " ")
  text = text:gsub("%s+", " "):gsub("^ ", ""):gsub(" $", "")
  return text:sub(1, 64)
end

local function Names()
  return ns.db and ns.db.names
end

-- Remembers an item's name (from a loot link or the client's item cache).
local function NoteItemName(itemID, name)
  local names = Names()
  if not names or not itemID then
    return
  end
  name = ns.Plain(name)
  if type(name) ~= "string" or name == "" then
    local quick = C_Item and C_Item.GetItemNameByID and ns.Plain(C_Item.GetItemNameByID(itemID))
    name = type(quick) == "string" and quick or (ns.GetItemInfo and ns.Plain((ns.GetItemInfo(itemID))))
  end
  if type(name) == "string" and name ~= "" and not name:find("^Item %d+$") then
    names.items[itemID] = CleanName(name)
  end
end

local function NoteMapName(mapID)
  local names = Names()
  if not names or not mapID or names.maps[mapID] then
    return
  end
  local info = C_Map and C_Map.GetMapInfo and C_Map.GetMapInfo(mapID)
  local name = info and ns.Plain(info.name)
  if type(name) == "string" and name ~= "" then
    names.maps[mapID] = CleanName(name)
  end
end

-- Drops can't outnumber attempts (one corpse can hold two stacks of an item),
-- so counts are clamped to keep every export valid.
local function SortedKeys(table_)
  local keys = {}
  for key in pairs(table_ or {}) do
    keys[#keys + 1] = key
  end
  table.sort(keys)
  return keys
end

local function ItemList(items, attempts)
  local parts = {}
  for _, itemID in ipairs(SortedKeys(items)) do
    local stat = items[itemID]
    local drops = math.min(stat.d or 0, attempts)
    if drops > 0 then
      parts[#parts + 1] = itemID .. ":" .. drops .. ":" .. math.max(stat.q or 0, drops)
    end
  end
  return table.concat(parts, ",")
end

-- How many export snapshots to keep besides the one the community data has.
local KEEP_SNAPSHOTS = 10
local ID_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789"

-- A random ID for this WoW account's GoldScout data. It isn't derived from
-- anything about you; it only lets your client recognize its own exports.
local function NewInstallID()
  local chars = {}
  for i = 1, 12 do
    local n = math.random(1, #ID_CHARS)
    chars[i] = ID_CHARS:sub(n, n)
  end
  return table.concat(chars)
end

-- Remembers an item's quality, class and Crafting Reagent flag as
-- "quality:class:reagent" (reagent 1, 0, or x when the client doesn't say).
-- Kept in saved data so exports stay identical when the item cache empties.
local function NoteItemMeta(itemID)
  local names = Names()
  if not names or not itemID then
    return
  end
  names.meta = names.meta or {}
  if not ns.GetItemInfo then
    return
  end
  local info = { ns.GetItemInfo(itemID) }
  local quality, classID, reagent = ns.Plain(info[3]), ns.Plain(info[12]), ns.Plain(info[17])
  if type(quality) ~= "number" or type(classID) ~= "number" then
    return
  end
  local flag = (reagent == true and "1") or (reagent == false and "0") or "x"
  names.meta[itemID] = ("%d:%d:%s"):format(quality, classID, flag)
end

-- The lines of an export, in a fixed order so unchanged data gives identical
-- text: one per mob, then the names of the items and zones they mention
-- ("@i^itemID^name", "@m^uiMapID^name"), what kind of item each is
-- ("@q^itemID^quality:class:reagent"), then every item a recipe makes
-- ("@c^itemID^"), which players' Market rows leave out. Version 5 adds the
-- grid squares each mob was looted in ("@a^npcID^cell:count,...") and the
-- game's language ("@l^0^enUS"), and what was fished up, one line per zone
-- and spot ("@f^uiMapID^spot^catches^skill^items^cells").
local function FishLines(items, maps)
  local lines = {}
  local fish = (ns.db and ns.db.fish) or {}
  for _, map in ipairs(SortedKeys(fish)) do
    for _, spot in ipairs(SortedKeys(fish[map])) do
      local entry = fish[map][spot]
      local catches = entry.n or 0
      if catches > 0 then
        -- A very long session at one spot is scaled down to the shared limit.
        local factor = math.min(1, MAX_EXPORT_CATCHES / catches)
        local scaled = {}
        for itemID, stat in pairs(entry.i or {}) do
          local times = math.floor(stat.d * factor + 0.5)
          if times > 0 then
            scaled[itemID] = { d = times, q = math.max(times, math.floor(stat.q * factor + 0.5)) }
          end
        end
        catches = math.min(catches, MAX_EXPORT_CATCHES)
        local cells, placed = {}, 0
        for _, cell in ipairs(SortedKeys(entry.a)) do
          local count = math.floor(entry.a[cell] * factor + 0.5)
          if count > 0 and placed + count <= catches then
            cells[#cells + 1] = cell .. ":" .. count
            placed = placed + count
          end
        end
        local itemList = ItemList(scaled, catches)
        lines[#lines + 1] = table.concat({ "@f", map, spot, catches, entry.s or 0, itemList,
          table.concat(cells, ",") }, "^")
        for itemID in itemList:gmatch("(%d+):%d+:%d+") do
          items[tonumber(itemID)] = true
        end
        maps[map] = true
      end
    end
  end
  return lines
end

local function ExportBody()
  local drops = (ns.db and ns.db.drops) or {}
  local names = Names() or { items = {}, maps = {} }
  local lines, items, maps, areas = {}, {}, {}, {}
  for _, npcID in ipairs(SortedKeys(drops)) do
    local entry = drops[npcID]
    local kills, picks = entry.k or 0, entry.p or 0
    if kills + picks > 0 then
      local map, count, x, y = entry.m or 0, math.min(entry.c or 0, kills), 0, 0
      if map > 0 and count > 0 then
        x, y = entry.sx / entry.c, entry.sy / entry.c
      else
        map, count = 0, 0
      end
      local lmin, lmax = entry.lmin or 0, entry.lmax or 0
      if lmin == 0 or lmax == 0 or lmax - lmin > 15 or lmax > 63 then
        lmin, lmax = 0, 0
      end
      if map > 0 and type(entry.a) == "table" then
        local cells = {}
        for _, cell in ipairs(SortedKeys(entry.a)) do
          cells[#cells + 1] = cell .. ":" .. entry.a[cell]
        end
        if #cells > 0 then
          areas[#areas + 1] = "@a^" .. npcID .. "^" .. table.concat(cells, ",")
        end
      end
      local dropList, pickList = ItemList(entry.i, kills), ItemList(entry.pi, picks)
      lines[#lines + 1] = table.concat({
        npcID, kills, picks, lmin, lmax, map,
        ("%.4f"):format(x), ("%.4f"):format(y), count, Clean(entry.n), dropList, pickList,
      }, "^")
      for itemID in (dropList .. "," .. pickList):gmatch("(%d+):%d+:%d+") do
        items[tonumber(itemID)] = true
      end
      if map > 0 then
        maps[map] = true
      end
    end
  end
  local mobs = #lines
  local fishLines = ExportVersion() >= 5 and FishLines(items, maps) or {}
  for _, itemID in ipairs(SortedKeys(items)) do
    if not names.items[itemID] then
      NoteItemName(itemID)
    end
    if names.items[itemID] and names.items[itemID] ~= "" then
      lines[#lines + 1] = "@i^" .. itemID .. "^" .. names.items[itemID]
    end
  end
  -- What kind of item each is ("@q^itemID^quality:class:reagent"), so the
  -- website can tell crafting reagents from food, gear and gray junk.
  local meta = names.meta or {}
  for _, itemID in ipairs(SortedKeys(items)) do
    if not meta[itemID] then
      NoteItemMeta(itemID)
    end
    if meta[itemID] then
      lines[#lines + 1] = "@q^" .. itemID .. "^" .. meta[itemID]
    end
  end
  for _, mapID in ipairs(SortedKeys(maps)) do
    NoteMapName(mapID)
    if names.maps[mapID] and names.maps[mapID] ~= "" then
      lines[#lines + 1] = "@m^" .. mapID .. "^" .. names.maps[mapID]
    end
  end
  for _, itemID in ipairs(SortedKeys((ns.db and ns.db.crafted) or {})) do
    lines[#lines + 1] = "@c^" .. itemID .. "^"
  end
  if ExportVersion() >= 5 then
    for _, line in ipairs(areas) do
      lines[#lines + 1] = line
    end
    for _, line in ipairs(fishLines) do
      lines[#lines + 1] = line
    end
    lines[#lines + 1] = "@l^0^" .. (ns.LOCALE or "enUS")
  end
  return table.concat(lines, "\n"), mobs, #fishLines
end

-- Saves the current export as a numbered snapshot (a new number only when the
-- data changed) and returns its full text, mob count and fishing spot count. The companion app
-- shares the latest snapshot, and the community data records which snapshot
-- it includes, so your client can take exactly that back out.
function Learn:Snapshot()
  local db = ns.db
  if not db then
    return nil, 0, 0
  end
  local body, count, spots = ExportBody()
  if count + spots == 0 then
    return nil, 0, 0
  end
  local exports = db.exports
  local latest = exports.list[exports.seq]
  if not (latest and latest:match("^[^\n]*\n(.*)$") == body) then
    exports.seq = exports.seq + 1
    exports.list[exports.seq] = ("GoldScout-export %d^%s^%d\n%s"):format(ExportVersion(), db.installID,
      exports.seq, body)
    local included = ns.COMMUNITY_SOURCES and ns.COMMUNITY_SOURCES[db.installID]
    for seq in pairs(exports.list) do
      if seq ~= included and seq <= exports.seq - KEEP_SNAPSHOTS then
        exports.list[seq] = nil
      end
    end
  end
  return exports.list[exports.seq], count, spots
end

function Learn:ExportString()
  return self:Snapshot()
end

-- On load: give this account an install ID, then take your own shared loot
-- back out of the community data so it isn't counted twice.
ns.Listen("DB_READY", function()
  local db = ns.db
  db.installID = db.installID or NewInstallID()
  db.exports = db.exports or { seq = 0, list = {} }
  db.crafted = db.crafted or {}
  db.names = db.names or {}
  db.names.items = db.names.items or {}
  db.names.maps = db.names.maps or {}
  db.names.meta = db.names.meta or {}
  db.fish = db.fish or {}
  ns.COMMUNITY_FISH = ns.COMMUNITY_FISH or {}
  Learn.ownShared = ns.Community.RemoveOwn(ns.COMMUNITY, ns.COMMUNITY_SOURCES, ns.COMMUNITY_CAP,
    db.installID, db.exports, db.drops, ns.COMMUNITY_FISH, db.fish)
end)

-- Keep the latest snapshot current for the companion app, which reads it
-- from the saved data the game writes when you log out or /reload.
ns.On("PLAYER_LOGOUT", function()
  if ns.db and ns.db.settings.learnDrops then
    Learn:Snapshot()
  end
end)

-- Average spot where you've looted this mob: uiMapID, x, y in map percent.
function Learn:Spot(npcID)
  local entry = Entry(npcID, false)
  if not entry or not entry.m or (entry.c or 0) == 0 then
    return nil
  end
  return entry.m, entry.sx / entry.c * 100, entry.sy / entry.c * 100
end

-- Remembers a mob's name and level whenever we get a clear look at it.
function Learn:NoteUnit(npcID, name, level)
  local entry = Entry(npcID, false)
  if not entry then
    return
  end
  name, level = ns.Plain(name), ns.Plain(level)
  if type(name) == "string" and name ~= "" then
    entry.n = name
  end
  if type(level) == "number" and level > 0 then
    entry.lmin = math.min(entry.lmin or level, level)
    entry.lmax = math.max(entry.lmax or level, level)
  end
end

-- Your zone map and position on it (0-1), or nil when the game doesn't say.
-- x and y are nil when only the zone is known.
local function PlayerSpot()
  if not C_Map or not C_Map.GetBestMapForUnit or not C_Map.GetPlayerMapPosition then
    return nil
  end
  local map = ns.Plain(C_Map.GetBestMapForUnit("player"))
  if type(map) ~= "number" then
    return nil
  end
  local position = C_Map.GetPlayerMapPosition(map, "player")
  if not position then
    return map
  end
  local x, y = position:GetXY()
  x, y = ns.Plain(x), ns.Plain(y)
  if type(x) ~= "number" or type(y) ~= "number" or (x == 0 and y == 0) then
    return map
  end
  return map, x, y
end

local function NotePosition(entry)
  local map, x, y = PlayerSpot()
  if not x then
    return
  end
  if entry.m ~= map then
    if (entry.c or 0) >= 5 then
      return -- stick with the zone we've seen it in most
    end
    entry.m, entry.sx, entry.sy, entry.c, entry.a = map, 0, 0, 0, {}
  end
  entry.sx = entry.sx + x
  entry.sy = entry.sy + y
  entry.c = entry.c + 1
  entry.a = entry.a or {}
  local cell = AreaCell(x, y)
  entry.a[cell] = (entry.a[cell] or 0) + 1
  NoteMapName(map)
end

-- Everything fished up so far: { [uiMapID] = { [spot] = { n, s, i, a } } }.
function Learn:Fish()
  return (ns.db and ns.db.fish) or {}
end

-- One fishing loot window: counts the catch where you are, with what's in it.
local function RecordCatch(spot, slots)
  local map, x, y = PlayerSpot()
  if not map or not ns.db or not ns.db.fish then
    return
  end
  local zone = ns.db.fish[map] or {}
  ns.db.fish[map] = zone
  local entry = zone[spot]
  if not entry then
    entry = { n = 0, i = {}, a = {} }
    zone[spot] = entry
  end
  entry.n = entry.n + 1
  local skill = ns.Professions and ns.Professions:Skills()[ns.SKILL.FISHING]
  local rank = skill and ns.Plain(skill.rank)
  if type(rank) == "number" and rank > 0 then
    entry.s = math.min(entry.s or rank, rank)
  end
  if x then
    local cell = AreaCell(x, y)
    entry.a[cell] = (entry.a[cell] or 0) + 1
  end
  -- An item counts once per catch however many slots it fills.
  local caught = {}
  for _, slotInfo in pairs(slots) do
    if slotInfo.item then
      caught[slotInfo.item] = (caught[slotInfo.item] or 0) + slotInfo.quantity
      NoteItemName(slotInfo.item, slotInfo.name)
      NoteItemMeta(slotInfo.item)
    end
  end
  for itemID, quantity in pairs(caught) do
    local stat = entry.i[itemID]
    if not stat then
      stat = { d = 0, q = 0 }
      entry.i[itemID] = stat
    end
    stat.d = stat.d + 1
    stat.q = stat.q + quantity
  end
  NoteMapName(map)
end

local function RecordDrop(npcID, role, itemID, quantity)
  local entry = Entry(npcID, true)
  local items = (role == "pick") and entry.pi or entry.i
  local stat = items[itemID]
  if not stat then
    stat = { d = 0, q = 0 }
    items[itemID] = stat
  end
  stat.d = stat.d + 1
  stat.q = stat.q + quantity
end

---------------------------------------------------------------------------
-- Reading the loot window
---------------------------------------------------------------------------
local function SourceRole(kind, guid, targetGUID, targetAlive, fishing, gathering)
  if fishing then
    return "fish"
  elseif kind == "Creature" or kind == "Vehicle" then
    -- Looting a living target means you just picked its pocket.
    if targetAlive and guid == targetGUID then
      return "pick"
    end
    if gathering then
      return "gather"
    end
    return "kill"
  elseif kind == "GameObject" then
    return "node"
  end
  return "other"
end

local function ReadWindow()
  local targetGUID = ns.Plain(UnitGUID("target"))
  -- If the game hides whether the target is dead, assume it's a corpse.
  local targetAlive = targetGUID ~= nil and ns.Plain(UnitIsDead("target")) == false
  local fishing = (IsFishingLoot and IsFishingLoot()) or false
  local gathering = GetTime() - lastGatherCast <= GATHER_SECONDS
  local result = { slots = {}, sources = {}, fishing = fishing, spot = OPEN_WATER }

  -- A window holding only gathering products is gathering as well.
  local count, allGathered = GetNumLootItems() or 0, true
  for slot = 1, count do
    local link = GetLootSlotType(slot) == ITEM_SLOT and GetLootSlotLink(slot)
    local itemID = link and tonumber(link:match("item:(%d+)"))
    if not itemID or not IsGatherProduct(itemID) then
      allGathered = false
    end
  end
  gathering = gathering or (count > 0 and allGathered)

  for slot = 1, count do
    local slotInfo = { sources = {} }
    if GetLootSlotType(slot) == ITEM_SLOT then
      local link = GetLootSlotLink(slot)
      slotInfo.item = link and tonumber(link:match("item:(%d+)"))
      slotInfo.name = link and link:match("%[(.-)%]")
      local _, _, quantity = GetLootSlotInfo(slot)
      quantity = ns.Plain(quantity)
      slotInfo.quantity = (type(quantity) == "number" and quantity > 0) and quantity or 1
    end

    local sourceList = { GetLootSourceInfo(slot) }
    for i = 1, #sourceList, 2 do
      local guid, quantity = ns.Plain(sourceList[i]), ns.Plain(sourceList[i + 1])
      if type(guid) == "string" then
        slotInfo.sources[#slotInfo.sources + 1] = { guid = guid, quantity = (type(quantity) == "number") and quantity or nil }
        if not result.sources[guid] then
          local kind, id = ns.ParseGUID(guid)
          if fishing and kind == "GameObject" and id and id ~= FISHING_BOBBER then
            result.spot = id   -- the bobber landed in a fishing pool
          end
          local role = SourceRole(kind, guid, targetGUID, targetAlive, fishing, gathering)
          local key = guid .. ":" .. role
          result.sources[guid] = {
            id = id, role = role, key = key, new = not counted[key], isTarget = (guid == targetGUID),
            pending = role == "kill" and pendingDrops[guid] == true,
          }
        end
      end
    end
    result.slots[slot] = slotInfo
  end
  return result
end

local function OnLootReady()
  if window or not ns.db then
    return
  end
  window = ReadWindow()
  local learn = ns.db.settings.learnDrops
  if window.fishing then
    -- One loot window per catch; it stays open (window set) until it closes.
    if learn then
      RecordCatch(window.spot, window.slots)
    end
    ns.Fire("LOOT_ACTION", "catch", window.spot)
    for _, slotInfo in pairs(window.slots) do
      if slotInfo.item then
        ns.Fire("LOOT_DROP", "catch", window.spot, slotInfo.item, slotInfo.quantity)
      end
    end
    return
  end
  for guid, source in pairs(window.sources) do
    if source.pending then
      -- Counted when it died; its drops still count now.
      pendingDrops[guid] = nil
      source.records = true
    elseif source.new then
      counted[source.key] = true
      source.records = true
      local isMob = source.role == "kill" or source.role == "pick"
      if isMob and source.id and learn then
        local entry = Entry(source.id, true)
        if source.role == "kill" then
          entry.k = entry.k + 1
          NotePosition(entry)
        else
          entry.p = entry.p + 1
        end
        if source.isTarget then
          Learn:NoteUnit(source.id, UnitName("target"), UnitLevel("target"))
        end
      end
      ns.Fire("LOOT_ACTION", source.role, source.id)
    end
  end
end

local function OnSlotCleared(slot)
  local slotInfo = window and window.slots[slot]
  if not slotInfo or slotInfo.cleared then
    return
  end
  slotInfo.cleared = true
  if not slotInfo.item then
    return
  end
  ns.Fire("LOOT_GAINED", slotInfo.item, slotInfo.quantity)
  for _, slotSource in ipairs(slotInfo.sources) do
    local source = window.sources[slotSource.guid]
    if source and source.records and source.id and (source.role == "kill" or source.role == "pick") then
      local quantity = slotSource.quantity or slotInfo.quantity
      if ns.db.settings.learnDrops then
        RecordDrop(source.id, source.role, slotInfo.item, quantity)
        NoteItemName(slotInfo.item, slotInfo.name)
        NoteItemMeta(slotInfo.item)
      end
      ns.Fire("LOOT_DROP", source.role, source.id, slotInfo.item, quantity)
    end
  end
end

ns.On("LOOT_READY", OnLootReady)
ns.On("LOOT_OPENED", OnLootReady)
ns.On("LOOT_SLOT_CLEARED", OnSlotCleared)
ns.On("LOOT_CLOSED", function()
  window = nil
  ns.Debounce("lootLearned", 2, function()
    ns.Fire("LOOT_LEARNED")
  end)
end)

---------------------------------------------------------------------------
-- Gathering casts (Skinning, Herb Gathering, Mining)
---------------------------------------------------------------------------
local function SpellName(spellID)
  local name = C_Spell and C_Spell.GetSpellName and C_Spell.GetSpellName(spellID)
  if name == nil and GetSpellInfo then
    name = GetSpellInfo(spellID)
  end
  return ns.Plain(name)
end

-- The gathering spells' names in this client's language, so higher ranks and
-- this client's own spell IDs match too.
local gatherNames
local function IsGatherSpell(spellID)
  if GATHER_SPELLS[spellID] then
    return true
  end
  if not gatherNames then
    gatherNames = {}
    for id in pairs(GATHER_SPELLS) do
      local name = SpellName(id)
      if type(name) == "string" then
        gatherNames[name] = true
      end
    end
  end
  local name = SpellName(spellID)
  return type(name) == "string" and gatherNames[name] == true
end

ns.On("UNIT_SPELLCAST_SUCCEEDED", function(unit, _, spellID)
  if unit ~= "player" then
    return
  end
  spellID = ns.Plain(spellID)
  if type(spellID) ~= "number" then
    return
  end
  if IsGatherSpell(spellID) then
    lastGatherCast = GetTime()
  end
end)

---------------------------------------------------------------------------
-- Kills whose corpse has no loot
---------------------------------------------------------------------------
-- A corpse with nothing on it never opens a loot window, so without this the
-- kill would never be counted and every drop rate would look too high. When a
-- mob you tagged dies while you're solo, GoldScout checks its corpse a moment
-- later; with no loot on it, the kill counts right away. (In a group, others
-- loot your kills, so only opened corpses count.)
local function JudgeDeath(guid, npcID, name, level)
  if counted[guid .. ":kill"] then
    return -- already looted
  end
  local hasLoot
  if CanLootUnit then
    local ok, result = pcall(CanLootUnit, guid)
    hasLoot = ok and ns.Plain(result) or nil
  end
  if hasLoot == true then
    return -- the loot window will count it when you open the corpse
  end
  counted[guid .. ":kill"] = true
  pendingDrops[guid] = true -- if you do loot it after all, its drops still count
  local entry = Entry(npcID, true)
  entry.k = entry.k + 1
  NotePosition(entry)
  Learn:NoteUnit(npcID, name, level)
  ns.Fire("LOOT_ACTION", "kill", npcID)
  ns.Debounce("lootLearned", 2, function()
    ns.Fire("LOOT_LEARNED")
  end)
end

ns.On("UNIT_HEALTH", function(unit)
  if not ns.db or not ns.db.settings.learnDrops or type(unit) ~= "string" then
    return
  end
  if unit ~= "target" and unit ~= "focus" and unit ~= "mouseover" and not unit:find("^nameplate") then
    return
  end
  if ns.Plain(UnitIsDead(unit)) ~= true then
    return
  end
  local guid = ns.Plain(UnitGUID(unit))
  if type(guid) ~= "string" or judgedDeaths[guid] then
    return
  end
  judgedDeaths[guid] = true
  local kind, npcID = ns.ParseGUID(guid)
  if kind ~= "Creature" or not npcID or (IsInGroup and IsInGroup()) then
    return
  end
  -- Only mobs you tagged: their loot is yours.
  if not UnitIsTapDenied or ns.Plain(UnitIsTapDenied(unit)) ~= false then
    return
  end
  local name, level = UnitName(unit), UnitLevel(unit)
  C_Timer.After(1.5, function()
    JudgeDeath(guid, npcID, name, level)
  end)
end)
