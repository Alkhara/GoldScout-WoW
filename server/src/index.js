// GoldScout upload service (Cloudflare Worker + D1).
//
// The companion app uploads each WoW account's latest drop data export here.
// The service only does quick checks and keeps the newest snapshot per
// install; the full validation (tools/submission.py) runs in the GitHub
// merge workflow, which reads uploads through the admin-only list endpoint
// and opens the data pull request for review.
//
//   POST /v1/uploads   body: export text. Headers: X-GoldScout-Terms, and
//                      Authorization: Bearer <token> after the first upload.
//                      X-GoldScout-Recovery: the install's recovery secret
//                      (companion 0.12.26+): stored hashed, and if the token
//                      was lost, a matching secret gets a new one in "token".
//                      The website's share page (wowgoldscout.com/share,
//                      site/share.js) posts here too, from the browser:
//                      OPTIONS answers its CORS preflight (preflight() below).
//   GET  /v1/uploads   admin only (Authorization: Bearer <ADMIN_TOKEN>).
//                      ?since=<unix seconds> limits it to newer uploads. Each
//                      upload lists the companion version it last came from.
//   PUT  /v1/admin/stats   admin only; the dashboard statistics from
//                      tools/admin_stats.py.
//   GET  /admin, /admin/api/summary, POST /admin/api/errors/dismiss   the
//                      admin dashboard (src/admin.js),
//                      behind Cloudflare Access.
//   GET  /v1/prices    auction houses with prices: id, ruleset, faction,
//                      snapshot time, item count. Public.
//   GET  /v1/prices/<region>/<house>   one house's prices; ?ago=N (1 to 29): its first
//                      snapshot from N days ago or the nearest day before, with "day":
//                      {"itemID": [lowest unit buyout in copper, quantity]}.
//   PUT  /v1/admin/prices/<region>/<house>   admin only; tools/ah_prices.py
//                      sends each new snapshot (metadata in X- headers).
//   PUT  /v1/admin/realms/<region>   admin only; {"realm": ruleset id}, the
//                      whole map for that region (listed by GET /v1/prices).
//   GET  /v1/leaderboard, GET /v1/leaderboard/zones, GET and PUT /v1/leaderboard/me, PUT /v1/admin/leaderboard
//                      the contributor leaderboard (src/leaderboard.js).
//   GET  /health
//
// Alerts (alerts.js): the hourly cron posts problems to a Discord webhook
// (ALERT_WEBHOOK_URL secret) when they start, daily while open, and when they clear.
//
// Cron triggers (wrangler.toml) start GitHub workflows on time: GitHub's own
// schedule can skip runs for hours. SCHEDULE says which cron starts which
// workflow; the GITHUB_DISPATCH_TOKEN secret (a fine-grained token for this
// repository with Actions: read and write) is all the access it has.
//
// Prices come from Blizzard's Game Data API. Its terms require naming Blizzard
// as the source (SOURCE, in every price response) and keeping data at most 30
// days. The price lists are stored and served as text, never parsed here, so
// even the largest house stays within the free plan's CPU time.

