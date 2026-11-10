-- GoldScout's page in Blizzard's Options > AddOns: the settings the slash
-- commands change, grouped in two columns. The list filters (All levels,
-- Gives XP, ...) are the checkboxes at the top of the GoldScout window, so
-- they aren't repeated here. Open it with the gear on the GoldScout window or
-- /gscout options.
local _, ns = ...
local L = ns.L

local Options = {}
ns.Options = Options

local COLUMN_WIDTH = 300
local TOP = -76

-- key: the setting in GoldScoutDB.settings. Numbers have min/max.
local LEFT = {
  { title = L["Auction house"], items = {
    { key = "openWithAH", label = L["Open GoldScout next to the auction house"] },
    { key = "autoScan", label = L["Scan automatically when the auction house opens"],
      tip = L["Off by default, so opening the auction house to buy something doesn't start a scan."] },
    { key = "autoScanMinutes", label = L["Minutes between automatic scans"], min = 1, max = 120 },
    { key = "tooltip", label = L["Show GoldScout prices on item tooltips"] },
    { key = "blackwaterTooltip", label = L["Also show the Blackwater (goblin) auction house price"] },
  } },
  { title = L["Your pace"], note = L["Gold per hour estimates use these."], items = {
    { key = "killsPerHour", label = L["Kills per hour"], min = 1, max = 999 },
    { key = "nodesPerHour", label = L["Herb or ore nodes per hour"], min = 1, max = 999 },
    { key = "picksPerHour", label = L["Pickpockets per hour"], min = 1, max = 999 },
  } },
}
local RIGHT = {
  { title = L["Hunting"], items = {
    { key = "huntWaypoint", label = L["Place a map waypoint at the farm"] },
    { key = "huntMarkers", label = L["Mark the mobs you're hunting on their nameplates"],
      tip = L["Turn on enemy nameplates (V) to see the markers."] },
    { key = "unitTooltips", label = L["Add farm info to mob tooltips"] },
  } },
  { title = L["Farm list"], note = L["More filters are the checkboxes at the top of the GoldScout window."], items = {
    { key = "showCloth", label = L["Show cloth from humanoids"] },
  } },
  { title = L["Data and sharing"], items = {
    { key = "learnDrops", label = L["Learn drop rates from what you loot"] },
    { key = "companionHint", label = L["Show the GoldScout Companion tip on the Farm tab"] },
  } },
  { title = L["Interface"], items = {
    { key = "minimap", label = L["Show the minimap button"] },
  } },
}

local function Apply(key)
  if key == "minimap" and ns.UI.UpdateMinimapButton then
    ns.UI:UpdateMinimapButton()
  end
  if ns.UI.QueueRefresh then
    ns.UI:QueueRefresh()
  end
end

local function AddTip(frame, item)
  if not item.tip then
    return
  end
  frame:SetScript("OnEnter", function(self)
    GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
    GameTooltip:SetText(item.label, 1, 1, 1)
    GameTooltip:AddLine(item.tip, nil, nil, nil, true)
    GameTooltip:Show()
  end)
  frame:SetScript("OnLeave", function()
    GameTooltip:Hide()
  end)
end

local function CreateCheck(parent, item)
  local check = CreateFrame("CheckButton", nil, parent, "UICheckButtonTemplate")
  check:SetSize(26, 26)
  check.label = check:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
  check.label:SetPoint("TOPLEFT", check, "TOPRIGHT", 2, -6)
  check.label:SetWidth(COLUMN_WIDTH - 36)
  check.label:SetJustifyH("LEFT")
  check.label:SetText(item.label)
  check:SetScript("OnClick", function(self)
    ns.db.settings[item.key] = self:GetChecked() and true or false
    Apply(item.key)
  end)
  AddTip(check, item)
  function check.Load(self)
    local value = ns.db.settings[item.key]
    self:SetChecked(value ~= false and value ~= nil)
  end
  function check.Height()
    return math.max(26, (check.label:GetStringHeight() or 14) + 12)
  end
  return check
end

