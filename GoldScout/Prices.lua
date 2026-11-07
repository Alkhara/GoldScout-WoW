-- GoldScout price storage: lowest buyout per unit and quantity listed,
-- kept per realm and faction, with a week of daily lows for context.
local _, ns = ...

local Prices = {}
ns.Prices = Prices

local HISTORY_DAYS = 7

function Prices:Market()
  local key = ns.MarketKey()
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

-- Returns lowest unit buyout (copper), quantity listed, and age in seconds.
-- The price is the last one seen, even if the item has since sold out.
function Prices:Get(itemID)
  if not ns.db or not itemID then
    return nil
  end
  local entry = self:Market().items[itemID]
  if not entry or not entry.p then
    return nil
  end
  return entry.p, entry.q or 0, time() - (entry.t or 0)
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

-- Number of items with a price, and when the last complete scan finished.
function Prices:Summary()
  local market = self:Market()
  local count = 0
  for _ in pairs(market.items) do
    count = count + 1
  end
  return count, market.lastScan
end

function Prices:Reset()
  ns.db.markets[ns.MarketKey()] = nil
end