// One export; tools/submission.py has the same limits (MAX_BYTES, MAX_MOBS, MAX_EXTRA_LINES). A long-time
// player's export passes 60 KB, the share form's limit, which only GitHub issues need.
const MAX_BYTES = 250000;
const MAX_LINES = 1 + 1500 + 20000; // header, mobs, @ lines (names, item details, crafted items, areas, fishing)
const HEADER = /^GoldScout-export [2345]\^([a-z0-9]{12})\^([1-9][0-9]{0,8})$/;
const EXTRA_LINE = /^@[imcqla]\^[0-9]{1,9}\^[^^]*$/;
// Fishing: @f^uiMapID^spot^catches^skill^items^cells (tools/submission.py checks the rest).
const FISH_LINE = /^@f\^[0-9]{1,9}\^[0-9]{1,9}\^[0-9]{1,9}\^[0-9]{1,3}\^[0-9:,]*\^[0-9:,]*$/;
const TERMS_VERSIONS = new Set(["2026-11-07"]);
const NEW_INSTALLS_PER_IP_PER_DAY = 5;
// GoldScout's recovery secret for an install: 32 random letters and digits from its saved data.
const RECOVERY_SECRET = /^[a-z0-9]{32}$/;
// "GoldScoutCompanion/0.8.0 (macOS)"; companions before 0.8.0 send no system.
const CLIENT_AGENT = /^GoldScoutCompanion\/([0-9A-Za-z.+-]{1,24})(?: \(([A-Za-z]{1,16})\))?$/;
const CLIENT_SYSTEMS = new Set(["Windows", "macOS"]);
// Uploads from the website's share page are recorded as client "web".
const SITE_ORIGINS = new Set(["https://wowgoldscout.com", "https://www.wowgoldscout.com"]);
// CORS preflight answers for the routes the share page calls from the browser (site/share.js): uploads,
// and the uploader's own leaderboard entry. They take the upload token in a header, never cookies, so
// any origin may call them, as any program can.
function preflight(methods, headers) {
  return new Response(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": methods,
      "Access-Control-Allow-Headers": headers,
      "Access-Control-Max-Age": "86400",
    },
  });
}
const CLIENT_REGIONS = new Set(["us", "eu", "kr", "tw", "cn"]);
const SOURCE = "Auction data from the Blizzard Entertainment Game Data API. GoldScout is not affiliated with or endorsed by Blizzard.";
const PRICES_MAX_BYTES = 1900000; // D1 rows hold up to 2 MB
const PRICE_ENTRY = String.raw`"[0-9]{1,9}":\[[0-9]{1,15},[0-9]{1,9}\]`;
const PRICES_FORMAT = new RegExp(String.raw`^\{(?:${PRICE_ENTRY}(?:,${PRICE_ENTRY})*)?\}$`);
const MAX_AGE_SECONDS = 30 * 86400; // Blizzard Developer API Terms 2(s)
const REGIONS = new Set(["us", "eu", "kr", "tw"]);
const AH_FACTIONS = new Set(["Alliance", "Horde", "Neutral"]);
const HOUSE_PATH = /^\/v1\/prices\/([a-z]{2})\/([0-9]{1,6})$/;
const ADMIN_HOUSE_PATH = /^\/v1\/admin\/prices\/([a-z]{2})\/([0-9]{1,6})$/;
const ADMIN_REALMS_PATH = /^\/v1\/admin\/realms\/([a-z]{2})$/;
const REALM_NAME = /^[A-Za-z0-9' -]{1,64}$/;
const MAX_REALMS = 500;
const REPOSITORY = "Alkhara/GoldScout-WoW";
const SCHEDULE = {
  "7,22,37,52 * * * *": ["ah-prices.yml"], // Blizzard's snapshots land around :16
  "17 * * * *": ["data-merge.yml"],
  // Daily; GitHub skipped its own 15:00 runs. site-refresh rebuilds the site when main had no push in 20 hours.
  "0 15 * * *": ["data-release.yml", "site-refresh.yml"],
};
// Hourly: alerts.js checks what the dashboard marks red and tells Discord.
const ALERT_CRON = "17 * * * *";

import { handleAdmin, storeStats } from "./admin.js";
import { receiveErrors } from "./errors.js";
import { checkAlerts, recordDispatchFailure } from "./alerts.js";
import { handleLeaderboard } from "./leaderboard.js";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    try {
      if (url.pathname === "/health") {
        return json({ ok: true });
      }
      const adminToken = (r) => isAdminToken(r, env);
      const tooMany = await limited(request, env, url);
      if (tooMany) {
        return tooMany;
      }
      const admin = await handleAdmin(request, env, url, adminToken);
      if (admin) {
        return admin;
      }
      if (url.pathname === "/v1/leaderboard/me" && request.method === "OPTIONS") {
        return preflight("GET, PUT", "Authorization, Content-Type, X-GoldScout-Install");
      }
      if (url.pathname.startsWith("/v1/leaderboard") || url.pathname === "/v1/admin/leaderboard") {
        const answer = await handleLeaderboard(request, env, url,
          { json, publicJson, sha256, sameText, bearer, isAdminToken: adminToken });
        if (answer) {
          if (url.pathname === "/v1/leaderboard/me") {
            answer.headers.set("Access-Control-Allow-Origin", "*");   // the share page reads it
          }
          return answer;
        }
      }
      if (url.pathname === "/v1/admin/stats" && request.method === "PUT") {
        return await storeStats(request, env, adminToken);
      }
      if (url.pathname === "/v1/uploads" && request.method === "POST") {
        const answer = await receive(request, env);
        answer.headers.set("Access-Control-Allow-Origin", "*");   // the website's share page reads the reply
        return answer;
      }
      if (url.pathname === "/v1/uploads" && request.method === "OPTIONS") {
        return preflight("POST", "Authorization, Content-Type, X-GoldScout-Terms");
      }
      if (url.pathname === "/v1/errors" && request.method === "POST") {
        return await receiveErrors(request, env, clientVersion(request));
      }
      if (url.pathname === "/v1/uploads" && request.method === "GET") {
        return await list(request, env, url);
      }
      if (url.pathname === "/v1/prices" && request.method === "GET") {
        return await priceHouses(env);
      }
      const house = HOUSE_PATH.exec(url.pathname);
      if (house && request.method === "GET") {
        return await housePrices(env, house[1], Number(house[2]), url.searchParams.get("ago"));
      }
      const adminHouse = ADMIN_HOUSE_PATH.exec(url.pathname);
      if (adminHouse && request.method === "PUT") {
        return await storePrices(request, env, adminHouse[1], Number(adminHouse[2]));
      }
      const adminRealms = ADMIN_REALMS_PATH.exec(url.pathname);
      if (adminRealms && request.method === "PUT") {
        return await storeRealms(request, env, adminRealms[1]);
      }
      return json({ error: "Not found." }, 404);
    } catch (error) {
      console.error(error);
      return json({ error: "Server error." }, 500);
    }
  },

  async scheduled(event, env, ctx) {
    // A failed start is recorded for the next alert check (an expired GITHUB_DISPATCH_TOKEN would otherwise
    // only show in Cloudflare's logs), then still thrown, so the cron shows as failed there too.
    ctx.waitUntil(startWorkflows(SCHEDULE[event.cron] || [], env).catch(async (error) => {
      await recordDispatchFailure(env, error.message).catch(() => {});
      throw error;
    }));
    if (event.cron === ALERT_CRON) {
      ctx.waitUntil(checkAlerts(env));   // separate, so a failed alert never stops a workflow starting
    }
  },
};

