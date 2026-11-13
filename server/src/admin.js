// GoldScout admin dashboard: /admin (page, script, styles), /admin/api/summary,
// POST /admin/api/errors/dismiss and POST /admin/api/names/review (leaderboard
// names waiting for approval).
//
// Who may see it: Cloudflare Access sits in front of the admin hostname and
// signs every request it lets through (Cf-Access-Jwt-Assertion). The Worker
// checks that signature itself against the Access team's public keys, so the
// dashboard stays closed even when reached another way (workers.dev) or if the
// Access rule were misconfigured. Settings (wrangler vars/secrets):
//   ACCESS_TEAM_DOMAIN  e.g. goldscout.cloudflareaccess.com
//   ACCESS_AUD          the Access application's audience tag
//   ADMIN_EMAILS        optional comma-separated allow-list on top of Access
// Without ACCESS_TEAM_DOMAIN and ACCESS_AUD nothing is shown. The admin bearer
// token (ADMIN_TOKEN) also opens /admin/api/summary, for scripts and tests.
// ADMIN_LOCAL=1 opens it on 127.0.0.1 for local development only.
//
// The heavy statistics come from tools/admin_stats.py (run by the hourly data
// merge workflow) through PUT /v1/admin/stats; this file adds cheap live counts.

import PAGE from "./admin/index.html";
import SCRIPT from "./admin/app.client.js";
import STYLES from "./admin/app.css";
import { dismissError } from "./errors.js";
import { pendingNames, reviewName } from "./leaderboard.js";

const STATS_MAX_BYTES = 1500000;
const KEYS_TTL_MS = 3600 * 1000;
const SECURITY_HEADERS = {
  "Cache-Control": "no-store",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
  "X-Frame-Options": "DENY",
  "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; " +
    "img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
};

let keyCache = { url: "", keys: [], fetched: 0 };

function respond(body, type, status = 200) {
  return new Response(body, { status, headers: { "Content-Type": type, ...SECURITY_HEADERS } });
}

function base64url(text) {
  const padded = text.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((text.length + 3) % 4);
  return Uint8Array.from(atob(padded), (c) => c.charCodeAt(0));
}

async function accessKeys(env, refresh) {
  const url = env.ACCESS_CERTS_URL || `https://${env.ACCESS_TEAM_DOMAIN}/cdn-cgi/access/certs`;
  if (!refresh && keyCache.url === url && Date.now() - keyCache.fetched < KEYS_TTL_MS) {
    return keyCache.keys;
  }
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error("Access keys: HTTP " + response.status);
  }
  const { keys } = await response.json();
  keyCache = { url, keys: Array.isArray(keys) ? keys : [], fetched: Date.now() };
  return keyCache.keys;
}

// The signed-in email from a valid Access token, or null.
export async function verifyAccess(token, env) {
  if (!token || !env.ACCESS_TEAM_DOMAIN || !env.ACCESS_AUD) {
    return null;
  }
  const parts = token.split(".");
  if (parts.length !== 3) {
    return null;
  }
  let header, payload;
  try {
    header = JSON.parse(new TextDecoder().decode(base64url(parts[0])));
    payload = JSON.parse(new TextDecoder().decode(base64url(parts[1])));
  } catch {
    return null;
  }
  if (header.alg !== "RS256" || !header.kid) {
    return null;
  }
  let jwk = (await accessKeys(env, false)).find((k) => k.kid === header.kid);
  if (!jwk) {
    jwk = (await accessKeys(env, true)).find((k) => k.kid === header.kid); // keys rotate
  }
  if (!jwk) {
    return null;
  }
  const key = await crypto.subtle.importKey("jwk", { kty: jwk.kty, n: jwk.n, e: jwk.e, alg: "RS256", ext: true },
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
  const signed = new TextEncoder().encode(parts[0] + "." + parts[1]);
  if (!await crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, base64url(parts[2]), signed)) {
    return null;
  }
  const now = Date.now() / 1000;
  const audiences = Array.isArray(payload.aud) ? payload.aud : [payload.aud];
  if (!audiences.includes(env.ACCESS_AUD) || !(payload.exp > now) || (payload.nbf && payload.nbf > now + 60) ||
      payload.iss !== `https://${env.ACCESS_TEAM_DOMAIN}`) {
    return null;
  }
  const email = String(payload.email || "").toLowerCase();
  if (env.ADMIN_EMAILS) {
    const allowed = env.ADMIN_EMAILS.toLowerCase().split(",").map((s) => s.trim()).filter(Boolean);
    if (!allowed.includes(email)) {
      return null;
    }
  }
  return email || "signed in";
}

