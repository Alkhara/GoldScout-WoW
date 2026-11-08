-- GoldScout window, item tooltips and slash commands.
local _, ns = ...

local UI = { tab = "farm", offset = 0, rows = {}, data = {}, expanded = {} }
ns.UI = UI

local FRAME_WIDTH, FRAME_HEIGHT = 760, 486
local ROW_HEIGHT = 20
local VISIBLE_ROWS = 16
local MAX_COLUMNS = 8

local COLUMNS = {
  farm = {
    { key = "item", title = "Item", width = 165, align = "LEFT" },
    { key = "kind", title = "Type", width = 70, align = "LEFT" },
    { key = "source", title = "Best source", width = 154, align = "LEFT" },
    { key = "lvl", title = "Lvl", width = 45, align = "CENTER" },
    { key = "chance", title = "Chance", width = 55, align = "RIGHT" },
    { key = "each", title = "Each", width = 70, align = "RIGHT" },
    { key = "hour", title = "Est. /hour", width = 80, align = "RIGHT" },
    { key = "listed", title = "Listed", width = 50, align = "RIGHT" },
  },
  craft = {
    { key = "item", title = "Item", width = 189, align = "LEFT" },
    { key = "profit", title = "Profit", width = 85, align = "RIGHT" },
    { key = "sell", title = "Sells for", width = 85, align = "RIGHT" },
    { key = "cost", title = "Mats cost", width = 85, align = "RIGHT" },
    { key = "listed", title = "Listed", width = 55, align = "RIGHT" },
    { key = "skill", title = "Skill-up", width = 65, align = "CENTER" },
    { key = "profession", title = "Profession", width = 110, align = "LEFT" },
  },
}

-- The two checkboxes change meaning with the tab.
local TAB_OPTIONS = {
  farm = {
    { setting = "showAllLevels", label = "All levels", tip = "Show farms for every level, not just mobs near yours." },
    { setting = "showOtherProfs", label = "Other profs",
      tip = "Also show herbs, ore and leather you could gather if you trained that profession." },
    { setting = "xpOnly", label = "Gives XP",
      tip = "Hide farms whose mobs are all gray to you (no experience). The Lvl column is green when "
        .. "every mob gives XP, yellow when some do, and gray when none do." },
    { setting = "knownRatesOnly", label = "Known rates",
      tip = "Only show farms with a drop rate. Unchecked, crafting reagents selling on your auction house are "
        .. "listed by price too, even before anyone has learned where they drop.\n\nThe Chance column's "
        .. "color shows how many kills back a drop rate up: |cffff8040orange|r under 5, |cffffd100yellow|r "
        .. "5-14, |cff9be35alight green|r 15-49, |cff40ff40green|r 50 or more." },
    { setting = "showRareDrops", label = "Rare drops",
      tip = "Also show BoE gear and recipes players have looted. They're rare world drops that can come "
        .. "from many mobs, so their rates per mob are rough guides at best." },
  },
  craft = {
    { setting = "showTrivial", label = "Gray recipes", tip = "Include recipes that no longer give skill-ups." },
    { setting = "showBound", label = "Soulbound results", tip = "Include recipes whose product can't be sold on the auction house." },
  },
}

