// GoldScout admin dashboard: reads /admin/api/summary and draws every section.
// Everything from the server goes into the page with textContent, never as HTML.
(function () {
  "use strict";
  var app = document.getElementById("app");
  var tip = document.getElementById("tip");
  var HOUR = 3600, DAY = 86400;

  // -- small DOM helpers ----------------------------------------------------------
  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (key) {
      if (key === "text") { node.textContent = attrs[key]; }
      else if (key === "cls") { node.className = attrs[key]; }
      else { node.setAttribute(key, attrs[key]); }
    });
    (children || []).forEach(function (child) {
      if (child !== null && child !== undefined) {
        node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
      }
    });
    return node;
  }
  var SVG = "http://www.w3.org/2000/svg";
  function svg(tag, attrs) {
    var node = document.createElementNS(SVG, tag);
    Object.keys(attrs || {}).forEach(function (key) { node.setAttribute(key, attrs[key]); });
    return node;
  }
  function num(n) { return n === null || n === undefined ? "?" : Number(n).toLocaleString("en-US"); }
  function pct(part, whole) { return whole ? Math.round(100 * part / whole) + "%" : "-"; }
  function money(copper) {
    if (copper === null || copper === undefined) { return "-"; }
    var g = Math.floor(copper / 10000), s = Math.floor(copper / 100) % 100, c = copper % 100;
    return g ? g.toLocaleString("en-US") + "g " + s + "s" : (s ? s + "s " + c + "c" : c + "c");
  }
  function ago(seconds) {
    if (seconds === null || seconds === undefined) { return "never"; }
    if (seconds < 90) { return "just now"; }
    if (seconds < 90 * 60) { return Math.round(seconds / 60) + " min ago"; }
    if (seconds < 2 * DAY) { return Math.round(seconds / HOUR) + " h ago"; }
    return Math.round(seconds / DAY) + " days ago";
  }
  function date(unix) {
    return unix ? new Date(unix * 1000).toLocaleDateString("en-US", { month: "short", day: "numeric" }) : "-";
  }
  // Status always comes as a colored dot plus a word, never color alone.
  function status(level, label) {
    return el("span", { cls: "pill" }, [el("span", { cls: "dot s-" + level, "aria-hidden": "true" }), label]);
  }
  function card(title, hint, children) {
    return el("div", { cls: "card" }, [title ? el("h3", { text: title }) : null].concat(children || [])
      .concat([hint ? el("p", { cls: "hint", text: hint }) : null]));
  }
  function section(id, title, sub, children) {
    return el("section", { id: id }, [
      el("div", { cls: "section-head" }, [el("h2", { text: title }), sub ? el("span", { cls: "muted", text: sub }) : null]),
    ].concat(children));
  }
  function tiles(list) {
    return el("div", { cls: "tiles" }, list.map(function (t) {
      return el("div", { cls: "tile" }, [el("div", { cls: "label", text: t[0] }), el("div", { cls: "value", text: t[1] }),
        t[2] ? el("div", { cls: "note", text: t[2] }) : null]);
    }));
  }
  function table(columns, rows) {
    // columns: [[label, key or fn, "num"?]]
    var head = el("tr", {}, columns.map(function (c) { return el("th", { cls: c[2] || "", text: c[0] }); }));
    var body = rows.map(function (row) {
      return el("tr", {}, columns.map(function (c) {
        var value = typeof c[1] === "function" ? c[1](row) : row[c[1]];
        var cell = el("td", { cls: c[2] || "" });
        if (value instanceof Node) { cell.appendChild(value); } else { cell.textContent = value === null || value === undefined ? "-" : String(value); }
        return cell;
      }));
    });
    if (!rows.length) {
      body = [el("tr", {}, [el("td", { colspan: String(columns.length), cls: "muted", text: "Nothing yet." })])];
    }
    return el("table", {}, [el("thead", {}, [head]), el("tbody", {}, body)]);
  }

  // -- tooltip --------------------------------------------------------------------
  function attachTip(target, title, lines) {
    function show(event) {
      tip.textContent = "";
      tip.appendChild(el("b", { text: title }));
      lines.forEach(function (line) { tip.appendChild(el("div", { text: line })); });
      tip.hidden = false;
      var x = event.clientX !== undefined ? event.clientX : target.getBoundingClientRect().left;
      var y = event.clientY !== undefined ? event.clientY : target.getBoundingClientRect().top;
      tip.style.left = Math.min(x + 12, window.innerWidth - tip.offsetWidth - 8) + "px";
      tip.style.top = Math.max(8, y - tip.offsetHeight - 12) + "px";
    }
    target.addEventListener("pointermove", show);
    target.addEventListener("focus", show);
    target.addEventListener("pointerleave", function () { tip.hidden = true; });
    target.addEventListener("blur", function () { tip.hidden = true; });
  }

  // -- charts ---------------------------------------------------------------------
  // Vertical bars, one series, zero baseline, 4px rounded top, every bar hoverable.
  function columnChart(points, label) {
    var width = 640, height = 170, left = 30, right = 14, bottom = 22, top = 8;
    var peak = Math.max.apply(null, points.map(function (p) { return p[1]; }).concat([1]));
    var step = (width - left - right) / points.length, barWidth = Math.max(3, step - 2);
    var chart = svg("svg", { viewBox: "0 0 " + width + " " + height, role: "img",
      "aria-label": label, "class": "chart" });
    var plot = height - bottom - top;
    var ticks = peak <= 4 ? peak : 4;
    for (var i = 0; i <= ticks; i++) {
      var value = Math.round(peak * i / ticks);
      var y = top + plot - plot * value / peak;
      chart.appendChild(svg("line", { x1: left, x2: width - right, y1: y, y2: y, "class": i === 0 ? "base" : "grid-line" }));
      var t = svg("text", { x: left - 6, y: y + 4, "text-anchor": "end" });
      t.textContent = String(value);
      chart.appendChild(t);
    }
    points.forEach(function (p, index) {
      var x = left + index * step + 1;
      var h = plot * p[1] / peak;
      var hit = svg("rect", { x: x - 1, y: top, width: step, height: plot, "class": "hit", tabindex: "0" });
      chart.appendChild(hit);
      if (p[1] > 0) {
        var r = Math.min(4, barWidth / 2, h);
        var yTop = top + plot - h, yBase = top + plot;
        chart.appendChild(svg("path", { "class": "bar", d: "M" + x + "," + yBase + "V" + (yTop + r) +
          "Q" + x + "," + yTop + " " + (x + r) + "," + yTop + "H" + (x + barWidth - r) +
          "Q" + (x + barWidth) + "," + yTop + " " + (x + barWidth) + "," + (yTop + r) + "V" + yBase + "Z" }));
      }
      attachTip(hit, p[0], [num(p[1]) + " " + label.toLowerCase()]);
      if (index % 7 === points.length % 7 || index === points.length - 1) {
        var lt = svg("text", { x: x + barWidth / 2, y: height - 6, "text-anchor": "middle" });
        lt.textContent = p[0].slice(5);
        chart.appendChild(lt);
      }
    });
    return chart;
  }

  // Horizontal part-of-whole bars: [name, first, second] with a legend.
  function splitBars(rows, firstLabel, secondLabel) {
    var peak = Math.max.apply(null, rows.map(function (r) { return r[1] + r[2]; }).concat([1]));
    var box = el("div", {}, [el("div", { cls: "legend" }, [
      el("span", {}, [el("i", { cls: "swatch s1" }), firstLabel]),
      el("span", {}, [el("i", { cls: "swatch s2" }), secondLabel])])]);
    rows.forEach(function (r) {
      var track = el("div", { cls: "track", tabindex: "0" });
      var a = el("div", { cls: "fill" }), b = el("div", { cls: "fill-2" });
      a.style.width = (100 * r[1] / peak) + "%";
      b.style.width = (100 * r[2] / peak) + "%";
      if (!r[1]) { a.style.minWidth = "0"; }
      track.appendChild(a);
      track.appendChild(b);
      attachTip(track, r[0], [firstLabel + ": " + num(r[1]), secondLabel + ": " + num(r[2])]);
      box.appendChild(el("div", { cls: "hbar" }, [el("span", { cls: "name", text: r[0] }), track,
        el("span", { cls: "n", text: num(r[1]) + " / " + num(r[1] + r[2]) })]));
    });
    return box;
  }

  function simpleBars(rows) {
    var peak = Math.max.apply(null, rows.map(function (r) { return r[1]; }).concat([1]));
    return el("div", {}, rows.map(function (r) {
      var fill = el("div", { cls: "fill" });
      fill.style.width = (100 * r[1] / peak) + "%";
      return el("div", { cls: "hbar" }, [el("span", { cls: "name", text: r[0] }), el("div", { cls: "track" }, [fill]),
        el("span", { cls: "n", text: num(r[1]) })]);
    }));
  }

  // -- sections -------------------------------------------------------------------
  function growthSection(live, snap) {
    var g = (snap && snap.growth) || {};
    var daily = g.daily_new || [];
    var community = (snap && snap.community) || {};
    var cohorts = g.cohorts || [];
    return section("growth", "Growth", "Companion installs that share drop data", [
      tiles([
        ["Installs", num(live.installs), snap && snap.mine ? snap.mine + " of them yours" : ""],
        ["Active 24 h", num(live.d1), "uploaded in the last day"],
        ["Active 7 days", num(live.d7), g.active ? num(g.active.d30) + " in 30 days" : ""],
        ["New this week", num(live.new7), "first upload in the last 7 days"],
        ["Quiet 14+ days", g.quiet14 === undefined ? "?" : num(g.quiet14), "no upload for two weeks"],
        ["Uploads", num(g.uploads), "all installs, all time"],
        ["Contributors", num(community.contributors), "in the community data"],
      ]),
      el("div", { cls: "grid" }, [
        card("New players per day (30 days, UTC)", null, [columnChart(daily, "New players"),
          el("details", {}, [el("summary", { text: "Table" }), table([["Day", 0], ["New", 1, "num"]],
            daily.slice().reverse())])]),
        card("Still uploading after...", "Each install's first and last upload; weeks start Monday. " +
          "A dash means that week's installs aren't old enough yet.", [table([
          ["Week of", "week"], ["Joined", "joined", "num"],
          ["7 days", function (c) { return c.eligible7 ? pct(c.after7, c.eligible7) : "-"; }, "num"],
          ["14 days", function (c) { return c.eligible14 ? pct(c.after14, c.eligible14) : "-"; }, "num"],
          ["28 days", function (c) { return c.eligible28 ? pct(c.after28, c.eligible28) : "-"; }, "num"],
        ], cohorts.slice().reverse())]),
      ]),
    ]);
  }

  function versionsSection(live, snap) {
    var clients = (live.clients || []).map(function (c) { return [c.client, c.n]; });
    var unknown = (live.installs || 0) - clients.reduce(function (s, c) { return s + c[1]; }, 0);
    if (unknown > 0) { clients.push(["not reported yet", unknown]); }
    var exports = Object.keys((snap && snap.export_versions) || {}).map(function (k) {
      return ["v" + k, snap.export_versions[k]]; });
    var systems = (live.systems || []).map(function (s) {
      return [s.os || "before 0.8.0", s.n, s.d7]; });
    var regions = (live.regions || []).map(function (r) {
      return [r.region ? r.region.toUpperCase() : "before 0.9.0", r.n, r.d7]; });
    return section("versions", "Versions", null, [el("div", { cls: "grid" }, [
      card("Companion system", "From each install's latest upload. Companions before 0.8.0 don't send it " +
        "(they were Windows only). Bars split installs that shared in the last 7 days from the rest. " +
        "Price-only users aren't counted.",
        [splitBars(systems.map(function (s) { return [s[0], s[2], s[1] - s[2]]; }), "Shared in 7 days", "Earlier")]),
      card("Region", "Where each install plays, from its latest upload (companion 0.9.0 and later). Prices " +
        "come for US, EU, KR and TW. Price-only users aren't counted.",
        [splitBars(regions.map(function (r) { return [r[0], r[2], r[1] - r[2]]; }), "Shared in 7 days", "Earlier")]),
      card("Companion version (latest upload)", "Recorded since Nov 10, 2026; an install shows its version " +
        "after its next upload. Price-only companion users don't upload, so they aren't counted here.",
        [simpleBars(clients)]),
      card("Export format", "The addon's export version in each install's newest upload.", [simpleBars(exports)]),
    ])]);
  }

  function reachSection(live, snap) {
    var downloads = (snap && snap.downloads) || [];
    var exeTotal = downloads.reduce(function (s, d) { return s + d.exe; }, 0);
    var zipTotal = downloads.reduce(function (s, d) { return s + d.zip; }, 0);
    var macTotal = downloads.reduce(function (s, d) { return s + (d.mac || 0); }, 0);
    var form = (snap && snap.form) || null;
    return section("reach", "Downloads and sharing", "GitHub release downloads (CurseForge and Wago keep their own counts)", [
      tiles([
        ["Companion downloads", num(exeTotal + macTotal), num(exeTotal) + " Windows, " + num(macTotal) + " Mac; last 10 releases"],
        ["Addon zip downloads", num(zipTotal), "GitHub only"],
        ["Companion installs", num(live.installs), exeTotal + macTotal ? pct(live.installs, exeTotal + macTotal) +
          " of companion downloads" : ""],
        ["Sharing this week", num(live.d7), live.installs ? pct(live.d7, live.installs) + " of installs" : ""],
        ["Share form", form ? num(form.total) : "?", form ? num(form.people) + " people, " + num(form.open) + " open" : ""],
      ]),
      el("div", { cls: "grid" }, [
        card("Downloads per release", null, [table([
          ["Release", "tag"], ["Published", function (d) { return date(d.published); }],
          ["Windows", "exe", "num"], ["Mac", function (d) { return num(d.mac || 0); }, "num"],
          ["Addon zip", "zip", "num"]], downloads)]),
        card("Links", null, [el("ul", {}, [
          el("li", {}, [el("a", { href: "https://www.curseforge.com/", text: "CurseForge author dashboard" })]),
          el("li", {}, [el("a", { href: "https://addons.wago.io/", text: "Wago addons dashboard" })]),
          el("li", {}, [el("a", { href: "https://github.com/Alkhara/GoldScout-WoW/releases", text: "GitHub releases" })]),
          el("li", {}, [el("a", { href: "https://github.com/Alkhara/GoldScout-WoW/issues?q=label%3Adata-submission",
            text: "Share drop data issues" })]),
        ])]),
      ]),
    ]);
  }

  function playersSection(snap) {
    var players = (snap && snap.players) || [];
    var now = snap ? snap.generated : 0;
    var columns = [
        ["Player", function (p) { return p.tag + (p.you ? " *" : ""); }],
        ["Companion", "client"], ["System", function (p) { return p.os || "not sent"; }],
        ["Region", function (p) { return p.region ? p.region.toUpperCase() : "-"; }], ["Uploads", "uploads", "num"],
        ["First seen", function (p) { return date(p.created); }],
        ["Last upload", function (p) { return ago(now - p.updated); }],
        ["Mobs", function (p) { return num(p.mobs); }, "num"], ["Kills", function (p) { return num(p.kills); }, "num"],
        ["Pickpockets", function (p) { return num(p.picks); }, "num"], ["Drops", function (p) { return num(p.drops); }, "num"],
    ];
    var shown = 30;
    return section("players", "Players", num(players.length) + " installs: hashed tags, newest export each", [card(null,
      "* marks your own installs (GOLDSCOUT_MY_INSTALLS). Totals are each install's newest export, " +
      "before the per-player cap of 1,000 kills per mob. Most kills first.", [table(columns, players.slice(0, shown)),
      players.length > shown ? el("details", {}, [el("summary", { text: "Show all " + num(players.length) }),
        table(columns, players.slice(shown))]) : null])]);
  }

  function coverageSection(snap) {
    var c = (snap && snap.community) || {};
    var priceHouse = snap && snap.price_house;
    var brackets = (c.brackets || []).map(function (b) { return [b.label, b.good, b.mobs - b.good]; });
    var zones = (c.zones || []).map(function (z) { return [z.name, z.good, z.mobs - z.good]; });
    return section("coverage", "Data coverage", "Where the community data is thin (includes data waiting in the open data PR)", [
      tiles([
        ["Mobs seen", num(c.mobs_seen), num(c.mobs_shown) + " with 5+ kills"],
        ["Good confidence", num(c.mobs_good), "15+ kills or pickpockets"],
        ["Kills", num(c.kills), "after the per-player cap"],
        ["Pickpockets", num(c.picks), ""],
      ]),
      el("div", { cls: "grid" }, [
        card("Mobs by level", "Mob level brackets as on the Farm tab.", [splitBars(brackets, "Good confidence", "Not yet")]),
        card("Mobs by zone", "Zone where each mob was looted most.", [splitBars(zones.slice(0, 15), "Good confidence", "Not yet")]),
      ]),
      el("div", { cls: "grid wide" }, [
        card("Closest to good confidence", "A few more kills each turns these into trustworthy farms: " +
          "good targets to ask players for.", [table([
          ["Mob", "name"], ["Levels", "levels"], ["Zone", "zone"], ["Kills + picks", "attempts", "num"],
          ["Needed", function (m) { return num(15 - m.attempts); }, "num"]], c.close_to_good || [])]),
        card("Valuable reagents with few good sources", "Crafting reagents from mob drops, fewest well-measured " +
          "sources first, then by price" + (priceHouse ? " (" + priceHouse.ruleset + " " + priceHouse.faction +
          " auction house)" : "") + ".", [table([
          ["Reagent", "name"], ["Good sources", "good_sources", "num"], ["All sources", "sources", "num"],
          ["Best rate", function (r) { return Math.round(r.best_rate * 1000) / 10 + "%"; }, "num"],
          ["Price", function (r) { return money(r.price); }, "num"], ["Listed", function (r) { return num(r.listed); }, "num"]],
          c.thin_reagents || [])]),
      ]),
      el("div", { cls: "grid wide" }, [card("Most-farmed mobs", "Where players actually spend their time.", [table([
        ["Mob", "name"], ["Levels", "levels"], ["Zone", "zone"], ["Kills", "kills", "num"], ["Pickpockets", "picks", "num"]],
        c.top_mobs || [])])]),
    ]);
  }

  function pricesSection(live) {
    var now = live.now;
    var rulesets = {};
    (live.realms || []).forEach(function (r) { (rulesets[r.ruleset] = rulesets[r.ruleset] || []).push(r.realm); });
    var houses = live.houses || [];
    var mapped = houses.filter(function (h) { return h.ruleset; }).length;
    return section("prices", "Auction prices", "Blizzard Game Data API, copied by the hourly price workflow", [
      tiles([
        ["Auction houses", num(houses.length), num(mapped) + " mapped to a ruleset"],
        ["Unmapped", num(houses.length - mapped), "need a player scan to identify"],
        ["Known realms", num((live.realms || []).length), "in the server's realm map"],
      ]),
      el("div", { cls: "grid" }, [card("Houses", "Snapshot age: under 2 h good, under 6 h stale, older is a problem.", [table([
        ["Region", function (h) { return h.region.toUpperCase(); }], ["House", "house", "num"],
        ["Ruleset", function (h) { return h.ruleset_name || "unmapped"; }],
        ["Faction", "faction"], ["Items", function (h) { return num(h.items); }, "num"],
        ["Snapshot", function (h) {
          var age = now - h.snapshot;
          return status(age < 2 * HOUR ? "good" : age < 6 * HOUR ? "warning" : "critical", ago(age));
        }]], houses)]),
        card("Realm map", "From data/ah_houses.json. Companions match unmapped realms from players' scans on " +
          "their own PCs; those matches stay private.", [table([["Ruleset", 0], ["Realms", 1]],
          Object.keys(rulesets).map(function (k) { return [k, rulesets[k].join(", ")]; }))]),
      ]),
    ]);
  }

  function automationSection(snap) {
    var flows = (snap && snap.workflows) || [];
    var now = snap ? snap.generated : 0;
    var pr = snap && snap.data_pr;
    function health(w) {
      var last = w.latest;
      if (!last) { return status("none", "no runs"); }
      if (last.status !== "completed") { return status("warning", last.status.replace("_", " ")); }
      return last.conclusion === "success" ? status("good", "success") : status("critical", last.conclusion || "failed");
    }
    return section("automation", "Automation", "GitHub Actions, as of the statistics snapshot", [
      el("div", { cls: "grid wide" }, [card("Workflows", "Auction prices should run about 4 times an hour and the " +
        "merge hourly; the server's cron starts them (workflow_dispatch) and GitHub's schedule is the backup.", [table([
        ["Workflow", function (w) { return w.latest && w.latest.url ? el("a", { href: w.latest.url, text: w.name }) : w.name; }],
        ["Latest", health], ["When", function (w) { return w.latest ? ago(now - w.latest.created) : "-"; }],
        ["Runs 24 h", function (w) { return num(w.runs_24h) + (w.expected_24h ? " of ~" + w.expected_24h : ""); }, "num"],
        ["Succeeded", function (w) { return w.runs_24h ? pct(w.success_24h, w.runs_24h) : "-"; }, "num"],
        ["Started by", function (w) { return Object.keys(w.by_event_24h || {}).map(function (k) {
          return k + " " + w.by_event_24h[k]; }).join(", ") || "-"; }]], flows)]),
        card("Data pull request", null, [pr ? el("p", {}, [el("a", { href: pr.url, text: "#" + pr.number }),
          " is open, updated " + ago(now - pr.updated) + ". It merges itself when nothing is held or rejected " +
          "and the website build passes."]) : el("p", { cls: "muted", text: "No data pull request is open." })]),
      ]),
    ]);
  }

  // What needs attention now: stale prices per region, failing price runs.
  // Blizzard publishes snapshots about hourly; the price workflow copies them.
  var PRICE_REGIONS = ["us", "eu", "kr", "tw"];
  var PRICE_WARN = 1.5 * HOUR, PRICE_ALERT = 3 * HOUR;
  var PAID_MONTH = 10000000, FREE_DAY = 100000;   // Workers Paid includes 10M a month; Free allows 100k a day

  function healthChecks(live, snap) {
    var checks = [], now = live.now;
    var newest = {};
    (live.houses || []).forEach(function (h) {
      if (h.items > 0) { newest[h.region] = Math.max(newest[h.region] || 0, h.snapshot || 0); }
    });
    PRICE_REGIONS.forEach(function (region) {
      var label = region.toUpperCase() + " prices";
      if (!newest[region]) {
        checks.push(["critical", label + ": none on the server", "Players in this region get no companion prices."]);
        return;
      }
      var age = now - newest[region];
      var level = age >= PRICE_ALERT ? "critical" : age >= PRICE_WARN ? "warning" : "good";
      checks.push([level, label + ": newest snapshot " + ago(age),
        level === "good" ? null : "The auction price workflow may be failing, or Blizzard's API is behind."]);
    });
    var flows = (snap && snap.workflows) || [];
    flows.forEach(function (w) {
      var last = w.latest;
      if (/price/i.test(w.name) && last && last.status === "completed" && last.conclusion !== "success") {
        checks.push(["critical", w.name + ": last run " + (last.conclusion || "failed"), last.url || null]);
      }
    });
    var usage = snap && snap.requests;
    if (usage && usage.month) {
      var monthTotal = Object.keys(usage.month).reduce(function (s, k) { return s + usage.month[k]; }, 0);
      var day = new Date(usage.through * 1000);
      var daysIn = new Date(Date.UTC(day.getUTCFullYear(), day.getUTCMonth() + 1, 0)).getUTCDate();
      var elapsed = day.getUTCDate() - 1 + (day.getUTCHours() * 60 + day.getUTCMinutes()) / 1440;
      var projected = elapsed > 0.25 ? monthTotal / elapsed * daysIn : monthTotal;
      checks.push([projected > 0.8 * PAID_MONTH ? "warning" : "good",
        "Server requests this month: " + num(monthTotal) + ", on course for about " + num(Math.round(projected)),
        projected > 0.8 * PAID_MONTH ? "Past 80% of the Workers Paid plan's 10 million included requests." : null]);
    }
    var recent = live.errors24 || {};
    checks.push(recent.errors ? [recent.players >= 3 ? "critical" : "warning",
      "Errors in the last 24 h: " + num(recent.errors) + " kinds, from " + num(recent.players) +
      (recent.players === 1 ? " player" : " players"), "See Errors below."]
      : ["good", "No error reports in the last 24 h", null]);
    return checks;
  }

  function healthSection(live, snap) {
    var checks = healthChecks(live, snap);
    var problems = checks.filter(function (c) { return c[0] !== "good"; });
    var rows = checks.map(function (c) {
      var detail = c[2] && /^https?:/.test(c[2]) ? el("a", { href: c[2], text: "Open the run" })
        : (c[2] ? el("span", { cls: "muted", text: c[2] }) : null);
      return el("li", { cls: "check" }, [status(c[0], c[1]), detail]);
    });
    return section("health", "Health", problems.length ? problems.length + " to look at" : "All clear", [
      card(null, "Prices: amber after " + (PRICE_WARN / HOUR) + " h, red after " + (PRICE_ALERT / HOUR) +
        " h without a new snapshot.", [el("ul", { cls: "checks" }, rows)])]);
  }

  function usageSection(snap) {
    var usage = snap && snap.requests;
    if (!usage || !usage.days) {
      var why = usage && usage.error
        ? "Cloudflare refused the analytics request: " + usage.error + ". The CLOUDFLARE_ANALYTICS_TOKEN secret " +
          "needs Account Analytics: Read on the account named by the CLOUDFLARE_ACCOUNT_ID variable."
        : usage && usage.missing
          ? "The data merge workflow didn't get " + usage.missing.join(" or ") + ", and couldn't work it out " +
            "from the token. Add it under the repository's Settings > Secrets and variables > Actions, as a " +
            "repository secret or variable (the workflow can't see environment or Dependabot secrets), with " +
            "that exact name."
          : "Not set up yet: add the CLOUDFLARE_ANALYTICS_TOKEN secret (a Cloudflare API token with Account " +
            "Analytics: Read) and the CLOUDFLARE_ACCOUNT_ID variable to the GitHub repository.";
      return section("usage", "Server requests", null, [card(null, null, [el("p", { cls: "muted", text: why })])]);
    }
    function total(day) { return Object.keys(day.scripts).reduce(function (s, k) { return s + day.scripts[k]; }, 0); }
    var days = usage.days;
    var today = days.length ? days[days.length - 1] : null;
    var week = days.slice(-8, -1);
    var weekAvg = week.length ? week.reduce(function (s, d) { return s + total(d); }, 0) / week.length : 0;
    var busiest = days.slice(0, -1).reduce(function (m, d) { return Math.max(m, total(d)); }, 0);
    var month = Object.keys(usage.month || {}).reduce(function (s, k) { return s + usage.month[k]; }, 0);
    var scripts = {};
    days.forEach(function (d) { Object.keys(d.scripts).forEach(function (k) { scripts[k] = true; }); });
    return section("usage", "Server requests", "Cloudflare Workers analytics, as of the statistics snapshot", [
      tiles([
        ["Today so far (UTC)", num(today ? total(today) : 0), today ? today.date : ""],
        ["Daily average, 7 days", num(Math.round(weekAvg)), pct(weekAvg, FREE_DAY) + " of the free plan's day"],
        ["Busiest day, 30 days", num(busiest), pct(busiest, FREE_DAY) + " of the free plan's day"],
        ["This month", num(month), pct(month, PAID_MONTH) + " of Workers Paid's 10M"],
      ]),
      el("div", { cls: "grid" }, [
        card("Requests per day", "All GoldScout Workers together. Free plan: 100,000 a day; Workers Paid: " +
          "10 million a month included.", [columnChart(days.map(function (d) { return [d.date.slice(5), total(d)]; }),
            "requests")]),
        card("By Worker, this month", null, [table([["Worker", 0], ["Requests", 1, "num"], ["Errors", 2, "num"]],
          Object.keys(scripts).sort().map(function (k) {
            return [k, num((usage.month || {})[k] || 0), num((usage.errors || {})[k] || 0)];
          }))]),
      ]),
    ]);
  }

  function dismissButton(e) {
    var button = el("button", { type: "button", text: "Dismiss", title: "Remove this error and ignore later reports of it" });
    button.addEventListener("click", function () {
      if (!window.confirm("Dismiss this error for good? Later reports of the same error are ignored.\n\n" + e.message)) {
        return;
      }
      button.disabled = true;
      fetch("/admin/api/errors/dismiss", {
        method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fingerprint: e.fingerprint }),
      }).then(function (response) {
        if (!response.ok) { throw new Error("HTTP " + response.status); }
        load();
      }).catch(function (error) {
        button.disabled = false;
        window.alert("Couldn't dismiss it: " + error.message);
      });
    });
    return button;
  }

  function errorsSection(live) {
    var now = live.now;
    var list = live.errors || [];
    var rows = list.map(function (e) {
      var stack = el("details", {}, [el("summary", { text: e.message }), el("pre", { cls: "stack", text: e.stack || "" })]);
      return el("tr", {}, [
        el("td", { cls: "wrap" }, [stack]),
        el("td", { cls: "num", text: num(e.players) }),
        el("td", { cls: "num", text: num(e.occurrences) }),
        el("td", { text: e.addon_version || "-" }),
        el("td", { text: ago(now - e.last_seen) }),
        el("td", { text: date(e.first_seen) }),
        el("td", {}, [dismissButton(e)]),
      ]);
    });
    var head = el("tr", {}, ["Error", "Players", "Times", "Version", "Last seen", "First seen", ""].map(function (h, i) {
      return el("th", { cls: i === 1 || i === 2 ? "num" : "", text: h });
    }));
    return section("errors", "Errors", "Reports from GoldScout Companion, newest first", [
      card(null, "Companions of players who share send them unless reports are turned off. Each row is one error, " +
        "grouped by its message and first stack line; click it for GoldScout's stack lines. Dismiss removes an " +
        "error for good: later reports of the same error are ignored.",
        [list.length ? el("div", { cls: "table-wrap" }, [el("table", {}, [el("thead", {}, [head]),
          el("tbody", {}, rows)])]) : el("p", { cls: "muted", text: "No error reports yet." })])]);
  }

  function gapsSection() {
    return section("gaps", "Not tracked yet", null, [card(null, null, [el("ul", {}, [
      el("li", { text: "Companion users who only download prices (no ID, no uploads). Phase 2: aggregate counts by version." }),
      el("li", { text: "Addon versions: exports don't include them." }),
      el("li", { text: "Errors from players who don't share or turned error reports off (they stay on their PC)." }),
      el("li", { text: "Uploads the server refused, by reason." }),
      el("li", { text: "Website traffic: the site has no analytics by design." }),
    ])])]);
  }

  function reviewButton(n, approve) {
    var button = el("button", { type: "button", text: approve ? "Approve" : "Reject",
      title: approve ? "Show this name on the public leaderboard" : "Clear it; the player shows under their alias" });
    button.addEventListener("click", function () {
      button.disabled = true;
      fetch("/admin/api/names/review", {
        method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: n.id, name: n.name, approve: approve }),
      }).then(function (response) {
        if (!response.ok) { throw new Error("HTTP " + response.status); }
        load();
      }).catch(function (error) {
        button.disabled = false;
        window.alert("Couldn't review it: " + error.message);
      });
    });
    return button;
  }

  function namesSection(live) {
    var list = live.names || [];
    var rows = list.map(function (n) {
      return el("tr", {}, [
        el("td", { cls: "wrap", text: n.name }),
        el("td", { text: n.alias }),
        el("td", { cls: "num", text: num(n.kills) }),
        el("td", { text: ago(live.now - n.updated_at) }),
        el("td", {}, [reviewButton(n, true), document.createTextNode(" "), reviewButton(n, false)]),
      ]);
    });
    var head = el("tr", {}, ["Name", "Alias until approved", "Kills", "Asked", ""].map(function (h, i) {
      return el("th", { cls: i === 2 ? "num" : "", text: h });
    }));
    return section("names", "Leaderboard names", "Names players chose in GoldScout Companion, waiting for review", [
      card(null, "A name shows on the public leaderboard only once approved; until then the player shows under " +
        "their alias. Reject anything offensive, impersonating someone, or advertising. Rejecting clears the name.",
        [list.length ? el("div", { cls: "table-wrap" }, [el("table", {}, [el("thead", {}, [head]),
          el("tbody", {}, rows)])]) : el("p", { cls: "muted", text: "No names waiting." })])]);
  }

  function render(data) {
    var live = data.live, snap = data.snapshot;
    document.getElementById("who").textContent = "Signed in as " + live.who;
    var age = snap ? live.now - snap.generated : null;
    var fresh = document.getElementById("freshness");
    fresh.replaceWith(Object.assign(
      status(age === null ? "critical" : age < 2 * HOUR ? "good" : age < 6 * HOUR ? "warning" : "critical",
        age === null ? "No statistics yet" : "Statistics " + ago(age)), { id: "freshness",
        title: "Built hourly by the data merge workflow; live counts are current." }));
    app.textContent = "";
    if (snap && snap.problems && snap.problems.length) {
      app.appendChild(el("div", { cls: "problems" }, [el("b", { text: "The last statistics run had problems:" }),
        el("ul", {}, snap.problems.map(function (p) { return el("li", { text: p }); }))]));
    }
    if (!snap) {
      app.appendChild(el("p", { cls: "problems", text: "No statistics snapshot yet: the data merge workflow sends " +
        "one every hour (tools/admin_stats.py). Live counts are shown below." }));
    }
    [healthSection(live, snap), growthSection(live, snap), versionsSection(live, snap), reachSection(live, snap),
      playersSection(snap),
      coverageSection(snap), pricesSection(live), usageSection(snap), errorsSection(live), namesSection(live),
      automationSection(snap),
      gapsSection()]
      .forEach(function (s) { app.appendChild(s); });
  }

  function load() {
    fetch("/admin/api/summary", { credentials: "same-origin" }).then(function (response) {
      if (!response.ok) { throw new Error("HTTP " + response.status); }
      return response.json();
    }).then(render).catch(function (error) {
      app.textContent = "";
      app.appendChild(el("p", { cls: "problems", text: "Couldn't load the dashboard: " + error.message }));
    });
  }

  document.getElementById("reload").addEventListener("click", load);
  load();
})();
