// Opt-in error reports from GoldScout Companion: GoldScout's own Lua errors,
// already cleaned on the player's PC to the message and GoldScout's own stack
// lines. A report carries a random reporter ID (made by the companion, not the
// install ID) so the dashboard can count how many players hit each error.
// Reports are grouped by error, rate-limited per reporter, and deleted 90 days
// after an error was last seen.

const MAX_BYTES = 32000;
const MAX_ERRORS = 25;
const REPORTER = /^[0-9a-f]{16}$/;
const VERSION = /^[0-9A-Za-z.@+-]{0,24}$/;
const MIN_SECONDS_BETWEEN_REPORTS = 30 * 60;
const KEEP_SECONDS = 90 * 86400;

function reply(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

async function fingerprint(message, stack) {
  const firstFrame = (stack.split("\n").find((line) => line.trim() !== "") || "").trim();
  const bytes = new TextEncoder().encode(message + "\n" + firstFrame);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].slice(0, 16).map((b) => b.toString(16).padStart(2, "0")).join("");
}

// The list of errors in a report, or null if anything about it is off.
function validErrors(body) {
  if (!body || typeof body !== "object" || !REPORTER.test(body.reporter || "") || !Array.isArray(body.errors)) {
    return null;
  }
  if (body.errors.length < 1 || body.errors.length > MAX_ERRORS) {
    return null;
  }
  const errors = [];
  for (const entry of body.errors) {
    if (!entry || typeof entry !== "object") {
      return null;
    }
    const { m, s, n, v } = entry;
    if (typeof m !== "string" || m.length < 1 || m.length > 400) {
      return null;
    }
    if (typeof s !== "string" || s.length > 2500) {
      return null;
    }
    if (!Number.isInteger(n) || n < 1 || n > 1000000) {
      return null;
    }
    if (v !== undefined && (typeof v !== "string" || !VERSION.test(v))) {
      return null;
    }
    errors.push({ m, s, n, v: v || null });
  }
  return errors;
}

const FINGERPRINT = /^[0-9a-f]{32}$/;

// The admin dashboard's Dismiss: forget an error and ignore its later reports.
// Returns false if the fingerprint isn't one.
export async function dismissError(env, id) {
  if (typeof id !== "string" || !FINGERPRINT.test(id)) {
    return false;
  }
  await env.DB.batch([
    env.DB.prepare("INSERT INTO error_dismissed (fingerprint, dismissed_at) VALUES (?, ?) " +
      "ON CONFLICT (fingerprint) DO NOTHING").bind(id, Math.floor(Date.now() / 1000)),
    env.DB.prepare("DELETE FROM error_reports WHERE fingerprint = ?").bind(id),
    env.DB.prepare("DELETE FROM error_reporters WHERE fingerprint = ?").bind(id),
  ]);
  return true;
}

// POST /v1/errors: {"reporter": "16 hex", "errors": [{"m", "s", "n", "v"}]}
export async function receiveErrors(request, env, companionVersion) {
  const declared = Number(request.headers.get("Content-Length") || 0);
  if (declared > MAX_BYTES) {
    return reply({ error: "The report is too large." }, 413);
  }
  const text = await request.text();
  if (new TextEncoder().encode(text).length > MAX_BYTES) {
    return reply({ error: "The report is too large." }, 413);
  }
  let body;
  try {
    body = JSON.parse(text);
  } catch {
    body = null;
  }
  const errors = validErrors(body);
  if (!errors) {
    return reply({ error: "That isn't a GoldScout error report." }, 400);
  }
  const now = Math.floor(Date.now() / 1000);
  const reporter = body.reporter;
  const last = await env.DB.prepare("SELECT last_report FROM error_senders WHERE reporter = ?").bind(reporter).first();
  if (last && now - last.last_report < MIN_SECONDS_BETWEEN_REPORTS) {
    return reply({ error: "Error reports are sent at most every 30 minutes." }, 429);
  }
  const statements = [
    env.DB.prepare(
      "INSERT INTO error_senders (reporter, last_report, companion) VALUES (?, ?, ?) " +
      "ON CONFLICT (reporter) DO UPDATE SET last_report = excluded.last_report, companion = excluded.companion",
    ).bind(reporter, now, companionVersion),
  ];
  const dismissed = new Set((await env.DB.prepare("SELECT fingerprint FROM error_dismissed").all()).results
    .map((row) => row.fingerprint));
  for (const error of errors) {
    const id = await fingerprint(error.m, error.s);
    if (dismissed.has(id)) {
      continue;                     // dismissed on the admin dashboard
    }
    statements.push(env.DB.prepare(
      "INSERT INTO error_reports (fingerprint, message, stack, addon_version, first_seen, last_seen, occurrences, reports) " +
      "VALUES (?, ?, ?, ?, ?, ?, ?, 1) ON CONFLICT (fingerprint) DO UPDATE SET " +
      "last_seen = excluded.last_seen, occurrences = occurrences + excluded.occurrences, reports = reports + 1, " +
      "addon_version = COALESCE(excluded.addon_version, addon_version)",
    ).bind(id, error.m, error.s, error.v, now, now, error.n));
    statements.push(env.DB.prepare(
      "INSERT INTO error_reporters (reporter, fingerprint, last_seen) VALUES (?, ?, ?) " +
      "ON CONFLICT (reporter, fingerprint) DO UPDATE SET last_seen = excluded.last_seen",
    ).bind(reporter, id, now));
  }
  const old = now - KEEP_SECONDS;
  statements.push(env.DB.prepare("DELETE FROM error_reports WHERE last_seen < ?").bind(old));
  statements.push(env.DB.prepare("DELETE FROM error_reporters WHERE last_seen < ?").bind(old));
  statements.push(env.DB.prepare("DELETE FROM error_senders WHERE last_report < ?").bind(old));
  await env.DB.batch(statements);
  return reply({ status: "stored", errors: errors.length });
}
