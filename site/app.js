// CroissantMiner leaderboard page: theme switch, copy buttons, tabs, sorting, per-system field panels, tooltips.
(function () {
  "use strict";
  var root = document.documentElement;
  var DATA = JSON.parse(document.getElementById("field-data").textContent);

  // Theme: follows the system until the visitor picks one; the choice is remembered when the browser allows it.
  var themeButton = document.getElementById("theme");
  function isDark() {
    return root.dataset.theme ? root.dataset.theme === "dark"
      : window.matchMedia("(prefers-color-scheme: dark)").matches;
  }
  function labelTheme() {
    themeButton.setAttribute("aria-label", isDark() ? "Switch to light mode" : "Switch to dark mode");
    themeButton.title = themeButton.getAttribute("aria-label");
  }
  themeButton.addEventListener("click", function () {
    root.dataset.theme = isDark() ? "light" : "dark";
    try { localStorage.setItem("theme", root.dataset.theme); } catch (e) { /* storage blocked: choice lasts this visit */ }
    labelTheme();
  });
  labelTheme();

  // Copy buttons
  function copied(button) {
    var text = button.textContent;
    button.textContent = "Copied";
    setTimeout(function () { button.textContent = text; }, 1500);
  }
  function copyFallback(text, button) {
    var area = document.createElement("textarea");
    area.value = text;
    document.body.appendChild(area);
    area.select();
    try { document.execCommand("copy"); copied(button); } catch (e) { /* nothing to do */ }
    area.remove();
  }
  document.querySelectorAll("[data-copy]").forEach(function (button) {
    button.addEventListener("click", function () {
      var text = document.getElementById(button.dataset.copy).textContent;
      if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(function () { copied(button); },
                                                  function () { copyFallback(text, button); });
      } else {
        copyFallback(text, button);
      }
    });
  });

  // Per-system panel with the score on each field
  function fieldRow(id, value, kind, average) {
    var tip = DATA.labels[id] + ": " + DATA.descriptions[id] + " This system " + value.toFixed(3) +
      "; average of the ranked systems " + average.toFixed(3) + ".";
    return '<div class="frow" tabindex="0" data-tip="' + tip + '"><span class="fname">' + DATA.labels[id] + "</span>" +
      '<span class="track"><span class="bar ' + kind + '" style="width:' + (100 * value).toFixed(1) + '%"></span>' +
      '<span class="tick" style="left:' + (100 * average).toFixed(1) + '%"></span></span>' +
      '<span class="fval">' + value.toFixed(2) + "</span></div>";
  }
  function panel(row) {
    var scores = DATA.systems[row.dataset.key];
    var facts = '<div class="dsum"><span>Composite <b>' + parseFloat(row.dataset.composite).toFixed(3) +
      "</b>, 95% interval " + row.dataset.ci + "</span>" +
      (row.dataset.paper ? "<span>In the paper " + parseFloat(row.dataset.paper).toFixed(3) + "</span>" : "") +
      (row.dataset.date ? "<span>Outputs made in " + row.dataset.date + "</span>" : "") +
      '<button class="panel-link" type="button" data-link>Copy link to this system</button></div>';
    if (!scores) return facts + '<p class="muted">No field scores for this entry.</p>';
    var group = function (title, ids, kind) {
      return '<div class="fgroup"><h4>' + title + "</h4>" + ids.map(function (id) {
        return fieldRow(id, scores[id], kind, DATA.average[id]);
      }).join("") + "</div>";
    };
    return facts + '<div class="legend"><span><i style="background:var(--core)"></i>Core field (scored by rules)</span>' +
      '<span><i style="background:var(--rai)"></i>Responsible AI field (scored by the judge)</span>' +
      '<span><i class="tick-key"></i>Average of the ranked systems</span></div>' +
      '<div class="fgroups">' + group("Core fields", DATA.core, "core") +
      group("Responsible AI fields", DATA.rai, "rai") + "</div>";
  }
  var body = document.querySelector("#board tbody");
  function closeAll() {
    body.querySelectorAll("tr.detail").forEach(function (row) { row.remove(); });
    body.querySelectorAll(".name").forEach(function (b) { b.setAttribute("aria-expanded", "false"); });
  }
  function toggle(row) {
    var button = row.querySelector(".name");
    var next = row.nextElementSibling;
    if (next && next.classList.contains("detail")) {
      next.remove();
      button.setAttribute("aria-expanded", "false");
      saveState();
      return;
    }
    var detail = document.createElement("tr");
    detail.className = "detail";
    detail.innerHTML = '<td colspan="' + row.cells.length + '"><div class="dpanel">' + panel(row) + "</div></td>";
    row.after(detail);
    button.setAttribute("aria-expanded", "true");
    saveState();
  }
  body.addEventListener("click", function (event) {
    var linkButton = event.target.closest("[data-link]");
    if (linkButton) {
      var url = location.href.split("#")[0] + "#system=" + linkButton.closest("tr").previousElementSibling.dataset.slug;
      if (navigator.clipboard) navigator.clipboard.writeText(url).then(function () { copied(linkButton); });
      else copyFallback(url, linkButton);
      return;
    }
    var row = event.target.closest("tr.sys-row");
    if (row && !event.target.closest("a")) toggle(row);
  });

  // Tabs
  var current = "all";
  function applyTab() {
    closeAll();
    body.querySelectorAll("tr.sys-row").forEach(function (row) {
      var show = current === "all" || row.classList.contains("ref") ||
        row.dataset.group.split(" ").indexOf(current) >= 0;
      row.hidden = !show;
    });
  }
  document.querySelectorAll(".tabs button").forEach(function (button) {
    button.addEventListener("click", function () {
      document.querySelectorAll(".tabs button").forEach(function (b) {
        b.classList.toggle("on", b === button);
        b.setAttribute("aria-selected", b === button ? "true" : "false");
      });
      current = button.dataset.tab;
      applyTab();
      saveState();
    });
  });

  // Sorting: the reference row stays on top
  function sortBy(th, direction) {
      closeAll();
      var key = th.dataset.sort;
      var ascending = direction ? direction === "asc"
        : th.dataset.dir ? th.dataset.dir !== "asc" : key === "rank" || key === "cost";
      document.querySelectorAll("th[data-sort]").forEach(function (other) {
        delete other.dataset.dir;
        other.removeAttribute("aria-sort");
      });
      th.dataset.dir = ascending ? "asc" : "desc";
      th.setAttribute("aria-sort", ascending ? "ascending" : "descending");
      var rows = Array.prototype.slice.call(body.querySelectorAll("tr.sys-row:not(.ref)"));
      rows.sort(function (a, b) {
        var x = parseFloat(a.dataset[key]), y = parseFloat(b.dataset[key]);
        if (isNaN(x) || isNaN(y)) return isNaN(x) - isNaN(y);      // no value (self-hosted cost): always last
        return ascending ? x - y : y - x;
      });
      rows.forEach(function (row) { body.appendChild(row); });
  }
  document.querySelectorAll("th[data-sort]").forEach(function (th) {
    th.addEventListener("click", function () { sortBy(th); saveState(); });
  });

  // The page address keeps the tab, the sorting and the open system, so a link shows the same view.
  function saveState() {
    var parts = [];
    if (current !== "all") parts.push("tab=" + current);
    var sorted = document.querySelector("th[data-dir]");
    if (sorted) parts.push("sort=" + sorted.dataset.sort + "-" + sorted.dataset.dir);
    body.querySelectorAll('.name[aria-expanded="true"]').forEach(function (b) {
      parts.push("system=" + b.closest("tr").dataset.slug);
    });
    var hash = parts.length ? "#" + parts.join("&") : "";
    if (location.hash !== hash) history.replaceState(null, "", location.pathname + location.search + hash);
  }
  function loadState() {
    var params = {};
    location.hash.replace(/^#/, "").split("&").forEach(function (part) {
      var kv = part.split("=");
      if (kv[0] && kv[1]) (params[kv[0]] = params[kv[0]] || []).push(decodeURIComponent(kv[1]));
    });
    if (params.tab) {
      var tab = document.querySelector('.tabs button[data-tab="' + params.tab[0] + '"]');
      if (tab) tab.click();
    }
    if (params.sort) {
      var m = params.sort[0].match(/^(\w+)-(asc|desc)$/);
      var th = m && document.querySelector('th[data-sort="' + m[1] + '"]');
      if (th) sortBy(th, m[2]);
    }
    var first = null;
    (params.system || []).forEach(function (s) {
      var row = body.querySelector('tr.sys-row[data-slug="' + s.replace(/[^a-z0-9-]/g, "") + '"]');
      if (row && !row.hidden) { toggle(row); first = first || row; }
    });
    if (first) first.scrollIntoView({ block: "start" });
  }

  // Tooltips for field bars (mouse and keyboard)
  var tip = document.createElement("div");
  tip.className = "tip";
  tip.setAttribute("role", "tooltip");
  document.body.appendChild(tip);
  function showTip(target, x, y) {
    tip.textContent = target.dataset.tip;
    tip.style.display = "block";
    var w = tip.offsetWidth, h = tip.offsetHeight;
    tip.style.left = Math.max(8, Math.min(window.innerWidth - w - 8, x + 12)) + "px";
    tip.style.top = Math.max(8, y - h - 12) + "px";
  }
  document.addEventListener("mousemove", function (event) {
    var target = event.target.closest && event.target.closest("[data-tip]");
    if (target) showTip(target, event.clientX, event.clientY); else tip.style.display = "none";
  });
  document.addEventListener("focusin", function (event) {
    var target = event.target.closest && event.target.closest("[data-tip]");
    if (!target) { tip.style.display = "none"; return; }
    var box = target.getBoundingClientRect();
    showTip(target, box.left + box.width / 3, box.top);
  });
  document.addEventListener("scroll", function () { tip.style.display = "none"; }, true);

  loadState();
})();
