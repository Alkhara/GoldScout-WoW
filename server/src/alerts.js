// Alerts: every hour the cron checks what the admin dashboard's Health
// section marks red, and posts to a private Discord channel (the
// ALERT_WEBHOOK_URL secret, a Discord webhook) when a problem starts, once a
// day while it lasts, and when it clears. Which problems are open is kept in
// the alerts table, so each message goes out once.
//
// The same message also says when leaderboard names are waiting for review
// (key "_names" in the alerts table): when new ones arrive, and once a day
// while any wait. It gives only how many and a link, never the names.
//
// Messages hold only regions, workflow names, counts and links to runs:
// never player data, and never text a player wrote (error messages and
// names stay on the dashboard).

const HOUR = 3600;
const PRICE_ALERT = 3 * HOUR;   // the dashboard turns red at 3 h too
const STATS_ALERT = 3 * HOUR;   // the data merge reports hourly
const REMIND = 24 * HOUR;
const ERROR_PLAYERS = 3;        // the dashboard's red line for errors
const REGIONS = ["us", "eu", "kr", "tw"];
const FAILED = new Set(["failure", "timed_out", "startup_failure"]);
const ON = "_on";               // marks that the "alerts are on" message went out
const NAMES = "_names";         // when Discord last heard about waiting names
const NAMES_LINK = "https://admin.wowgoldscout.com/admin#names";
const MAX_MESSAGE = 1900;       // Discord allows 2000 characters

function hours(seconds) {
  return seconds < 2 * HOUR ? Math.round(seconds / 60) + " min" : Math.round(seconds / HOUR) + " h";
}

// What's wrong now, as { key: message }. `data` holds the newest snapshot per
// region (houses with items), when the dashboard stats were stored, the
// stats themselves, and the last 24 h of error reports.
export function findProblems(data, now) {
  const found = {};
  const newest = {};
  for (const house of data.houses || []) {
    if (house.items > 0) {
      newest[house.region] = Math.max(newest[house.region] || 0, house.snapshot || 0);
    }
  }
  for (const region of REGIONS) {
    const name = region.toUpperCase();
    if (!newest[region]) {
      found["prices:" + region] = `${name} auction prices: none on the server, so ${name} players get no companion prices.`;
    } else if (now - newest[region] >= PRICE_ALERT) {
      found["prices:" + region] = `${name} auction prices are ${hours(now - newest[region])} old. ` +
        "The auction price workflow may be failing, or Blizzard's API is behind.";
    }
  }
  if (data.statsUpdated && now - data.statsUpdated >= STATS_ALERT) {
    found.stats = `The hourly data merge last reported ${hours(now - data.statsUpdated)} ago, so the merge ` +
      "workflow is probably failing or not starting.";
  }
  for (const flow of (data.snapshot && data.snapshot.workflows) || []) {
    const last = flow.latest;
    if (last && last.status === "completed" && FAILED.has(last.conclusion)) {
      found["workflow:" + flow.file] = `${flow.name}: the last run ended as ${last.conclusion}.` +
        (last.url ? " " + last.url : "");
    }
  }
  const errors = data.errors24 || {};
  if (errors.errors && errors.players >= ERROR_PLAYERS) {
    found.errors = `GoldScout errors: ${errors.errors} kinds from ${errors.players} players in the last 24 h. ` +
      "See Errors on the dashboard.";
  }
  return found;
}

// What to send and store, given the open problems (rows of the alerts table)
// and what's wrong now. Pure, so the tests can drive it.
export function planAlerts(stored, current, now) {
  const lines = [];
  const writes = [];   // [sql, ...params]
  const open = new Map(stored.map((row) => [row.key, row]));
  if (!open.has(ON)) {
    lines.push("GoldScout alerts are on. This channel hears when something on the dashboard turns red, " +
      "once a day while it stays red, and when it clears.");
    writes.push(["INSERT INTO alerts (key, message, since, notified) VALUES (?, ?, ?, ?)", ON, "", now, now]);
  }
  for (const [key, message] of Object.entries(current)) {
    const row = open.get(key);
    if (!row) {
      lines.push("🔴 " + message);
      writes.push(["INSERT INTO alerts (key, message, since, notified) VALUES (?, ?, ?, ?)", key, message, now, now]);
    } else if (now - row.notified >= REMIND) {
      lines.push(`🔴 Still, for ${hours(now - row.since)}: ` + message);
      writes.push(["UPDATE alerts SET message = ?, notified = ? WHERE key = ?", message, now, key]);
    }
  }
  for (const row of stored) {
    if (row.key !== ON && !(row.key in current)) {
      lines.push(`✅ Cleared after ${hours(now - row.since)}: ` + row.message);
      writes.push(["DELETE FROM alerts WHERE key = ?", row.key]);
    }
  }
  let text = lines.join("\n");
  if (text.length > MAX_MESSAGE) {
    text = text.slice(0, MAX_MESSAGE - 40) + "\n… and more: see the dashboard.";
  }
  return { text, writes };
}

