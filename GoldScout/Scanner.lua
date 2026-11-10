-- GoldScout auction house scanner.
--
-- Uses the same approach as Auctionator's summary scan on the Forever client:
-- an empty browse query returns every item on the auction house with its
-- lowest unit buyout and total quantity, delivered in pages. This avoids the
-- 15-minute throttle and disconnect risk of a full ReplicateItems scan.
local _, ns = ...

local Scanner = { ahOpen = false }
ns.Scanner = Scanner

local PAGE_TIMEOUT = 20 -- seconds to wait for one page of results

-- The auction house throttles requests; queue them until it is ready.
local queue = {}

local function Pump()
  if #queue == 0 then
    return
  end
  if not Scanner.ahOpen then
    wipe(queue)
    return
  end
  if C_AuctionHouse.IsThrottledMessageSystemReady() then
    local send = table.remove(queue, 1)
    send()
  end
end

local function Enqueue(send)
  queue[#queue + 1] = send
  Pump()
end

local function KeyString(itemKey)
  return table.concat({
    itemKey.itemID,
    itemKey.itemLevel or 0,
    itemKey.itemSuffix or 0,
    itemKey.battlePetSpeciesID or 0,
  }, ":")
end

function Scanner:IsScanning()
  return self.scan ~= nil
end

-- Pages received and distinct items seen so far, or nil when idle.
function Scanner:Progress()
  local scan = self.scan
  if not scan then
    return nil
  end
  return scan.pages, scan.count
end

function Scanner:Start(reason)
  if not self.ahOpen then
    ns.Print("Open the auction house to scan prices.")
    return false
  end
  if self.scan then
    ns.Print("A scan is already running.")
    return false
  end
  local scan = { results = {}, count = 0, pages = 0, seen = 0, reason = reason }
  self.scan = scan
  scan.ticker = C_Timer.NewTicker(1, Pump)
  self:Request("first", function()
    C_AuctionHouse.SendBrowseQuery({ searchString = "", sorts = {}, filters = {}, itemClassFilters = {} })
  end)
  ns.Fire("SCAN_STARTED")
  return true
end

-- Queues one request and remembers which reply we are waiting for.
function Scanner:Request(kind, send)
  local scan = self.scan
  Enqueue(function()
    if self.scan ~= scan then
      return
    end
    scan.waiting = kind
    send()
    local token = {}
    scan.timeoutToken = token
    C_Timer.After(PAGE_TIMEOUT, function()
      if self.scan == scan and scan.timeoutToken == token and scan.waiting then
        ns.Print("The auction house stopped responding; saving what was received.")
        self:Finish(false)
      end
    end)
  end)
end

-- Results are keyed by item key, so seeing the same entry twice is harmless.
function Scanner:AddResults(results)
  local scan = self.scan
  if not scan or type(results) ~= "table" then
    return
  end
  for _, result in ipairs(results) do
    local itemKey = result.itemKey
    local quantity = result.totalQuantity
    if itemKey and itemKey.itemID and result.minPrice and quantity and quantity > 0 then
      local key = KeyString(itemKey)
      if not scan.results[key] then
        scan.count = scan.count + 1
      end
      scan.results[key] = { id = itemKey.itemID, p = result.minPrice, q = quantity }
    end
  end
end

-- Called after each page arrives: ask for the next page or finish.
function Scanner:Continue()
  local scan = self.scan
  if not scan then
    return
  end
  scan.pages = scan.pages + 1
  ns.Fire("SCAN_PROGRESS", scan.pages, scan.count)
  if C_AuctionHouse.HasFullBrowseResults() then
    self:Finish(true)
  else
    self:Request("more", function()
      C_AuctionHouse.RequestMoreBrowseResults()
    end)
  end
end

-- Browse results are cumulative, so only a longer list means a new page.
local function OnBrowseResults()
  local scan = Scanner.scan
  if not scan or not scan.waiting then
    return
  end
  local all = C_AuctionHouse.GetBrowseResults() or {}
  if scan.waiting == "more" and #all <= scan.seen then
    return
  end
  scan.waiting = nil
  scan.seen = #all
  Scanner:AddResults(all)
  Scanner:Continue()
end

function Scanner:Finish(complete)
  local scan = self.scan
  if not scan then
    return
  end
  self.scan = nil
  wipe(queue)
  if scan.ticker then
    scan.ticker:Cancel()
  end

  -- Combine item-level variants of the same item.
  local byItem = {}
  for _, result in pairs(scan.results) do
    local current = byItem[result.id]
    if current then
      current.p = math.min(current.p, result.p)
      current.q = current.q + result.q
    else
      byItem[result.id] = { p = result.p, q = result.q }
    end
  end

  local now = time()
  local blackwater = self.marketKey ~= nil and self.marketKey ~= ns.MarketKey()
  local market = ns.Prices:Market(self.marketKey)
  local count = 0
  for itemID, result in pairs(byItem) do
    ns.Prices:Record(itemID, result.p, result.q, now, market)
    count = count + 1
  end
  if complete and count > 0 then
    -- Items we knew about that a complete scan didn't find are sold out.
    for itemID, entry in pairs(market.items) do
      if not byItem[itemID] then
        entry.q = 0
      end
    end
    market.lastScan = now
  end

  ns.Print(("%s: %d items priced."):format(complete and "Scan complete" or "Scan stopped", count))
  if blackwater then
    ns.Print("This was a Blackwater (goblin) auction house: its prices are kept separately and show as an "
      .. "extra tooltip line. Your " .. (UnitFactionGroup("player") or "faction") .. " prices are unchanged.")
  end
  ns.Fire("SCAN_FINISHED", complete, count)
end

---------------------------------------------------------------------------
-- Auction house open and close
---------------------------------------------------------------------------
local function OnAuctionHouseShown()
  if Scanner.ahOpen then
    return
  end
  Scanner.ahOpen = true
  -- Which market this auction house's scans belong to (see Prices:AtBlackwater).
  Scanner.marketKey = ns.Prices:AtBlackwater() and ns.Prices:BlackwaterKey() or ns.MarketKey()
  ns.Fire("AH_SHOWN")

  local settings = ns.db and ns.db.settings
  if settings and settings.autoScan then
    local last = ns.Prices:Market(Scanner.marketKey).lastScan or 0
    if time() - last >= (settings.autoScanMinutes or 10) * 60 then
      -- Give the default UI a moment to send its own opening queries first.
      C_Timer.After(2, function()
        if Scanner.ahOpen and not Scanner.scan then
          Scanner:Start("auto")
        end
      end)
    end
  end
end

local function OnAuctionHouseClosed()
  if not Scanner.ahOpen then
    return
  end
  Scanner.ahOpen = false
  if Scanner.scan then
    Scanner:Finish(false)
  end
  Scanner.marketKey = nil
  wipe(queue)
  ns.Fire("AH_HIDDEN")
end

local function IsAuctioneer(kind)
  return Enum.PlayerInteractionType ~= nil and kind == Enum.PlayerInteractionType.Auctioneer
end

ns.On("AUCTION_HOUSE_SHOW", OnAuctionHouseShown)
ns.On("AUCTION_HOUSE_CLOSED", OnAuctionHouseClosed)
ns.On("PLAYER_INTERACTION_MANAGER_FRAME_SHOW", function(kind)
  if IsAuctioneer(kind) then
    OnAuctionHouseShown()
  end
end)
ns.On("PLAYER_INTERACTION_MANAGER_FRAME_HIDE", function(kind)
  if IsAuctioneer(kind) then
    OnAuctionHouseClosed()
  end
end)

ns.On("AUCTION_HOUSE_BROWSE_RESULTS_UPDATED", OnBrowseResults)
ns.On("AUCTION_HOUSE_BROWSE_RESULTS_ADDED", OnBrowseResults)
ns.On("AUCTION_HOUSE_THROTTLED_SYSTEM_READY", Pump)
ns.On("AUCTION_HOUSE_BROWSE_FAILURE", function()
  if Scanner.scan and Scanner.scan.waiting then
    ns.Print("The auction house refused the request; try again in a moment.")
    Scanner:Finish(false)
  end
end)