-- Experience styling for the Lvl column (see Engine's XP check).
local XP_COLOR = { full = "|cff40ff40", some = "|cffffd100", none = "|cff808080" }
local XP_TEXT = {
  full = "|cff40ff40These mobs give you experience.|r",
  some = "|cffffd100Only the higher-level mobs here give you experience.|r",
  none = "|cff808080These mobs are gray to you: no experience.|r",
}

local function ShowTip(owner, text)
  GameTooltip:SetOwner(owner, "ANCHOR_TOP")
  GameTooltip:SetText(text, 1, 1, 1, 1, true)
  GameTooltip:Show()
end

local function HideTip()
  GameTooltip:Hide()
end

local function Percent(chance)
  return ("%d%%"):format(math.floor(chance * 100 + 0.5))
end

local function Gray(text)
  return "|cff9d9d9d" .. text .. "|r"
end

---------------------------------------------------------------------------
-- Cell text
---------------------------------------------------------------------------
local function ItemText(row)
  if row.child then
    return Gray("    " .. ns.ItemName(row.item))
  end
  local text = ns.ItemColor(row.item) .. ns.ItemName(row.item) .. "|r"
  if row.sources and row.sources > 1 then
    text = text .. Gray((" (%d)"):format(row.sources))
  end
  if row.quantity and row.quantity ~= 1 then
    text = text .. Gray((" x%g"):format(row.quantity))
  end
  return text
end

local function CellText(key, row)
  if key == "item" then
    return ItemText(row)
  elseif key == "kind" then
    return row.needsProfession and Gray(row.kind) or row.kind
  elseif key == "source" then
    return row.source or ""
  elseif key == "lvl" then
    if row.above then
      return Gray(row.itemLevel and ("i" .. row.itemLevel) or (row.lvl or ""))
    end
    local color = XP_COLOR[row.xp]
    return color and (color .. (row.lvl or "") .. "|r") or (row.lvl or "")
  elseif key == "chance" then
    if row.chanceText then
      return Gray(row.chanceText)
    end
    if row.chance and row.confidence then
      return row.confidence.color .. Percent(row.chance) .. "|r"
    end
    return row.chance and Percent(row.chance) or ""
  elseif key == "each" then
    return ns.Money(row.each)
  elseif key == "hour" then
    if row.unknownRate then
      return Gray("?")
    end
    return ns.Money(row.hour)
  elseif key == "listed" then
    if row.bound then
      return Gray("bound")
    end
    if not row.listed then
      return Gray("-")
    end
    if row.listed == 0 then
      return "|cffff8040none|r"
    end
    return tostring(row.listed)
  elseif key == "profit" then
    if row.profit then
      return ns.Money(row.profit)
    end
    return Gray(row.missing and "no price" or "-")
  elseif key == "sell" then
    return ns.Money(row.sell)
  elseif key == "cost" then
    if not row.cost then
      return Gray("?")
    end
    return (row.estimated and Gray("~") or "") .. ns.Money(row.cost)
  elseif key == "skill" then
    return ns.Engine.DIFFICULTY_TEXT[row.diff or -1] or ""
  elseif key == "profession" then
    return row.profession or ""
  end
  return ""
end

---------------------------------------------------------------------------
-- Row tooltips and clicks
---------------------------------------------------------------------------
local function AddMoneyLine(label, copper)
  GameTooltip:AddDoubleLine(label, ns.Money(copper), 0.8, 0.8, 0.8, 1, 1, 1)
end

local function CraftTooltip(row)
  GameTooltip:AddLine((row.profession or "") .. ": " .. (row.name or ""), 1, 1, 1)
  if row.quantity ~= 1 then
    GameTooltip:AddLine(("Makes %g per craft on average."):format(row.quantity), 0.8, 0.8, 0.8)
  end
  GameTooltip:AddLine(" ")
  for _, part in ipairs(row.parts) do
    local source = ({ vendor = "vendor", ["vendor~"] = "vendor, estimated", ah = "AH" })[part.source]
      or "|cffff4040no price|r"
    local cost = part.unit and ns.Money(part.unit * part.count) or "?"
    GameTooltip:AddDoubleLine(part.count .. "x " .. ns.ItemName(part.id), cost .. " (" .. source .. ")",
      1, 1, 1, 1, 1, 1)
  end
  GameTooltip:AddLine(" ")
  AddMoneyLine("Materials", row.cost)
  AddMoneyLine("You receive (after 5% AH cut)", row.revenue)
  AddMoneyLine("Profit per craft", row.profit)
  if row.age then
    GameTooltip:AddLine(("Price seen %s; %d listed."):format(ns.Age(row.age), row.listed or 0), 0.6, 0.6, 0.6)
  end
  if row.listed and row.listed > 0 and row.listed < 10 then
    GameTooltip:AddLine("Few listings, so this price may not hold.", 1, 0.5, 0.25, true)
  end
  if row.estimated then
    GameTooltip:AddLine("Some vendor costs are estimates until you visit a vendor that sells them.", 0.6, 0.6, 0.6, true)
  end
end

local function FarmTooltip(row)
  GameTooltip:AddLine(row.kind .. ": " .. (row.source or ""), 1, 1, 1)
  if row.zone then
    GameTooltip:AddLine(row.zone, 0.8, 0.8, 0.8, true)
  end
  GameTooltip:AddLine(" ")
  local price, listed, age = ns.Prices:Get(row.item)
  if price then
    AddMoneyLine("AH price per unit", price)
  end
  if row.chance then
    GameTooltip:AddDoubleLine("Chance per " .. (row.per or "try"), Percent(row.chance), 0.8, 0.8, 0.8, 1, 1, 1)
  end
  if row.confidence then
    GameTooltip:AddDoubleLine("Confidence", ("%s%s|r (%d %s)"):format(row.confidence.color, row.confidence.text,
      row.seenTrials or 0, row.per == "pick" and "picks" or "kills"), 0.8, 0.8, 0.8, 1, 1, 1)
  end
  if row.kind ~= "Learned" and row.seenTrials and row.seenTrials > 0 then
    GameTooltip:AddDoubleLine(("Player data (%d %s)"):format(row.seenTrials, row.per == "pick" and "picks" or "kills"),
      Percent(row.seenRate or 0), 0.8, 0.8, 0.8, 1, 1, 1)
    if row.baseChance then
      GameTooltip:AddDoubleLine("Starting rate", Percent(row.baseChance), 0.8, 0.8, 0.8, 1, 1, 1)
    end
  end
  if not row.unknownRate then
    AddMoneyLine("Expected value per " .. (row.per or "try"), row.each)
    AddMoneyLine("Rough estimate per hour", row.hour)
  end
  if row.xp then
    GameTooltip:AddLine(XP_TEXT[row.xp], 0.8, 0.8, 0.8)
  end
  if age then
    GameTooltip:AddLine(("Price seen %s; %d listed."):format(ns.Age(age), listed or 0), 0.6, 0.6, 0.6)
  end
  if row.note then
    GameTooltip:AddLine(row.note, 0.95, 0.85, 0.55, true)
  end
  GameTooltip:AddLine("Per-hour figures assume your /gscout set kills, nodes and picks rates.", 0.5, 0.5, 0.5, true)
  if row.sources and row.sources > 1 then
    GameTooltip:AddLine(("Best of %d sources by gold per hour. Click + to see the others."):format(row.sources),
      0.4, 0.8, 1, true)
  end
  if row.hunt then
    GameTooltip:AddLine(row.hunt.spots and "Click to select it, then press Hunt for a waypoint and loot tracker."
      or "Click to select it, then press Hunt to track this farm's loot.", 0.4, 0.8, 1, true)
  end
end

-- True while a row's tooltip loads the game's own item tooltip, so the item
-- tooltip hook doesn't add price lines the row tooltip already shows.
local inRowTooltip = false

local function RowOnEnter(self)
  local row = self.data
  if not row then
    return
  end
  GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
  -- The game's own item tooltip first (quality, "Crafting Reagent", vendor
  -- price...), then GoldScout's details.
  local shownItem = false
  if row.item and GameTooltip.SetItemByID then
    inRowTooltip = true
    local ok = pcall(GameTooltip.SetItemByID, GameTooltip, row.item)
    inRowTooltip = false
    shownItem = ok and GameTooltip:NumLines() > 0
  end
  if shownItem then
    GameTooltip:AddLine(" ")
    GameTooltip:AddLine("GoldScout", 1, 0.82, 0)
  else
    GameTooltip:AddLine(ItemText(row))
  end
  if row.kind == "craft" then
    CraftTooltip(row)
  else
    FarmTooltip(row)
  end
  GameTooltip:AddLine(" ")
  GameTooltip:AddLine("Shift-click to link the item in chat.", 0.5, 0.5, 0.5)
  GameTooltip:Show()
