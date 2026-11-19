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
  var HEADER = /^GoldScout-export [2-6]\^([a-z0-9]{12})\^([1-9][0-9]{0,8})$/;
  var STORE = "goldscout-share-tokens";
  var LAST = "goldscout-share-last";   // the install this browser shared most recently: its leaderboard entry
  // Leaderboard names, as the server checks them (server/src/leaderboard.js NAME).
  var NAME = /^[\p{L}\p{N}](?:[\p{L}\p{N} ._'-]{1,18})[\p{L}\p{N}]$/u;
  // German, Spanish and French pages (<html lang="de"> under /de/, "es" under /es/, "fr" under /fr/) answer in
  // their language; everything else in English.
  var TEXT = {de: {
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
    rank: "Dein Rang: #{rank} von {of}, mit {kills} gezählten Kills.",
    rankNone: "Deine Kills zählen, sobald sie in den Gemeinschaftsdaten sind, meist innerhalb eines Tages nach dem " +
      "Teilen.",
    shown: " Öffentlich gezeigt als {name}",
    until: ", bis {name} freigegeben ist",
    anonymous: " In der öffentlichen Bestenliste bist du anonym.",
    saved: "Gespeichert.",
    badName: "Namen haben 3 bis 20 Buchstaben, Ziffern und Leerzeichen (dazu . _ ' -).",
    boardFailed: "Konnte nicht gespeichert werden ({status}). Versuch es gleich noch einmal.",
    serverErrors: false   // the server's own messages are English: show ours
  }, es: {
    registered: "¡Gracias! Tus datos han llegado. Se comprueban y se suman a los datos de la comunidad en la próxima " +
      "actualización de cada hora. Comparte de nuevo cuando quieras desde este navegador: la exportación más reciente " +
      "sustituye a la anterior.",
    stored: "¡Gracias! Tu exportación más reciente ha llegado y sustituye a la anterior en la próxima actualización de " +
      "cada hora.",
    unchanged: "Ya compartida: el servidor ya tiene esta exportación. Juega un poco más y vuelve a exportar.",
    noKey: " (Este navegador no pudo guardar la clave de tus datos, así que comparte las exportaciones nuevas con " +
      "GoldScout Companion o con el formulario de GitHub.)",
    empty: "Pega primero tu exportación: escribe /gscout export en el juego y copia el texto.",
    notExport: "Eso no es una exportación de GoldScout. En el juego, escribe /gscout export, pulsa Ctrl+C en la " +
      "ventana y pégalo todo aquí.",
    tooLarge: "Esta exportación es demasiado grande para esta página. GoldScout Companion puede compartirla.",
    boxes: "Marca las dos casillas para compartir.",
    sending: "Enviando...",
    elsewhere: "Estos datos ya se comparten desde GoldScout Companion o desde otro navegador, así que solo ese puede " +
      "actualizarlos. Companion comparte las exportaciones nuevas solo; o usa el formulario de GitHub de abajo.",
    failed: "Algo salió mal (%s). Inténtalo de nuevo en unos minutos.",
    offline: "No se pudo conectar con el servidor de GoldScout. Comprueba tu conexión e inténtalo de nuevo.",
    tooOften: "Demasiados intentos ahora mismo. Inténtalo de nuevo en unos minutos.",
    rank: "Tu puesto: n.º {rank} de {of}, con {kills} muertes contadas.",
    rankNone: "Tus muertes cuentan cuando están en los datos de la comunidad, normalmente en el día siguiente a " +
      "compartir.",
    shown: " Se te muestra públicamente como {name}",
    until: ", hasta que se apruebe {name}",
    anonymous: " En la clasificación pública eres anónimo.",
    saved: "Guardado.",
    badName: "Los nombres tienen de 3 a 20 letras, dígitos y espacios (y . _ ' -).",
    boardFailed: "No se pudo guardar ({status}). Inténtalo de nuevo en un momento.",
    serverErrors: false   // the server's own messages are English: show ours
  }, fr: {
    registered: "Merci\u00a0! Vos données sont arrivées. Elles sont vérifiées et rejoignent les données de la " +
      "communauté à la prochaine mise à jour horaire. Partagez à nouveau quand vous voulez depuis ce navigateur\u00a0: " +
      "l'exportation la plus récente remplace la précédente.",
    stored: "Merci\u00a0! Votre exportation plus récente est arrivée et remplace la précédente à la prochaine mise à " +
      "jour horaire.",
    unchanged: "Déjà partagée\u00a0: le serveur a déjà cette exportation. Jouez encore un peu et exportez à nouveau.",
    noKey: " (Ce navigateur n'a pas pu garder la clé de vos données, alors partagez les nouvelles exportations avec " +
      "GoldScout Companion ou le formulaire GitHub.)",
    empty: "Collez d'abord votre exportation\u00a0: tapez /gscout export en jeu et copiez le texte.",
    notExport: "Ce n'est pas une exportation GoldScout. En jeu, tapez /gscout export, appuyez sur Ctrl+C dans la " +
      "fenêtre et collez tout ici.",
    tooLarge: "Cette exportation est trop grande pour cette page. GoldScout Companion peut la partager.",
    boxes: "Cochez les deux cases pour partager.",
    sending: "Envoi...",
    elsewhere: "Ces données sont déjà partagées depuis GoldScout Companion ou un autre navigateur, donc seul celui-ci " +
      "peut les mettre à jour. Companion partage les nouvelles exportations tout seul\u00a0; ou utilisez le formulaire " +
      "GitHub ci-dessous.",
    failed: "Quelque chose s'est mal passé (%s). Réessayez dans quelques minutes.",
    offline: "Impossible de joindre le serveur GoldScout. Vérifiez votre connexion et réessayez.",
    tooOften: "Trop d'essais pour le moment. Réessayez dans quelques minutes.",
    rank: "Votre rang\u00a0: n°\u00a0{rank} sur {of}, avec {kills} victimes comptées.",
    rankNone: "Vos victimes comptent une fois dans les données de la communauté, en général dans la journée qui suit " +
      "le partage.",
    shown: " Vous êtes affiché publiquement sous le nom {name}",
    until: ", jusqu'à l'approbation de {name}",
    anonymous: " Vous êtes anonyme dans le classement public.",
    saved: "Enregistré.",
    badName: "Les noms ont de 3 à 20 lettres, chiffres et espaces (plus . _ ' -).",
    boardFailed: "Impossible d'enregistrer ({status}). Réessayez dans un instant.",
    serverErrors: false   // the server's own messages are English: show ours
  }}[document.documentElement.lang] || {
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
    rank: "Your rank: #{rank} of {of}, with {kills} kills counted.",
    rankNone: "Your kills count once they're in the community data, usually within a day of sharing.",
    shown: " Shown publicly as {name}",
    until: " until {name} is approved",
    anonymous: " You're anonymous on the public board.",
    saved: "Saved.",
    badName: "Names are 3 to 20 letters, digits and spaces (and . _ ' -).",
    boardFailed: "Couldn't save it ({status}). Try again in a moment.",
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

  function remember(install) {
    try {
      localStorage.setItem(LAST, install);
    } catch (error) { /* the leaderboard box just won't come back on the next visit */ }
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
          remember(install);
          board.load(install);
        } else if (response.ok && REPLIES[reply.status]) {
          say(REPLIES[reply.status], "good");
          remember(install);
          board.load(install);
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

  // "Your leaderboard entry": the rank of the install this browser shared, and whether (and under which name)
  // it's shown publicly, through /v1/leaderboard/me with the install's upload token, as the companion does.
  var board = (function () {
    var section = document.getElementById("share-board");
    if (!section) {
      return { load: function () {} };
    }
    var rank = document.getElementById("board-rank");
    var shown = document.getElementById("board-public");
    var name = document.getElementById("board-name");
    var save = document.getElementById("board-save");
    var note = document.getElementById("board-status");
    var current = null;

    function number(n) {
      return Number(n || 0).toLocaleString({ de: "de-DE", es: "es-ES", fr: "fr-FR" }[document.documentElement.lang] || "en-US");
    }

    function fill(info) {
      var text = info.rank === null || info.rank === undefined ? TEXT.rankNone :
        TEXT.rank.replace("{rank}", info.rank).replace("{of}", number(info.contributors || info.rank))
          .replace("{kills}", number(info.kills));
      if (info.public) {
        text += TEXT.shown.replace("{name}", info.approved ? info.name : info.alias);
        if (info.name && !info.approved) {
          text += TEXT.until.replace("{name}", info.name);
        }
        text += ".";
      } else {
        text += TEXT.anonymous;
      }
      rank.textContent = text;
      shown.checked = Boolean(info.public);
      name.value = info.name || "";
      name.disabled = !shown.checked;
      section.hidden = false;
    }

    function request(install, method, body) {
      var headers = { "X-GoldScout-Install": install, Authorization: "Bearer " + tokens()[install] };
      if (body) {
        headers["Content-Type"] = "application/json";
      }
      return fetch(API + "/v1/leaderboard/me", { method: method, headers: headers, body: body });
    }

    function load(install) {
      if (!install || !tokens()[install]) {
        return;
      }
      current = install;
      request(install, "GET").then(function (response) {
        return response.ok ? response.json() : null;
      }).then(function (info) {
        if (info && current === install) {
          fill(info);
        }
      }).catch(function () { /* the box is a bonus: sharing works without it */ });
    }

    shown.addEventListener("change", function () {
      name.disabled = !shown.checked;
    });
    save.addEventListener("click", function () {
      var wanted = name.value.trim();
      if (shown.checked && wanted && !NAME.test(wanted)) {
        note.textContent = TEXT.badName;
        note.className = "share-status bad";
        return;
      }
      save.disabled = true;
      request(current, "PUT", JSON.stringify({ public: shown.checked, name: wanted || null })).then(function (response) {
        return response.json().catch(function () { return {}; }).then(function (reply) {
          if (response.ok) {
            fill(reply);
            note.textContent = TEXT.saved;
            note.className = "share-status good";
          } else {
            note.textContent = TEXT.boardFailed.replace("{status}", response.status);
            note.className = "share-status bad";
          }
        });
      }).catch(function () {
        note.textContent = TEXT.offline;
        note.className = "share-status bad";
      }).then(function () {
        save.disabled = false;
      });
    });

    try {
      load(localStorage.getItem(LAST));
    } catch (error) { /* no storage: nothing shared from here to show */ }
    return { load: load };
  })();
})();
