// Contributor leaderboard.
//
// Scores are each install's kills that count in the community data: worked
// out by tools/leaderboard.py from the validated submissions on main (each
// mob's kills capped like tools/merge_data.py caps them), and sent hourly by
// the data merge workflow. Everyone with a score is ranked; nobody is named
// unless they choose it in GoldScout Companion, which proves which install it
// speaks for with that install's upload token. A player who opts in is shown
// under a made-up alias, or under a name of their own once it's approved on
// the admin dashboard. Install IDs never leave this file.
//
//   GET  /v1/leaderboard          public: the top 100, contributor count, total kills.
//   GET  /v1/leaderboard/me       the install's rank and leaderboard settings.
//   PUT  /v1/leaderboard/me       {"public": bool, "name": "..." | null}.
//                                 Both "me" routes need X-GoldScout-Install
//                                 and Authorization: Bearer <upload token>.
//   PUT  /v1/admin/leaderboard    admin only; {"generated", "scores": {install: [kills, mobs]}}.
// Name review (approve or reject) is on the admin dashboard (src/admin.js).

const TOP = 100;
const INSTALL_ID = /^[a-z0-9]{12}$/;
const MAX_SCORES = 20000;
const SCORES_MAX_BYTES = 1000000;
const ROWS_PER_INSERT = 33;   // 3 values a row; D1 takes at most 100 bound values per statement
// 3 to 20 letters, digits, spaces and . _ ' -, starting and ending with a letter or digit.
const NAME = /^[\p{L}\p{N}](?:[\p{L}\p{N} ._'-]{1,18})[\p{L}\p{N}]$/u;

// Made-up aliases: plain words, nothing from the game.
const ADJECTIVES = ["Patient", "Swift", "Lucky", "Quiet", "Steady", "Bold", "Clever", "Tireless", "Keen", "Thrifty",
  "Brave", "Nimble", "Sly", "Stout", "Diligent", "Wandering", "Careful", "Eager", "Humble", "Merry", "Silent",
  "Hardy", "Restless", "Wily", "Gilded", "Frugal", "Shrewd", "Sturdy", "Watchful", "Cheerful"];
const NOUNS = ["Boar", "Wolf", "Owl", "Bear", "Lynx", "Hawk", "Stag", "Crab", "Turtle", "Spider", "Bat", "Fox",
  "Badger", "Heron", "Moth", "Viper", "Toad", "Ram", "Yak", "Crane", "Otter", "Raven", "Wasp", "Gryphon",
  "Wyvern", "Basilisk", "Kobold", "Ogre", "Golem", "Wisp", "Drake", "Harpy", "Imp", "Hydra", "Beetle", "Scorpion"];

function pick(list) {
  return list[crypto.getRandomValues(new Uint32Array(1))[0] % list.length];
}

function newAlias() {
  return pick(ADJECTIVES) + " " + pick(NOUNS);
}

// "  Big   Farmer " -> "Big Farmer"; "" -> null; undefined if it isn't allowed.
export function cleanName(value) {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value !== "string") {
    return undefined;
  }
  const name = value.normalize("NFC").replace(/\s+/g, " ").trim();
  if (name === "") {
    return null;
  }
  return NAME.test(name) ? name : undefined;
}

// Handles the leaderboard routes; returns null for anything else.
export async function handleLeaderboard(request, env, url, h) {
  const path = url.pathname;
  if (path === "/v1/leaderboard" && request.method === "GET") {
    return await board(env, h);
  }
  if (path === "/v1/leaderboard/me" && (request.method === "GET" || request.method === "PUT")) {
    const installId = await authorized(request, env, h);
    if (installId instanceof Response) {
      return installId;
    }
    if (request.method === "PUT") {
      const problem = await change(request, env, installId, h);
      if (problem) {
        return problem;
      }
    }
    return h.json(await mine(env, installId));
  }
  if (path === "/v1/admin/leaderboard" && request.method === "PUT") {
    return await storeScores(request, env, h);
  }
  return null;
}

// The install a request speaks for, after checking its upload token; or an error response.
async function authorized(request, env, h) {
  const installId = (request.headers.get("X-GoldScout-Install") || "").trim();
  const token = h.bearer(request);
  if (!INSTALL_ID.test(installId) || !token) {
    return h.json({ error: "Share your GoldScout data with the companion first." }, 401);
  }
  const row = await env.DB.prepare("SELECT token_hash FROM installs WHERE install_id = ?").bind(installId).first();
  if (!row) {
    return h.json({ error: "Share your GoldScout data with the companion first." }, 404);
  }
  if (!h.sameText(await h.sha256(token), row.token_hash)) {
    return h.json({ error: "This GoldScout data is registered to another copy of the companion." }, 403);
  }
  return installId;
}

function shownName(row) {
  if (!row.alias) {
    return null;
  }
  return row.name && row.approved ? row.name : row.alias;
}

async function board(env, h) {
  const [top, totals] = await env.DB.batch([
    env.DB.prepare(
      "SELECT s.kills, s.mobs, n.alias, n.name, n.approved, " +
      "(SELECT COUNT(*) FROM leaderboard_scores o WHERE o.kills > s.kills) + 1 AS rank " +
      "FROM leaderboard_scores s LEFT JOIN leaderboard_names n USING (install_id) " +
      "ORDER BY s.kills DESC, s.mobs DESC, s.install_id LIMIT ?",
    ).bind(TOP),
    env.DB.prepare("SELECT COUNT(*) AS contributors, COALESCE(SUM(kills), 0) AS kills, " +
      "MAX(updated_at) AS updated FROM leaderboard_scores"),
  ]);
  const rows = top.results.map((row) => ({ rank: row.rank, name: shownName(row), kills: row.kills, mobs: row.mobs }));
  const { contributors, kills, updated } = totals.results[0];
  return h.publicJson(JSON.stringify({ contributors, kills, updated, top: rows }));
}

async function mine(env, installId) {
  const [score, names, totals] = await env.DB.batch([
    env.DB.prepare("SELECT kills, mobs, " +
      "(SELECT COUNT(*) FROM leaderboard_scores o WHERE o.kills > s.kills) + 1 AS rank " +
      "FROM leaderboard_scores s WHERE install_id = ?").bind(installId),
    env.DB.prepare("SELECT alias, name, approved FROM leaderboard_names WHERE install_id = ?").bind(installId),
    env.DB.prepare("SELECT COUNT(*) AS contributors, MAX(updated_at) AS updated FROM leaderboard_scores"),
  ]);
  const s = score.results[0];
  const n = names.results[0];
  return {
    rank: s ? s.rank : null,
    kills: s ? s.kills : 0,
    mobs: s ? s.mobs : 0,
    contributors: totals.results[0].contributors,
    updated: totals.results[0].updated,
    public: Boolean(n),
    alias: n ? n.alias : null,
    name: n ? n.name : null,
    approved: Boolean(n && n.name && n.approved),
  };
}

// Applies a PUT /v1/leaderboard/me; returns an error response, or null.
async function change(request, env, installId, h) {
  if (Number(request.headers.get("Content-Length") || 0) > 1000) {
    return h.json({ error: "Too large." }, 413);
  }
  let body;
  try {
    body = JSON.parse(await request.text());
  } catch {
    body = null;
  }
  if (!body || typeof body !== "object" || typeof body.public !== "boolean") {
    return h.json({ error: "Expected {\"public\": true or false, \"name\": \"...\"}." }, 400);
  }
  if (!body.public) {
    await env.DB.prepare("DELETE FROM leaderboard_names WHERE install_id = ?").bind(installId).run();
    return null;
  }
  const name = cleanName(body.name);
  if (name === undefined) {
    return h.json({ error: "Names are 3 to 20 letters, digits and spaces (and . _ ' -)." }, 400);
  }
  const now = Math.floor(Date.now() / 1000);
  const current = await env.DB.prepare("SELECT alias, name, approved FROM leaderboard_names WHERE install_id = ?")
    .bind(installId).first();
  if (!current) {
    await env.DB.prepare("INSERT INTO leaderboard_names (install_id, alias, name, approved, updated_at) " +
      "VALUES (?, ?, ?, 0, ?)").bind(installId, newAlias(), name, now).run();
    return null;
  }
  if (name !== current.name) {
    // A new name waits for review again; until then the alias shows.
    await env.DB.prepare("UPDATE leaderboard_names SET name = ?, approved = 0, updated_at = ? WHERE install_id = ?")
      .bind(name, now, installId).run();
  }
  return null;
}

// PUT /v1/admin/leaderboard: replaces every score.
async function storeScores(request, env, h) {
  if (!h.isAdminToken(request)) {
    return h.json({ error: "Not allowed." }, 401);
  }
  if (Number(request.headers.get("Content-Length") || 0) > SCORES_MAX_BYTES) {
    return h.json({ error: "Too large." }, 413);
  }
  let body;
  try {
    body = JSON.parse(await request.text());
  } catch {
    body = null;
  }
  const entries = body && typeof body.scores === "object" && !Array.isArray(body.scores) && body.scores
    ? Object.entries(body.scores) : null;
  const valid = ([id, value]) => INSTALL_ID.test(id) && Array.isArray(value) && value.length === 2 &&
    value.every((n) => Number.isInteger(n) && n >= 0 && n < 1e9) && value[0] > 0;
  if (!entries || entries.length > MAX_SCORES || !Number.isInteger(body.generated) || !entries.every(valid)) {
    return h.json({ error: "Expected {\"generated\": unix seconds, \"scores\": {install: [kills, mobs]}}." }, 400);
  }
  const statements = [env.DB.prepare("DELETE FROM leaderboard_scores")];
  for (let start = 0; start < entries.length; start += ROWS_PER_INSERT) {
    const chunk = entries.slice(start, start + ROWS_PER_INSERT);
    statements.push(env.DB.prepare(
      "INSERT INTO leaderboard_scores (install_id, kills, mobs, updated_at) VALUES " +
      chunk.map(() => "(?, ?, ?, " + body.generated + ")").join(", "),
    ).bind(...chunk.flatMap(([id, [kills, mobs]]) => [id, kills, mobs])));
  }
  await env.DB.batch(statements);
  return h.json({ status: "stored", scores: entries.length });
}

// The admin dashboard's list of names waiting for review.
export function pendingNames(env) {
  return env.DB.prepare(
    "SELECT n.rowid AS id, n.alias, n.name, n.updated_at, COALESCE(s.kills, 0) AS kills FROM leaderboard_names n " +
    "LEFT JOIN leaderboard_scores s USING (install_id) WHERE n.name IS NOT NULL AND n.approved = 0 " +
    "ORDER BY n.updated_at LIMIT 100");
}

// Approves or rejects a name (the dashboard's buttons). Only if it's still the
// name the dashboard showed. Rejecting clears it, so the alias shows. Returns
// whether a row changed.
export async function reviewName(env, id, name, approve) {
  if (!Number.isInteger(id) || id < 1 || typeof name !== "string" || typeof approve !== "boolean") {
    return false;
  }
  const result = await env.DB.prepare(approve
    ? "UPDATE leaderboard_names SET approved = 1 WHERE rowid = ? AND name = ? AND approved = 0"
    : "UPDATE leaderboard_names SET name = NULL, approved = 0 WHERE rowid = ? AND name = ? AND approved = 0",
  ).bind(id, name).run();
  return (result.meta?.changes ?? 0) > 0;
}
