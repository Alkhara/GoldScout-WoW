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

-- GUIDs stay stable for a play session, so each corpse, pickpocket or node is
-- counted once even if you reopen its loot (or skin it afterwards).
local counted = {}
local window -- the loot window that is open right now

-- Kills counted when the mob died, before (or without) its loot window. If you
-- do loot the corpse, its drops still count but the kill isn't counted twice.
local pendingDrops = {}
local judgedDeaths = {}

-- When you last cast Skinning: a corpse's loot window that opens right after
-- is the skin, not the mob's drops.
local SKINNING_SPELL = 8613
local SKIN_SECONDS = 3
local lastSkinCast = -math.huge

-- Leather, hides and scraps: what skinning gives. A creature loot window with
-- nothing else in it is a skin, even if the Skinning cast went unseen.
local skinProducts
local function IsSkinProduct(itemID)
  if not skinProducts then
    skinProducts = { [2934] = true } -- Ruined Leather Scraps
    for _, band in ipairs(ns.SKINNING or {}) do
      skinProducts[band.leather] = true
      if band.hide then
        skinProducts[band.hide] = true
      end
    end
  end
  return skinProducts[itemID] == true
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

-- The lines of an export, in a fixed order so unchanged data gives identical
-- text: one per mob, then the names of the items and zones they mention
-- ("@i^itemID^name", "@m^uiMapID^name"), then every item a recipe makes
-- ("@c^itemID^"), which players' Market rows leave out.
local function ExportBody()
  local drops = (ns.db and ns.db.drops) or {}
  local names = Names() or { items = {}, maps = {} }
  local lines, items, maps = {}, {}, {}
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
  for _, itemID in ipairs(SortedKeys(items)) do
    if not names.items[itemID] then
      NoteItemName(itemID)
    end
    if names.items[itemID] and names.items[itemID] ~= "" then
      lines[#lines + 1] = "@i^" .. itemID .. "^" .. names.items[itemID]
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
  return table.concat(lines, "\n"), mobs
end

-- Saves the current export as a numbered snapshot (a new number only when the
-- data changed) and returns its full text and mob count. The companion app
-- shares the latest snapshot, and the community data records which snapshot
-- it includes, so your client can take exactly that back out.
function Learn:Snapshot()
  local db = ns.db
  if not db then
    return nil, 0
  end
  local body, count = ExportBody()
  if count == 0 then
    return nil, 0
  end
  local exports = db.exports
  local latest = exports.list[exports.seq]
  if not (latest and latest:match("^[^\n]*\n(.*)$") == body) then
    exports.seq = exports.seq + 1
    exports.list[exports.seq] = ("GoldScout-export 3^%s^%d\n%s"):format(db.installID, exports.seq, body)
    local included = ns.COMMUNITY_SOURCES and ns.COMMUNITY_SOURCES[db.installID]
    for seq in pairs(exports.list) do
      if seq ~= included and seq <= exports.seq - KEEP_SNAPSHOTS then
        exports.list[seq] = nil
      end
    end
  end
  return exports.list[exports.seq], count
end

function Learn:ExportString()
  return self:Snapshot()
end

-- On load: give this account an install ID, then take your own shared loot
-- back out of the community data so it isn't counted twice.
-- One-time repair: before GoldScout recognized skinning, a corpse skinned
-- after a /reload (or without looting it first) counted as a new kill, with
-- the leather or scraps recorded as its drops. Each such window holds only
-- skinning products, so the most-recorded skinning product per mob is the
-- number of false kills: take those kills and items back out.
local function RepairSkinningKills(drops)
  for npcID, entry in pairs(drops) do
    local phantom = 0
    for itemID, stat in pairs(entry.i or {}) do
      if IsSkinProduct(itemID) then
        phantom = math.max(phantom, stat.d or 0)
        entry.i[itemID] = nil
      end
    end
    if phantom > 0 then
      local kills = entry.k or 0
      local kept = math.max(0, kills - phantom)
      if (entry.c or 0) > 0 and kills > 0 then
        local scale = kept / kills
        entry.sx, entry.sy = (entry.sx or 0) * scale, (entry.sy or 0) * scale
        entry.c = math.floor((entry.c or 0) * scale + 0.5)
        if entry.c == 0 then
          entry.m, entry.sx, entry.sy = nil, 0, 0
        end
      end
      entry.k = kept
      if kept == 0 and (entry.p or 0) == 0 then
        drops[npcID] = nil
      end
    end
  end
end
Learn.RepairSkinningKills = RepairSkinningKills

ns.Listen("DB_READY", function()
  local db = ns.db
  if (db.repairs or 0) < 1 then
    RepairSkinningKills(db.drops or {})
    db.repairs = 1
  end
  db.installID = db.installID or NewInstallID()
  db.exports = db.exports or { seq = 0, list = {} }
  db.crafted = db.crafted or {}
  db.names = db.names or {}
  db.names.items = db.names.items or {}
  db.names.maps = db.names.maps or {}
  Learn.ownShared = ns.Community.RemoveOwn(ns.COMMUNITY, ns.COMMUNITY_SOURCES, ns.COMMUNITY_CAP,
    db.installID, db.exports, db.drops)
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

local function NotePosition(entry)
  if not C_Map or not C_Map.GetBestMapForUnit or not C_Map.GetPlayerMapPosition then
    return
  end
  local map = ns.Plain(C_Map.GetBestMapForUnit("player"))
  if type(map) ~= "number" then
    return
  end
  local position = C_Map.GetPlayerMapPosition(map, "player")
  if not position then
    return
  end
  local x, y = position:GetXY()
  x, y = ns.Plain(x), ns.Plain(y)
  if type(x) ~= "number" or type(y) ~= "number" or (x == 0 and y == 0) then
    return
  end
  if entry.m ~= map then
    if (entry.c or 0) >= 5 then
      return -- stick with the zone we've seen it in most
    end
    entry.m, entry.sx, entry.sy, entry.c = map, 0, 0, 0
  end
  entry.sx = entry.sx + x
  entry.sy = entry.sy + y
  entry.c = entry.c + 1
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
local function SourceRole(kind, guid, targetGUID, targetAlive, fishing, skinning)
  if fishing then
    return "fish"
  elseif kind == "Creature" or kind == "Vehicle" then
    -- Looting a living target means you just picked its pocket.
    if targetAlive and guid == targetGUID then
      return "pick"
    end
    if skinning then
      return "skin"
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
  local skinning = GetTime() - lastSkinCast <= SKIN_SECONDS
  local result = { slots = {}, sources = {} }

  -- A window holding only leather, hides or scraps is a skin as well.
  local count, allSkin = GetNumLootItems() or 0, true
  for slot = 1, count do
    local link = GetLootSlotType(slot) == ITEM_SLOT and GetLootSlotLink(slot)
    local itemID = link and tonumber(link:match("item:(%d+)"))
    if not itemID or not IsSkinProduct(itemID) then
      allSkin = false
    end
  end
  skinning = skinning or (count > 0 and allSkin)

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
          local role = SourceRole(kind, guid, targetGUID, targetAlive, fishing, skinning)
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
-- Skinning casts
---------------------------------------------------------------------------
local skinningName
local function SkinningName()
  if skinningName == nil then
    local name = C_Spell and C_Spell.GetSpellName and C_Spell.GetSpellName(SKINNING_SPELL)
    if name == nil and GetSpellInfo then
      name = GetSpellInfo(SKINNING_SPELL)
    end
    skinningName = ns.Plain(name) or false
  end
  return skinningName
end

ns.On("UNIT_SPELLCAST_SUCCEEDED", function(unit, _, spellID)
  if unit ~= "player" then
    return
  end
  spellID = ns.Plain(spellID)
  if type(spellID) ~= "number" then
    return
  end
  local name = C_Spell and C_Spell.GetSpellName and ns.Plain(C_Spell.GetSpellName(spellID))
  if spellID == SKINNING_SPELL or (name and name == SkinningName()) then
    lastSkinCast = GetTime()
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