async function identity(request, env, url, isAdminToken) {
  if (env.ADMIN_LOCAL === "1" && (url.hostname === "127.0.0.1" || url.hostname === "localhost")) {
    return "local development";
  }
  const access = await verifyAccess(request.headers.get("Cf-Access-Jwt-Assertion"), env);
  if (access) {
    return access;
  }
  if (url.pathname.startsWith("/admin/api/") && isAdminToken(request)) {
    return "admin token";
  }
  return null;
}

const CLOSED = `<!doctype html><meta charset="utf-8"><title>GoldScout admin</title>
<p>Not allowed. The GoldScout admin dashboard opens only through its Cloudflare Access sign-in.</p>`;

// Handles /admin paths; returns null for anything else.
export async function handleAdmin(request, env, url, isAdminToken) {
  const path = url.pathname;
  if (path !== "/admin" && !path.startsWith("/admin/")) {
    return null;
  }
  const dismissing = path === "/admin/api/errors/dismiss";
  const reviewing = path === "/admin/api/names/review";
  if (request.method !== (dismissing || reviewing ? "POST" : "GET")) {
    return respond("Method not allowed.", "text/plain; charset=utf-8", 405);
  }
  const who = await identity(request, env, url, isAdminToken);
  if (!who) {
    return respond(CLOSED, "text/html; charset=utf-8", 403);
  }
  if (dismissing) {
    return dismiss(request, env, url);
  }
  if (reviewing) {
    return review(request, env, url);
  }
  if (path === "/admin" || path === "/admin/") {
    return respond(PAGE, "text/html; charset=utf-8");
  }
  if (path === "/admin/app.js") {
    return respond(SCRIPT, "text/javascript; charset=utf-8");
  }
  if (path === "/admin/app.css") {
    return respond(STYLES, "text/css; charset=utf-8");
  }
  if (path === "/admin/api/summary") {
    return summary(env, who);
  }
  return respond("Not found.", "text/plain; charset=utf-8", 404);
}

// The JSON body of a dashboard button's POST, or a 403 response. JSON only, and
// only from the dashboard's own origin, so another site can't make a
// signed-in browser send it.
async function buttonBody(request, url) {
  const origin = request.headers.get("Origin");
  if ((origin && origin !== url.origin) || !(request.headers.get("Content-Type") || "").startsWith("application/json")) {
    return respond('{"error":"Not allowed."}', "application/json; charset=utf-8", 403);
  }
  try {
    return JSON.parse(await request.text());
  } catch {
    return null;
  }
}

// POST /admin/api/names/review {"id", "name", "approve"}: a leaderboard name's
// Approve or Reject button.
async function review(request, env, url) {
  const body = await buttonBody(request, url);
  if (body instanceof Response) {
    return body;
  }
  if (!body || !await reviewName(env, body.id, body.name, body.approve)) {
    return respond('{"error":"That name changed or was already reviewed; refresh."}',
      "application/json; charset=utf-8", 409);
  }
  return respond('{"status":"reviewed"}', "application/json; charset=utf-8");
}

// POST /admin/api/errors/dismiss {"fingerprint"}: the dashboard's Dismiss button.
async function dismiss(request, env, url) {
  const body = await buttonBody(request, url);
  if (body instanceof Response) {
    return body;
  }
  if (!body || !await dismissError(env, body.fingerprint)) {
    return respond('{"error":"Expected {\\"fingerprint\\": \\"32 hex\\"}."}', "application/json; charset=utf-8", 400);
  }
  return respond('{"status":"dismissed"}', "application/json; charset=utf-8");
}

