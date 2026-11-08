-- GoldScout community data: drop rates and spawn spots collected by players
-- with /gscout export and combined by tools/merge_data.py. Generated file;
-- don't edit by hand. Built from 1 submission(s).
-- Covered by the GoldScout Data License (DATA_LICENSE.md), not the MIT
-- License: no use outside GoldScout without permission.
local _, ns = ...

ns.COMMUNITY = {
  [3809] = { k = 27, p = 0, lmin = 21, lmax = 22, n = "Ashenvale Bear", m = 1440, x = 0.5474, y = 0.5436, c = 27, i = { [2940] = { d = 9, q = 9 }, [3702] = { d = 5, q = 5 }, [3730] = { d = 8, q = 8 }, [5635] = { d = 1, q = 1 }, [11406] = { d = 7, q = 7 }, [11407] = { d = 7, q = 7 }, [250182] = { d = 1, q = 1 } }, pi = {} },
  [3812] = { k = 20, p = 0, lmin = 19, lmax = 20, n = "Clattering Crawler", m = 1440, x = 0.1181, y = 0.2580, c = 20, i = { [2674] = { d = 9, q = 9 }, [2675] = { d = 10, q = 10 }, [3010] = { d = 11, q = 11 }, [4874] = { d = 4, q = 4 }, [5523] = { d = 8, q = 8 }, [14125] = { d = 1, q = 1 } }, pi = {} },
  [3814] = { k = 18, p = 0, lmin = 20, lmax = 21, n = "Spined Crawler", m = 1440, x = 0.1144, y = 0.2472, c = 18, i = { [2674] = { d = 6, q = 6 }, [2675] = { d = 7, q = 7 }, [3010] = { d = 2, q = 2 }, [5523] = { d = 6, q = 6 }, [5569] = { d = 9, q = 9 }, [17057] = { d = 4, q = 4 } }, pi = {} },
  [3817] = { k = 15, p = 0, lmin = 22, lmax = 23, n = "Shadowhorn Stag", m = 1440, x = 0.5346, y = 0.5412, c = 15, i = { [1206] = { d = 1, q = 1 }, [5471] = { d = 9, q = 9 }, [5566] = { d = 7, q = 7 }, [5871] = { d = 2, q = 2 } }, pi = {} },
  [4054] = { k = 15, p = 0, lmin = 24, lmax = 25, n = "Laughing Sister", m = 1440, x = 0.5873, y = 0.5544, c = 15, i = { [1205] = { d = 1, q = 1 }, [2592] = { d = 2, q = 2 }, [2782] = { d = 1, q = 1 }, [3012] = { d = 1, q = 1 }, [4538] = { d = 2, q = 2 }, [16645] = { d = 1, q = 1 }, [16654] = { d = 1, q = 1 }, [16656] = { d = 1, q = 1 }, [211784] = { d = 1, q = 1 } }, pi = {} },
}

-- The export snapshot of each install included above, so a player's own
-- client can take its shared loot back out (see Community.lua).
ns.COMMUNITY_SOURCES = {
  ["m00jxkjr841x"] = 7,
}
ns.COMMUNITY_CAP = 1000

-- Items players' professions can make, so Market rows leave them out.
ns.COMMUNITY_CRAFTED = {
  [118] = true, [858] = true, [929] = true, [1251] = true, [2300] = true, [2302] = true, [2303] = true, [2304] = true, [2308] = true, [2309] = true,
  [2310] = true, [2313] = true, [2314] = true, [2315] = true, [2316] = true, [2318] = true, [2319] = true, [2581] = true, [3530] = true, [3531] = true,
  [3719] = true, [4231] = true, [4233] = true, [4234] = true, [4236] = true, [4237] = true, [4239] = true, [4242] = true, [4243] = true, [4246] = true,
  [4247] = true, [4249] = true, [4251] = true, [4253] = true, [4257] = true, [4265] = true, [5957] = true, [5961] = true, [5962] = true, [6218] = true,
  [6452] = true, [6468] = true, [7276] = true, [7277] = true, [7278] = true, [7279] = true, [7281] = true, [7282] = true, [7285] = true, [7348] = true,
  [7371] = true, [7372] = true, [11287] = true, [247786] = true, [247789] = true, [252424] = true, [252425] = true, [252426] = true, [252427] = true, [255716] = true,
  [279968] = true, [279978] = true,
}
