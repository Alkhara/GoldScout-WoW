-- GoldScout upload service schema (D1 / SQLite).
-- One row per install (one WoW account's GoldScout data): the newest export
-- snapshot it uploaded, and a hash of its upload token. No IP addresses are
-- stored; registrations keep only a salted hash for 2 days for rate limiting.
CREATE TABLE IF NOT EXISTS installs (
  install_id TEXT PRIMARY KEY,
  token_hash TEXT NOT NULL,
  seq INTEGER NOT NULL,
  body TEXT NOT NULL,
  terms TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  uploads INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS installs_updated ON installs (updated_at);

CREATE TABLE IF NOT EXISTS registrations (
  ip_hash TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS registrations_ip ON registrations (ip_hash, created_at);

-- Auction house prices from Blizzard's Game Data API (WoW Forever), sent by
-- tools/ah_prices.py: one row per auction house with its newest snapshot,
-- reduced to {"itemID":[lowest unit buyout in copper, quantity listed]}.
-- No player data. Blizzard's API terms allow keeping API data for at most
-- 30 days, so rows with older snapshots are deleted on every update.
CREATE TABLE IF NOT EXISTS ah_houses (
  region TEXT NOT NULL,
  house INTEGER NOT NULL,
  name TEXT NOT NULL,
  ruleset INTEGER,          -- null until mapped (data/ah_houses.json)
  ruleset_name TEXT,
  faction TEXT NOT NULL,    -- Alliance, Horde or Neutral (Blackwater)
  snapshot INTEGER NOT NULL, -- Blizzard's Last-Modified, unix seconds
  fetched INTEGER NOT NULL,
  items INTEGER NOT NULL,
  prices TEXT NOT NULL,
  PRIMARY KEY (region, house)
);
