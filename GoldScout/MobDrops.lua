-- A mob's drop rates window: everything GoldScout players have looted from
-- one mob (the shared community data plus your own loot), with what each
-- item is worth. Opened from the target portrait's right-click menu, or with
-- /gscout drops for your current target.
local _, ns = ...
local L = ns.L

local MobDrops = {}
ns.MobDrops = MobDrops

local WIDTH, HEIGHT = 470, 430
local ROW_HEIGHT = 18
local LIST_WIDTH = WIDTH - 22 - 42
local SITE = "wowgoldscout.com"
-- The website's pages in the game's language, where there is one.
local SITE_PREFIX = { deDE = "/de", esES = "/es", esMX = "/es", frFR = "/fr" }
-- Kills before a mob's rates are more than a rough guide (the Farm tab's light green).
local SOLID_KILLS = 15

-- The columns: x of each cell's left edge and its width, inside a row.
local COLUMNS = {
  { key = "item", x = 20, width = 214, align = "LEFT" },
  { key = "chance", x = 234, width = 56, align = "RIGHT" },
  { key = "each", x = 290, width = 66, align = "RIGHT" },
  { key = "kill", x = 356, width = LIST_WIDTH - 356, align = "RIGHT" },
}

local frame

local function Gray(text)
  return "|cff9d9d9d" .. text .. "|r"
end

-- 25%, 2.5%, <0.1%: rare drops keep a digit so they don't all read 0%.
local function Chance(rate)
  if rate >= 0.1 then
    return ("%d%%"):format(math.floor(rate * 100 + 0.5))
  elseif rate >= 0.001 then
    return ("%.1f%%"):format(rate * 100)
  end
  return "<0.1%"
end

-- The creature a unit is ("target", "focus"), or nil for players, pets and nothing.
function MobDrops.NpcOf(unit)
  if not unit or not UnitExists(unit) or UnitIsPlayer(unit) then
    return nil
  end
  local kind, npcID = ns.ParseGUID(UnitGUID(unit))
  if kind == "Creature" or kind == "Vehicle" then
    return npcID
  end
end