end

local function LinkInChat(itemID)
  local link = ns.ItemLink(itemID)
  if not link then
    return
  end
  if ChatEdit_InsertLink then
    ChatEdit_InsertLink(link)
  elseif ChatFrameUtil and ChatFrameUtil.InsertLink then
    ChatFrameUtil.InsertLink(link)
  end
end

-- Shift-click links the item; a plain click selects the farm for the Hunt button.
local function RowOnClick(self)
  local row = self.data
  if not row then
    return
  end
  if IsShiftKeyDown() then
    LinkInChat(row.item)
  elseif row.hunt then
    UI.selectedKey = (UI.selectedKey ~= row.hunt.key) and row.hunt.key or nil
    UI:Render()
    UI:UpdateHeaderText()
  end
end

---------------------------------------------------------------------------
-- Window
---------------------------------------------------------------------------
local function CreateRow(parent, index)
  local row = CreateFrame("Button", nil, parent)
  row:SetHeight(ROW_HEIGHT)
  row:SetPoint("TOPLEFT", parent, "TOPLEFT", 0, -(index - 1) * ROW_HEIGHT)
  row:SetPoint("RIGHT", parent, "RIGHT", 0, 0)

  local stripe = row:CreateTexture(nil, "BACKGROUND")
  stripe:SetAllPoints()
  stripe:SetColorTexture(1, 1, 1, (index % 2 == 0) and 0.05 or 0)

  local highlight = row:CreateTexture(nil, "HIGHLIGHT")
  highlight:SetAllPoints()
  highlight:SetColorTexture(1, 0.82, 0, 0.12)

  row.selected = row:CreateTexture(nil, "BORDER")
  row.selected:SetAllPoints()
  row.selected:SetColorTexture(0.25, 0.6, 1, 0.25)
  row.selected:Hide()

  row.icon = row:CreateTexture(nil, "ARTWORK")
  row.icon:SetSize(ROW_HEIGHT - 2, ROW_HEIGHT - 2)
  row.icon:SetPoint("LEFT", 18, 0)

  -- Plus/minus button that shows or hides an item's other sources.
  row.expander = CreateFrame("Button", nil, row)
  row.expander:SetSize(14, 14)
  row.expander:SetPoint("LEFT", 2, 0)
  row.expander:SetScript("OnClick", function(self)
    local data = self:GetParent().data
    if data and data.sources and data.sources > 1 then
      UI.expanded[data.item] = not UI.expanded[data.item] or nil
      UI:Regroup()
      UI:Render()
    end
  end)
  row.expander:Hide()

  row.cells = {}
  for i = 1, MAX_COLUMNS do
    local cell = row:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    cell:SetWordWrap(false)
    row.cells[i] = cell
  end

  row:RegisterForClicks("LeftButtonUp")
  row:SetScript("OnEnter", RowOnEnter)
  row:SetScript("OnLeave", HideTip)
  row:SetScript("OnClick", RowOnClick)
  return row
end

local function CreateTabButton(frame, text, tab, x)
  local button = CreateFrame("Button", nil, frame, "UIPanelButtonTemplate")
  button:SetSize(80, 22)
  button:SetPoint("TOPLEFT", x, -64)
  button:SetText(text)
  button:SetScript("OnClick", function()
    UI:SetTab(tab)
  end)
  return button
end

local function CreateCheckbox(frame, x)
  local check = CreateFrame("CheckButton", nil, frame, "UICheckButtonTemplate")
  check:SetSize(24, 24)
  check:SetPoint("TOPLEFT", x, -63)
  check.label = check:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
  check.label:SetPoint("LEFT", check, "RIGHT", 2, 0)
  check:SetScript("OnClick", function(self)
    if self.setting then
      ns.db.settings[self.setting] = self:GetChecked() and true or false
      UI.offset = 0
      UI:Refresh()
    end
  end)
  check:SetScript("OnEnter", function(self)
    if self.tip then
      ShowTip(self, self.tip)
    end
  end)
  check:SetScript("OnLeave", HideTip)
  return check
end

local function CreateArrow(frame, direction, x)
  local button = CreateFrame("Button", nil, frame)
  button:SetSize(24, 24)
  button:SetPoint("BOTTOMRIGHT", x, 12)
  local prefix = "Interface\\Buttons\\UI-ScrollBar-Scroll" .. direction .. "Button-"
  button:SetNormalTexture(prefix .. "Up")
  button:SetPushedTexture(prefix .. "Down")
  button:SetDisabledTexture(prefix .. "Disabled")
  button:SetHighlightTexture(prefix .. "Highlight", "ADD")
  return button
end

