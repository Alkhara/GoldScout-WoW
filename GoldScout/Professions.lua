-- GoldScout professions: your skill levels, the recipes you know, and vendor prices.
local _, ns = ...
local L = ns.L

local Professions = {}
ns.Professions = Professions

local Plain = ns.Plain

---------------------------------------------------------------------------
-- Skill levels
---------------------------------------------------------------------------
local function AddSkill(found, skillID, rank, maxRank, name)
  skillID, rank, maxRank = Plain(skillID), Plain(rank), Plain(maxRank)
  if not skillID or not ns.SKILL_NAME[skillID] or found[skillID] then
    return
  end
  if type(rank) ~= "number" or rank <= 0 then
    return
  end
  found[skillID] = {
    rank = rank,
    max = (type(maxRank) == "number" and maxRank) or rank,
    name = (type(name) == "string" and name) or ns.SKILL_NAME[skillID],
  }
end

-- Forever has a classic-style skills list (C_SkillInfo); fall back to the
-- retail professions API if that returns nothing.
function Professions:ReadSkills()
  if not ns.cdb then
    return {}
  end
  local found = {}

  if C_SkillInfo and C_SkillInfo.GetSkillLineInfoByID then
    for skillID in pairs(ns.SKILL_NAME) do
      local ok, info = pcall(C_SkillInfo.GetSkillLineInfoByID, skillID)
      if ok and type(info) == "table" then
        AddSkill(found, skillID, info.rank, info.maxRank, info.name)
      end
    end
  end

  if not next(found) and C_SkillInfo and C_SkillInfo.GetNumSkillLines and C_SkillInfo.GetSkillLineInfo then
    local okCount, count = pcall(C_SkillInfo.GetNumSkillLines)
    count = okCount and Plain(count)
    if type(count) == "number" then
      for index = 1, count do
        local ok, info = pcall(C_SkillInfo.GetSkillLineInfo, index)
        if ok and type(info) == "table" and not info.isHeader then
          AddSkill(found, info.skillID, info.rank, info.maxRank, info.name)
        end
      end
    end
  end

  if GetProfessions and GetProfessionInfo then
    local slots = { GetProfessions() }
    for i = 1, 8 do
      local index = slots[i]
      if index then
        local ok, name, _, rank, maxRank, _, _, skillLine = pcall(GetProfessionInfo, index)
        if ok then
          AddSkill(found, skillLine, rank, maxRank, name)
        end
      end
    end
  end

  if next(found) then
    ns.cdb.skills = found
  end
  ns.Fire("SKILLS_UPDATED")
  return ns.cdb.skills
end

function Professions:Skills()
  return (ns.cdb and ns.cdb.skills) or {}
end

---------------------------------------------------------------------------
-- Recipes (read whenever one of your profession windows is open)
---------------------------------------------------------------------------
local function IsOwnProfessionOpen()
  if not C_TradeSkillUI or not C_TradeSkillUI.GetAllRecipeIDs then
    return false
  end
  if C_TradeSkillUI.IsTradeSkillLinked and C_TradeSkillUI.IsTradeSkillLinked() then
    return false
  end
  if C_TradeSkillUI.IsTradeSkillGuild and C_TradeSkillUI.IsTradeSkillGuild() then
    return false
  end
  if C_TradeSkillUI.IsNPCCrafting and C_TradeSkillUI.IsNPCCrafting() then
    return false
  end
  if C_TradeSkillUI.IsTradeSkillReady and not C_TradeSkillUI.IsTradeSkillReady() then
    return false
  end
  return true
end

