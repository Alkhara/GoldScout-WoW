// Site search: items, mobs, zones, fishing and level pages.
//
// The build writes /search.json, [[name, path, detail, weight], ...] for every
// data page; it's loaded the first time someone uses a search box. Search
// boxes (form.site-search, hidden until this runs, since they need it) show
// the best matches as you type; Enter opens the highlighted one, or the full
// list on /search?q=... Everything is written with textContent, never as HTML.
(function () {
  "use strict";
  var MAX_SUGGESTIONS = 8;
  var MAX_RESULTS = 100;
  var index = null, loading = null;

  function load() {
    if (!loading) {
      loading = fetch("/search.json").then(function (response) {
        if (!response.ok) {
          throw new Error("HTTP " + response.status);
        }
        return response.json();
      }).then(function (entries) {
        index = entries.map(function (entry) {
          var name = entry[0].toLowerCase();
          return { name: entry[0], path: entry[1], detail: entry[2], weight: entry[3], lower: name,
                   words: name.split(/[^a-z0-9']+/).filter(Boolean) };
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
    var terms = query.split(/[^a-z0-9']+/).filter(Boolean);
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
    window.location.href = "/search?q=" + encodeURIComponent(text.trim());
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
          none.textContent = "Nothing found yet. Players haven't recorded it, or try fewer letters.";
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
        failed.textContent = "Search isn't available right now.";
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
      status.textContent = "Type an item, mob or zone in the search box.";
      return;
    }
    load().then(function () {
      var hits = search(query, MAX_RESULTS);
      status.textContent = hits.length
        ? (hits.length === MAX_RESULTS ? "The first " : "") + hits.length + " result" + (hits.length === 1 ? "" : "s") + " for “" + query.trim() + "”."
        : "Nothing found for “" + query.trim() + "” yet. Players haven't recorded it, or try fewer letters.";
      hits.forEach(function (entry) {
        target.appendChild(resultItem(entry));
      });
    }).catch(function () {
      status.textContent = "Search isn't available right now.";
    });
  }

  document.querySelectorAll("form.site-search").forEach(setUp);
  var page = document.getElementById("search-page-results");
  if (page) {
    resultsPage(page);
  }
})();
