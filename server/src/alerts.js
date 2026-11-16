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
// Community data counts too: uploads held for review (as soon as the hourly
// merge holds one; they're left out, so they don't stop the rest), and the
// data pull request when it has been open 2 h without merging itself.
//
// Things that stop quietly, where every run still "succeeds", alert as well:
// no uploads for 12 h, new community data waiting 30 h for a release, a
// scheduled workflow running at under half its usual rate (or a daily one
// missing a day), and the server failing to start workflows on GitHub
// (recordDispatchFailure, from index.js).
//
// Once a day, after 16:00 UTC, a short all-clear (or "N problems open") with
// the day's upload and install counts goes out, so a silent channel means
// the alerts themselves broke. Key "_checked" records each completed check;
// GET /admin/api/alerts (admin.js) shows it to the data merge workflow, which
// warns Discord from GitHub when the checks stop (tools/alert_watch.py).
//
// Messages hold only regions, workflow names, counts and links to runs:
// never player data, and never text a player wrote (error messages and
// names stay on the dashboard).

const HOUR = 3600;
const PRICE_ALERT = 3 * HOUR;   // the dashboard turns red at 3 h too
const STATS_ALERT = 3 * HOUR;   // the data merge reports hourly
const DATA_PR_ALERT = 2 * HOUR; // a clean data pull request merges within its run; the next run retries
const UPLOAD_ALERT = 12 * HOUR; // with dozens of companions sharing, half a day of nothing means a break
const RELEASE_ALERT = 30 * HOUR; // the daily data release ships changes within about 24 h
const DAILY_LATE = 26 * HOUR;   // a once-a-day workflow (the backup) that hasn't started in this long missed a day
const DISPATCH_FRESH = 2 * HOUR; // a failed workflow start counts until starts have worked this long
const DAILY_HOUR = 16;          // UTC hour from which the daily summary goes out (after the 15:00 release)
const RELEASES_LINK = "https://github.com/Alkhara/GoldScout-WoW/actions/workflows/data-release.yml";
const REMIND = 24 * HOUR;
const ERROR_PLAYERS = 3;        // the dashboard's red line for errors
const REGIONS = ["us", "eu", "kr", "tw"];
const FAILED = new Set(["failure", "timed_out", "startup_failure"]);
const ON = "_on";               // marks that the "alerts are on" message went out
const NAMES = "_names";         // when Discord last heard about waiting names
const DAILY = "_daily";         // when the daily summary last went out
const CHECKED = "_checked";     // when the last check finished (read by tools/alert_watch.py)
const DISPATCH = "_dispatch";   // the latest failure to start a workflow on GitHub
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
  // The community data pull request merges itself once the website builds; held uploads are left out of it.
  const pr = data.snapshot && data.snapshot.data_pr;
  const open = pr ? now - (pr.created || pr.updated || now) : 0;
  if (pr && open >= DATA_PR_ALERT) {
    found.data_pr = `The community data pull request has been open ${hours(open)} without merging itself; ` +
      `its website build may have failed. ${pr.url}`;
  }
  const held = data.snapshot && data.snapshot.held_uploads;
  if (held && held.count > 0) {
    found.held = `${held.count} upload${held.count === 1 ? " is" : "s are"} held for review, so ` +
      `${held.count === 1 ? "its" : "their"} data isn't in the community data. The run summary says why; to ` +
      `accept one, add its install ID to data/approved-installs.txt.` + (held.url ? " " + held.url : "");
  }
  for (const flow of (data.snapshot && data.snapshot.workflows) || []) {
    const last = flow.latest;
    if (last && last.status === "completed" && FAILED.has(last.conclusion)) {
      found["workflow:" + flow.file] = `${flow.name}: the last run ended as ${last.conclusion}.` +
        (last.url ? " " + last.url : "");
    }
    // Running short: the server's cron (or GitHub's backup schedule) isn't starting it as often as it should.
    const expected = flow.expected_24h || 0;
    if (expected >= 2 && (flow.runs_24h || 0) < expected / 2) {
      found["runs:" + flow.file] = `${flow.name} ran ${flow.runs_24h || 0} times in the last 24 h, where about ` +
        `${expected} is normal, so something isn't starting it.`;
    } else if (expected === 1 && last && now - last.created >= DAILY_LATE) {
      found["runs:" + flow.file] = `${flow.name} hasn't run for ${hours(now - last.created)}; it should run daily.`;
    }
  }
  const uploads = data.uploads || {};
  if (uploads.newest && now - uploads.newest >= UPLOAD_ALERT) {
    found.uploads = `No uploads from players for ${hours(now - uploads.newest)}. The upload service, the ` +
      "companion or the website's share page may be broken.";
  }
  const release = data.snapshot && data.snapshot.data_release;
  if (release && release.waiting_since && now - release.waiting_since >= RELEASE_ALERT) {
    found.data_release = `New community data has waited ${hours(now - release.waiting_since)} for a release ` +
      `(the latest, ${release.latest || "?"}, came out ${hours(now - (release.published || now))} ago). ` +
      `The Data release workflow may be skipping it, for example because Tests haven't passed on main. ${RELEASES_LINK}`;
  }
  const dispatch = data.dispatch;
  if (dispatch && now - dispatch.notified < DISPATCH_FRESH) {
    found.dispatch = `The server couldn't start workflows on GitHub: ${dispatch.message}. A 401 means its ` +
      "GITHUB_DISPATCH_TOKEN expired or was revoked; GitHub's own schedule keeps them going, more slowly, " +
      "until it's replaced.";
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

// The daily summary, given the stored "_daily" row (or null), how many
// problems are open, the last 24 h of installs ({d1: installs that uploaded,
// new1: new installs}) and the latest release. Goes out once per UTC day, at
// the first check from DAILY_HOUR on. Pure, so the tests can drive it.
export function planDaily(stored, open, installs, release, now) {
  const today = Math.floor(now / 86400);
  if ((now % 86400) / HOUR < DAILY_HOUR || (stored && Math.floor(stored.notified / 86400) === today)) {
    return { line: "", writes: [] };
  }
  const counts = installs || {};
  let line = open ? `☀️ Daily check: ${open} problem${open === 1 ? "" : "s"} open (see above).`
    : "☀️ Daily check: all clear.";
  line += ` Last 24 h: ${counts.d1 || 0} install${counts.d1 === 1 ? "" : "s"} shared data, ` +
    `${counts.new1 || 0} new.`;
  if (release && release.latest) {
    line += ` Latest release ${release.latest}, ${hours(now - (release.published || now))} ago.`;
  }
  return { line, writes: [stored
    ? ["UPDATE alerts SET notified = ? WHERE key = ?", now, DAILY]
    : ["INSERT INTO alerts (key, message, since, notified) VALUES (?, ?, ?, ?)", DAILY, "", now, now]] };
}

// Called by index.js when the cron couldn't start a workflow on GitHub; the
// next check alerts while failures keep coming (DISPATCH_FRESH).
export async function recordDispatchFailure(env, message, now = Math.floor(Date.now() / 1000)) {
  await env.DB.prepare("INSERT INTO alerts (key, message, since, notified) VALUES (?, ?, ?, ?) " +
    "ON CONFLICT (key) DO UPDATE SET message = excluded.message, notified = excluded.notified")
    .bind(DISPATCH, String(message).slice(0, 300), now, now).run();
}

// For GET /admin/api/alerts: when the last check finished, and whether the
// webhook is set, for tools/alert_watch.py.
export async function alertStatus(env) {
  const row = await env.DB.prepare("SELECT notified FROM alerts WHERE key = ?").bind(CHECKED).first();
  return { checked: row ? row.notified : null, webhook: Boolean(env.ALERT_WEBHOOK_URL) };
}

// Run by the hourly cron. Does nothing without the webhook secret. The state
// is only written once Discord took the message, so a failed post is retried
// next hour (and "_checked" stays old, which tools/alert_watch.py notices).
export async function checkAlerts(env, now = Math.floor(Date.now() / 1000)) {
  if (!env.ALERT_WEBHOOK_URL) {
    return;
  }
  const [houses, stats, errors24, stored, waiting, installs] = await env.DB.batch([
    env.DB.prepare("SELECT region, snapshot, items FROM ah_houses"),
    env.DB.prepare("SELECT body, updated_at FROM admin_stats WHERE name = 'dashboard'"),
    env.DB.prepare("SELECT COUNT(DISTINCT fingerprint) AS errors, COUNT(DISTINCT reporter) AS players " +
      "FROM error_reporters WHERE last_seen > ?").bind(now - 86400),
    env.DB.prepare("SELECT key, message, since, notified FROM alerts"),
    env.DB.prepare("SELECT COUNT(*) AS count, MAX(updated_at) AS newest FROM leaderboard_names " +
      "WHERE name IS NOT NULL AND approved = 0"),
    env.DB.prepare("SELECT MAX(updated_at) AS newest, COALESCE(SUM(updated_at > ?), 0) AS d1, " +
      "COALESCE(SUM(created_at > ?), 0) AS new1 FROM installs").bind(now - 86400, now - 86400),
  ]);
  const row = stats.results[0];
  let snapshot = null;
  try {
    snapshot = row ? JSON.parse(row.body) : null;
  } catch {
    snapshot = null;
  }
  const kept = (key) => stored.results.find((r) => r.key === key) || null;
  const counts = installs.results[0] || {};
  const current = findProblems({
    houses: houses.results, statsUpdated: row ? row.updated_at : null, snapshot, errors24: errors24.results[0],
    uploads: { newest: counts.newest }, dispatch: kept(DISPATCH),
  }, now);
  // Keys starting "_" are bookkeeping, not problems (except "_on", which planAlerts handles).
  const health = planAlerts(stored.results.filter((r) => r.key === ON || !r.key.startsWith("_")), current, now);
  const names = planNames(waiting.results[0] || {}, kept(NAMES), now);
  const daily = planDaily(kept(DAILY), Object.keys(current).length, counts,
    snapshot && snapshot.data_release, now);
  let text = [health.text, names.line, daily.line].filter(Boolean).join("\n");
  if (text.length > 1990) {   // Discord's limit is 2000; planAlerts already trims its own part
    text = text.slice(0, 1990);
  }
  const checked = kept(CHECKED)
    ? ["UPDATE alerts SET notified = ? WHERE key = ?", now, CHECKED]
    : ["INSERT INTO alerts (key, message, since, notified) VALUES (?, ?, ?, ?)", CHECKED, "", now, now];
  const writes = health.writes.concat(names.writes, daily.writes, [checked]);
  if (!text) {
    await env.DB.batch(writes.map(([sql, ...params]) => env.DB.prepare(sql).bind(...params)));
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
  await env.DB.batch(writes.map(([sql, ...params]) => env.DB.prepare(sql).bind(...params)));
  console.log("Sent an alert: " + Object.keys(current).concat(names.line ? [NAMES] : [], daily.line ? [DAILY] : [])
    .join(", "));
}
