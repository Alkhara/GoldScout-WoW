-- GoldScout community data: drop rates and spawn spots collected by players
-- with /gscout export and combined by tools/merge_data.py. Generated file;
-- don't edit by hand. Built from 1 submission(s).
-- Covered by the GoldScout Data License (DATA_LICENSE.md), not the MIT
-- License: no use outside GoldScout without permission.
local _, ns = ...

ns.COMMUNITY = {
  [3812] = { k = 20, p = 0, lmin = 19, lmax = 20, n = "Clattering Crawler", m = 1440, x = 0.1181, y = 0.2580, c = 20, i = { [2674] = { d = 9, q = 9 }, [2675] = { d = 10, q = 10 }, [3010] = { d = 11, q = 11 }, [4874] = { d = 4, q = 4 }, [5523] = { d = 8, q = 8 }, [14125] = { d = 1, q = 1 } }, pi = {} },
  [3814] = { k = 18, p = 0, lmin = 20, lmax = 21, n = "Spined Crawler", m = 1440, x = 0.1144, y = 0.2472, c = 18, i = { [2674] = { d = 6, q = 6 }, [2675] = { d = 7, q = 7 }, [3010] = { d = 2, q = 2 }, [5523] = { d = 6, q = 6 }, [5569] = { d = 9, q = 9 }, [17057] = { d = 4, q = 4 } }, pi = {} },
}

-- The export snapshot of each install included above, so a player's own
-- client can take its shared loot back out (see Community.lua).
ns.COMMUNITY_SOURCES = {
  ["m00jxkjr841x"] = 2,
}
ns.COMMUNITY_CAP = 1000
