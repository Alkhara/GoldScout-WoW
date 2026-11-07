-- GoldScout core: namespace, saved variables, event wiring and shared helpers.
local ADDON_NAME, ns = ...

ns.ADDON_NAME = ADDON_NAME
ns.AH_CUT = 0.95 -- you keep 95% of a sale after the auction house cut

-- Forever runs on the modern client, where item lookups live in C_Item.
ns.GetItemInfo = (C_Item and C_Item.GetItemInfo) or GetItemInfo
ns.GetItemInfoInstant = (C_Item and C_Item.GetItemInfoInstant) or GetItemInfoInstant

local DEFAULT_SETTINGS = {
  autoScan = true,        -- scan automatically when the auction house opens
  autoScanMinutes = 10,   -- minimum minutes between automatic scans
  openWithAH = true,      -- show the GoldScout window next to the auction house
  tooltip = true,         -- add GoldScout prices to item tooltips
  killsPerHour = 70,      -- kills per hour on mobs of your own level
  nodesPerHour = 25,      -- herb or ore nodes per hour
  picksPerHour = 110,     -- pickpockets per hour
  showTrivial = false,    -- include gray recipes that no longer give skill-ups
  showBound = false,      -- include recipes whose product can't be sold
  showAllLevels = false,  -- ignore your level when listing farms
  showOtherProfs = false, -- include gathering professions you don't have
  xpOnly = false,         -- hide farms whose mobs give you no experience
  knownRatesOnly = false, -- hide AH items that have no drop rate yet
  huntWaypoint = true,    -- hunts place Blizzard's map waypoint at the farm
  huntMarkers = true,     -- hunts put an icon over matching mobs' nameplates
  learnDrops = true,      -- learn drop rates from what you loot
  unitTooltips = true,    -- add farm info to mob tooltips
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
    return "never"
  end
  if seconds < 90 then
    return "just now"
  end
  if seconds < 3600 then
    return math.floor(seconds / 60) .. "m ago"
  end
  if seconds < 172800 then
    return math.floor(seconds / 3600) .. "h ago"
  end
  return math.floor(seconds / 86400) .. "d ago"
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

function ns.ItemSellPrice(itemID)
  local sellPrice = select(11, ns.GetItemInfo(itemID))
  return sellPrice
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

---------------------------------------------------------------------------
-- Saved variables
---------------------------------------------------------------------------
ns.On("ADDON_LOADED", function(name)
  if name ~= ADDON_NAME then
    return
  end
  GoldScoutDB = GoldScoutDB or {}
  GoldScoutCharDB = GoldScoutCharDB or {}
  local db, cdb = GoldScoutDB, GoldScoutCharDB

  db.markets = db.markets or {}
  db.vendor = db.vendor or {}
  db.drops = db.drops or {} -- loot you've seen, per creature ID (all characters)
  db.hunts = db.hunts or {} -- recent hunt summaries
  db.settings = db.settings or {}
  for key, value in pairs(DEFAULT_SETTINGS) do
    if db.settings[key] == nil then
      db.settings[key] = value
    end
  end

  cdb.recipes = cdb.recipes or {}
  cdb.skills = cdb.skills or {}

  ns.db, ns.cdb = db, cdb
  ns.Fire("DB_READY")
end)

ns.On("PLAYER_LOGIN", function()
  ns.Fire("LOGIN")
end)
