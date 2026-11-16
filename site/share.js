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
  // German pages (<html lang="de">, under /de/) answer in German; everything else in English.
  var TEXT = document.documentElement.lang === "de" ? {
    registered: "Danke! Deine Daten sind angekommen. Sie werden geprüft und fließen beim nächsten stündlichen Update " +
      "in die Gemeinschaftsdaten. Teile jederzeit wieder aus diesem Browser: Der neueste Export ersetzt den letzten.",
    stored: "Danke! Dein neuerer Export ist angekommen und ersetzt beim nächsten stündlichen Update den letzten.",
    unchanged: "Schon geteilt: Diesen Export hat der Server bereits. Spiel noch etwas und exportiere dann erneut.",
    noKey: " (Dieser Browser konnte den Schlüssel für deine Daten nicht speichern. Teile neuere Exporte daher mit " +
      "GoldScout Companion oder dem GitHub-Formular.)",
    empty: "Füge zuerst deinen Export ein: Gib im Spiel /gscout export ein und kopiere den Text.",
    notExport: "Das ist kein GoldScout-Export. Gib im Spiel /gscout export ein, drücke im Fenster Strg+C und füge " +
      "alles hier ein.",
    tooLarge: "Dieser Export ist zu groß für diese Seite. GoldScout Companion kann ihn teilen.",
    boxes: "Setze beide Haken, um zu teilen.",
    sending: "Wird gesendet...",
    elsewhere: "Diese Daten werden schon über GoldScout Companion oder einen anderen Browser geteilt, daher kann nur " +
      "dieser sie aktualisieren. Die Companion-App teilt neuere Exporte von selbst; oder nutze das GitHub-Formular " +
      "unten.",
    failed: "Etwas ist schiefgelaufen (%s). Versuch es in ein paar Minuten noch einmal.",
    offline: "Der GoldScout-Server ist nicht erreichbar. Prüfe deine Verbindung und versuch es noch einmal.",
    tooOften: "Zu viele Versuche gerade. Versuch es in ein paar Minuten noch einmal.",
    serverErrors: false   // the server's own messages are English: show ours
  } : {
    registered: "Thanks! Your data is in. It's checked and joins the community data at the next hourly update. " +
      "Share again any time from this browser: the newest export replaces the last.",
    stored: "Thanks! Your newer export is in and replaces the last one at the next hourly update.",
    unchanged: "Already shared: this export is the one the server has. Play some more, then export again.",
    noKey: " (This browser couldn't save the key for your data, so share newer exports with GoldScout Companion " +
      "or the GitHub form.)",
    empty: "Paste your export first: type /gscout export in game and copy the text.",
    notExport: "That isn't a GoldScout export. In game, type /gscout export, press Ctrl+C in the window, and paste " +
      "everything here.",
    tooLarge: "This export is too large to send here. GoldScout Companion can share it.",
    boxes: "Tick both boxes to share.",
    sending: "Sending...",
    elsewhere: "This data is already shared from GoldScout Companion or another browser, so only that one can " +
      "update it. The companion shares newer exports by itself; or use the GitHub form below.",
    failed: "Something went wrong (%s). Try again in a few minutes.",
    offline: "Couldn't reach the GoldScout server. Check your connection and try again.",
    tooOften: "Too many tries just now. Try again in a few minutes.",
    serverErrors: true
  };

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

  var REPLIES = { registered: TEXT.registered, stored: TEXT.stored, unchanged: TEXT.unchanged };

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var text = box.value.replace(/\r/g, "").trim();
    var first = text.split("\n")[0].trim();
    var match = HEADER.exec(first);
    if (!text) {
      say(TEXT.empty, "bad");
      return;
    }
    if (!match) {
      say(TEXT.notExport, "bad");
      return;
    }
    if (new TextEncoder().encode(text).length > MAX_BYTES) {
      say(TEXT.tooLarge, "bad");
      return;
    }
    var unchecked = form.querySelectorAll("input[type=checkbox]:not(:checked)");
    if (unchecked.length) {
      say(TEXT.boxes, "bad");
      return;
    }
    var install = match[1];
    var token = tokens()[install];
    var headers = { "Content-Type": "text/plain; charset=utf-8", "X-GoldScout-Terms": TERMS };
    if (token) {
      headers.Authorization = "Bearer " + token;
    }
    button.disabled = true;
    say(TEXT.sending, "");
    fetch(API + "/v1/uploads", { method: "POST", headers: headers, body: text + "\n" }).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (reply) {
        if (response.ok && reply.status === "registered" && reply.token) {
          var kept = keep(install, reply.token);
          say(REPLIES.registered + (kept ? "" : TEXT.noKey), "good");
        } else if (response.ok && REPLIES[reply.status]) {
          say(REPLIES[reply.status], "good");
        } else if (response.status === 403) {
          say(TEXT.elsewhere, "bad");
        } else {
          say(response.status === 413 ? TEXT.tooLarge : (TEXT.serverErrors && reply.error) ||
              (response.status === 429 ? TEXT.tooOften : TEXT.failed.replace("%s", response.status)), "bad");
        }
      });
    }).catch(function () {
      say(TEXT.offline, "bad");
    }).then(function () {
      button.disabled = false;
    });
  });
})();
