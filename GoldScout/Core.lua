-- GoldScout core: namespace, saved variables, event wiring and shared helpers.
local ADDON_NAME, ns = ...
local L = ns.L

ns.ADDON_NAME = ADDON_NAME
ns.AH_CUT = 0.95 -- you keep 95% of a sale after the auction house cut

-- Forever runs on the modern client, where item lookups live in C_Item.
ns.GetItemInfo = (C_Item and C_Item.GetItemInfo) or GetItemInfo
ns.GetItemInfoInstant = (C_Item and C_Item.GetItemInfoInstant) or GetItemInfoInstant

local DEFAULT_SETTINGS = {
  autoScan = false,       -- scan automatically when the auction house opens (off: press Scan AH)
  autoScanMinutes = 10,   -- minimum minutes between automatic scans
  openWithAH = true,      -- show the GoldScout window next to the auction house
  tooltip = true,         -- add GoldScout prices to item tooltips
  blackwaterTooltip = true, -- add the Blackwater (goblin) auction house price as a second tooltip line
  killsPerHour = 70,      -- kills per hour on mobs of your own level
  nodesPerHour = 25,      -- herb or ore nodes per hour
  picksPerHour = 110,     -- pickpockets per hour
  catchesPerHour = 200,   -- fishing catches per hour in open water (pools count half)
  showTrivial = false,    -- include gray recipes that no longer give skill-ups
  showBound = false,      -- include recipes whose product can't be sold
  showAllLevels = false,  -- ignore your level when listing farms
  showOtherProfs = false, -- include gathering professions you don't have
  xpOnly = false,         -- hide farms whose mobs give you no experience
  knownRatesOnly = false, -- hide AH items that have no drop rate yet
  showRareDrops = false,  -- show BoE gear, recipes and gems (rare world drops)
  showCloth = false,      -- show rough per-kill cloth rows for humanoids
  allLoot = false,        -- add a mob's other loot (vendor trash too) to its rows' gold per hour
  huntWaypoint = true,    -- hunts place Blizzard's map waypoint at the farm
  huntMarkers = true,     -- hunts put an icon over matching mobs' nameplates
  learnDrops = true,      -- learn drop rates from what you loot
  unitTooltips = true,    -- add farm info to mob tooltips
  minimap = true,         -- show the minimap button
  minimapAngle = 200,     -- where the minimap button sits around the minimap, in degrees
  companionHint = true,   -- Farm tab companion tip: true until shared, "always", or false once hidden
}

-- securecallfunction reports an error without stopping the other handlers.
local SafeCall = securecallfunction or function(fn, ...) return fn(...) end

---------------------------------------------------------------------------
-- Game events
---------------------------------------------------------------------------
local eventFrame = CreateFrame("Frame")
local eventHandlers = {}

