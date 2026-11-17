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
  // German and Spanish pages (<html lang="de"> under /de/, "es" under /es/) show their language; the rest English.
  var LANG = document.documentElement.lang;
  var LOCALE = { de: "de-DE", es: "es-ES" }[LANG] || "en-US";
  var TEXT = {
    de: {
      anonymous: "Anonyme Mitwirkende",
      empty: "Noch keine Wertung. Sie erscheint innerhalb einer Stunde, nachdem geteilte Daten übernommen wurden.",
      summary: "{contributors} Mitwirkende haben {kills} Kills geteilt, die in den Gemeinschaftsdaten zählen.",
      updated: " Aktualisiert {ago}.",
      minutes: "vor {n} Minuten",
      hours: "vor {n} Stunden",
      days: "vor {n} Tagen",
      failed: "Die Bestenliste konnte gerade nicht geladen werden. Versuch es in ein paar Minuten noch einmal."
    },
    es: {
      anonymous: "Colaborador anónimo",
      empty: "Aún no hay puntuaciones. Aparecen en la hora siguiente a que se incorporen los datos compartidos.",
      summary: "{contributors} colaboradores han compartido {kills} muertes que cuentan en los datos de la comunidad.",
      updated: " Actualizado {ago}.",
      minutes: "hace {n} min",
      hours: "hace {n} horas",
      days: "hace {n} días",
      failed: "No se pudo cargar la clasificación ahora mismo. Inténtalo de nuevo en unos minutos."
    }
  }[LANG] || {
    anonymous: "Anonymous contributor",
    empty: "No scores yet. They appear within the hour after shared data is merged.",
    summary: "{contributors} contributors have shared {kills} kills that count in the community data.",
    updated: " Updated {ago}.",
    minutes: "{n} min ago",
    hours: "{n} hours ago",
    days: "{n} days ago",
    failed: "The leaderboard couldn't be loaded right now. Try again in a few minutes."
  };

  function cell(text, cls) {
    var td = document.createElement("td");
    td.textContent = text;
    if (cls) {
      td.className = cls;
    }
    return td;
  }

  function number(n) {
    return Number(n || 0).toLocaleString(LOCALE);
  }

  function ago(unix) {
    var minutes = Math.max(0, Math.round((Date.now() / 1000 - unix) / 60));
    if (minutes < 90) {
      return TEXT.minutes.replace("{n}", minutes);
    }
    return minutes < 48 * 60 ? TEXT.hours.replace("{n}", Math.round(minutes / 60)) :
      TEXT.days.replace("{n}", Math.round(minutes / 1440));
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
      tr.appendChild(cell(row.name || TEXT.anonymous, row.name ? "" : "anon"));
      tr.appendChild(cell(number(row.kills), "num"));
      tr.appendChild(cell(number(row.mobs), "num"));
      body.appendChild(tr);
    });
    if (!(data.top || []).length) {
      var empty = document.createElement("tr");
      var td = cell(TEXT.empty);
      td.colSpan = 4;
      empty.appendChild(td);
      body.appendChild(empty);
    }
    status.textContent = TEXT.summary.replace("{contributors}", number(data.contributors))
      .replace("{kills}", number(data.kills)) + (data.updated ? TEXT.updated.replace("{ago}", ago(data.updated)) : "");
    table.hidden = false;
  }).catch(function () {
    status.textContent = TEXT.failed;
  });
})();
