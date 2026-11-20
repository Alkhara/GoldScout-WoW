// Live Blackwater flips on /flips/<market> pages (site/flips.py builds them).
//
// The page carries the flips from when it was built. This works them out again from the latest auction prices:
// table#flips names the two houses (data-region, data-buy: Blackwater, data-sell: the faction's) and the
// add-on's rules (data-cut, data-min-profit, data-min-margin, data-max-age, data-top, data-cap),
// /flips-names.json names the items, and /flips/reference-<region>.json has each item's regional price. Everything from the server is written with textContent, never as HTML. Without JavaScript,
// or if the prices can't be loaded, the built table stays.
(function () {
  "use strict";
  var API = "https://api.wowgoldscout.com";

  // The add-on's flips (GoldScout/Engine.lua Engine:Flips, site/flips.py flips()): buy and sell are
  // {itemID: [lowest unit buyout in copper, quantity listed]}; a sell price over cap times reference[itemID]
  // (the region's median price) isn't one anyone pays.
  function flips(buy, sell, cut, minProfit, minMargin, reference, cap) {
    reference = reference || {};
    var rows = [];
    Object.keys(buy).forEach(function (item) {
      var bought = buy[item], sold = sell[item];
      if (!sold) {
        return;
      }
      var cost = bought[0], stock = bought[1], price = sold[0], listed = sold[1];
      if (cost <= 0 || stock <= 0 || listed <= 0 || price <= 0) {
        return;
      }
      if (reference[item] && price > reference[item] * cap) {
        return;
      }
      var profit = price * cut - cost;
      if (profit >= minProfit && profit >= cost * minMargin) {
        rows.push({ item: Number(item), cost: cost, sell: price, profit: profit, margin: profit / cost,
          stock: stock, listed: listed });
      }
    });
    rows.sort(function (a, b) { return b.profit - a.profit || a.item - b.item; });
    return rows;
  }

  if (typeof module !== "undefined" && module.exports) {   // the tests run flips() in Node
    module.exports = { flips: flips };
  }
  if (typeof document === "undefined") {
    return;
  }
  var table = document.getElementById("flips");
  var status = document.getElementById("flips-status");
  var more = document.getElementById("flips-more");
  if (!table || !status || !window.fetch) {
    return;
  }
  var d = table.dataset;

  function money(copper) {   // site/guides.py money(): 12g 34s, 4s 12c, 80c
    copper = Math.round(copper);
    var g = Math.floor(copper / 10000), s = Math.floor(copper / 100) % 100, c = copper % 100;
    if (g) {
      return g.toLocaleString("en-US") + "g" + (s ? " " + s + "s" : "");
    }
    if (s) {
      return s + "s" + (c ? " " + c + "c" : "");
    }
    return c + "c";
  }

  function ago(unix) {
    var minutes = Math.max(0, Math.round((Date.now() / 1000 - unix) / 60));
    return minutes < 90 ? minutes + " min ago" : Math.round(minutes / 60) + " hours ago";
  }

  function getJson(url) {
    return fetch(url).then(function (response) {
      if (!response.ok) {
        throw new Error("HTTP " + response.status);
      }
      return response.json();
    });
  }

  function cell(row, text, cls) {
    var td = document.createElement("td");
    if (cls) {
      td.className = cls;
    }
    if (text instanceof Node) {
      td.appendChild(text);
    } else {
      td.textContent = text;
    }
    row.appendChild(td);
    return td;
  }

  function itemName(names, item) {
    var known = names[item] || ["Item " + item, 1, 0];
    var el = document.createElement(known[2] ? "a" : "span");
    el.className = "q" + known[1];
    el.textContent = known[0];
    if (known[2]) {
      el.href = "/item/" + item;
    }
    return el;
  }

  function show(rows, names) {
    var body = table.tBodies[0];
    body.textContent = "";
    var top = Number(d.top) || 50;
    rows.slice(0, top).forEach(function (r) {
      var tr = document.createElement("tr");
      cell(tr, itemName(names, r.item));
      cell(tr, money(r.cost), "num");
      cell(tr, money(r.sell), "num");
      var b = document.createElement("b");
      b.textContent = money(r.profit);
      cell(tr, b, "num");
      cell(tr, Math.round(r.margin * 100) + "%", "num");
      cell(tr, r.stock.toLocaleString("en-US") + " / " + r.listed.toLocaleString("en-US"), "num");
      body.appendChild(tr);
    });
    if (!rows.length) {
      var empty = document.createElement("tr");
      cell(empty, "No flips right now.", "small").colSpan = 6;
      body.appendChild(empty);
    }
    if (more) {
      more.textContent = rows.length > top ? "The top " + top + " of " + rows.length.toLocaleString("en-US") + "." : "";
    }
  }

  Promise.all([
    getJson(API + "/v1/prices/" + d.region + "/" + d.buy),
    getJson(API + "/v1/prices/" + d.region + "/" + d.sell),
    getJson("/flips-names.json"),
    getJson("/flips/reference-" + d.region + ".json").catch(function () { return {}; }),
  ]).then(function (got) {
    var buy = got[0], sell = got[1];
    var oldest = Math.min(buy.snapshot || 0, sell.snapshot || 0);
    if (Date.now() / 1000 - oldest > Number(d.maxAge)) {
      status.textContent = "The latest auction house snapshots are more than " + Math.round(Number(d.maxAge) / 3600) +
        " hours old, so there's nothing to flip safely right now.";
      show([], got[2]);
      return;
    }
    show(flips(buy.prices || {}, sell.prices || {}, Number(d.cut), Number(d.minProfit), Number(d.minMargin), got[3],
      Number(d.cap)), got[2]);
    status.textContent = "Live prices: Blackwater snapshot " + ago(buy.snapshot) + ", " + d.faction + " snapshot " +
      ago(sell.snapshot) + ".";
  }).catch(function () {
    status.textContent += " Couldn't load the latest prices just now; these are from when the page was built.";
  });
})();