async function summary(env, who) {
  const now = Math.floor(Date.now() / 1000);
  const [installs, clients, systems, regions, houses, realms, stats, errors, errors24, names] = await env.DB.batch([
    env.DB.prepare("SELECT COUNT(*) AS installs, COALESCE(SUM(updated_at > ?), 0) AS d1, " +
      "COALESCE(SUM(updated_at > ?), 0) AS d7, COALESCE(SUM(created_at > ?), 0) AS new7 FROM installs")
      .bind(now - 86400, now - 7 * 86400, now - 7 * 86400),
    env.DB.prepare("SELECT client, COUNT(*) AS n FROM install_clients GROUP BY client ORDER BY n DESC"),
    // Installs without a system are from companions before 0.8.0, which were Windows only.
    env.DB.prepare("SELECT install_os.os AS os, COUNT(*) AS n, COALESCE(SUM(installs.updated_at > ?), 0) AS d7 " +
      "FROM installs LEFT JOIN install_os USING (install_id) GROUP BY install_os.os ORDER BY n DESC")
      .bind(now - 7 * 86400),
    // Installs without a region are from companions before 0.9.0.
    env.DB.prepare("SELECT install_region.region AS region, COUNT(*) AS n, " +
      "COALESCE(SUM(installs.updated_at > ?), 0) AS d7 " +
      "FROM installs LEFT JOIN install_region USING (install_id) GROUP BY install_region.region ORDER BY n DESC")
      .bind(now - 7 * 86400),
    env.DB.prepare("SELECT region, house, name, ruleset, ruleset_name, faction, snapshot, fetched, items " +
      "FROM ah_houses ORDER BY region, house"),
    env.DB.prepare("SELECT region, realm, ruleset FROM ah_realms ORDER BY region, realm"),
    env.DB.prepare("SELECT body, updated_at FROM admin_stats WHERE name = 'dashboard'"),
    env.DB.prepare("SELECT fingerprint, message, stack, addon_version, first_seen, last_seen, occurrences, reports, " +
      "(SELECT COUNT(*) FROM error_reporters e WHERE e.fingerprint = r.fingerprint) AS players " +
      "FROM error_reports r ORDER BY last_seen DESC LIMIT 30"),
    env.DB.prepare("SELECT COUNT(DISTINCT fingerprint) AS errors, COUNT(DISTINCT reporter) AS players " +
      "FROM error_reporters WHERE last_seen > ?").bind(now - 86400),
    pendingNames(env),
  ]);
  const live = {
    now, who, ...installs.results[0],
    clients: clients.results,
    systems: systems.results,
    regions: regions.results,
    errors: errors.results,
    errors24: errors24.results[0],
    names: names.results,
    houses: houses.results,
    realms: realms.results,
    statsStored: stats.results[0] ? stats.results[0].updated_at : null,
  };
  // The snapshot was validated when stored; splice it in rather than re-parsing.
  const snapshot = stats.results[0] ? stats.results[0].body : "null";
  return respond('{"live":' + JSON.stringify(live) + ',"snapshot":' + snapshot + "}",
    "application/json; charset=utf-8");
}

// PUT /v1/admin/stats (admin bearer): the snapshot from tools/admin_stats.py.
export async function storeStats(request, env, isAdminToken) {
  if (!isAdminToken(request)) {
    return respond('{"error":"Not allowed."}', "application/json; charset=utf-8", 401);
  }
  const text = await request.text();
  if (new TextEncoder().encode(text).length > STATS_MAX_BYTES) {
    return respond('{"error":"Too large."}', "application/json; charset=utf-8", 413);
  }
  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch {
    parsed = null;
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed) || !Number.isInteger(parsed.generated)) {
    return respond('{"error":"Expected the admin_stats.py snapshot."}', "application/json; charset=utf-8", 400);
  }
  await env.DB.prepare(
    "INSERT INTO admin_stats (name, body, updated_at) VALUES ('dashboard', ?, ?) " +
    "ON CONFLICT (name) DO UPDATE SET body = excluded.body, updated_at = excluded.updated_at",
  ).bind(JSON.stringify(parsed), Math.floor(Date.now() / 1000)).run();
  return respond('{"status":"stored"}', "application/json; charset=utf-8");
}
