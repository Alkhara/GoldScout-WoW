// Zone champions on zone pages: fills in the list the zone goal box marks
// (#zone-champions, data-zone = the zone's uiMapID) with the zone's top
// contributors from the GoldScout server. Players are named only if they chose
// that in GoldScout Companion. Everything from the server is written with
// textContent, never as HTML; the list stays hidden if nothing comes back.
(function () {
  "use strict";
  var API = "https://api.wowgoldscout.com";
  var box = document.getElementById("zone-champions");
  if (!box || !window.fetch) {
    return;
  }
  var list = box.querySelector("ol");

  function number(n) {
    return Number(n || 0).toLocaleString("en-US");
  }

  fetch(API + "/v1/leaderboard/zones").then(function (response) {
    if (!response.ok) {
      throw new Error("HTTP " + response.status);
    }
    return response.json();
  }).then(function (data) {
    var rows = (data.zones || {})[box.getAttribute("data-zone")] || [];
    if (!rows.length) {
      return;
    }
    rows.forEach(function (row) {
      var li = document.createElement("li");
      li.value = row.rank;   // ties share a place
      var name = document.createElement("span");
      name.className = row.name ? "champion" : "champion anon";
      name.textContent = row.name || "Anonymous contributor";
      var kills = document.createElement("span");
      kills.className = "small";
      kills.textContent = " · " + number(row.kills) + " kills here";
      li.appendChild(name);
      li.appendChild(kills);
      list.appendChild(li);
    });
    box.hidden = false;
  }).catch(function () { /* champions are a bonus: the page works without them */ });
})();
