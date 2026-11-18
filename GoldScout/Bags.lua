-- A gold coin on bag items worth listing on the auction house instead of
-- selling to a vendor: crafting reagents and green or better items whose
-- auction price, after the cut, is at least RATIO times the vendor price.
-- Gray junk, quest items and bound items never get one, and neither does an
-- item priced only by the regional estimate: it takes your own realm and
-- faction's prices (a scan or GoldScout Companion). Works in Blizzard's bags
-- and in Bagnon; the coin is only a picture on the slot, so clicking the item
-- works as always, in combat too. /gscout set bagcoins off turns it off.
local _, ns = ...
local L = ns.L

local Bags = {}
ns.Bags = Bags

Bags.RATIO = 2
local GREEN = 2                          -- item quality: uncommon
local BIND_ON_PICKUP, QUEST_ITEM = 1, 4  -- item bind types that can't go on the auction house
local COIN_TEXTURE = "Interface\\MoneyFrame\\UI-GoldIcon"
local DISC_TEXTURE = "Interface\\CharacterFrame\\TempPortraitAlphaMask"   -- a plain white disc

-- What an item fetches each on the auction house after the cut, and its vendor price, when it's worth listing
-- rather than vendoring; nil otherwise (or until the game has loaded the item). isBound: the copy in your bags.
-- Without a coin, the second return says why.
local function Judge(itemID, isBound)
  if not itemID then
    return nil, "empty"
  end
  if not ns.db or ns.db.settings.bagCoins == false then
    return nil, "turned off"
  end
  if isBound then
    return nil, "bound"
  end
  local info = { ns.GetItemInfo(itemID) }
  local quality, sell, bindType, reagent = info[3], info[11] or 0, info[14], ns.Plain(info[17])
  if quality == nil then
    ns.RequestItem(itemID)
    return nil, "item not loaded yet"
  end
  if quality == ns.QUALITY_POOR or bindType == BIND_ON_PICKUP or bindType == QUEST_ITEM then
    return nil, "gray, soulbound or quest"
  end
  if reagent ~= true and quality < GREEN then
    return nil, "white, not a reagent"   -- vendor fodder, whatever someone lists them for
  end
  local price, _, _, source = ns.Prices:Get(itemID)
  if not price or price <= 0 then
    return nil, "no auction price"
  end
  if source == "estimate" then
    return nil, "only a regional estimate"
  end
  local value = price * ns.AH_CUT
  if value < sell * Bags.RATIO then
    return nil, ("under %dx vendor"):format(Bags.RATIO)
  end
  return value, sell
end

function Bags:Worth(itemID, isBound)
  local value, sell = Judge(itemID, isBound)
  if value then
    return value, sell
  end
end

-- The item a bag slot holds and whether that copy is bound: Bagnon's slots carry it (button.info), Blizzard's
-- are looked up by bag and slot.
local function SlotItem(button)
  if type(button) ~= "table" then
    return nil
  end
  if type(button.info) == "table" then
    return button.info.itemID, button.info.isBound
  end
  if not (button.GetID and C_Container and C_Container.GetContainerItemInfo) then
    return nil
  end
  local bag
  if button.GetBagID then
    bag = button:GetBagID()
  elseif button.GetParent and button:GetParent() and button:GetParent().GetID then
    bag = button:GetParent():GetID()
  end
  if type(bag) ~= "number" then
    return nil
  end
  local item = C_Container.GetContainerItemInfo(bag, button:GetID())
  if type(item) ~= "table" then
    return nil
  end
  return ns.Plain(item.itemID), ns.Plain(item.isBound)
end

-- Worth() for whatever a bag slot holds (the tooltip asks this about its owner), or nil.
function Bags:ForButton(button)
  local itemID, isBound = SlotItem(button)
  if itemID then
    return self:Worth(itemID, isBound)
  end
end

local seen = setmetatable({}, { __mode = "k" })   -- slots drawn so far, redrawn when prices change
local hookedBlizzard, hookedBagnon = nil, {}
local BAG_ADDONS = { "Bagnon", "Bagnonium", "BagBrother" }   -- globals that can hold Bagnon's Item class
local BAG_ADDON_SET = {}
for _, name in ipairs(BAG_ADDONS) do
  BAG_ADDON_SET[name] = true
end