// What to say and store about leaderboard names waiting for review, given
// how many wait, when the newest arrived, and the stored "_names" row (or
// null). Pure, so the tests can drive it.
export function planNames(waiting, stored, now) {
  const count = waiting.count || 0;
  if (!count) {
    return { line: "", writes: stored ? [["DELETE FROM alerts WHERE key = ?", NAMES]] : [] };
  }
  const what = count === 1 ? "1 leaderboard name is" : `${count} leaderboard names are`;
  let line = "";
  if (!stored || (waiting.newest || 0) > stored.notified) {
    line = `📝 ${what} waiting for your approval: ${NAMES_LINK}`;
  } else if (now - stored.notified >= REMIND) {
    line = `📝 Still ${what.replace(/ is$| are$/, "")} waiting for your approval: ${NAMES_LINK}`;
  }
  if (!line) {
    return { line, writes: [] };
  }
  return { line, writes: [stored
    ? ["UPDATE alerts SET notified = ? WHERE key = ?", now, NAMES]
    : ["INSERT INTO alerts (key, message, since, notified) VALUES (?, ?, ?, ?)", NAMES, "", now, now]] };
}

// Run by the hourly cron. Does nothing without the webhook secret. The state
// is only written once Discord took the message, so a failed post is retried
// next hour.
export async function checkAlerts(env, now = Math.floor(Date.now() / 1000)) {
  if (!env.ALERT_WEBHOOK_URL) {
    return;
  }
  const [houses, stats, errors24, stored, waiting] = await env.DB.batch([
    env.DB.prepare("SELECT region, snapshot, items FROM ah_houses"),
    env.DB.prepare("SELECT body, updated_at FROM admin_stats WHERE name = 'dashboard'"),
    env.DB.prepare("SELECT COUNT(DISTINCT fingerprint) AS errors, COUNT(DISTINCT reporter) AS players " +
      "FROM error_reporters WHERE last_seen > ?").bind(now - 86400),
    env.DB.prepare("SELECT key, message, since, notified FROM alerts"),
    env.DB.prepare("SELECT COUNT(*) AS count, MAX(updated_at) AS newest FROM leaderboard_names " +
      "WHERE name IS NOT NULL AND approved = 0"),
  ]);
  const row = stats.results[0];
  let snapshot = null;
  try {
    snapshot = row ? JSON.parse(row.body) : null;
  } catch {
    snapshot = null;
  }
  const current = findProblems({
    houses: houses.results, statsUpdated: row ? row.updated_at : null, snapshot, errors24: errors24.results[0],
  }, now);
  const namesRow = stored.results.find((r) => r.key === NAMES) || null;
  const health = planAlerts(stored.results.filter((r) => r.key !== NAMES), current, now);
  const names = planNames(waiting.results[0] || {}, namesRow, now);
  const text = [health.text, names.line].filter(Boolean).join("\n");
  const writes = health.writes.concat(names.writes);
  if (!text) {
    if (writes.length) {   // names were all reviewed: forget them quietly
      await env.DB.batch(writes.map(([sql, ...params]) => env.DB.prepare(sql).bind(...params)));
    }
    return;
  }
  const response = await fetch(env.ALERT_WEBHOOK_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json", "User-Agent": "GoldScout-server" },
    // No @mentions, whatever the text says.
    body: JSON.stringify({ username: "GoldScout", content: text, allowed_mentions: { parse: [] } }),
  });
  if (!response.ok) {
    throw new Error(`Alert webhook: HTTP ${response.status} ${(await response.text()).slice(0, 200)}`);
  }
  if (writes.length) {
    await env.DB.batch(writes.map(([sql, ...params]) => env.DB.prepare(sql).bind(...params)));
  }
  console.log("Sent an alert: " + Object.keys(current).concat(names.line ? [NAMES] : []).join(", "));
}