function UI:Create()
  if self.frame then
    return self.frame
  end
  local f = CreateFrame("Frame", "GoldScoutFrame", UIParent, "BackdropTemplate")
  self.frame = f
  f:SetSize(FRAME_WIDTH, FRAME_HEIGHT)
  f:SetPoint("CENTER")
  f:SetFrameStrata("HIGH")
  f:SetClampedToScreen(true)
  f:SetMovable(true)
  f:EnableMouse(true)
  f:RegisterForDrag("LeftButton")
  f:SetScript("OnDragStart", f.StartMoving)
  f:SetScript("OnDragStop", function(frame)
    frame:StopMovingOrSizing()
    frame.autoShown = false -- the player placed it; don't auto-hide it
  end)
  f:SetBackdrop({
    bgFile = "Interface\\DialogFrame\\UI-DialogBox-Background-Dark",
    edgeFile = "Interface\\DialogFrame\\UI-DialogBox-Border",
    tile = true,
    tileSize = 32,
    edgeSize = 32,
    insets = { left = 11, right = 12, top = 12, bottom = 11 },
  })
  f:SetScript("OnShow", function()
    UI:Refresh()
  end)
  f:Hide()
  table.insert(UISpecialFrames, "GoldScoutFrame") -- Escape closes it

  local close = CreateFrame("Button", nil, f, "UIPanelCloseButton")
  close:SetPoint("TOPRIGHT", -6, -6)

  local title = f:CreateFontString(nil, "OVERLAY", "GameFontNormalLarge")
  title:SetPoint("TOP", 0, -18)
  title:SetText("GoldScout")

  f.scanButton = CreateFrame("Button", nil, f, "UIPanelButtonTemplate")
  f.scanButton:SetSize(110, 22)
  f.scanButton:SetPoint("TOPRIGHT", -38, -15)
  f.scanButton:SetText("Scan AH")
  f.scanButton:SetScript("OnClick", function()
    ns.Scanner:Start("manual")
  end)
  f.scanButton:SetScript("OnEnter", function(self)
    ShowTip(self, "Reads the lowest price and quantity of every item on the auction house. "
      .. "Takes a few seconds; avoid searching the auction house while it runs.")
  end)
  f.scanButton:SetScript("OnLeave", HideTip)

  f.huntButton = CreateFrame("Button", nil, f, "UIPanelButtonTemplate")
  f.huntButton:SetSize(85, 22)
  f.huntButton:SetPoint("TOPRIGHT", -22, -64)
  f.huntButton:SetText("Hunt")
  f.huntButton:SetScript("OnClick", function()
    UI:OnHuntClicked()
  end)
  f.huntButton:SetScript("OnEnter", function(self)
    ShowTip(self, "Starts a hunt for the selected farm: Blizzard's map waypoint to the spot, an icon over "
      .. "the mobs you're after, and a live loot and gold-per-hour tracker. Information only; it never "
      .. "moves, targets or loots for you.")
  end)
  f.huntButton:SetScript("OnLeave", HideTip)

  f.charText = f:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
  f.charText:SetPoint("TOPLEFT", 22, -44)
  f.charText:SetPoint("RIGHT", f, "RIGHT", -22, 0)
  f.charText:SetJustifyH("LEFT")
  f.charText:SetWordWrap(false)

  f.farmTab = CreateTabButton(f, "Farm", "farm", 18)
  f.craftTab = CreateTabButton(f, "Craft", "craft", 100)
  f.checks = { CreateCheckbox(f, 196), CreateCheckbox(f, 300), CreateCheckbox(f, 390), CreateCheckbox(f, 470),
    CreateCheckbox(f, 565) }

  f.infoText = f:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
  f.infoText:SetPoint("TOPLEFT", 22, -96)
  f.infoText:SetPoint("RIGHT", f, "RIGHT", -22, 0)
  f.infoText:SetJustifyH("LEFT")
  f.infoText:SetWordWrap(false)

  local list = CreateFrame("Frame", nil, f)
  list:SetPoint("TOPLEFT", 16, -134)
  list:SetSize(FRAME_WIDTH - 32, ROW_HEIGHT * VISIBLE_ROWS)
  list:EnableMouseWheel(true)
  list:SetScript("OnMouseWheel", function(_, delta)
    UI:Scroll(-delta * 3)
  end)
  f.list = list

  local header = CreateFrame("Frame", nil, f)
  header:SetPoint("BOTTOMLEFT", list, "TOPLEFT", 0, 4)
  header:SetSize(FRAME_WIDTH - 32, 16)
  header.cells = {}
  for i = 1, MAX_COLUMNS do
    local cell = header:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    cell:SetWordWrap(false)
    header.cells[i] = cell
  end
  f.header = header

  for i = 1, VISIBLE_ROWS do
    self.rows[i] = CreateRow(list, i)
  end

  f.emptyText = list:CreateFontString(nil, "OVERLAY", "GameFontDisable")
  f.emptyText:SetPoint("TOPLEFT", 10, -30)
  f.emptyText:SetPoint("RIGHT", list, "RIGHT", -10, 0)
  f.emptyText:SetJustifyH("CENTER")

  f.statusText = f:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
  f.statusText:SetPoint("BOTTOMLEFT", 22, 19)
  f.statusText:SetJustifyH("LEFT")

  f.upButton = CreateArrow(f, "Up", -46)
  f.downButton = CreateArrow(f, "Down", -20)
  f.upButton:SetScript("OnClick", function()
    UI:Scroll(-VISIBLE_ROWS)
  end)
  f.downButton:SetScript("OnClick", function()
    UI:Scroll(VISIBLE_ROWS)
  end)

  f.pageText = f:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
  f.pageText:SetPoint("BOTTOMRIGHT", -76, 19)
  f.pageText:SetJustifyH("RIGHT")

  self:SetTab(self.tab)
  return f
end

