// Site search: items, mobs, zones, fishing and level pages.
//
// The build writes /search.json, [[name, path, detail, weight], ...] for every
// data page; it's loaded the first time someone uses a search box. Search
// boxes (form.site-search, hidden until this runs, since they need it) show
// the best matches as you type; Enter opens the highlighted one, or the full
// list on /search?q=... Everything is written with textContent, never as HTML.
//
// It also adds the Menu button phones use: below 820px the CSS hides the header's links and language codes until the
// button opens them.
(function () {
  "use strict";
  var MAX_SUGGESTIONS = 8;
  var MAX_RESULTS = 100;
  var index = null, loading = null;
  // German, Spanish and French pages (<html lang="de"> under /de/, "es" under /es/, "fr" under /fr/) search their own
  // index and show their language; the rest English.
  var LANG = ["de", "es", "fr"].indexOf(document.documentElement.lang) >= 0 ? document.documentElement.lang : "en";
  var PREFIX = LANG === "en" ? "" : "/" + LANG;
  var INDEX = LANG === "en" ? "/search.json" : "/search-" + LANG + ".json";
  var WORDS = /[^\p{L}\p{N}']+/u;   // letters in any script, so "Händler" is one word
  var TEXT = {
    de: {
      none: "Noch nichts gefunden. Spieler haben es noch nicht erfasst, oder versuch es mit weniger Buchstaben.",
      failed: "Die Suche ist gerade nicht verfügbar.",
      empty: "Gib einen Gegenstand, Gegner oder ein Gebiet ins Suchfeld ein.",
      first: "Die ersten ", result: " Treffer", results: " Treffer",
      menu: "Menü",
      quote: function (q) { return " für „" + q + "“"; },
      nothing: function (q) {
        return "Noch nichts gefunden für „" + q + "“. Spieler haben es noch nicht erfasst, oder versuch es " +
          "mit weniger Buchstaben.";
      }
    },
    es: {
      none: "Aún no se encontró nada. Los jugadores no lo han registrado aún, o prueba con menos letras.",
      failed: "La búsqueda no está disponible ahora mismo.",
      empty: "Escribe un objeto, un enemigo o una zona en el cuadro de búsqueda.",
      first: "Los primeros ", result: " resultado", results: " resultados",
      menu: "Menú",
      quote: function (q) { return " para «" + q + "»"; },
      nothing: function (q) {
        return "Aún no se encontró nada para «" + q + "». Los jugadores no lo han registrado aún, o prueba " +
          "con menos letras.";
      }
    },
    fr: {
      none: "Rien trouvé pour l'instant. Les joueurs ne l'ont pas encore enregistré, ou essayez avec moins de lettres.",
      failed: "La recherche n'est pas disponible pour le moment.",
      empty: "Tapez un objet, un monstre ou une zone dans le champ de recherche.",
      first: "Les ", result: " résultat", results: " résultats",
      menu: "Menu",
      quote: function (q) { return " pour «\u00a0" + q + "\u00a0»"; },
      nothing: function (q) {
        return "Rien trouvé pour «\u00a0" + q + "\u00a0» pour l'instant. Les joueurs ne l'ont pas encore " +
          "enregistré, ou essayez avec moins de lettres.";
      }
    }
  }[LANG] || {
    none: "Nothing found yet. Players haven't recorded it, or try fewer letters.",
    failed: "Search isn't available right now.",
    empty: "Type an item, mob or zone in the search box.",
    first: "The first ", result: " result", results: " results",
    menu: "Menu",
    quote: function (q) { return " for \u201c" + q + "\u201d"; },
    nothing: function (q) {
      return "Nothing found for \u201c" + q + "\u201d yet. Players haven't recorded it, or try fewer letters.";
    }
  };

  function load() {
    if (!loading) {
      loading = fetch(INDEX).then(function (response) {
        if (!response.ok) {
          throw new Error("HTTP " + response.status);
        }
        return response.json();
      }).then(function (entries) {
        index = entries.map(function (entry) {
          var name = entry[0].toLowerCase();
          return { name: entry[0], path: entry[1], detail: entry[2], weight: entry[3], lower: name,
                   words: name.split(WORDS).filter(Boolean) };
        });
        return index;
      });
    }
    return loading;
  }

  // 0 exact, 1 starts with the query, 2 every word of the query starts a word of the name,
  // 3 the query is somewhere in the name; -1 no match.
  function score(entry, query, terms) {
    if (entry.lower === query) {
      return 0;
    }
    if (entry.lower.indexOf(query) === 0) {
      return 1;
    }
    var all = terms.every(function (term) {
      return entry.words.some(function (word) {
        return word.indexOf(term) === 0;
      });
    });
    if (all) {
      return 2;
    }
    return entry.lower.indexOf(query) >= 0 ? 3 : -1;
  }

  function search(text, limit) {
    var query = text.trim().toLowerCase().replace(/\s+/g, " ");
    if (!query || !index) {
      return [];
    }
    var terms = query.split(WORDS).filter(Boolean);
    var found = [];
    index.forEach(function (entry) {
      var s = score(entry, query, terms);
      if (s >= 0) {
        found.push({ entry: entry, score: s });
      }
    });
    found.sort(function (a, b) {
      return a.score - b.score || b.entry.weight - a.entry.weight || a.entry.name.length - b.entry.name.length;
    });
    return found.slice(0, limit).map(function (hit) {
      return hit.entry;
    });
  }

  function resultItem(entry) {
    var li = document.createElement("li");
    var link = document.createElement("a");
    link.href = entry.path;
    var name = document.createElement("span");
    name.className = "name";
    name.textContent = entry.name;
    var detail = document.createElement("span");
    detail.className = "detail";
    detail.textContent = entry.detail;
    link.appendChild(name);
    link.appendChild(detail);
    li.appendChild(link);
    return li;
  }

  function fullSearch(text) {
    window.location.href = PREFIX + "/search?q=" + encodeURIComponent(text.trim());
  }

  function setUp(form) {
    var input = form.querySelector("input");
    var list = form.querySelector(".results");
    var active = -1;
    form.hidden = false;

    function links() {
      return list.querySelectorAll("a");
    }

    function highlight(n) {
      var all = links();
      active = n;
      Array.prototype.forEach.call(all, function (link, i) {
        link.classList.toggle("active", i === n);
        link.setAttribute("aria-selected", i === n ? "true" : "false");
      });
    }

    function close() {
      list.hidden = true;
      active = -1;
    }

    function show() {
      var text = input.value;
      list.textContent = "";
      active = -1;
      if (!text.trim()) {
        close();
        return;
      }
      load().then(function () {
        if (input.value !== text) {
          return;   // the box changed while the index loaded
        }
        var hits = search(text, MAX_SUGGESTIONS);
        if (!hits.length) {
          var none = document.createElement("li");
          none.className = "none";
          none.textContent = TEXT.none;
          list.appendChild(none);
        }
        hits.forEach(function (entry) {
          list.appendChild(resultItem(entry));
        });
        list.hidden = false;
      }).catch(function () {
        list.textContent = "";
        var failed = document.createElement("li");
        failed.className = "none";
        failed.textContent = TEXT.failed;
        list.appendChild(failed);
        list.hidden = false;
      });
    }

    input.addEventListener("focus", function () {
      load().catch(function () { /* shown when they type */ });
    });
    input.addEventListener("input", show);
    input.addEventListener("keydown", function (event) {
      var count = links().length;
      if (event.key === "ArrowDown" && count) {
        event.preventDefault();
        highlight((active + 1) % count);
      } else if (event.key === "ArrowUp" && count) {
        event.preventDefault();
        highlight((active - 1 + count) % count);
      } else if (event.key === "Escape") {
        close();
      }
    });
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var all = links();
      if (active >= 0 && all[active]) {
        window.location.href = all[active].getAttribute("href");
      } else if (input.value.trim()) {
        fullSearch(input.value);
      }
    });
    document.addEventListener("click", function (event) {
      if (!form.contains(event.target)) {
        close();
      }
    });
  }

  // The /search page: every match for ?q=.
  function resultsPage(target) {
    var query = new URLSearchParams(window.location.search).get("q") || "";
    var status = document.getElementById("search-status");
    document.querySelectorAll("form.site-search input").forEach(function (input) {
      input.value = query;
    });
    if (!query.trim()) {
      status.textContent = TEXT.empty;
      return;
    }
    load().then(function () {
      var hits = search(query, MAX_RESULTS);
      status.textContent = hits.length
        ? (hits.length === MAX_RESULTS ? TEXT.first : "") + hits.length +
          (hits.length === 1 ? TEXT.result : TEXT.results) + TEXT.quote(query.trim()) + "."
        : TEXT.nothing(query.trim());
      hits.forEach(function (entry) {
        target.appendChild(resultItem(entry));
      });
    }).catch(function () {
      status.textContent = TEXT.failed;
    });
  }

  // Phones: a Menu button in the header that shows and hides its links (the CSS hides them below 820px).
  function menu(header) {
    var nav = header.querySelector("nav");
    if (!nav) {
      return;
    }
    nav.id = "site-nav";
    var button = document.createElement("button");
    button.type = "button";
    button.className = "menu-toggle";
    button.textContent = TEXT.menu;
    button.setAttribute("aria-controls", nav.id);
    button.setAttribute("aria-expanded", "false");
    function show(open) {
      header.classList.toggle("menu-open", open);
      button.setAttribute("aria-expanded", String(open));
    }
    button.addEventListener("click", function () {
      show(!header.classList.contains("menu-open"));
    });
    header.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && header.classList.contains("menu-open")) {
        show(false);
        button.focus();
      }
    });
    header.insertBefore(button, nav);
  }

  var header = document.querySelector("header.top");
  if (header) {
    menu(header);
  }
  document.querySelectorAll("form.site-search").forEach(setUp);
  var page = document.getElementById("search-page-results");
  if (page) {
    resultsPage(page);
  }
})();