// Per-network limits on the API (wrangler.toml [[ratelimits]]): a flood from one address gets 429s before
// it reaches the database. Not counted: preflights, requests with the admin token (GitHub's workflows), and
// requests from this computer (no CF-Connecting-IP, or a loopback one: local development and tests;
// Cloudflare always sets the real address). If a limiter fails, the request goes through: the
// per-install and per-reporter limits still apply.
const WRITE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
const LOOPBACK = new Set(["127.0.0.1", "::1"]);

// The key a request is counted under: its IPv4 address, or its IPv6 /64 (one household's block, so an
// attacker can't dodge the limit by changing the last part of their address).
export function networkKey(ip) {
  if (!ip.includes(":")) {
    return ip;
  }
  const [head, tail = ""] = ip.toLowerCase().split("::");
  const left = head ? head.split(":") : [];
  const right = tail ? tail.split(":") : [];
  const groups = ip.includes("::") ? [...left, ...Array(Math.max(0, 8 - left.length - right.length)).fill("0"), ...right]
    : left;
  return groups.slice(0, 4).map((g) => g.replace(/^0+(?=.)/, "")).join(":") + "::/64";
}

async function limited(request, env, url) {
  if (!url.pathname.startsWith("/v1/") || request.method === "OPTIONS") {
    return null;
  }
  const ip = request.headers.get("CF-Connecting-IP");
  if (!ip || LOOPBACK.has(ip) || isAdminToken(request, env)) {
    return null;
  }
  const key = networkKey(ip);
  for (const limiter of [env.API_LIMIT, WRITE_METHODS.has(request.method) ? env.WRITE_LIMIT : null]) {
    if (!limiter) {
      continue;
    }
    let outcome;
    try {
      outcome = await limiter.limit({ key });
    } catch {
      continue;
    }
    if (outcome && outcome.success === false) {
      return new Response(JSON.stringify({ error: "Too many requests from your network; try again in a minute." }), {
        status: 429,
        headers: { "Content-Type": "application/json; charset=utf-8", "Retry-After": "60",
          "Access-Control-Allow-Origin": "*" },
      });
    }
  }
  return null;
}

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