-- Positions the header and row cells for the current tab's columns.
function UI:LayoutColumns()
  local f = self.frame
  local columns = COLUMNS[self.tab]
  local x = ROW_HEIGHT + 20
  for i = 1, MAX_COLUMNS do
    local column = columns[i]
    local headerCell = f.header.cells[i]
    if column then
      headerCell:ClearAllPoints()
      headerCell:SetPoint("LEFT", f.header, "LEFT", x, 0)
      headerCell:SetWidth(column.width - 6)
      headerCell:SetJustifyH(column.align)
      headerCell:SetText(column.title)
      headerCell:Show()
      for _, row in ipairs(self.rows) do
        local cell = row.cells[i]
        cell:ClearAllPoints()
        cell:SetPoint("LEFT", row, "LEFT", x, 0)
        cell:SetWidth(column.width - 6)
        cell:SetJustifyH(column.align)
        cell:Show()
      end
      x = x + column.width
    else
      headerCell:Hide()
      for _, row in ipairs(self.rows) do
        row.cells[i]:Hide()
      end
    end
  end
end

function UI:SetTab(tab)
  self.tab = tab
  self.offset = 0
  local f = self.frame
  if not f then
    return
  end
  self:LayoutColumns()
  if tab == "farm" then
    f.farmTab:LockHighlight()
    f.craftTab:UnlockHighlight()
  else
    f.craftTab:LockHighlight()
    f.farmTab:UnlockHighlight()
  end
  for i, check in ipairs(f.checks) do
    local option = TAB_OPTIONS[tab][i]
    if option then
      check.setting = option.setting
      check.tip = option.tip
      check.label:SetText(option.label)
      check:SetChecked(ns.db ~= nil and ns.db.settings[option.setting] == true)
      check:Show()
    else
      check.setting = nil
      check:Hide()
    end
  end
  self:Refresh()
end