-- Registers a handler for a game event. Returns false if this client does
-- not have the event, so optional events never break loading.
function ns.On(event, handler)
  local list = eventHandlers[event]
  if not list then
    if not pcall(eventFrame.RegisterEvent, eventFrame, event) then
      return false
    end
    list = {}
    eventHandlers[event] = list
  end
  list[#list + 1] = handler
  return true
end

eventFrame:SetScript("OnEvent", function(_, event, ...)
  local list = eventHandlers[event]
  if list then
    for i = 1, #list do
      SafeCall(list[i], ...)
    end
  end
end)

---------------------------------------------------------------------------
-- Internal messages between modules
---------------------------------------------------------------------------
local listeners = {}

function ns.Listen(message, handler)
  local list = listeners[message]
  if not list then
    list = {}
    listeners[message] = list
  end
  list[#list + 1] = handler
end

function ns.Fire(message, ...)
  local list = listeners[message]
  if list then
    for i = 1, #list do
      SafeCall(list[i], ...)
    end
  end
end

-- Runs fn once after `delay` seconds, however many times it is requested.
local pendingTimers = {}
function ns.Debounce(key, delay, fn)
  if pendingTimers[key] then
    return
  end
  pendingTimers[key] = true
  C_Timer.After(delay, function()
    pendingTimers[key] = nil
    fn()
  end)
end

---------------------------------------------------------------------------
-- Formatting
---------------------------------------------------------------------------
function ns.Print(...)
  print("|cffffd200GoldScout|r:", ...)
end

local GOLD = "|cffffd700g|r"
local SILVER = "|cffc7c7cfs|r"
local COPPER = "|cffeda55fc|r"

-- Formats copper as "12g 34s", "5s 20c" or "80c". Negative values get a red minus.
function ns.Money(copper)
  if copper == nil then
    return "|cff7f7f7f-|r"
  end
  local negative = copper < 0
  copper = math.floor(math.abs(copper) + 0.5)
  local gold = math.floor(copper / 10000)
  local silver = math.floor((copper % 10000) / 100)
  local rest = copper % 100
  local text
  if gold > 0 then
    text = gold .. GOLD
    if silver > 0 then
      text = text .. " " .. silver .. SILVER
    end
  elseif silver > 0 then
    text = silver .. SILVER
    if rest > 0 then
      text = text .. " " .. rest .. COPPER
    end
  else
    text = rest .. COPPER
  end
  if negative then
    text = "|cffff4040-|r" .. text
  end
  return text
end

function ns.Age(seconds)
  if not seconds then
    return L["never"]
  end
  if seconds < 90 then
    return L["just now"]
  end
  if seconds < 3600 then
    return L["%dm ago"]:format(math.floor(seconds / 60))
  end
  if seconds < 172800 then
    return L["%dh ago"]:format(math.floor(seconds / 3600))
  end
  return L["%dd ago"]:format(math.floor(seconds / 86400))
end

-- Midnight-era clients can hand addons "secret" values; treat them as unknown.
function ns.Plain(value)
  if issecretvalue and issecretvalue(value) then
    return nil
  end
  return value
end

---------------------------------------------------------------------------
-- Item helpers
---------------------------------------------------------------------------
local requestedItems = {}
local missingItems = {} -- IDs the server says don't exist; never ask again
-- Times each item has been requested this session. The client can drop items
-- from its cache again, and re-asking forever would refresh the UI in a loop.
local requestCounts = {}
local MAX_REQUESTS = 3

local function OnItemLoaded(itemID, success)
  if not itemID or not requestedItems[itemID] then
    return
  end
  requestedItems[itemID] = nil
  if success == false then
    missingItems[itemID] = true
    return
  end
  ns.Debounce("itemsLoaded", 0.5, function()
    ns.Fire("ITEMS_LOADED")
  end)
end
ns.On("ITEM_DATA_LOAD_RESULT", OnItemLoaded)
ns.On("GET_ITEM_INFO_RECEIVED", OnItemLoaded)

-- Asks the server for item data we have not seen yet.
function ns.RequestItem(itemID)
  if requestedItems[itemID] or missingItems[itemID] then
    return
  end
  local count = (requestCounts[itemID] or 0) + 1
  if count > MAX_REQUESTS then
    return
  end
  requestCounts[itemID] = count
  requestedItems[itemID] = true
  if C_Item and C_Item.RequestLoadItemDataByID then
    C_Item.RequestLoadItemDataByID(itemID)
  end
end

-- A mob's name in the game's current language: the game's own name for that
-- creature ID (the same lookup a creature link's tooltip uses), else the name
-- the player recorded (in whatever language their game was then), else the
-- name other players shared, which is English and so only shown on English
-- clients; else "Mob #id". The game may need a moment to load a creature it
-- hasn't seen: GoldScout then asks again shortly after (MOB_NAMES_LOADED).
local mobNames = {}
local ENGLISH_CLIENT = (ns.LOCALE or "enUS"):sub(1, 2) == "en"
local asked = {}   -- lookups tried, so a creature the game never names isn't asked forever

function ns.MobName(npcID, recorded, shared)
  if npcID and mobNames[npcID] == nil and (asked[npcID] or 0) < 3 and C_TooltipInfo and C_TooltipInfo.GetHyperlink then
    asked[npcID] = (asked[npcID] or 0) + 1
    local ok, data = pcall(C_TooltipInfo.GetHyperlink, ("unit:Creature-0-0-0-0-%d-0000000000"):format(npcID))
    local line = ok and type(data) == "table" and data.lines and data.lines[1]
    local name = line and ns.Plain(line.leftText)
    if type(name) == "string" and name ~= "" then
      mobNames[npcID] = name
    elseif ns.Debounce and ns.Fire then
      ns.Debounce("mobnames", 2, function()
        ns.Fire("MOB_NAMES_LOADED")
      end)
    end
  end
  if npcID and mobNames[npcID] then
    return mobNames[npcID]
  end
  if type(recorded) == "string" and recorded ~= "" then
    return recorded
  end
  if ENGLISH_CLIENT and type(shared) == "string" and shared ~= "" then
    return shared
  end
  return L["Mob #%d"]:format(npcID or 0)
end

function ns.ItemName(itemID)
  local name = ns.GetItemInfo(itemID)
  if name then
    return name
  end
  ns.RequestItem(itemID)
  local quickName = C_Item and C_Item.GetItemNameByID and C_Item.GetItemNameByID(itemID)
  return quickName or ("Item " .. itemID)
end

function ns.ItemIcon(itemID)
  local _, _, _, _, icon = ns.GetItemInfoInstant(itemID)
  return icon or 134400 -- question mark
end

function ns.ItemLink(itemID)
  local _, link = ns.GetItemInfo(itemID)
  return link
end

function ns.ItemColor(itemID)
  local quality = select(3, ns.GetItemInfo(itemID))
  local color = quality and ITEM_QUALITY_COLORS and ITEM_QUALITY_COLORS[quality]
  return (color and color.hex) or "|cffffffff"
end

-- Item quality (0 = poor/gray, 1 = common/white, ...), or nil until the item
-- has loaded.
ns.QUALITY_POOR = (Enum and Enum.ItemQuality and Enum.ItemQuality.Poor) or 0

function ns.ItemQuality(itemID)
  local quality = select(3, ns.GetItemInfo(itemID))
  if quality == nil and C_Item and C_Item.GetItemQualityByID then
    quality = C_Item.GetItemQualityByID(itemID)
  end
  if quality == nil then
    ns.RequestItem(itemID)
  end
  return quality
end

-- Gray items are vendor trash: nothing uses them, so an auction house price
-- for one says nothing about its value.
function ns.IsPoorQuality(itemID)
  return ns.ItemQuality(itemID) == ns.QUALITY_POOR
end

-- This WoW account's place on the contributor leaderboard, which GoldScout
-- Companion writes into GoldScout_Prices: { rank, of, kills }, or nil.
function ns.ContributorRank()
  local data = GoldScoutPricesData
  local id = ns.db and ns.db.installID
  local ranks = type(data) == "table" and type(data.contributors) == "table" and data.contributors
  local entry = ranks and id and ranks[id]
  if type(entry) == "table" and tonumber(entry.rank) then
    return entry
  end
end

function ns.ItemSellPrice(itemID)
  local sellPrice = select(11, ns.GetItemInfo(itemID))
  return sellPrice
end

-- What a looted item is worth to you: its auction price after the cut, or its
-- vendor price when that's more. Gray items are worth their vendor price,
-- whatever someone lists them for. Junkboxes count as zero because their
-- contents are counted when you open them.
function ns.LootValue(itemID)
  if ns.JUNKBOXES and ns.JUNKBOXES[itemID] then
    return 0
  end
  local sell = ns.ItemSellPrice(itemID) or 0
  local price = ns.Prices and ns.Prices:Get(itemID)
  if price and not ns.IsPoorQuality(itemID) then
    return math.max(price * ns.AH_CUT, sell)
  end
  return sell
end

-- What a kill's loot is worth on average, from one or more drop records for
-- the same mob (your own, the community's; either may be nil), leaving out
-- skipItem. Coin isn't recorded, so it isn't included. Returns value per kill
-- and the kills behind it.
function ns.KillLootValue(skipItem, ...)
  local kills, total = 0, 0
  for i = 1, select("#", ...) do
    local entry = select(i, ...)
    if entry and (entry.k or 0) > 0 then
      kills = kills + entry.k
      for itemID, stat in pairs(entry.i or {}) do
        if itemID ~= skipItem then
          total = total + ns.LootValue(itemID) * (stat.q or 0)
        end
      end
    end
  end
  return (kills > 0) and total / kills or 0, kills
end

-- 1 = binds when picked up, 4 = quest item. Both can't go on the auction house.
function ns.ItemBindType(itemID)
  local bindType = select(14, ns.GetItemInfo(itemID))
  return bindType
end

-- Each realm and faction has its own auction house, so prices are stored per market.
function ns.MarketKey()
  local realm = (GetNormalizedRealmName and GetNormalizedRealmName()) or GetRealmName() or "Unknown"
  local faction = UnitFactionGroup("player") or "Neutral"
  return realm .. "-" .. faction
end

-- WoW Forever realm names say their ruleset at the end ("CAMWOWUS2Realm2PvP"),
-- and every realm with the same ruleset shares one auction house per faction.
-- Longest suffix first: "RPPvP" also ends in "PvP".
local RULESET_SUFFIXES = {
  { "RPPvP", "Roleplay PvP" },
  { "PvP", "PvP" },
  { "PvE", "Normal" },
  { "RP", "Roleplay" },
}

-- A market as players would say it: "PvP Horde", "Normal Alliance",
-- "PvP Blackwater". Other realm names are shown as the game shows them.
function ns.MarketLabel(key)
  key = key or ns.MarketKey()
  local realm, faction = key:match("^(.*)%-([^-]*)$")
  if not realm then
    return key
  end
  -- Shown to players, so translated (ns.L may be missing when tests load this alone).
  local T = ns.L or {}
  local side = faction == "Neutral" and "Blackwater" or faction
  side = T[side] or side
  for _, suffix in ipairs(RULESET_SUFFIXES) do
    if #realm > #suffix[1] and realm:sub(-#suffix[1]) == suffix[1] then
      return (T["%s %s"] or "%s %s"):format(T[suffix[2]] or suffix[2], side)
    end
  end
  if GetNormalizedRealmName and realm == GetNormalizedRealmName() and GetRealmName then
    realm = GetRealmName() or realm
  end
  return realm .. " " .. side
end

-- Fits a row of labelled controls into `room` pixels. `widths` are the
-- labels' natural widths and `fixed` the rest of each control (the box).
-- Gaps shrink from `gap` down to `minGap` first; if that's still too wide,
-- the longest labels are cut to a common cap (nil when nothing is cut).
function ns.FitRow(widths, fixed, room, gap, minGap)
  local count, total = #widths, 0
  for _, width in ipairs(widths) do
    total = total + width
  end
  if count < 2 then
    gap = 0
  else
    local spare = room - count * fixed - total
    gap = math.max(minGap, math.min(gap, math.floor(spare / (count - 1))))
  end
  local labelRoom = room - count * fixed - gap * math.max(0, count - 1)
  if total <= labelRoom then
    return gap, nil
  end
  -- Lower the cap one label at a time, longest first, until the rest fit.
  local sorted = {}
  for i, width in ipairs(widths) do
    sorted[i] = width
  end
  table.sort(sorted)
  local below = 0
  for i, width in ipairs(sorted) do
    local cap = math.floor((labelRoom - below) / (count - i + 1))
    if cap <= width then
      return gap, math.max(0, cap)
    end
    below = below + width
  end
  return gap, nil
end

---------------------------------------------------------------------------
-- Error log: GoldScout's own Lua errors and blocked actions are kept in its
-- saved data (newest 25, repeats counted) so they can be read after the fact
-- with /gscout errors or tools/errors.py, instead of needing a screenshot.
---------------------------------------------------------------------------
local MAX_ERRORS = 25

function ns.RecordError(message, stack)
  message = tostring(message or "?"):sub(1, 400)
  stack = tostring(stack or ""):sub(1, 1500)
  local db = ns.db
  if not db or not db.errors then
    ns.pendingErrors = ns.pendingErrors or {}
    if #ns.pendingErrors < MAX_ERRORS then
      ns.pendingErrors[#ns.pendingErrors + 1] = { message, stack }
    end
    return
  end
  local now = time and time() or 0
  for _, entry in ipairs(db.errors) do
    if entry.m == message then
      entry.n = (entry.n or 1) + 1
      entry.t = now
      return
    end
  end
  local version = C_AddOns and C_AddOns.GetAddOnMetadata and C_AddOns.GetAddOnMetadata(ADDON_NAME, "Version")
  table.insert(db.errors, { m = message, s = stack, n = 1, t = now, v = version })
  while #db.errors > MAX_ERRORS do
    table.remove(db.errors, 1)
  end
end

local function MentionsGoldScout(text)
  return type(text) == "string" and text:find("AddOns[/\\]" .. ADDON_NAME .. "[/\\]") ~= nil
end

-- Pass every error on to whatever handler was there (the default popup,
-- BugSack...), but keep a copy of the ones that come from GoldScout.
if geterrorhandler and seterrorhandler then
  local previous = geterrorhandler()
  seterrorhandler(function(message, ...)
    pcall(function()
      -- Level 4 is the code that failed: 1 is this function, 2 pcall, 3 this
      -- handler. Starting any higher puts the handler itself in every stack,
      -- so every addon's errors looked like GoldScout's.
      local stack = debugstack and debugstack(4, 12, 0) or ""
      if MentionsGoldScout(tostring(message)) or MentionsGoldScout(stack) then
        ns.RecordError(message, stack)
      end
    end)
    if previous then
      return previous(message, ...)
    end
  end)
end

-- The game refused something GoldScout tried (for example a protected call
-- in combat): that's not a Lua error, so it has to be caught separately.
local function OnBlocked(addon, action)
  if addon == ADDON_NAME then
    ns.RecordError("Blocked action: " .. tostring(action), debugstack and debugstack(3, 12, 0) or "")
  end
end

---------------------------------------------------------------------------
-- Saved variables
---------------------------------------------------------------------------
ns.On("ADDON_ACTION_BLOCKED", OnBlocked)
ns.On("ADDON_ACTION_FORBIDDEN", OnBlocked)

-- Saved data versions. GoldScoutDB.schema (and each character's
-- GoldScoutCharDB.schema) says which shape the saved data is in. At login,
-- each step below upgrades it by one version, in order, once. Rules:
--   * add a step, never edit or remove an old one;
--   * a step must be safe to run twice (a step that errors stops the upgrade,
--     the error is logged, and the same step runs again at the next login);
--   * new saved data starts at the current version and runs no steps;
--   * data from a newer GoldScout (the addon was downgraded) is left alone.
-- Tests: tests/test_engine_lua.py SavedDataTests.
ns.SCHEMA = 3
ns.UPGRADES = {
  [2] = function(db)
    db.settings = db.settings or {}
    db.settings.autoScan = false -- scans became manual: opening the AH to buy something shouldn't start one
  end,
  [3] = function(db)
    db.seenIntro = true -- the first-run welcome is for new players, not everyone updating
  end,
}
ns.CHAR_SCHEMA = 1
ns.CHAR_UPGRADES = {}

-- Brings one saved table up to `current` with `upgrades`. Returns "fresh",
-- "current", "upgraded", "newer" (left alone) or "failed" (stopped at a step).
function ns.UpgradeSavedData(store, current, upgrades, fresh)
  -- Before schema existed, GoldScoutDB.settingsVersion played its part (1 or 2).
  local version = store.schema or store.settingsVersion or 1
  store.settingsVersion = nil
  if fresh then
    store.schema = current
    return "fresh"
  end
  if version > current then
    store.schema = version
    return "newer"
  end
  local result = version == current and "current" or "upgraded"
  for step = version + 1, current do
    local ok, problem = pcall(upgrades[step] or function() end, store)
    if not ok then
      store.schema = step - 1
      ns.RecordError(("Saved data upgrade to version %d failed: %s"):format(step, tostring(problem)), "")
      return "failed"
    end
    store.schema = step
  end
  store.schema = current
  return result
end

ns.On("ADDON_LOADED", function(name)
  if name ~= ADDON_NAME then
    return
  end
  local freshDB, freshCharDB = GoldScoutDB == nil, GoldScoutCharDB == nil
  GoldScoutDB = GoldScoutDB or {}
  GoldScoutCharDB = GoldScoutCharDB or {}
  local db, cdb = GoldScoutDB, GoldScoutCharDB

  db.markets = db.markets or {}
  db.vendor = db.vendor or {}
  db.drops = db.drops or {} -- loot you've seen, per creature ID (all characters)
  db.hunts = db.hunts or {} -- recent hunt summaries
  db.crafted = db.crafted or {} -- every recipe output seen in a profession window (all characters)
  db.names = db.names or {} -- item and zone names seen, for shared exports
  db.names.items = db.names.items or {}
  db.names.maps = db.names.maps or {}
  db.names.meta = db.names.meta or {}
  db.errors = db.errors or {} -- GoldScout's own errors and blocked actions, for /gscout errors
  db.settings = db.settings or {}
  for key, value in pairs(DEFAULT_SETTINGS) do
    if db.settings[key] == nil then
      db.settings[key] = value
    end
  end
  ns.savedData = ns.UpgradeSavedData(db, ns.SCHEMA, ns.UPGRADES, freshDB)

  cdb.recipes = cdb.recipes or {}
  cdb.skills = cdb.skills or {}
  local charResult = ns.UpgradeSavedData(cdb, ns.CHAR_SCHEMA, ns.CHAR_UPGRADES, freshCharDB)
  if charResult == "newer" or charResult == "failed" then
    ns.savedData = charResult
  end

  ns.db, ns.cdb = db, cdb
  -- Errors from before the saved data was ready (loading, an upgrade step).
  local pending = ns.pendingErrors or {}
  ns.pendingErrors = nil
  for _, entry in ipairs(pending) do
    ns.RecordError(entry[1], entry[2])
  end
  ns.Fire("DB_READY")
end)

ns.On("PLAYER_LOGIN", function()
  if ns.savedData == "newer" then
    ns.Print(L["Your saved GoldScout data is from a newer version of GoldScout. Update GoldScout so nothing is lost."])
  elseif ns.savedData == "failed" then
    ns.Print(L["Couldn't finish updating your saved GoldScout data; it will try again next login. /gscout errors shows why."])
  end
  ns.Fire("LOGIN")
end)
