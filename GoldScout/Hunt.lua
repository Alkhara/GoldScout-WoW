-- GoldScout hunt mode: a waypoint to the farm, icons over the mobs you're
-- after, and a live tracker of what the hunt is earning.
--
-- Staying within the rules: this is all information. It uses Blizzard's own map
-- waypoint, draws icons only you can see, and never moves, targets, attacks,
-- loots or sets raid markers for you. Values the game hides from addons are
-- skipped rather than worked around.
local _, ns = ...

local Hunt = {}
ns.Hunt = Hunt

local ARRIVE_YARDS = 80          -- close enough to call it "arrived"
local ARRIVE_MAP_PERCENT = 2.5   -- same, when only map coordinates are available
local HISTORY_LIMIT = 20

local session -- the hunt in progress, or nil

function Hunt:Active()
  return session
end

---------------------------------------------------------------------------
-- Positions and the waypoint
---------------------------------------------------------------------------

-- Your current zone map and position on it, in map percent.
local function PlayerPosition()
  if not C_Map or not C_Map.GetBestMapForUnit then
    return nil
  end
  local map = ns.Plain(C_Map.GetBestMapForUnit("player"))
  if type(map) ~= "number" then
    return nil
  end
  local position = C_Map.GetPlayerMapPosition and C_Map.GetPlayerMapPosition(map, "player")
  if not position then
    return map
  end
  local x, y = position:GetXY()
  x, y = ns.Plain(x), ns.Plain(y)
  if type(x) ~= "number" or type(y) ~= "number" then
    return map
  end
  return map, x * 100, y * 100
end

-- The hotspot nearest to you on your current map, otherwise the biggest one.
local function ChooseSpot(spots)
  if not spots or #spots == 0 then
    return nil
  end
  local map, x, y = PlayerPosition()
  local best, bestDistance
  if x then
    for _, spot in ipairs(spots) do
      if spot[1] == map then
        local distance = math.sqrt((spot[2] - x) ^ 2 + (spot[3] - y) ^ 2)
        if not bestDistance or distance < bestDistance then
          best, bestDistance = spot, distance
        end
      end
    end
  end
  return best or spots[1]
end

local function SetWaypoint(spot)
  if not spot or not (C_Map and C_Map.SetUserWaypoint and UiMapPoint and UiMapPoint.CreateFromCoordinates) then
    return false
  end
  local map, x, y = spot[1], spot[2] / 100, spot[3] / 100
  if C_Map.CanSetUserWaypointOnMap and not C_Map.CanSetUserWaypointOnMap(map) then
    return false
  end
  C_Map.SetUserWaypoint(UiMapPoint.CreateFromCoordinates(map, x, y))
  if C_SuperTrack and C_SuperTrack.SetSuperTrackedUserWaypoint then
    C_SuperTrack.SetSuperTrackedUserWaypoint(true)
  end
  session.waypoint = { map = map, x = x, y = y }
  session.arrived = false
  return true
end

-- Removes the waypoint, but only if it is still the one GoldScout placed.
local function ClearWaypoint()
  local ours = session and session.waypoint
  if not ours then
    return
  end
  session.waypoint = nil
  if not (C_Map and C_Map.HasUserWaypoint and C_Map.HasUserWaypoint()) then
    return
  end
  local point = C_Map.GetUserWaypoint()
  local position = point and point.position
  if position and point.uiMapID == ours.map
      and math.abs(position.x - ours.x) < 0.001 and math.abs(position.y - ours.y) < 0.001 then
    C_Map.ClearUserWaypoint()
  end
end

-- Distance to the waypoint: yards when the game reports it, else map percent.
local function DistanceToWaypoint()
  local waypoint = session and session.waypoint
  if not waypoint then
    return nil
  end
  if C_Navigation and C_Navigation.GetDistance and C_SuperTrack and C_SuperTrack.IsSuperTrackingUserWaypoint
      and C_SuperTrack.IsSuperTrackingUserWaypoint() then
    local yards = ns.Plain(C_Navigation.GetDistance())
    if type(yards) == "number" and yards > 0 then
      return yards, "yd"
    end
  end
  local map, x, y = PlayerPosition()
  if x and map == waypoint.map then
    return math.sqrt((waypoint.x * 100 - x) ^ 2 + (waypoint.y * 100 - y) ^ 2), "%"
  end
  return nil
