-- GoldScout community data helpers. These are plain functions with no game
-- API calls, so the tests can run them outside the game.
--
-- Each export starts with "GoldScout-export 2^<install ID>^<snapshot>". The
-- install ID is random and identifies one WoW account's GoldScout data, not a
-- person. Data_Community.lua lists which snapshot of each install it includes
-- (ns.COMMUNITY_SOURCES), so your own client can take your shared loot back
-- out of the community numbers instead of counting it twice.
local _, ns = ...

local Community = {}
ns.Community = Community

Community.HEADER_PATTERN = "^GoldScout%-export [234]%^(%w+)%^(%d+)$"
Community.DEFAULT_CAP = 1000

local function Round(value)
  return math.floor(value + 0.5)
end

local function Split(line)
  local fields, start = {}, 1
  while true do
    local found = line:find("^", start, true)
    if not found then
      fields[#fields + 1] = line:sub(start)
      return fields
    end
    fields[#fields + 1] = line:sub(start, found - 1)
    start = found + 1
  end
end

local function Items(text)
  local items = {}
  for itemID, drops, quantity in (text or ""):gmatch("(%d+):(%d+):(%d+)") do
    items[tonumber(itemID)] = { d = tonumber(drops), q = tonumber(quantity) }
  end
  return items
end

-- Export text -> install ID, snapshot number, { [npcID] = mob }. Returns nil
-- for anything that isn't a version 2 export.
function Community.ParseExport(text)
  local lines = {}
  for line in tostring(text or ""):gmatch("[^\r\n]+") do
    lines[#lines + 1] = line
  end
  local install, seq = (lines[1] or ""):match(Community.HEADER_PATTERN)
  if not install then
    return nil
  end
  local mobs = {}
  for i = 2, #lines do
    local f = Split(lines[i])
    local npcID = tonumber(f[1])
    if #f == 12 and npcID then
      mobs[npcID] = {
        k = tonumber(f[2]) or 0, p = tonumber(f[3]) or 0, m = tonumber(f[6]) or 0,
        x = tonumber(f[7]) or 0, y = tonumber(f[8]) or 0, c = tonumber(f[9]) or 0,
        i = Items(f[11]), pi = Items(f[12]),
      }
    end
  end
  return install, tonumber(seq), mobs
end

-- What one player's mob counts add to the community data, after the same
-- per-player cap tools/merge_data.py applies (drops scale down with kills).
local function Scaled(items, factor)
  local scaled = {}
  for itemID, stat in pairs(items or {}) do
    if factor >= 1 then
      scaled[itemID] = { d = stat.d, q = stat.q }
    else
      local drops = Round(stat.d * factor)
      if drops > 0 then
        scaled[itemID] = { d = drops, q = math.max(drops, Round(stat.q * factor)) }
      end
    end
  end
  return scaled
end

function Community.Contribution(mob, cap)
  local kills, picks = mob.k or 0, mob.p or 0
  return {
    k = math.min(kills, cap), p = math.min(picks, cap), c = math.min(mob.c or 0, cap),
    m = mob.m, x = mob.x, y = mob.y,
    i = Scaled(mob.i, kills > 0 and math.min(1, cap / kills) or 1),
    pi = Scaled(mob.pi, picks > 0 and math.min(1, cap / picks) or 1),
  }
end

local function SubtractItems(items, own)
  for itemID, stat in pairs(own) do
    local entry = items and items[itemID]
    if entry then
      entry.d = math.max(0, (entry.d or 0) - stat.d)
      entry.q = math.max(0, (entry.q or 0) - stat.q)
      if entry.d == 0 then
        items[itemID] = nil
      end
    end
  end
end

-- Takes one player's mobs back out of the community table, in place.
function Community.Subtract(community, mobs, cap)
  cap = cap or Community.DEFAULT_CAP
  for npcID, mob in pairs(mobs) do
    local entry = community[npcID]
    if entry then
      local own = Community.Contribution(mob, cap)
      entry.k = math.max(0, (entry.k or 0) - own.k)
      entry.p = math.max(0, (entry.p or 0) - own.p)
      SubtractItems(entry.i, own.i)
      SubtractItems(entry.pi, own.pi)
      if entry.m and entry.m == own.m and own.c > 0 and (entry.c or 0) > 0 then
        local rest = entry.c - own.c
        if rest > 0 then
          entry.x = math.max(0, math.min(1, (entry.x * entry.c - own.x * own.c) / rest))
          entry.y = math.max(0, math.min(1, (entry.y * entry.c - own.y * own.c) / rest))
          entry.c = rest
        else
          entry.m, entry.x, entry.y, entry.c = nil, nil, nil, nil
        end
      end
      if entry.k + entry.p == 0 then
        community[npcID] = nil
      end
    end
  end
end

-- Your saved loot (GoldScoutDB.drops) in the same shape ParseExport returns.
function Community.MobsFromDrops(drops)
  local mobs = {}
  for npcID, entry in pairs(drops or {}) do
    local count = entry.c or 0
    mobs[npcID] = {
      k = entry.k or 0, p = entry.p or 0, m = entry.m or 0, c = count,
      x = count > 0 and entry.sx / count or 0, y = count > 0 and entry.sy / count or 0,
      i = entry.i or {}, pi = entry.pi or {},
    }
  end
  return mobs
end

-- Removes your own shared loot from ns.COMMUNITY. exports is
-- GoldScoutDB.exports; drops is GoldScoutDB.drops for the fallback. Returns
-- "snapshot", "estimate" or nil (nothing of yours is in the community data).
function Community.RemoveOwn(community, sources, cap, install, exports, drops)
  local included = install and sources and sources[install]
  if not included then
    return nil
  end
  local text = exports and exports.list and exports.list[included]
  if text then
    local _, _, mobs = Community.ParseExport(text)
    if mobs then
      Community.Subtract(community, mobs, cap)
      return "snapshot"
    end
  end
  -- The shared snapshot is gone (pruned, or shared from another PC): take out
  -- everything you've looted, which can only undercount your newest loot.
  Community.Subtract(community, Community.MobsFromDrops(drops), cap)
  return "estimate"
end