local function ReadReagents(schematic)
  local reagents = {}
  local basic = Enum.CraftingReagentType and Enum.CraftingReagentType.Basic
  for _, slot in ipairs(schematic.reagentSlotSchematics or {}) do
    local first = slot.reagents and slot.reagents[1]
    local isBasic = (basic == nil) or slot.reagentType == basic
    if isBasic and first and first.itemID and (slot.quantityRequired or 0) > 0 then
      reagents[#reagents + 1] = { first.itemID, slot.quantityRequired }
    end
  end
  return reagents
end

local function ReadOutput(recipeID, schematic)
  if schematic.outputItemID then
    return schematic.outputItemID
  end
  if C_TradeSkillUI.GetRecipeOutputItemData then
    local ok, data = pcall(C_TradeSkillUI.GetRecipeOutputItemData, recipeID)
    if ok and type(data) == "table" then
      return data.itemID
    end
  end
  return nil
end

function Professions:CaptureRecipes()
  if not ns.cdb or not IsOwnProfessionOpen() then
    return
  end
  local base = C_TradeSkillUI.GetBaseProfessionInfo and C_TradeSkillUI.GetBaseProfessionInfo()
  local professionID = base and Plain(base.professionID)
  if not professionID or professionID == 0 then
    return
  end
  local recipeIDs = C_TradeSkillUI.GetAllRecipeIDs()
  if type(recipeIDs) ~= "table" or #recipeIDs == 0 then
    return
  end

  local list, count = {}, 0
  local crafted = ns.db and ns.db.crafted
  for _, recipeID in ipairs(recipeIDs) do
    local info = C_TradeSkillUI.GetRecipeInfo(recipeID)
    if info and not info.isDummyRecipe and not info.isGatheringRecipe
        and not info.isSalvageRecipe and not info.isRecraft then
      local schematic = C_TradeSkillUI.GetRecipeSchematic(recipeID, false)
      local output = schematic and ReadOutput(recipeID, schematic)
      -- Anything a recipe makes, learned or not, isn't a world drop to farm.
      if crafted and type(output) == "number" then
        crafted[output] = true
      end
      if schematic and info.learned then
        list[recipeID] = {
          name = info.name,
          out = output,
          qmin = schematic.quantityMin or 1,
          qmax = schematic.quantityMax or schematic.quantityMin or 1,
          reagents = ReadReagents(schematic),
          diff = info.relativeDifficulty,
        }
        count = count + 1
      end
    end
  end

  ns.cdb.recipes[professionID] = {
    name = base.professionName or ns.SKILL_NAME[professionID] or L["Profession"],
    rank = Plain(base.skillLevel),
    max = Plain(base.maxSkillLevel),
    updated = time(),
    list = list,
  }
  ns.Fire("RECIPES_UPDATED", professionID, count)
end

---------------------------------------------------------------------------
-- Vendor prices (learned from every merchant you open)
---------------------------------------------------------------------------
local function MerchantItem(index)
  if C_MerchantFrame and C_MerchantFrame.GetItemInfo then
    local info = C_MerchantFrame.GetItemInfo(index)
    if info then
      return info.price, info.stackCount, info.numAvailable, info.hasExtendedCost
    end
    return nil
  end
  if GetMerchantItemInfo then
    local _, _, price, stack, available, _, _, extendedCost = GetMerchantItemInfo(index)
    return price, stack, available, extendedCost
  end
  return nil
end

function Professions:CaptureVendor()
  if not ns.db or not GetMerchantNumItems or not GetMerchantItemID then
    return
  end
  local learned = 0
  for index = 1, GetMerchantNumItems() or 0 do
    local itemID = GetMerchantItemID(index)
    local price, stack, available, extendedCost = MerchantItem(index)
    -- Only unlimited-supply items bought with gold; price covers the whole stack.
    if itemID and price and price > 0 and not extendedCost and available == -1 then
      ns.db.vendor[itemID] = price / math.max(1, stack or 1)
      learned = learned + 1
    end
  end
  if learned > 0 then
    ns.Fire("VENDOR_UPDATED", learned)
  end
end

---------------------------------------------------------------------------
-- Events
---------------------------------------------------------------------------
local function QueueSkills()
  ns.Debounce("skills", 1, function()
    Professions:ReadSkills()
  end)
end

local function QueueRecipes()
  ns.Debounce("recipes", 1, function()
    Professions:CaptureRecipes()
    Professions:ReadSkills()
  end)
end

local function QueueVendor()
  ns.Debounce("vendor", 0.5, function()
    Professions:CaptureVendor()
  end)
end

ns.Listen("LOGIN", function()
  C_Timer.After(3, function()
    Professions:ReadSkills()
  end)
end)
ns.On("SKILL_LINES_CHANGED", QueueSkills)
ns.On("CHAT_MSG_SKILL", QueueSkills)
ns.On("TRADE_SKILL_SHOW", QueueRecipes)
ns.On("TRADE_SKILL_LIST_UPDATE", QueueRecipes)
ns.On("TRADE_SKILL_DATA_SOURCE_CHANGED", QueueRecipes)
ns.On("MERCHANT_SHOW", QueueVendor)
ns.On("MERCHANT_UPDATE", QueueVendor)
ns.On("PLAYER_INTERACTION_MANAGER_FRAME_SHOW", function(kind)
  if Enum.PlayerInteractionType and kind == Enum.PlayerInteractionType.Merchant then
    QueueVendor()
  end
end)