end

---------------------------------------------------------------------------
-- Nameplate icons (only you see them; nothing is targeted or marked)
---------------------------------------------------------------------------
local markers, spareMarkers = {}, {}

local function GetMarker()
  local marker = table.remove(spareMarkers)
  if not marker then
    marker = CreateFrame("Frame", nil, UIParent)
    marker:SetSize(20, 20)
    marker.icon = marker:CreateTexture(nil, "ARTWORK")
    marker.icon:SetAllPoints()
    marker.glow = marker:CreateTexture(nil, "OVERLAY")
    marker.glow:SetPoint("CENTER")
    marker.glow:SetSize(36, 36)
    marker.glow:SetTexture("Interface\\Buttons\\UI-ActionButton-Border")
    marker.glow:SetBlendMode("ADD")
    marker.glow:SetVertexColor(0.3, 1, 0.3)
  end
  return marker
end

local function Unmark(unit)
  local marker = markers[unit]
  if marker then
    marker:Hide()
    marker:ClearAllPoints()
    markers[unit] = nil
    spareMarkers[#spareMarkers + 1] = marker
  end
end

local function IsHuntTarget(unit)
  if not session or not next(session.target.npcs) then
    return false
  end
  if not UnitExists(unit) or ns.Plain(UnitIsDead(unit)) ~= false then
    return false
  end
  local _, npcID = ns.ParseGUID(UnitGUID(unit))
  return npcID ~= nil and session.target.npcs[npcID] == true
end

local function Mark(unit)
  Unmark(unit)
  if not ns.db.settings.huntMarkers or not IsHuntTarget(unit) then
    return
  end
  local plate = C_NamePlate and C_NamePlate.GetNamePlateForUnit and C_NamePlate.GetNamePlateForUnit(unit)
  if not plate or (plate.IsForbidden and plate:IsForbidden()) then
    return
  end
  local marker = GetMarker()
  marker.icon:SetTexture(ns.ItemIcon(session.target.item))
  -- If the game won't let addons anchor to this nameplate, skip the icon.
  if not pcall(marker.SetPoint, marker, "BOTTOM", plate, "TOP", 0, 2) then
    spareMarkers[#spareMarkers + 1] = marker
    return
  end
  marker:Show()
  markers[unit] = marker
end

local function RefreshMarkers()
  for unit in pairs(markers) do
    Unmark(unit)
  end
  if not session then
    return
  end
  for i = 1, 40 do
    local unit = "nameplate" .. i
    if UnitExists(unit) then
      Mark(unit)
    end
  end
end

ns.On("NAME_PLATE_UNIT_ADDED", function(unit)
  if session then
    Mark(unit)
  end
end)
ns.On("NAME_PLATE_UNIT_REMOVED", Unmark)

---------------------------------------------------------------------------
-- Session tracking
---------------------------------------------------------------------------

-- What a looted item is worth to you. Junkboxes count as zero because their
-- contents are counted when you open them.
local function ItemValue(itemID)
  if ns.JUNKBOXES[itemID] then
    return 0
  end
  local sell = ns.ItemSellPrice(itemID) or 0
  local price = ns.Prices:Get(itemID)
  -- Gray items are worth their vendor price, whatever someone lists them for.
  if price and not ns.IsPoorQuality(itemID) then
    return math.max(price * ns.AH_CUT, sell)
  end
  return sell
end

local ACTION_FIELD = { kill = "kills", pick = "picks", node = "nodes" }

ns.Listen("LOOT_ACTION", function(role)
  local field = ACTION_FIELD[role]
  if session and field then
    session[field] = session[field] + 1
    Hunt:UpdatePanel()
  end
end)

ns.Listen("LOOT_GAINED", function(itemID, quantity)
  if session then
    session.gained[itemID] = (session.gained[itemID] or 0) + quantity
    Hunt:UpdatePanel()
  end
end)

-- Counts how many of your kills (or picks) dropped the item you're hunting.
ns.Listen("LOOT_DROP", function(role, npcID, itemID)
  if not session or itemID ~= session.target.item or role ~= session.target.per then
    return
  end
  local npcs = session.target.npcs
  if not next(npcs) or npcs[npcID] then
    session.hits = session.hits + 1
  end
end)

local function Summarize(s)
  local duration = math.max(1, time() - s.started)
  local value = 0
  for itemID, quantity in pairs(s.gained) do
    value = value + ItemValue(itemID) * quantity
  end
  local coin = math.max(0, GetMoney() - s.startMoney)
  return {
    item = s.target.item,
    label = s.target.label,
    zone = s.target.zone,
    started = s.started,
    duration = duration,
    kills = s.kills,
    picks = s.picks,
    nodes = s.nodes,
    hits = s.hits,
    count = s.gained[s.target.item] or 0,
    value = value,
    coin = coin,
    perHour = (value + coin) * 3600 / duration,
  }
end

local function Clock(seconds)
  seconds = math.floor(seconds)
  local hours = math.floor(seconds / 3600)
  local minutes = math.floor((seconds % 3600) / 60)
  if hours > 0 then
    return ("%d:%02d:%02d"):format(hours, minutes, seconds % 60)
  end
  return ("%d:%02d"):format(minutes, seconds % 60)
end

function Hunt:Start(target)
  if not target or not ns.db then
    return
  end
  if session then
    self:Stop(true)
  end
  session = {
    target = target,
    started = time(),
    startMoney = GetMoney(),
    kills = 0, picks = 0, nodes = 0, hits = 0,
    gained = {},
  }
  local placed = false
  if ns.db.settings.huntWaypoint then
    placed = SetWaypoint(ChooseSpot(target.spots))
  end
  session.ticker = C_Timer.NewTicker(1, function()
    Hunt:Tick()
  end)
  RefreshMarkers()
  self:ShowPanel()

  local itemName = ns.ItemName(target.item)
  if placed then
    ns.Print(("Hunting %s. Follow the waypoint arrow to %s."):format(itemName, target.zone or "the spot"))
  elseif target.spots and ns.db.settings.huntWaypoint then
    ns.Print(("Hunting %s. Couldn't place a waypoint on that map; head to %s."):format(itemName, target.zone or "the zone"))
  else
    ns.Print(("Hunting %s in %s. Tracking your loot; no waypoint for this one."):format(itemName, target.zone or "the area"))
  end
  if next(target.npcs) and ns.db.settings.huntMarkers then
    ns.Print("Mobs you're hunting get an icon over their nameplate (turn on enemy nameplates with V).")
  end
  ns.Fire("HUNT_CHANGED")
end

function Hunt:Stop(silent)
  if not session then
    return
  end
  local finished = session
  if finished.ticker then
    finished.ticker:Cancel()
  end
  ClearWaypoint()
  session = nil
  RefreshMarkers()
  self:HidePanel()

  local summary = Summarize(finished)
  if summary.duration >= 60 then
    local history = ns.db.hunts
    table.insert(history, 1, summary)
    while #history > HISTORY_LIMIT do
      table.remove(history)
    end
  end
  if not silent then
    ns.Print(("Hunt over after %s: %d %s, %s in loot and %s in coin, about %s an hour."):format(
      Clock(summary.duration), summary.count, ns.ItemName(summary.item),
      ns.Money(summary.value), ns.Money(summary.coin), ns.Money(summary.perHour)))
  end
  ns.Fire("HUNT_CHANGED")
end

-- Points the waypoint at the nearest hotspot again.
function Hunt:Retarget()
  if not session then
    return
  end
  if not session.target.spots then
    ns.Print("No spawn coordinates for this hunt yet.")
    return
  end
  ClearWaypoint()
  if SetWaypoint(ChooseSpot(session.target.spots)) then
    ns.Print("Waypoint set to the nearest spot.")
  else
    ns.Print("Couldn't place a waypoint on that map.")
  end
  self:UpdatePanel()
end

function Hunt:Tick()
  if not session then
    return
  end
  if session.waypoint and not session.arrived then
    local distance, unit = DistanceToWaypoint()
    session.distance, session.distanceUnit = distance, unit
    local close = distance and ((unit == "yd" and distance <= ARRIVE_YARDS) or (unit == "%" and distance <= ARRIVE_MAP_PERCENT))
    if close then
      session.arrived = true
      ClearWaypoint()
      ns.Print(("You've reached the %s spot."):format(ns.ItemName(session.target.item)))
      RefreshMarkers()
    end
  end
  self:UpdatePanel()
end

---------------------------------------------------------------------------
-- Hunt panel
---------------------------------------------------------------------------
local panel

local function CreatePanel()
  panel = CreateFrame("Frame", "GoldScoutHuntPanel", UIParent, "BackdropTemplate")
  panel:SetSize(270, 140)
  local saved = ns.db.settings.huntPanelPos
  if saved then
    panel:SetPoint(saved[1], UIParent, saved[2], saved[3], saved[4])
  else
    panel:SetPoint("TOP", UIParent, "TOP", 0, -150)
  end
  panel:SetClampedToScreen(true)
  panel:SetMovable(true)
  panel:EnableMouse(true)
  panel:RegisterForDrag("LeftButton")
  panel:SetScript("OnDragStart", panel.StartMoving)
  panel:SetScript("OnDragStop", function(self)
    self:StopMovingOrSizing()
    local point, _, relativePoint, x, y = self:GetPoint()
    ns.db.settings.huntPanelPos = { point, relativePoint, x, y }
  end)
  panel:SetBackdrop({
    bgFile = "Interface\\Tooltips\\UI-Tooltip-Background",
    edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
    tile = true,
    tileSize = 16,
    edgeSize = 16,
    insets = { left = 4, right = 4, top = 4, bottom = 4 },
  })
  panel:SetBackdropColor(0, 0, 0, 0.85)

  panel.icon = panel:CreateTexture(nil, "ARTWORK")
  panel.icon:SetSize(30, 30)
  panel.icon:SetPoint("TOPLEFT", 10, -10)

  panel.title = panel:CreateFontString(nil, "OVERLAY", "GameFontNormal")
  panel.title:SetPoint("TOPLEFT", panel.icon, "TOPRIGHT", 7, -1)
  panel.title:SetPoint("RIGHT", panel, "RIGHT", -10, 0)
  panel.title:SetJustifyH("LEFT")
  panel.title:SetWordWrap(false)

  panel.subtitle = panel:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
  panel.subtitle:SetPoint("TOPLEFT", panel.title, "BOTTOMLEFT", 0, -3)
  panel.subtitle:SetPoint("RIGHT", panel, "RIGHT", -10, 0)
  panel.subtitle:SetJustifyH("LEFT")
  panel.subtitle:SetWordWrap(false)

  panel.body = panel:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
  panel.body:SetPoint("TOPLEFT", panel.icon, "BOTTOMLEFT", 0, -8)
  panel.body:SetPoint("RIGHT", panel, "RIGHT", -10, 0)
  panel.body:SetJustifyH("LEFT")
  panel.body:SetSpacing(3)

  panel.stop = CreateFrame("Button", nil, panel, "UIPanelButtonTemplate")
  panel.stop:SetSize(70, 20)
  panel.stop:SetPoint("BOTTOMRIGHT", -8, 8)
  panel.stop:SetText("Stop")
  panel.stop:SetScript("OnClick", function()
    Hunt:Stop()
  end)

  panel.retarget = CreateFrame("Button", nil, panel, "UIPanelButtonTemplate")
  panel.retarget:SetSize(84, 20)
  panel.retarget:SetPoint("RIGHT", panel.stop, "LEFT", -4, 0)
  panel.retarget:SetText("Waypoint")
  panel.retarget:SetScript("OnClick", function()
    Hunt:Retarget()
  end)

  panel:Hide()
end

local function TravelLine(s)
  if s.arrived then
    return "|cff40ff40On site.|r"
  end
  if s.waypoint then
    if s.distance and s.distanceUnit == "yd" then
      return ("Travel: %d yards to go."):format(math.floor(s.distance))
    end
    return "Travel: follow the waypoint arrow."
  end
  if not s.target.spots then
    return "|cff9d9d9dNo spawn coordinates for this one.|r"
  end
  return "|cff9d9d9dWaypoint cleared.|r"
end

function Hunt:UpdatePanel()
  if not panel or not session or not panel:IsShown() then
    return
  end
  local s, target = session, session.target
  local summary = Summarize(s)
  panel.icon:SetTexture(ns.ItemIcon(target.item))
  panel.title:SetText("Hunting " .. ns.ItemName(target.item))
  panel.subtitle:SetText(((target.label and target.label ~= "") and (target.label .. ", ") or "") .. (target.zone or ""))

  local actions, noun = s.kills, "Kills"
  if target.per == "pick" then
    actions, noun = s.picks, "Pickpockets"
  elseif target.per == "node" then
    actions, noun = s.nodes, "Nodes"
  end

  local lines = {
    TravelLine(s),
    ("Time %s   ·   %s %d"):format(Clock(summary.duration), noun, actions),
  }
  local targetLine = ("%s: %d"):format(ns.ItemName(target.item), summary.count)
  if target.chance and actions > 0 and (target.per == "kill" or target.per == "pick") then
    targetLine = targetLine .. ("   ·   %d%% per %s (expected %d%%)"):format(
      math.floor(s.hits / actions * 100 + 0.5), target.per, math.floor(target.chance * 100 + 0.5))
  end
  lines[#lines + 1] = targetLine
  lines[#lines + 1] = ("Loot %s   ·   Coin %s"):format(ns.Money(summary.value), ns.Money(summary.coin))
  lines[#lines + 1] = ("About %s an hour"):format(ns.Money(summary.perHour))
  panel.body:SetText(table.concat(lines, "\n"))
  panel:SetHeight(10 + 30 + 8 + panel.body:GetStringHeight() + 36)
end

function Hunt:ShowPanel()
  if not panel then
    CreatePanel()
  end
  panel:Show()
  self:UpdatePanel()
end

function Hunt:HidePanel()
  if panel then
    panel:Hide()
  end
end

function Hunt:History()
  return (ns.db and ns.db.hunts) or {}
end

---------------------------------------------------------------------------
-- Mob tooltips
---------------------------------------------------------------------------
local function Percent(value)
  return math.floor(value * 100 + 0.5) .. "%"
end

-- Lines GoldScout adds when you mouse over a mob.
function Hunt:UnitLines(npcID)
  local lines = {}
  if session and session.target.npcs[npcID] then
    lines[#lines + 1] = "|cff40ff40You're hunting this mob.|r"
  end
  local _, class = UnitClass("player")
  for _, farm in ipairs(ns.FARMS_BY_NPC[npcID] or {}) do
    local entry = farm.entry
    if farm.kind == "Drop" then
      local price = ns.Prices:Get(entry.item)
      local text = ("%s: %s per kill"):format(ns.ItemName(entry.item), Percent(entry.chance))
      if price then
        text = text .. " (" .. ns.Money(price) .. " each)"
      end
      lines[#lines + 1] = text
    elseif farm.kind == "Pickpocket" and class == "ROGUE" then
      lines[#lines + 1] = ("Pickpocket: junkbox on %s of picks"):format(Percent(entry.chance))
    end
  end
  local learned = ns.Learn:Entry(npcID)
  if learned and (learned.k or 0) > 0 then
    local bestItem, bestValue, bestRate
    for itemID, stat in pairs(learned.i or {}) do
      local price = ns.Prices:Get(itemID)
      if price and not ns.IsPoorQuality(itemID) then
        local value = price * stat.q / learned.k
        if not bestValue or value > bestValue then
          bestItem, bestValue, bestRate = itemID, value, stat.d / learned.k
        end
      end
    end
    local text = ("You've looted %d of these"):format(learned.k)
    if bestItem then
      text = text .. ("; best drop %s at %s"):format(ns.ItemName(bestItem), Percent(bestRate))
    end
    lines[#lines + 1] = text .. "."
  end
  return lines
end

if TooltipDataProcessor and TooltipDataProcessor.AddTooltipPostCall and Enum.TooltipDataType and Enum.TooltipDataType.Unit then
  TooltipDataProcessor.AddTooltipPostCall(Enum.TooltipDataType.Unit, function(tooltip, data)
    if tooltip ~= GameTooltip or (tooltip.IsForbidden and tooltip:IsForbidden()) then
      return
    end
    if not ns.db or not ns.db.settings.unitTooltips then
      return
    end
    local _, npcID = ns.ParseGUID(data and data.guid)
    if not npcID then
      return
    end
    local _, unit = tooltip:GetUnit()
    unit = ns.Plain(unit)
    if type(unit) == "string" then
      ns.Learn:NoteUnit(npcID, UnitName(unit), UnitLevel(unit))
    end
    for _, line in ipairs(Hunt:UnitLines(npcID)) do
      tooltip:AddLine("GoldScout: " .. line, 1, 0.82, 0, true)
    end
  end)
end