function UI:Scroll(delta)
  local maxOffset = math.max(0, #self.data - VISIBLE_ROWS)
  self.offset = math.max(0, math.min(maxOffset, self.offset + delta))
  self:Render()
end

local function SkillSummary()
  local parts = {}
  for skillID, skill in pairs(ns.Professions:Skills()) do
    if skillID ~= ns.SKILL.LOCKPICKING then
      parts[#parts + 1] = ("%s %d/%d"):format(skill.name or ns.SKILL_NAME[skillID] or "?", skill.rank, skill.max or skill.rank)
    end
  end
  table.sort(parts)
  return table.concat(parts, "  ·  ")
end

function UI:UpdateHeaderText()
  local f = self.frame
  local className = UnitClass("player") or ""
  local text = ("Level %d %s (%s)"):format(UnitLevel("player") or 0, className, UnitFactionGroup("player") or "?")
  local skills = SkillSummary()
  if skills ~= "" then
    text = text .. "  ·  " .. skills
  end
  f.charText:SetText(text)

  local scanning = ns.Scanner:IsScanning()
  if scanning then
    f.scanButton:SetText("Scanning...")
    f.scanButton:Disable()
  else
    f.scanButton:SetText("Scan AH")
    if ns.Scanner.ahOpen then
      f.scanButton:Enable()
    else
      f.scanButton:Disable()
    end
  end

  local count, lastScan = ns.Prices:Summary()
  local status
  if scanning then
    local pages, items = ns.Scanner:Progress()
    status = ("Scanning the auction house: page %d, %d items so far."):format(pages or 0, items or 0)
  elseif count == 0 then
    status = "No prices yet. Visit an auctioneer; GoldScout scans automatically."
  else
    status = ("%d prices for %s, last full scan %s."):format(count, ns.MarketKey(),
      lastScan and ns.Age(time() - lastScan) or "never")
    if not ns.Scanner.ahOpen then
      status = status .. " Visit an auctioneer to refresh."
    end
  end
  f.statusText:SetText(status)
  self:UpdateHuntButton()
end

-- The Farm row picked for the Hunt button, if it's still on the list.
function UI:SelectedRow()
  if self.tab ~= "farm" or not self.selectedKey then
    return nil
  end
  for _, row in ipairs(self.allRows or self.data) do
    if row.hunt and row.hunt.key == self.selectedKey then
      return row
    end
  end
  return nil
end

function UI:UpdateHuntButton()
  local button = self.frame and self.frame.huntButton
  if not button then
    return
  end
  local active = ns.Hunt:Active()
  local row = self:SelectedRow()
  if active and (not row or row.hunt.key == active.target.key) then
    button:SetText("Stop hunt")
    button:Enable()
  else
    button:SetText("Hunt")
    if row then
      button:Enable()
    else
      button:Disable()
    end
  end
end

function UI:OnHuntClicked()
  local active = ns.Hunt:Active()
  local row = self:SelectedRow()
  if active and (not row or row.hunt.key == active.target.key) then
    ns.Hunt:Stop()
  elseif row then
    ns.Hunt:Start(row.hunt)
  end
  self:UpdateHuntButton()
end

function UI:UpdateInfoText()
  local f = self.frame
  local best = self.data[1]
  local info = ""
  local hunting = ns.Hunt:Active()
  if self.tab == "farm" and hunting then
    info = ("Hunting %s; the hunt panel shows how it's going. Select another farm and press Hunt to switch."):format(
      ns.ItemName(hunting.target.item))
  elseif self.tab == "farm" then
    if best and best.hour then
      info = ("Best for you right now: %s from %s, roughly %s an hour."):format(
        ns.ItemName(best.item), best.source or "?", ns.Money(best.hour))
    elseif best and best.unknownRate then
      info = "No drop rates yet, so items are ranked by price. Loot them to learn where they drop."
    elseif #self.data > 0 then
      info = "Scan the auction house to price these farms."
    end
  else
    if not ns.Engine:HasRecipes() then
      info = "Open each of your profession windows once so GoldScout can learn your recipes."
    elseif best and best.profit and best.profit > 0 then
      info = ("Most profitable craft: %s, %s profit each."):format(ns.ItemName(best.item), ns.Money(best.profit))
    elseif best and best.profit then
      info = "None of your recipes make a profit at current prices."
    else
      info = "Scan the auction house to price your recipes."
    end
  end
  f.infoText:SetText(info)
end

-- Fills the visible rows from the current data and offset.
function UI:Render()
  local f = self.frame
  if not f then
    return
  end
  local columns = COLUMNS[self.tab]
  for i = 1, VISIBLE_ROWS do
    local rowFrame = self.rows[i]
    local row = self.data[self.offset + i]
    rowFrame.data = row
    if row then
      rowFrame.icon:SetTexture(ns.ItemIcon(row.item))
      for c, column in ipairs(columns) do
        rowFrame.cells[c]:SetText(CellText(column.key, row))
      end
      rowFrame.selected:SetShown(row.hunt ~= nil and row.hunt.key == self.selectedKey)
      local expandable = row.sources ~= nil and row.sources > 1
      if expandable then
        local prefix = UI.expanded[row.item] and "Interface\\Buttons\\UI-MinusButton-" or "Interface\\Buttons\\UI-PlusButton-"
        rowFrame.expander:SetNormalTexture(prefix .. "Up")
        rowFrame.expander:SetPushedTexture(prefix .. "Down")
      end
      rowFrame.expander:SetShown(expandable)
      rowFrame:Show()
    else
      rowFrame:Hide()
    end
  end

  local total = #self.data
  if total == 0 then
    if self.tab == "craft" then
      f.emptyText:SetText(ns.Engine:HasRecipes() and "No recipes match these filters."
        or "No recipes yet: open each of your profession windows once.")
    else
      f.emptyText:SetText("Nothing in range for your level. Try 'All levels'.")
    end
    f.emptyText:Show()
    f.pageText:SetText("")
  else
    f.emptyText:Hide()
    f.pageText:SetText(("%d-%d of %d"):format(self.offset + 1, math.min(total, self.offset + VISIBLE_ROWS), total))
  end
  if self.offset > 0 then
    f.upButton:Enable()
  else
    f.upButton:Disable()
  end
  if self.offset + VISIBLE_ROWS < total then
    f.downButton:Enable()
  else
    f.downButton:Disable()
  end
end

-- One row per item: its best source by gold per hour. An expanded item lists
-- its other sources underneath, dimmed. allRows is already sorted best first.
function UI:Regroup()
  local order, groups = {}, {}
  for _, row in ipairs(self.allRows or {}) do
    row.child, row.sources = nil, nil
    local group = groups[row.item]
    if group then
      group[#group + 1] = row
    else
      groups[row.item] = { row }
      order[#order + 1] = row.item
    end
  end
  local list = {}
  for _, itemID in ipairs(order) do
    local group = groups[itemID]
    group[1].sources = #group
    list[#list + 1] = group[1]
    if self.expanded[itemID] then
      for i = 2, #group do
        group[i].child = true
        list[#list + 1] = group[i]
      end
    end
  end
  self.data = list
end

-- Recomputes the current tab's list and redraws everything.
function UI:Refresh()
  local f = self.frame
  if not f or not f:IsShown() or not ns.db or not ns.cdb then
    return
  end
  if self.tab == "craft" then
    self.data = ns.Engine:Crafts()
  else
    self.allRows = ns.Engine:Farms()
    self:Regroup()
  end
  local maxOffset = math.max(0, #self.data - VISIBLE_ROWS)
  self.offset = math.min(self.offset, maxOffset)
  self:UpdateHeaderText()
  self:UpdateInfoText()
  self:Render()
end

function UI:QueueRefresh()
  ns.Debounce("ui", 0.2, function()
    UI:Refresh()
  end)
end

function UI:Show(tab)
  self:Create()
  if tab and tab ~= self.tab then
    self:SetTab(tab)
  end
  self.frame:Show()
end

function UI:Toggle()
  if self.frame and self.frame:IsShown() then
    self.frame:Hide()
  else
    self:Show()
  end
end

-- Open beside the auction house, and close again with it unless moved.
ns.Listen("AH_SHOWN", function()
  if not ns.db.settings.openWithAH then
    UI:QueueRefresh()
    return
  end
  C_Timer.After(0.1, function()
    local f = UI:Create()
    if not f:IsShown() then
      f:ClearAllPoints()
      if AuctionHouseFrame and AuctionHouseFrame:IsShown() then
        f:SetPoint("TOPLEFT", AuctionHouseFrame, "TOPRIGHT", 2, 0)
      else
        f:SetPoint("CENTER")
      end
      UI:Show()
      f.autoShown = true
    end
    UI:QueueRefresh()
  end)
end)

ns.Listen("AH_HIDDEN", function()
  local f = UI.frame
  if f and f.autoShown then
    f:Hide()
  end
  if f then
    f.autoShown = false
  end
  UI:QueueRefresh()
end)

for _, message in ipairs({ "SCAN_STARTED", "SCAN_PROGRESS", "SCAN_FINISHED", "SKILLS_UPDATED",
    "RECIPES_UPDATED", "VENDOR_UPDATED", "ITEMS_LOADED", "HUNT_CHANGED", "LOOT_LEARNED" }) do
  ns.Listen(message, function()
    UI:QueueRefresh()
  end)
end
ns.On("PLAYER_LEVEL_UP", function()
  UI:QueueRefresh()
end)

---------------------------------------------------------------------------
-- Item tooltips
---------------------------------------------------------------------------
local function AddTooltipPrices(tooltip, itemID)
  if not ns.db or not ns.db.settings.tooltip or not itemID or inRowTooltip then
    return
  end
  local price, listed, age = ns.Prices:Get(itemID)
  local vendor = ns.db.vendor[itemID]
  if not price and not vendor then
    return
  end
  if price then
    local text = ns.Money(price)
    if listed == 0 then
      text = text .. Gray(" (none listed)")
    end
    tooltip:AddDoubleLine("GoldScout AH (" .. ns.Age(age) .. ")", text, 1, 0.82, 0, 1, 1, 1)
    local average, days = ns.Prices:Average(itemID)
    if average and days and days > 1 then
      tooltip:AddDoubleLine(("GoldScout %d-day avg low"):format(days), ns.Money(average), 1, 0.82, 0, 1, 1, 1)
    end
  end
  if vendor then
    tooltip:AddDoubleLine("GoldScout vendor price", ns.Money(vendor), 1, 0.82, 0, 1, 1, 1)
  end
end

local function IsUsableTooltip(tooltip)
  if tooltip.IsForbidden and tooltip:IsForbidden() then
    return false
  end
  return tooltip == GameTooltip or tooltip == ItemRefTooltip
end

if TooltipDataProcessor and TooltipDataProcessor.AddTooltipPostCall and Enum.TooltipDataType then
  TooltipDataProcessor.AddTooltipPostCall(Enum.TooltipDataType.Item, function(tooltip, data)
    if not IsUsableTooltip(tooltip) then
      return
    end
    local itemID = data and ns.Plain(data.id)
    if type(itemID) == "number" then
      AddTooltipPrices(tooltip, itemID)
    end
  end)
elseif GameTooltip and GameTooltip.HookScript then
  GameTooltip:HookScript("OnTooltipSetItem", function(tooltip)
    local _, link = tooltip:GetItem()
    local itemID = link and tonumber(link:match("item:(%d+)"))
    AddTooltipPrices(tooltip, itemID)
  end)
end

---------------------------------------------------------------------------
-- Slash commands and the addon compartment button
---------------------------------------------------------------------------
---------------------------------------------------------------------------
-- Sharing your drop data (/gscout export)
---------------------------------------------------------------------------
local exportFrame
local SHARE_URL = "github.com/Alkhara/GoldScout-WoW/issues/new?template=data-submission.yml"

-- A one-line box holding text to copy. Typing can't change it, and clicking
-- selects all of it.
local function CreateCopyBox(parent, text)
  local box = CreateFrame("EditBox", nil, parent, "InputBoxTemplate")
  box:SetAutoFocus(false)
  box:SetFontObject(ChatFontNormal)
  box:SetText(text)
  box:SetCursorPosition(0)
  box:SetScript("OnTextChanged", function(self, userInput)
    if userInput then
      self:SetText(text)
      self:HighlightText()
    end
  end)
  box:SetScript("OnMouseUp", function(self)
    self:SetFocus()
    self:HighlightText()
  end)
  box:SetScript("OnEditFocusGained", function(self)
    self:HighlightText()
  end)
  box:SetScript("OnEscapePressed", function(self)
    self:ClearFocus()
  end)
  return box
end

local function CreateExportFrame()
  local f = CreateFrame("Frame", "GoldScoutExportFrame", UIParent, "BackdropTemplate")
  f:SetSize(540, 380)
  f:SetPoint("CENTER")
  f:SetFrameStrata("DIALOG")
  f:SetMovable(true)
  f:EnableMouse(true)
  f:RegisterForDrag("LeftButton")
  f:SetScript("OnDragStart", f.StartMoving)
  f:SetScript("OnDragStop", f.StopMovingOrSizing)
  f:SetBackdrop({
    bgFile = "Interface\\DialogFrame\\UI-DialogBox-Background-Dark",
    edgeFile = "Interface\\DialogFrame\\UI-DialogBox-Border",
    tile = true, tileSize = 32, edgeSize = 32,
    insets = { left = 11, right = 12, top = 12, bottom = 11 },
  })
  table.insert(UISpecialFrames, "GoldScoutExportFrame")

  local close = CreateFrame("Button", nil, f, "UIPanelCloseButton")
  close:SetPoint("TOPRIGHT", -6, -6)

  local title = f:CreateFontString(nil, "OVERLAY", "GameFontNormalLarge")
  title:SetPoint("TOP", 0, -18)
  title:SetText("Share your drop data")

  f.info = f:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
  f.info:SetPoint("TOPLEFT", 22, -44)
  f.info:SetPoint("RIGHT", f, "RIGHT", -22, 0)
  f.info:SetJustifyH("LEFT")

  local linkLabel = f:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
  linkLabel:SetPoint("BOTTOMLEFT", 22, 26)
  linkLabel:SetText("Share form:")
  f.link = CreateCopyBox(f, SHARE_URL)
  f.link:SetPoint("LEFT", linkLabel, "RIGHT", 10, 0)
  f.link:SetPoint("RIGHT", f, "RIGHT", -24, 0)
  f.link:SetHeight(20)

  local scroll = CreateFrame("ScrollFrame", nil, f, "UIPanelScrollFrameTemplate")
  scroll:SetPoint("TOPLEFT", 22, -104)
  scroll:SetPoint("BOTTOMRIGHT", -42, 56)
  local edit = CreateFrame("EditBox", nil, scroll)
  edit:SetMultiLine(true)
  edit:SetAutoFocus(false)
  edit:SetFontObject(ChatFontNormal)
  edit:SetWidth(460)
  edit:SetScript("OnEscapePressed", function()
    f:Hide()
  end)
  scroll:SetScrollChild(edit)
  f.edit = edit
  f:Hide()
  return f
end

function UI:ShowExport()
  local text, count = ns.Learn:ExportString()
  if count == 0 then
    ns.Print("Nothing to share yet; loot some mobs first.")
    return
  end
  exportFrame = exportFrame or CreateExportFrame()
  exportFrame.info:SetText(("Drop data for %d mobs from your loot: drops, kill counts, levels and loot "
    .. "locations, with no character names. Press Ctrl+C to copy it, then open the share form below in your "
    .. "browser and paste it there. Sharing means you agree to the GoldScout Contributor Terms. "
    .. "On Windows, the GoldScout Companion app does this for you."):format(count))
  exportFrame.edit:SetText(text)
  exportFrame:Show()
  exportFrame.edit:SetFocus()
  exportFrame.edit:HighlightText()
end

local SETTING_ALIASES = {
  kills = "killsPerHour",
  nodes = "nodesPerHour",
  picks = "picksPerHour",
  autoscan = "autoScan",
  tooltip = "tooltip",
  window = "openWithAH",
  waypoint = "huntWaypoint",
  markers = "huntMarkers",
  learn = "learnDrops",
  mobtips = "unitTooltips",
  raredrops = "showRareDrops",
}

local function PrintHelp()
  ns.Print("commands:")
  print("  /gscout - show or hide the window")
  print("  /gscout farm | craft - open a tab")
  print("  /gscout scan - scan prices (auction house must be open)")
  print("  /gscout hunt - show the current hunt; /gscout hunt stop | history")
  print("  /gscout export - copy your learned drop data to share with GoldScout")
  print("  /gscout skills - show the skills and recipes GoldScout knows")
  print("  /gscout set kills|nodes|picks <number> - your rates per hour")
  print("  /gscout set autoscan|tooltip|window|waypoint|markers|learn|mobtips|raredrops on|off")
  print("  /gscout reset prices | drops - forget saved prices or learned drop rates")
end

local function HuntCommand(rest)
  local action = rest:lower()
  local active = ns.Hunt:Active()
  if action == "stop" then
    if active then
      ns.Hunt:Stop()
    else
      ns.Print("No hunt is running.")
    end
  elseif action == "history" then
    local history = ns.Hunt:History()
    if #history == 0 then
      ns.Print("No finished hunts yet (hunts under a minute aren't saved).")
    end
    for i = 1, math.min(5, #history) do
      local h = history[i]
      ns.Print(("%s: %d %s in %d min, about %s an hour."):format(date("%b %d", h.started), h.count,
        ns.ItemName(h.item), math.floor(h.duration / 60), ns.Money(h.perHour)))
    end
  elseif active then
    ns.Hunt:ShowPanel()
  else
    ns.Print("Pick a farm on the Farm tab and press Hunt to start one.")
    UI:Show("farm")
  end
end

local function PrintSkills()
  local skills = ns.Professions:ReadSkills()
  if not next(skills) then
    ns.Print("No profession skills found yet.")
  end
  for skillID, skill in pairs(skills) do
    ns.Print(("%s %d/%d"):format(skill.name or ns.SKILL_NAME[skillID] or "?", skill.rank, skill.max or skill.rank))
  end
  local anyRecipes = false
  for _, profession in pairs(ns.cdb.recipes) do
    local count = 0
    for _ in pairs(profession.list or {}) do
      count = count + 1
    end
    anyRecipes = true
    ns.Print(("%s: %d recipes learned (read %s)."):format(profession.name, count, ns.Age(time() - (profession.updated or 0))))
  end
  if not anyRecipes then
    ns.Print("No recipes yet: open each of your profession windows once.")
  end
end

local function SetOption(rest)
  local key, value = rest:match("^(%S+)%s+(%S+)$")
  local setting = key and SETTING_ALIASES[key:lower()]
  if not setting then
    ns.Print("Usage: /gscout set kills|nodes|picks <number>, or "
      .. "/gscout set autoscan|tooltip|window|waypoint|markers|learn|mobtips|raredrops on|off")
    return
  end
  if type(ns.db.settings[setting]) == "boolean" then
    value = value:lower()
    ns.db.settings[setting] = (value == "on" or value == "true" or value == "1")
  else
    local number = tonumber(value)
    if not number or number <= 0 then
      ns.Print("Please give a number above zero.")
      return
    end
    ns.db.settings[setting] = number
  end
  ns.Print(("%s is now %s."):format(key:lower(), tostring(ns.db.settings[setting])))
  UI:QueueRefresh()
end

function UI:HandleSlash(message)
  local command, rest = (message or ""):match("^%s*(%S*)%s*(.-)%s*$")
  command = (command or ""):lower()
  rest = rest or ""
  if not ns.db then
    ns.Print("Still loading; try again in a moment.")
  elseif command == "" or command == "show" then
    self:Toggle()
  elseif command == "farm" or command == "craft" then
    self:Show(command)
  elseif command == "scan" then
    ns.Scanner:Start("manual")
  elseif command == "skills" then
    PrintSkills()
  elseif command == "hunt" then
    HuntCommand(rest)
  elseif command == "export" then
    self:ShowExport()
  elseif command == "set" then
    SetOption(rest)
  elseif command == "reset" and rest:lower() == "prices" then
    ns.Prices:Reset()
    ns.Print("Cleared saved prices for " .. ns.MarketKey() .. ".")
    self:QueueRefresh()
  elseif command == "reset" and rest:lower() == "drops" then
    wipe(ns.db.drops)
    ns.Print("Cleared the drop rates GoldScout learned from your loot.")
    self:QueueRefresh()
  else
    PrintHelp()
  end
end

SLASH_GOLDSCOUT1 = "/goldscout"
SLASH_GOLDSCOUT2 = "/gscout"
SlashCmdList.GOLDSCOUT = function(message)
  UI:HandleSlash(message)
end

function GoldScout_OnCompartmentClick()
  UI:Toggle()
end