-- The rows to show: corpse loot, then pickpocketing under its own heading.
-- Returns rows, kills, picks.
function MobDrops.Rows(npcID)
  local own, shared = ns.Learn:Entry(npcID), ns.COMMUNITY[npcID]
  local rows = {}
  local kills, loot = ns.Community.DropList(false, own, shared)
  for _, entry in ipairs(loot) do
    entry.attempts = kills
    rows[#rows + 1] = entry
  end
  local picks, picked = ns.Community.DropList(true, own, shared)
  if #picked > 0 then
    rows[#rows + 1] = { heading = (L["Pickpocketing: %d picks (values per pick)"]):format(picks) }
    for _, entry in ipairs(picked) do
      entry.attempts, entry.pick = picks, true
      rows[#rows + 1] = entry
    end
  end
  return rows, kills, picks
end

local function SiteLink(npcID)
  return SITE .. (SITE_PREFIX[ns.LOCALE] or "") .. "/mob/" .. npcID
end

---------------------------------------------------------------------------
-- Window
---------------------------------------------------------------------------
local function RowOnEnter(self)
  local row = self.data
  if not row or not row.item then
    return
  end
  GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
  GameTooltip:SetItemByID(row.item)
  local text = row.pick and L["Found in %d of %d picks."] or L["Dropped in %d of %d kills."]
  GameTooltip:AddLine("GoldScout: " .. text:format(row.drops, row.attempts), 1, 0.82, 0, true)
  GameTooltip:Show()
end

local function RowOnLeave()
  GameTooltip:Hide()
end

-- Shift-click links the item in chat.
local function RowOnClick(self)
  local row = self.data
  if row and row.item and IsShiftKeyDown() and ns.UI and ns.UI.LinkInChat then
    ns.UI.LinkInChat(row.item)
  end
end

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
  row.icon = row:CreateTexture(nil, "ARTWORK")
  row.icon:SetSize(ROW_HEIGHT - 2, ROW_HEIGHT - 2)
  row.icon:SetPoint("LEFT", 0, 0)
  row.cells = {}
  for i, column in ipairs(COLUMNS) do
    local cell = row:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    cell:SetPoint("LEFT", row, "LEFT", column.x, 0)
    cell:SetWidth(column.width)
    cell:SetJustifyH(column.align)
    cell:SetWordWrap(false)
    row.cells[i] = cell
  end
  row:RegisterForClicks("LeftButtonUp")
  row:SetScript("OnEnter", RowOnEnter)
  row:SetScript("OnLeave", RowOnLeave)
  row:SetScript("OnClick", RowOnClick)
  return row
end

local function FillRow(row, data)
  row.data = data
  if data.heading then
    row.icon:Hide()
    row.cells[1]:SetText("|cffffd200" .. data.heading .. "|r")
    for i = 2, #COLUMNS do
      row.cells[i]:SetText("")
    end
    return
  end
  row.icon:SetTexture(ns.ItemIcon(data.item))
  row.icon:Show()
  local name = ns.ItemColor(data.item) .. ns.ItemName(data.item) .. "|r"
  local stack = math.floor(data.stack * 10 + 0.5) / 10
  if stack ~= 1 then
    name = name .. Gray((" x%g"):format(stack))
  end
  local value = ns.LootValue(data.item)
  row.cells[1]:SetText(name)
  row.cells[2]:SetText(Chance(data.rate))
  row.cells[3]:SetText(value > 0 and ns.Money(value) or Gray("-"))
  row.cells[4]:SetText(value > 0 and ns.Money(value * data.quantity / data.attempts) or Gray("-"))
end

-- The mob's page on the website, in a box to copy from: typing can't change
-- it, and clicking selects all of it. Only mobs in the shared data have one.
local function CreateLinkBox(f)
  local box = CreateFrame("EditBox", nil, f, "InputBoxTemplate")
  box:SetAutoFocus(false)
  box:SetFontObject(ChatFontNormal)
  box:SetPoint("LEFT", f.linkLabel, "RIGHT", 10, 0)
  box:SetPoint("RIGHT", f, "RIGHT", -24, 0)
  box:SetHeight(20)
  box:SetScript("OnTextChanged", function(self, userInput)
    if userInput then
      self:SetText(self.url or "")
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

local function ShowLink(f, npcID)
  local shown = ns.COMMUNITY[npcID] ~= nil
  f.linkLabel:SetShown(shown)
  f.link:SetShown(shown)
  if shown then
    f.link.url = SiteLink(npcID)
    f.link:SetText(f.link.url)
    f.link:SetCursorPosition(0)
  end
end

local function CreateFrameOnce()
  local f = CreateFrame("Frame", "GoldScoutDropsFrame", UIParent, "BackdropTemplate")
  f:SetSize(WIDTH, HEIGHT)
  f:SetPoint("CENTER")
  f:SetFrameStrata("DIALOG")
  f:SetClampedToScreen(true)
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
  table.insert(UISpecialFrames, "GoldScoutDropsFrame")

  local close = CreateFrame("Button", nil, f, "UIPanelCloseButton")
  close:SetPoint("TOPRIGHT", -6, -6)
  -- Hidden directly: the template's handler is blocked for addons in combat.
  close:SetScript("OnClick", function()
    f:Hide()
  end)

  f.title = f:CreateFontString(nil, "OVERLAY", "GameFontNormalLarge")
  f.title:SetPoint("TOP", 0, -18)
  f.title:SetPoint("LEFT", f, "LEFT", 40, 0)
  f.title:SetPoint("RIGHT", f, "RIGHT", -40, 0)
  f.title:SetWordWrap(false)

  f.info = f:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
  f.info:SetPoint("TOPLEFT", 22, -44)
  f.info:SetPoint("RIGHT", f, "RIGHT", -22, 0)
  f.info:SetJustifyH("LEFT")

  -- Column headings, above the list.
  local headings = { L["Item"], L["Chance"], L["Each"], L["Per kill"] }
  f.headings = {}
  for i, column in ipairs(COLUMNS) do
    local text = f:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    text:SetPoint("TOPLEFT", f, "TOPLEFT", 22 + column.x, -86)
    text:SetWidth(column.width)
    text:SetJustifyH(column.align)
    text:SetText(headings[i])
    f.headings[i] = text
  end

  local scroll = CreateFrame("ScrollFrame", nil, f, "UIPanelScrollFrameTemplate")
  scroll:SetPoint("TOPLEFT", 22, -102)
  scroll:SetPoint("BOTTOMRIGHT", -42, 74)
  f.list = CreateFrame("Frame", nil, scroll)
  f.list:SetSize(LIST_WIDTH, ROW_HEIGHT)
  scroll:SetScrollChild(f.list)
  f.scroll = scroll
  f.rows = {}

  f.empty = f:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
  f.empty:SetPoint("TOPLEFT", scroll, "TOPLEFT", 0, -6)
  f.empty:SetPoint("RIGHT", f, "RIGHT", -22, 0)
  f.empty:SetJustifyH("LEFT")

  f.total = f:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
  f.total:SetPoint("BOTTOMLEFT", 22, 52)
  f.total:SetPoint("RIGHT", f, "RIGHT", -22, 0)
  f.total:SetJustifyH("LEFT")

  f.linkLabel = f:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
  f.linkLabel:SetPoint("BOTTOMLEFT", 22, 26)
  f.linkLabel:SetText(L["On the website:"])
  f.link = CreateLinkBox(f)
  f:Hide()
  return f
end

function MobDrops:Render()
  local f, npcID = frame, self.npcID
  if not f or not npcID then
    return
  end
  local own, shared = ns.Learn:Entry(npcID), ns.COMMUNITY[npcID]
  f.title:SetText(ns.MobName(npcID, own and own.n, shared and shared.n))
  local rows, kills, picks = MobDrops.Rows(npcID)
  local yours = own and own.k or 0

  if kills + picks == 0 then
    f.info:SetText(L["Nobody has recorded loot from this mob yet. Kill it a few times and share your loot to add it."])
  else
    local text = yours > 0 and (L["%d kills recorded by GoldScout players, %d of them yours."]):format(kills, yours)
      or (L["%d kills recorded by GoldScout players."]):format(kills)
    if kills < SOLID_KILLS then
      text = text .. " " .. L["That's only a few, so these rates are a rough guide."]
    end
    f.info:SetText(text)
  end

  for i, data in ipairs(rows) do
    f.rows[i] = f.rows[i] or CreateRow(f.list, i)
    FillRow(f.rows[i], data)
    f.rows[i]:Show()
  end
  for i = #rows + 1, #f.rows do
    f.rows[i]:Hide()
  end
  f.list:SetHeight(math.max(ROW_HEIGHT, #rows * ROW_HEIGHT))
  f.empty:SetShown(#rows == 0 and kills + picks > 0)
  f.empty:SetText(L["Players have killed it, but it hasn't dropped any items yet."])
  for _, heading in ipairs(f.headings) do
    heading:SetShown(#rows > 0)
  end

  local value = ns.KillLootValue(nil, own, shared)
  if kills > 0 and value > 0 then
    f.total:SetText((L["Loot averages %s per kill, counting items seen at least %d times. Coin isn't recorded."])
      :format(ns.Money(value), ns.OTHER_LOOT_MIN_DROPS))
  else
    f.total:SetText("")
  end
  ShowLink(f, npcID)
end

-- Opens the window on a mob (a creature ID).
function MobDrops:Show(npcID)
  if not npcID then
    return
  end
  frame = frame or CreateFrameOnce()
  if self.npcID ~= npcID then
    frame.scroll:SetVerticalScroll(0)
  end
  self.npcID = npcID
  self:Render()
  frame:Show()
end

-- /gscout drops: the window for your current target.
function MobDrops:ShowTarget()
  local npcID = MobDrops.NpcOf("target")
  if not npcID then
    ns.Print(L["Target a mob first, then try again."])
    return
  end
  self:Show(npcID)
end

-- Item names and icons the game was still loading.
ns.Listen("ITEMS_LOADED", function()
  if frame and frame:IsShown() then
    MobDrops:Render()
  end
end)

---------------------------------------------------------------------------
-- The target portrait's right-click menu (and the focus portrait's)
---------------------------------------------------------------------------
local function AddMenuEntry(_, root, context)
  local ok, err = pcall(function()
    local npcID = MobDrops.NpcOf((context and context.unit) or "target")
    if not npcID or not root or not root.CreateButton then
      return
    end
    if root.CreateDivider then
      root:CreateDivider()
    end
    if root.CreateTitle then
      root:CreateTitle("GoldScout")
    end
    root:CreateButton(L["Drop rates"], function()
      MobDrops:Show(npcID)
    end)
  end)
  if not ok and ns.RecordError then
    ns.RecordError(tostring(err), debugstack and debugstack() or "")
  end
end

if Menu and Menu.ModifyMenu then
  for _, tag in ipairs({ "MENU_UNIT_TARGET", "MENU_UNIT_FOCUS" }) do
    pcall(Menu.ModifyMenu, tag, AddMenuEntry)
  end
end
