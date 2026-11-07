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