local function Mark(button)
  if type(button) ~= "table" or not button.CreateTexture then
    return
  end
  seen[button] = true
  local worth = Bags:ForButton(button)
  local coin = button.GoldScoutCoin
  if worth and not coin then
    -- A dark disc behind the coin so it stands out on bright icons.
    local back = button:CreateTexture(nil, "OVERLAY", nil, 6)
    back:SetTexture(DISC_TEXTURE)
    back:SetVertexColor(0, 0, 0, 0.75)
    back:SetSize(19, 19)
    back:SetPoint("TOPRIGHT", button, "TOPRIGHT", 1, 1)
    coin = button:CreateTexture(nil, "OVERLAY", nil, 7)
    coin:SetTexture(COIN_TEXTURE)
    coin:SetSize(15, 15)
    coin:SetPoint("CENTER", back, "CENTER")
    button.GoldScoutCoin, button.GoldScoutCoinBack = coin, back
  end
  if coin then
    coin:SetShown(worth ~= nil)
    button.GoldScoutCoinBack:SetShown(worth ~= nil)
  end
end
Bags.Mark = Mark

local function MarkFrame(frame)
  if type(frame) ~= "table" then
    return
  end
  if frame.EnumerateValidItems then
    for _, button in frame:EnumerateValidItems() do
      Mark(button)
    end
  elseif type(frame.Items) == "table" then
    for _, button in ipairs(frame.Items) do
      Mark(button)
    end
  elseif frame.GetName and frame:GetName() then
    for i = 1, 40 do
      local button = _G[frame:GetName() .. "Item" .. i]
      if not button then
        break
      end
      Mark(button)
    end
  end
end

-- Redraws every slot seen so far: after a scan or new companion prices, once items load, or the setting changes.
-- Closed bags too: Bagnon only redraws a slot when its contents change, so a slot first drawn before its item
-- or prices loaded would otherwise keep no coin.
function Bags:Refresh()
  for button in pairs(seen) do
    Mark(button)
  end
end

local function HookBags()
  if not hooksecurefunc then
    return
  end
  if not hookedBlizzard then
    hookedBlizzard = true
    if type(ContainerFrame_Update) == "function" then
      hooksecurefunc("ContainerFrame_Update", MarkFrame)
    end
    -- The bank's own slots (Blizzard's bank window, without a bag addon).
    if type(BankFrameItemButton_Update) == "function" then
      hooksecurefunc("BankFrameItemButton_Update", Mark)
    end
    local frames = { ContainerFrameCombinedBags }
    for i = 1, (NUM_CONTAINER_FRAMES or 13) do
      frames[#frames + 1] = _G["ContainerFrame" .. i]
    end
    for _, frame in pairs(frames) do
      if type(frame) == "table" and type(frame.UpdateItems) == "function" then
        hooksecurefunc(frame, "UpdateItems", MarkFrame)
      end
    end
  end
  -- Bagnon: every slot redraws through Item:Update. Bagnon (and Bagnonium) load BagBrother's core files into
  -- their own addon, so the classes are on the Bagnon global, not BagBrother.
  for _, name in ipairs(BAG_ADDONS) do
    local addon = _G[name]
    local item = type(addon) == "table" and rawget(addon, "Item")
    if not hookedBagnon[name] and type(item) == "table" and type(item.Update) == "function" then
      hookedBagnon[name] = true
      hooksecurefunc(item, "Update", Mark)
    end
  end
end

HookBags()
ns.On("ADDON_LOADED", function(name)
  if BAG_ADDON_SET[name] then
    HookBags()
  end
end)
for _, message in ipairs({ "SCAN_FINISHED", "ITEMS_LOADED", "DB_READY" }) do
  ns.Listen(message, function()
    Bags:Refresh()
  end)
end

-- The tooltip line for a slot with a coin: why it's there.
function Bags:TooltipLine(tooltip)
  local owner = tooltip and tooltip.GetOwner and tooltip:GetOwner()
  local value, sell = self:ForButton(owner)
  if not value then
    return nil
  end
  if sell <= 0 then
    return L["GoldScout: vendors won't buy it, but it sells on the auction house. List it."]
  end
  return (L["GoldScout: worth %s each on the auction house, %s at a vendor. List it."]):format(
    ns.Money(value), ns.Money(sell))
end
