// Live auction prices on GoldScout's data pages.
//
// Pages are static HTML; this fills in elements the build marked:
//   data-price="itemID"          the item's lowest unit buyout
//   data-qty="itemID"            how many are listed
//   data-value="id:mult,id:mult" sum of price x mult (gold per kill: mult is
//                                drop chance x average stack)
//   table.by-value               rows re-sorted by their data-value, highest first
// The prices come from the GoldScout server, which copies Blizzard's auction
// house snapshots (Game Data API) every 15 minutes. Everything from the server
// is written with textContent, never as HTML.
(function () {
  "use strict";
  var API = "https://goldscout-api.cawley22.workers.dev";
  var STORE = "goldscout.market";
  var bar = document.getElementById("prices-bar");
  if (!bar || !window.fetch) {
    return;
  }
  var pick = bar.querySelector("select");
  var status = bar.querySelector(".status");

  function money(copper) {
    copper = Math.round(copper);
    var g = Math.floor(copper / 10000), s = Math.floor(copper / 100) % 100, c = copper % 100;
    if (g > 0) {
      return g.toLocaleString("en-US") + "g " + s + "s";
    }
    if (s > 0) {
      return s + "s " + c + "c";
    }
    return c + "c";
  }

  function minutesAgo(unix) {
    var minutes = Math.max(0, Math.round((Date.now() / 1000 - unix) / 60));
    if (minutes < 90) {
      return minutes + " min ago";
    }
    return Math.round(minutes / 60) + " hours ago";
  }

  var REGION_ORDER = ["us", "eu", "kr", "tw"];

  function label(house) {
    var faction = house.faction === "Neutral" ? "Blackwater (neutral)" : house.faction;
    return house.region.toUpperCase() + ": " + house.rulesetName + " realms, " + faction;
  }

  // US first (the default), then EU, KR and TW; by ruleset and faction within each.
  function order(a, b) {
    var ra = REGION_ORDER.indexOf(a.region), rb = REGION_ORDER.indexOf(b.region);
    if (ra !== rb) {
      return ra - rb;
    }
    return label(a) < label(b) ? -1 : 1;
  }

  function remember(key) {
    try {
      localStorage.setItem(STORE, key);
    } catch (e) { /* storage blocked: just don't remember */ }
  }

  function remembered() {
    try {
      return localStorage.getItem(STORE);
    } catch (e) {
      return null;
    }
  }

  function getJson(path) {
    return fetch(API + path).then(function (response) {
      if (!response.ok) {
        throw new Error("HTTP " + response.status);
      }
      return response.json();
    });
  }

  function each(selector, fn) {
    Array.prototype.forEach.call(document.querySelectorAll(selector), fn);
  }

  function fill(prices) {
    each("[data-price]", function (el) {
      var p = prices[el.getAttribute("data-price")];
      el.textContent = p ? money(p[0]) : "not listed";
      el.classList.toggle("muted", !p);
    });
    each("[data-qty]", function (el) {
      var p = prices[el.getAttribute("data-qty")];
      el.textContent = p ? p[1].toLocaleString("en-US") + " listed" : "";
    });
    each("[data-value]", function (el) {
      var total = 0, priced = false;
      el.getAttribute("data-value").split(",").forEach(function (part) {
        var bits = part.split(":"), p = prices[bits[0]];
        if (p && bits.length === 2) {
          total += p[0] * Number(bits[1]);
          priced = true;
        }
      });
      el.textContent = priced ? money(total) : "-";
      el.setAttribute("data-copper", priced ? String(Math.round(total)) : "-1");
    });
    each("table.by-value", function (table) {
      var body = table.tBodies[0];
      var rows = Array.prototype.slice.call(body.rows);
      rows.sort(function (a, b) {
        return copperOf(b) - copperOf(a);
      });
      rows.forEach(function (row) {
        body.appendChild(row);
      });
    });
  }

  function copperOf(row) {
    var cell = row.querySelector("[data-copper]");
    return cell ? Number(cell.getAttribute("data-copper")) : -1;
  }

  function clear(text) {
    each("[data-price], [data-value]", function (el) {
      el.textContent = text;
    });
    each("[data-qty]", function (el) {
      el.textContent = "";
    });
  }

  function load(house) {
    status.textContent = "Loading prices...";
    getJson("/v1/prices/" + house.region + "/" + house.house).then(function (data) {
      fill(data.prices || {});
      status.textContent = "Lowest buyout, snapshot " + minutesAgo(data.snapshot) + ".";
    }).catch(function () {
      clear("-");
      status.textContent = "Prices are unavailable right now.";
    });
  }

  getJson("/v1/prices").then(function (list) {
    var houses = (list.houses || []).filter(function (h) {
      return h.ruleset !== null && h.rulesetName && h.items > 0;
    });
    if (!houses.length) {
      clear("-");
      status.textContent = "Prices are unavailable right now.";
      return;
    }
    houses.sort(order);
    var chosen = remembered();
    houses.forEach(function (h) {
      var option = document.createElement("option");
      option.value = h.region + "/" + h.house;
      option.textContent = label(h);
      if (option.value === chosen) {
        option.selected = true;
      }
      pick.appendChild(option);
    });
    pick.hidden = false;
    pick.addEventListener("change", function () {
      remember(pick.value);
      load(houses[pick.selectedIndex]);
    });
    load(houses[pick.selectedIndex]);
  }).catch(function () {
    clear("-");
    status.textContent = "Prices are unavailable right now.";
  });
})();
