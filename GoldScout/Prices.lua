-- GoldScout price storage: lowest buyout per unit and quantity listed,
-- kept per realm and faction, with a week of daily lows for context.
--
-- Two sources, and each item uses whichever is newer:
--   * your own auction house scans (saved in GoldScoutDB.markets), and
--   * GoldScout Companion's copy of Blizzard's hourly auction snapshot, in the
--     GoldScout_Prices data addon (global GoldScoutPricesData). The game only
--     reads addon files at login or /reload, so that copy is as fresh as your
--     last /reload; the window offers a button for it.
--
-- Blackwater (goblin) auction houses are a market of their own, "Realm-Neutral".
-- A scan at one is kept there and never replaces your faction's prices, which
-- stay the ones GoldScout ranks with; tooltips show the Blackwater price as an
-- extra line.
local _, ns = ...

local Prices = {}
ns.Prices = Prices

local HISTORY_DAYS = 7
local COMPANION_MAX_AGE = 30 * 86400 -- Blizzard's API terms: use API data for at most 30 days
Prices.SOURCE = "Auction data from the Blizzard Entertainment Game Data API. "
  .. "GoldScout is not affiliated with or endorsed by Blizzard."

-- Where the Blackwater auction houses are: Booty Bay (Stranglethorn Vale),
-- Gadgetzan (Tanaris) and Everlook (Winterspring). None of these zones has a
-- faction auction house. Auctioneers seen in game are listed too.
Prices.BLACKWATER_MAPS = { [1434] = true, [1446] = true, [1452] = true }
Prices.BLACKWATER_AUCTIONEERS = { [8661] = true } -- Gadgetzan

-- "Realm-Neutral": the Blackwater market on your realm.
function Prices:BlackwaterKey()
  return (ns.MarketKey():gsub("%-[^-]*$", "")) .. "-Neutral"
end

-- True only when the open auction house is positively a Blackwater one;
-- anything else counts as your faction's.
function Prices:AtBlackwater()
  local guid = UnitGUID and UnitGUID("npc")
  if guid then
    local npcID = tonumber((select(6, strsplit("-", guid))))
    if npcID and self.BLACKWATER_AUCTIONEERS[npcID] then
      return true
    end
  end
  local map = C_Map and C_Map.GetBestMapForUnit and C_Map.GetBestMapForUnit("player")
  return map ~= nil and self.BLACKWATER_MAPS[map] == true
end

-- The companion's snapshot for a market (default: your realm and faction), if
-- it's current: { house, snapshot, items = { [itemID] = { price, quantity } } }.
function Prices:Companion(key)
  local data = GoldScoutPricesData
  local market = type(data) == "table" and type(data.markets) == "table" and data.markets[key or ns.MarketKey()]
  if type(market) ~= "table" or type(market.items) ~= "table" or type(market.snapshot) ~= "number" then
    return nil
  end
  if time() - market.snapshot > COMPANION_MAX_AGE then
    return nil
  end
  return market
end

-- When GoldScout Companion last wrote its file (unix time), if it's loaded.
function Prices:CompanionWritten()
  local data = GoldScoutPricesData
  return type(data) == "table" and type(data.written) == "number" and data.written or nil
end

function Prices:Market(key)
  key = key or ns.MarketKey()
  local market = ns.db.markets[key]
  if not market then
    market = { items = {} }
    ns.db.markets[key] = market
  end
  return market
end

-- Saves one item's lowest unit buyout and total quantity listed.
function Prices:Record(itemID, minPrice, quantity, now, market)
  market = market or self:Market()
  local entry = market.items[itemID]
  if not entry then
    entry = {}
    market.items[itemID] = entry
  end
  entry.p = minPrice
  entry.q = quantity
  entry.t = now

  local day = math.floor(now / 86400)
  local history = entry.h or {}
  entry.h = history
  if history[day] then
    history[day] = math.min(history[day], minPrice)
  else
    history[day] = minPrice
  end
  for oldDay in pairs(history) do
    if oldDay <= day - HISTORY_DAYS then
      history[oldDay] = nil
    end
  end
end

-- Returns lowest unit buyout (copper), quantity listed, age in seconds, and
-- the source ("scan" or "blizzard"), from whichever source is newer.
-- The price is the last one seen, even if the item has since sold out.
function Prices:Get(itemID)
  return self:GetFor(itemID, ns.MarketKey())
end

-- The same for any market, without creating it.
function Prices:GetFor(itemID, key)
  if not ns.db or not itemID then
    return nil
  end
  local market = ns.db.markets[key]
  local entry = market and market.items and market.items[itemID]
  if entry and not entry.p then
    entry = nil
  end
  local companion = self:Companion(key)
  if companion and (not entry or (entry.t or 0) < companion.snapshot) then
    local listed = companion.items[itemID]
    if type(listed) == "table" and listed[1] then
      return listed[1], listed[2] or 0, time() - companion.snapshot, "blizzard"
    end
    if entry then
      -- Scanned before, but not in the newer snapshot: none listed right now.
      return entry.p, 0, time() - (entry.t or 0), "scan"
    end
    return nil
  end
  if not entry then
    return nil
  end
  return entry.p, entry.q or 0, time() - (entry.t or 0), "scan"
end

-- The Blackwater auction house's price on your realm (same returns as Get),
-- for an extra tooltip line. Never used for rankings.
function Prices:Blackwater(itemID)
  local key = self:BlackwaterKey()
  if key == ns.MarketKey() then
    return nil -- a character without a faction already uses the Blackwater market
  end
  return self:GetFor(itemID, key)
end

-- Every item with a price from either source: { [itemID] = true }.
function Prices:ItemIDs()
  local ids = {}
  for itemID in pairs(self:Market().items) do
    ids[itemID] = true
  end
  local companion = self:Companion()
  if companion then
    for itemID in pairs(companion.items) do
      ids[itemID] = true
    end
  end
  return ids
end

-- Average of the daily lows we have, and how many days that covers.
function Prices:Average(itemID)
  if not ns.db or not itemID then
    return nil
  end
  local entry = self:Market().items[itemID]
  if not entry or not entry.h then
    return nil
  end
  local sum, days = 0, 0
  for _, price in pairs(entry.h) do
    sum = sum + price
    days = days + 1
  end
  if days == 0 then
    return nil
  end
  return math.floor(sum / days), days
end

-- Number of items with a price (either source), when your last complete
-- scan finished, and the companion's snapshot time (nil without one).
function Prices:Summary()
  local count = 0
  for _ in pairs(self:ItemIDs()) do
    count = count + 1
  end
  local companion = self:Companion()
  return count, self:Market().lastScan, companion and companion.snapshot
end

-- Remember which realms and factions you play, so GoldScout Companion knows
-- which auction houses' prices to save for you (read from this PC only).
ns.Listen("LOGIN", function()
  if ns.db then
    ns.db.seenMarkets = ns.db.seenMarkets or {}
    ns.db.seenMarkets[ns.MarketKey()] = time()
  end
end)

function Prices:Reset()
  ns.db.markets[ns.MarketKey()] = nil
end
