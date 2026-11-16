// The share form on /share: sends a pasted /gscout export to the GoldScout
// upload service, as GoldScout Companion does. The first upload of an install
// registers it and returns its upload token; this browser keeps the token
// (localStorage, per install ID) so it can send newer exports of the same data
// later. Everything from the server is written with textContent, never as HTML.
(function () {
  "use strict";
  var LOCAL = location.hostname === "localhost" || location.hostname === "127.0.0.1";
  var API = LOCAL ? "http://127.0.0.1:8799" : "https://api.wowgoldscout.com";   // local: wrangler dev
  var TERMS = "2026-11-07";   // the Contributor Terms version (server/src/index.js TERMS_VERSIONS)
  var MAX_BYTES = 250000;     // the server's limit for one export
  var HEADER = /^GoldScout-export [2345]\^([a-z0-9]{12})\^([1-9][0-9]{0,8})$/;
  var STORE = "goldscout-share-tokens";

  var form = document.getElementById("share-form");
  var status = document.getElementById("share-status");
  if (!form || !status || !window.fetch) {
    return;
  }
  var box = form.querySelector("textarea");
  var button = form.querySelector("button");
  form.hidden = false;

  function tokens() {
    try {
      return JSON.parse(localStorage.getItem(STORE) || "{}") || {};
    } catch (error) {
      return {};
    }
  }

  function keep(install, token) {
    try {
      var all = tokens();
      all[install] = token;
      localStorage.setItem(STORE, JSON.stringify(all));
      return true;
    } catch (error) {
      return false;
    }
  }

  function say(text, kind) {
    status.textContent = text;
    status.className = "share-status " + (kind || "");
  }

  var REPLIES = {
    registered: "Thanks! Your data is in. It's checked and joins the community data at the next hourly update. " +
      "Share again any time from this browser: the newest export replaces the last.",
    stored: "Thanks! Your newer export is in and replaces the last one at the next hourly update.",
    unchanged: "Already shared: this export is the one the server has. Play some more, then export again."
  };

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var text = box.value.replace(/\r/g, "").trim();
    var first = text.split("\n")[0].trim();
    var match = HEADER.exec(first);
    if (!text) {
      say("Paste your export first: type /gscout export in game and copy the text.", "bad");
      return;
    }
    if (!match) {
      say("That isn't a GoldScout export. In game, type /gscout export, press Ctrl+C in the window, and paste " +
          "everything here.", "bad");
      return;
    }
    if (new TextEncoder().encode(text).length > MAX_BYTES) {
      say("This export is too large to send here. GoldScout Companion can share it.", "bad");
      return;
    }
    var unchecked = form.querySelectorAll("input[type=checkbox]:not(:checked)");
    if (unchecked.length) {
      say("Tick both boxes to share.", "bad");
      return;
    }
    var install = match[1];
    var token = tokens()[install];
    var headers = { "Content-Type": "text/plain; charset=utf-8", "X-GoldScout-Terms": TERMS };
    if (token) {
      headers.Authorization = "Bearer " + token;
    }
    button.disabled = true;
    say("Sending...", "");
    fetch(API + "/v1/uploads", { method: "POST", headers: headers, body: text + "\n" }).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (reply) {
        if (response.ok && reply.status === "registered" && reply.token) {
          var kept = keep(install, reply.token);
          say(REPLIES.registered + (kept ? "" : " (This browser couldn't save the key for your data, so share " +
              "newer exports with GoldScout Companion or the GitHub form.)"), "good");
        } else if (response.ok && REPLIES[reply.status]) {
          say(REPLIES[reply.status], "good");
        } else if (response.status === 403) {
          say("This data is already shared from GoldScout Companion or another browser, so only that one can " +
              "update it. The companion shares newer exports by itself; or use the GitHub form below.", "bad");
        } else {
          say(reply.error || "Something went wrong (" + response.status + "). Try again in a few minutes.", "bad");
        }
      });
    }).catch(function () {
      say("Couldn't reach the GoldScout server. Check your connection and try again.", "bad");
    }).then(function () {
      button.disabled = false;
    });
  });
})();
