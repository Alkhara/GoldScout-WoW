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
//   GET  /v1/uploads   admin only (Authorization: Bearer <ADMIN_TOKEN>).
//                      ?since=<unix seconds> limits it to newer uploads.
//   GET  /health

const MAX_BYTES = 60000;
const MAX_LINES = 1501;
const HEADER = /^GoldScout-export 2\^([a-z0-9]{12})\^([1-9][0-9]{0,8})$/;
const TERMS_VERSIONS = new Set(["2026-11-07"]);
const NEW_INSTALLS_PER_IP_PER_DAY = 5;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    try {
      if (url.pathname === "/health") {
        return json({ ok: true });
      }
      if (url.pathname === "/v1/uploads" && request.method === "POST") {
        return await receive(request, env);
      }
      if (url.pathname === "/v1/uploads" && request.method === "GET") {
        return await list(request, env, url);
      }
      return json({ error: "Not found." }, 404);
    } catch (error) {
      console.error(error);
      return json({ error: "Server error." }, 500);
    }
  },
};

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
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

function bearer(request) {
  const value = request.headers.get("Authorization") || "";
  return value.startsWith("Bearer ") ? value.slice(7).trim() : "";
}

function newToken() {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
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
  if (lines.length < 2 || lines.length > MAX_LINES || lines.slice(1).some((line) => line.split("^").length !== 12)) {
    return json({ error: "The export is malformed." }, 400);
  }
  const [, installId, seqText] = match;
  const seq = Number(seqText);
  const text = lines.join("\n") + "\n";
  const now = Math.floor(Date.now() / 1000);
  const minSeconds = Number(env.MIN_SECONDS_BETWEEN_UPLOADS ?? 60);

  const row = await env.DB.prepare("SELECT token_hash, seq, updated_at FROM installs WHERE install_id = ?")
    .bind(installId).first();

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
    ]);
    return json({ status: "registered", token }, 201);
  }

  const token = bearer(request);
  if (!token || !sameText(await sha256(token), row.token_hash)) {
    return json({ error: "This GoldScout data is registered to another copy of the companion." }, 403);
  }
  if (seq <= row.seq) {
    return json({ status: "unchanged" });
  }
  if (now - row.updated_at < minSeconds) {
    return json({ error: "Uploading too often; try again in a minute." }, 429);
  }
  await env.DB.prepare(
    "UPDATE installs SET seq = ?, body = ?, terms = ?, updated_at = ?, uploads = uploads + 1 WHERE install_id = ?",
  ).bind(seq, text, request.headers.get("X-GoldScout-Terms"), now, installId).run();
  return json({ status: "stored" });
}

async function list(request, env, url) {
  if (!env.ADMIN_TOKEN || !sameText(bearer(request), env.ADMIN_TOKEN)) {
    return json({ error: "Not allowed." }, 401);
  }
  const since = Number(url.searchParams.get("since") || 0);
  const { results } = await env.DB.prepare(
    "SELECT install_id, seq, body, terms, updated_at FROM installs WHERE updated_at > ? ORDER BY updated_at",
  ).bind(since).all();
  return json({ uploads: results });
}
