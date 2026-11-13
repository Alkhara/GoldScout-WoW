// The contributor leaderboard on /leaderboard: fills in the table the page
// marks (#leaderboard) from the GoldScout server. Everything from the server
// is written with textContent, never as HTML.
(function () {
  "use strict";
  var API = "https://api.wowgoldscout.com";
  var table = document.getElementById("leaderboard");
  var status = document.getElementById("leaderboard-status");
  if (!table || !status || !window.fetch) {
    return;
  }

  function cell(text, cls) {
    var td = document.createElement("td");
    td.textContent = text;
    if (cls) {
      td.className = cls;
    }
    return td;
  }

  function number(n) {
    return Number(n || 0).toLocaleString("en-US");
  }

  function ago(unix) {
    var minutes = Math.max(0, Math.round((Date.now() / 1000 - unix) / 60));
    if (minutes < 90) {
      return minutes + " min ago";
    }
    return minutes < 48 * 60 ? Math.round(minutes / 60) + " hours ago" : Math.round(minutes / 1440) + " days ago";
  }

  fetch(API + "/v1/leaderboard").then(function (response) {
    if (!response.ok) {
      throw new Error("HTTP " + response.status);
    }
    return response.json();
  }).then(function (data) {
    var body = table.querySelector("tbody");
    body.textContent = "";
    (data.top || []).forEach(function (row) {
      var tr = document.createElement("tr");
      tr.appendChild(cell("#" + row.rank, "num"));
      tr.appendChild(cell(row.name || "Anonymous contributor", row.name ? "" : "anon"));
      tr.appendChild(cell(number(row.kills), "num"));
      tr.appendChild(cell(number(row.mobs), "num"));
      body.appendChild(tr);
    });
    if (!(data.top || []).length) {
      var empty = document.createElement("tr");
      var td = cell("No scores yet. They appear within the hour after shared data is merged.");
      td.colSpan = 4;
      empty.appendChild(td);
      body.appendChild(empty);
    }
    status.textContent = number(data.contributors) + " contributors have shared " + number(data.kills) +
      " kills that count in the community data." + (data.updated ? " Updated " + ago(data.updated) + "." : "");
    table.hidden = false;
  }).catch(function () {
    status.textContent = "The leaderboard couldn't be loaded right now. Try again in a few minutes.";
  });
})();
