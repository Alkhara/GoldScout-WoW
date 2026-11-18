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

-- What an item fetches each on the auction house after the cut, and its vendor price, when it's worth listing
-- rather than vendoring; nil otherwise (or until the game has loaded the item). isBound: the copy in your bags.
function Bags:Worth(itemID, isBound)
  if not itemID or isBound or not ns.db or ns.db.settings.bagCoins == false then
    return nil
  end
  local info = { ns.GetItemInfo(itemID) }
  local quality, sell, bindType, reagent = info[3], info[11] or 0, info[14], ns.Plain(info[17])
  if quality == nil then
    ns.RequestItem(itemID)
    return nil
  end
  if quality == ns.QUALITY_POOR or bindType == BIND_ON_PICKUP or bindType == QUEST_ITEM then
    return nil
  end
  if reagent ~= true and quality < GREEN then
    return nil   -- white items that aren't crafting reagents: vendor fodder, whatever someone lists them for
  end
  local price, _, _, source = ns.Prices:Get(itemID)
  if not price or price <= 0 or source == "estimate" then
    return nil
  end
  local value = price * ns.AH_CUT
  if value < sell * Bags.RATIO then
    return nil
  end
  return value, sell
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

local function Mark(button)
  if type(button) ~= "table" or not button.CreateTexture then
    return
  end
  seen[button] = true
  local worth = Bags:ForButton(button)
  local coin = button.GoldScoutCoin
  if worth and not coin then
    coin = button:CreateTexture(nil, "OVERLAY", nil, 7)
    coin:SetTexture(COIN_TEXTURE)
    coin:SetSize(12, 12)
    coin:SetPoint("TOPRIGHT", button, "TOPRIGHT", -2, -2)
    button.GoldScoutCoin = coin
  end
  if coin then
    coin:SetShown(worth ~= nil)
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
function Bags:Refresh()
  for button in pairs(seen) do
    if not button.IsVisible or button:IsVisible() then
      Mark(button)
    end
  end
end

local hookedBlizzard, hookedBagnon
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
  -- Bagnon (its core is the BagBrother addon): every slot redraws through Item:Update.
  local bagnon = BagBrother and BagBrother.Item
  if not hookedBagnon and type(bagnon) == "table" and type(bagnon.Update) == "function" then
    hookedBagnon = true
    hooksecurefunc(bagnon, "Update", Mark)
  end
end

HookBags()
ns.On("ADDON_LOADED", function(name)
  if name == "BagBrother" or name == "Bagnon" then
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