// Public price responses: readable from the website (any origin) and cacheable
// for a few minutes, since snapshots change at most a few times an hour.
function publicJson(text, status = 200) {
  return new Response(text, {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Access-Control-Allow-Origin": "*",
      "Cache-Control": status === 200 ? "public, max-age=300" : "no-store",
    },
  });
}

async function sha256(text) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function sameText(a, b) {
  const left = new TextEncoder().encode(a);
  const right = new TextEncoder().encode(b);
  return left.length === right.length && crypto.subtle.timingSafeEqual(left, right);
}

function isAdminToken(request, env) {
  return Boolean(env.ADMIN_TOKEN) && sameText(bearer(request), env.ADMIN_TOKEN);
}

function bearer(request) {
  const value = request.headers.get("Authorization") || "";
  return value.startsWith("Bearer ") ? value.slice(7).trim() : "";
}

function newToken() {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

// The companion version from the User-Agent ("0.7.0"), or "other".
function clientVersion(request) {
  const match = CLIENT_AGENT.exec(request.headers.get("User-Agent") || "");
  if (match) {
    return match[1];
  }
  return SITE_ORIGINS.has(request.headers.get("Origin") || "") ? "web" : "other";
}

// The companion's system from the User-Agent ("Windows" or "macOS"), or null.
function clientSystem(request) {
  const match = CLIENT_AGENT.exec(request.headers.get("User-Agent") || "");
  return match && CLIENT_SYSTEMS.has(match[2]) ? match[2] : null;
}

// The install's region from the companion ("eu"), or null.
function clientRegion(request) {
  const region = (request.headers.get("X-GoldScout-Region") || "").trim().toLowerCase();
  return CLIENT_REGIONS.has(region) ? region : null;
}

// Statements that record the install's companion version, and its system and
// region when the companion sent them.
function recordClient(env, installId, request, now) {
  const statements = [env.DB.prepare(
    "INSERT INTO install_clients (install_id, client, updated_at) VALUES (?, ?, ?) " +
    "ON CONFLICT (install_id) DO UPDATE SET client = excluded.client, updated_at = excluded.updated_at",
  ).bind(installId, clientVersion(request), now)];
  const system = clientSystem(request);
  if (system) {
    statements.push(env.DB.prepare(
      "INSERT INTO install_os (install_id, os, updated_at) VALUES (?, ?, ?) " +
      "ON CONFLICT (install_id) DO UPDATE SET os = excluded.os, updated_at = excluded.updated_at",
    ).bind(installId, system, now));
  }
  const region = clientRegion(request);
  if (region) {
    statements.push(env.DB.prepare(
      "INSERT INTO install_region (install_id, region, updated_at) VALUES (?, ?, ?) " +
      "ON CONFLICT (install_id) DO UPDATE SET region = excluded.region, updated_at = excluded.updated_at",
    ).bind(installId, region, now));
  }
  return statements;
}

async function receive(request, env) {
  const declared = Number(request.headers.get("Content-Length") || 0);
  if (declared > MAX_BYTES) {
    return json({ error: "The export is too large." }, 413);
  }
  const body = (await request.text()).replace(/\r/g, "");
  if (new TextEncoder().encode(body).length > MAX_BYTES) {
    return json({ error: "The export is too large." }, 413);
  }
  if (!TERMS_VERSIONS.has(request.headers.get("X-GoldScout-Terms") || "")) {
    return json({ error: "Agree to the current GoldScout Contributor Terms in the companion first." }, 400);
  }
  const lines = body.split("\n").filter((line) => line.trim() !== "");
  const match = HEADER.exec(lines[0] || "");
  if (!match) {
    return json({ error: "This isn't a GoldScout export. Update GoldScout and the companion." }, 400);
  }
  const malformed = (line) => (line.startsWith("@") ? !(EXTRA_LINE.test(line) || FISH_LINE.test(line))
    : line.split("^").length !== 12);
  if (lines.length < 2 || lines.length > MAX_LINES || lines.slice(1).some(malformed)) {
    return json({ error: "The export is malformed." }, 400);
  }
  const [, installId, seqText] = match;
  const seq = Number(seqText);
  const text = lines.join("\n") + "\n";
  const now = Math.floor(Date.now() / 1000);
  const minSeconds = Number(env.MIN_SECONDS_BETWEEN_UPLOADS ?? 60);

  const row = await env.DB.prepare("SELECT token_hash, seq, updated_at FROM installs WHERE install_id = ?")
    .bind(installId).first();
  const secret = (request.headers.get("X-GoldScout-Recovery") || "").trim();
  const secretHash = RECOVERY_SECRET.test(secret) ? await sha256("recovery:" + secret) : null;
  const keepSecret = () => (secretHash ? [env.DB.prepare(
    "INSERT INTO install_secrets (install_id, secret_hash, updated_at) VALUES (?, ?, ?) " +
    "ON CONFLICT (install_id) DO UPDATE SET secret_hash = excluded.secret_hash, updated_at = excluded.updated_at",
  ).bind(installId, secretHash, now)] : []);

  if (!row) {
    // First upload from this install: register it and hand back its token.
    const ip = request.headers.get("CF-Connecting-IP") || "unknown";
    const ipHash = await sha256((env.IP_SALT || "") + ip);
    const recent = await env.DB.prepare(
      "SELECT COUNT(*) AS n FROM registrations WHERE ip_hash = ? AND created_at > ?",
    ).bind(ipHash, now - 86400).first();
    if ((recent?.n ?? 0) >= NEW_INSTALLS_PER_IP_PER_DAY) {
      return json({ error: "Too many new installs from this network today." }, 429);
    }
    const token = newToken();
    await env.DB.batch([
      env.DB.prepare(
        "INSERT INTO installs (install_id, token_hash, seq, body, terms, created_at, updated_at, uploads) " +
        "VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
      ).bind(installId, await sha256(token), seq, text, request.headers.get("X-GoldScout-Terms"), now, now),
      env.DB.prepare("INSERT INTO registrations (ip_hash, created_at) VALUES (?, ?)").bind(ipHash, now),
      env.DB.prepare("DELETE FROM registrations WHERE created_at < ?").bind(now - 2 * 86400),
      ...recordClient(env, installId, request, now),
      ...keepSecret(),
    ]);
    return json({ status: "registered", token }, 201);
  }

  // The token proves this is the companion that registered the install. One that lost its token
  // (a new PC, Windows reinstalled) proves it reads the same saved data with the recovery secret,
  // and gets a new token; the old one stops working.
  let token = bearer(request);
  let issued = {};
  let updates = [];
  if (token && sameText(await sha256(token), row.token_hash)) {
    updates = keepSecret();
  } else {
    const stored = secretHash && await env.DB.prepare("SELECT secret_hash FROM install_secrets WHERE install_id = ?")
      .bind(installId).first();
    if (!stored || !sameText(secretHash, stored.secret_hash)) {
      return json({ error: "This GoldScout data is registered to another copy of the companion." }, 403);
    }
    token = newToken();
    issued = { token };
    updates = [env.DB.prepare("UPDATE installs SET token_hash = ? WHERE install_id = ?")
      .bind(await sha256(token), installId)];
  }
  if (seq <= row.seq) {
    await env.DB.batch([...updates, ...recordClient(env, installId, request, now)]);
    return json({ status: "unchanged", ...issued });
  }
  if (now - row.updated_at < minSeconds) {
    if (issued.token) {
      // The new token has to reach the companion, and an error reply wouldn't save it: keep the
      // stored export for now; the companion's next export uploads with the new token.
      await env.DB.batch([...updates, ...recordClient(env, installId, request, now)]);
      return json({ status: "unchanged", ...issued });
    }
    return json({ error: "Uploading too often; try again in a minute." }, 429);
  }
  await env.DB.batch([
    env.DB.prepare(
      "UPDATE installs SET seq = ?, body = ?, terms = ?, updated_at = ?, uploads = uploads + 1 WHERE install_id = ?",
    ).bind(seq, text, request.headers.get("X-GoldScout-Terms"), now, installId),
    ...updates,
    ...recordClient(env, installId, request, now),
  ]);
  return json({ status: "stored", ...issued });
}

async function list(request, env, url) {
  if (!env.ADMIN_TOKEN || !sameText(bearer(request), env.ADMIN_TOKEN)) {
    return json({ error: "Not allowed." }, 401);
  }
  // ?bodies=0: every install without its export (a few hundred bytes each), so the hourly merge can see
  // what changed; ?ids=a,b,c (up to MAX_LIST_IDS): just those installs, exports included
  // (tools/fetch_uploads.py). Without either, every install with its export, as before.
  const since = Number(url.searchParams.get("since") || 0);
  const ids = (url.searchParams.get("ids") || "").split(",").filter(Boolean);
  if (ids.length > MAX_LIST_IDS || ids.some((id) => !INSTALL_ID.test(id))) {
    return json({ error: `ids: up to ${MAX_LIST_IDS} install IDs, comma-separated.` }, 400);
  }
  const columns = url.searchParams.get("bodies") === "0" && !ids.length ? "" : "body, ";
  const where = ids.length ? `install_id IN (${ids.map(() => "?").join(", ")})` : "installs.updated_at > ?";
  const { results } = await env.DB.prepare(
    `SELECT install_id, seq, ${columns}terms, created_at, uploads, installs.updated_at AS updated_at, client, os, ` +
    "region FROM installs LEFT JOIN install_clients USING (install_id) LEFT JOIN install_os USING (install_id) " +
    `LEFT JOIN install_region USING (install_id) WHERE ${where} ORDER BY installs.updated_at`,
  ).bind(...(ids.length ? ids : [since])).all();
  return json({ uploads: results });
}

const MAX_LIST_IDS = 50;
const INSTALL_ID = /^[a-z0-9]{12}$/;

const HOUSE_COLUMNS = "region, house, name, ruleset, ruleset_name, faction, snapshot, fetched, items";

function houseInfo(row) {
  return {
    region: row.region, house: row.house, name: row.name, ruleset: row.ruleset,
    rulesetName: row.ruleset_name, faction: row.faction, snapshot: row.snapshot,
    fetched: row.fetched, items: row.items,
  };
}

async function priceHouses(env) {
  const oldest = Math.floor(Date.now() / 1000) - MAX_AGE_SECONDS;
  const { results } = await env.DB.prepare(
    `SELECT ${HOUSE_COLUMNS} FROM ah_houses WHERE snapshot >= ? ORDER BY region, house`,
  ).bind(oldest).all();
  const realms = {};
  const { results: realmRows } = await env.DB.prepare(
    "SELECT region, realm, ruleset FROM ah_realms ORDER BY region, realm",
  ).all();
  for (const row of realmRows) {
    (realms[row.region] = realms[row.region] || {})[row.realm] = row.ruleset;
  }
  return publicJson(JSON.stringify({ source: SOURCE, houses: results.map(houseInfo), realms }));
}

// YYYY-MM-DD in UTC.
function utcDay(seconds) {
  return new Date(seconds * 1000).toISOString().slice(0, 10);
}

async function housePrices(env, region, house, ago) {
  const oldest = Math.floor(Date.now() / 1000) - MAX_AGE_SECONDS;
  if (ago !== null) {
    return await pastPrices(env, region, house, ago, oldest);
  }
  const row = await env.DB.prepare(
    `SELECT ${HOUSE_COLUMNS}, prices FROM ah_houses WHERE region = ? AND house = ? AND snapshot >= ?`,
  ).bind(region, house, oldest).first();
  if (!row) {
    return publicJson(JSON.stringify({ error: "No prices for that auction house." }), 404);
  }
  // Splice the stored text in rather than parsing and re-serializing it.
  const head = JSON.stringify({ ...houseInfo(row), source: SOURCE });
  return publicJson(head.slice(0, -1) + ',"prices":' + row.prices + "}");
}

// A house's first snapshot of the day `ago` days back, or of the nearest day before it.
async function pastPrices(env, region, house, ago, oldest) {
  const days = Number(ago);
  if (!Number.isInteger(days) || days < 1 || days > 29) {
    return publicJson(JSON.stringify({ error: "ago is a number of days from 1 to 29." }), 400);
  }
  const day = utcDay(Math.floor(Date.now() / 1000) - days * 86400);
  const row = await env.DB.prepare(
    "SELECT day, snapshot, prices FROM ah_daily WHERE region = ? AND house = ? AND day <= ? AND snapshot >= ? " +
    "ORDER BY day DESC LIMIT 1",
  ).bind(region, house, day, oldest).first();
  if (!row) {
    return publicJson(JSON.stringify({ error: "No prices from that long ago for that auction house." }), 404);
  }
  const head = JSON.stringify({ region, house, day: row.day, snapshot: row.snapshot, source: SOURCE });
  return publicJson(head.slice(0, -1) + ',"prices":' + row.prices + "}");
}

async function storePrices(request, env, region, house) {
  if (!env.ADMIN_TOKEN || !sameText(bearer(request), env.ADMIN_TOKEN)) {
    return json({ error: "Not allowed." }, 401);
  }
  const now = Math.floor(Date.now() / 1000);
  const header = (name) => (request.headers.get(name) || "").trim();
  const snapshot = Number(header("X-Snapshot"));
  const items = Number(header("X-Items"));
  const rulesetText = header("X-Ruleset");
  const ruleset = rulesetText === "" ? null : Number(rulesetText);
  const rulesetName = ruleset === null ? null : header("X-Ruleset-Name").slice(0, 40);
  const name = header("X-House-Name").slice(0, 60);
  const faction = header("X-Faction");
  if (!REGIONS.has(region) || !Number.isInteger(snapshot) || snapshot < now - MAX_AGE_SECONDS ||
      snapshot > now + 600 || !Number.isInteger(items) || items < 0 || !name || !AH_FACTIONS.has(faction) ||
      (ruleset !== null && (!Number.isInteger(ruleset) || ruleset < 1 || !rulesetName))) {
    return json({ error: "Missing or invalid price headers." }, 400);
  }
  if (Number(request.headers.get("Content-Length") || 0) > PRICES_MAX_BYTES) {
    return json({ error: "The price list is too large." }, 413);
  }
  const prices = await request.text();
  if (new TextEncoder().encode(prices).length > PRICES_MAX_BYTES || !PRICES_FORMAT.test(prices)) {
    return json({ error: "The price list is malformed or too large." }, 400);
  }
  const previous = await env.DB.prepare("SELECT snapshot FROM ah_houses WHERE region = ? AND house = ?")
    .bind(region, house).first();
  if (previous && previous.snapshot > snapshot) {
    return json({ status: "older" });
  }
  await env.DB.batch([
    env.DB.prepare(
      "INSERT INTO ah_houses (region, house, name, ruleset, ruleset_name, faction, snapshot, fetched, items, prices) " +
      "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (region, house) DO UPDATE SET " +
      "name = excluded.name, ruleset = excluded.ruleset, ruleset_name = excluded.ruleset_name, " +
      "faction = excluded.faction, snapshot = excluded.snapshot, fetched = excluded.fetched, " +
      "items = excluded.items, prices = excluded.prices",
    ).bind(region, house, name, ruleset, rulesetName, faction, snapshot, now, items, prices),
    env.DB.prepare("DELETE FROM ah_houses WHERE snapshot < ?").bind(now - MAX_AGE_SECONDS),
    // The day's first snapshot stays as that day's (the guides' trends compare days).
    env.DB.prepare("INSERT INTO ah_daily (region, house, day, snapshot, prices) VALUES (?, ?, ?, ?, ?) " +
      "ON CONFLICT (region, house, day) DO NOTHING").bind(region, house, utcDay(snapshot), snapshot, prices),
    env.DB.prepare("DELETE FROM ah_daily WHERE snapshot < ?").bind(now - MAX_AGE_SECONDS),
  ]);
  return json({ status: previous && previous.snapshot === snapshot ? "unchanged" : "stored" });
}

// Replaces a region's realm map. The body is small (a few dozen realms), so
// parsing it fits in the free plan's CPU time.
async function storeRealms(request, env, region) {
  if (!env.ADMIN_TOKEN || !sameText(bearer(request), env.ADMIN_TOKEN)) {
    return json({ error: "Not allowed." }, 401);
  }
  if (!REGIONS.has(region) || Number(request.headers.get("Content-Length") || 0) > 50000) {
    return json({ error: "Unknown region or body too large." }, 400);
  }
  let map;
  try {
    map = JSON.parse(await request.text());
  } catch {
    return json({ error: "The body must be JSON." }, 400);
  }
  const entries = map && typeof map === "object" && !Array.isArray(map) ? Object.entries(map) : null;
  if (!entries || entries.length > MAX_REALMS ||
      !entries.every(([realm, ruleset]) => REALM_NAME.test(realm) && Number.isInteger(ruleset) && ruleset > 0)) {
    return json({ error: "Expected {\"realm name\": ruleset id}." }, 400);
  }
  await env.DB.batch([
    env.DB.prepare("DELETE FROM ah_realms WHERE region = ?").bind(region),
    ...entries.map(([realm, ruleset]) =>
      env.DB.prepare("INSERT INTO ah_realms (region, realm, ruleset) VALUES (?, ?, ?)").bind(region, realm, ruleset)),
  ]);
  return json({ status: "stored", realms: entries.length });
}

// Starts each workflow on main. Failures are logged (Workers Logs) and fail
// the cron run, so they show in the dashboard; GitHub's own schedule remains
// as a backup. GITHUB_API is only set for local tests.
async function startWorkflows(workflows, env) {
  if (!workflows.length) {
    return;
  }
  if (!env.GITHUB_DISPATCH_TOKEN) {
    console.log("GITHUB_DISPATCH_TOKEN is not set; not starting " + workflows.join(", "));
    return;
  }
  const api = env.GITHUB_API || "https://api.github.com";
  const failed = [];
  for (const workflow of workflows) {
    const response = await fetch(`${api}/repos/${REPOSITORY}/actions/workflows/${workflow}/dispatches`, {
      method: "POST",
      headers: {
        Authorization: "Bearer " + env.GITHUB_DISPATCH_TOKEN,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "GoldScout-server",
        "X-GitHub-Api-Version": "2022-11-28",
      },
      body: JSON.stringify({ ref: "main" }),
    });
    if (response.status === 204) {
      console.log("Started " + workflow);
    } else {
      const detail = (await response.text()).slice(0, 300);
      console.error(`Starting ${workflow}: HTTP ${response.status} ${detail}`);
      failed.push(`${workflow} (HTTP ${response.status})`);
    }
  }
  if (failed.length) {
    throw new Error("Could not start " + failed.join(", "));
  }
}