local function CreateNumber(parent, item)
  local row = CreateFrame("Frame", nil, parent)
  row:SetSize(COLUMN_WIDTH, 26)
  local box = CreateFrame("EditBox", nil, row, "InputBoxTemplate")
  box:SetSize(44, 20)
  box:SetPoint("LEFT", 8, 0)
  box:SetAutoFocus(false)
  box:SetNumeric(true)
  box:SetMaxLetters(3)
  local label = row:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
  label:SetPoint("LEFT", box, "RIGHT", 8, 0)
  label:SetPoint("RIGHT", row, "RIGHT", 0, 0)
  label:SetJustifyH("LEFT")
  label:SetText(item.label)
  local saving = false
  local function Show()
    box:SetText(tostring(ns.db.settings[item.key] or ""))
  end
  local function Save()
    if saving then
      return
    end
    saving = true
    local number = tonumber(box:GetText())
    if number then
      number = math.max(item.min, math.min(item.max, math.floor(number)))
      if number ~= ns.db.settings[item.key] then
        ns.db.settings[item.key] = number
        Apply(item.key)
      end
    end
    Show()
    box:ClearFocus()
    saving = false
  end
  box:SetScript("OnEnterPressed", Save)
  box:SetScript("OnEditFocusLost", Save)
  box:SetScript("OnEscapePressed", function(self)
    Show()
    self:ClearFocus()
  end)
  AddTip(row, item)
  row.Load = Show
  function row.Height()
    return 30
  end
  return row
end

-- Places one column's sections top to bottom; returns its controls.
local function Column(panel, sections, x)
  local controls, y = {}, TOP
  for _, section in ipairs(sections) do
    local header = panel:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    header:SetPoint("TOPLEFT", x, y)
    header:SetText(section.title)
    y = y - 20
    if section.note then
      local note = panel:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
      note:SetPoint("TOPLEFT", x + 4, y)
      note:SetWidth(COLUMN_WIDTH - 8)
      note:SetJustifyH("LEFT")
      note:SetText(section.note)
      y = y - (note:GetStringHeight() or 12) - 6
    end
    for _, item in ipairs(section.items) do
      local control = item.min and CreateNumber(panel, item) or CreateCheck(panel, item)
      control:SetPoint("TOPLEFT", x, y)
      y = y - control.Height()
      controls[#controls + 1] = control
    end
    y = y - 14
  end
  return controls
end

function Options:Create()
  if self.panel then
    return self.panel
  end
  local panel = CreateFrame("Frame")
  panel.name = "GoldScout"
  self.panel = panel

  local title = panel:CreateFontString(nil, "OVERLAY", "GameFontNormalLarge")
  title:SetPoint("TOPLEFT", 16, -16)
  title:SetText("GoldScout")
  local subtitle = panel:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
  subtitle:SetPoint("TOPLEFT", title, "BOTTOMLEFT", 0, -8)
  subtitle:SetPoint("RIGHT", panel, "RIGHT", -16, 0)
  subtitle:SetJustifyH("LEFT")
  subtitle:SetText(L["Changes apply right away. /gscout options opens this page."])

  panel:SetScript("OnShow", function(frame)
    if not ns.db then
      return
    end
    if not frame.controls then
      frame.controls = Column(frame, LEFT, 16)
      for _, control in ipairs(Column(frame, RIGHT, 16 + COLUMN_WIDTH + 24)) do
        frame.controls[#frame.controls + 1] = control
      end
    end
    for _, control in ipairs(frame.controls) do
      control:Load()
    end
  end)

  if Settings and Settings.RegisterCanvasLayoutCategory and Settings.RegisterAddOnCategory then
    local category = Settings.RegisterCanvasLayoutCategory(panel, "GoldScout")
    Settings.RegisterAddOnCategory(category)
    self.category = category
  elseif InterfaceOptions_AddCategory then
    InterfaceOptions_AddCategory(panel)
  end
  return panel
end

function Options:Open()
  if InCombatLockdown and InCombatLockdown() then
    ns.Print(L["Leave combat first, then open GoldScout's settings."])
    return
  end
  self:Create()
  if self.category and Settings and Settings.OpenToCategory then
    Settings.OpenToCategory(self.category:GetID())
  elseif InterfaceOptionsFrame_OpenToCategory then
    InterfaceOptionsFrame_OpenToCategory(self.panel)
    InterfaceOptionsFrame_OpenToCategory(self.panel) -- the old panel needed two calls to scroll to it
  end
end

ns.Listen("DB_READY", function()
  Options:Create()
end)
