// CroissantMiner leaderboard: renders data/leaderboard.json (built by scripts/build_site.py).
"use strict";

const DESIGNS = ["Single-pass", "ReAct", "Parallel Specialists", "Triage + Critique", "Locator-Extractor"];
// same colours as the demo's leaderboard tab (hf_space/leaderboard_tab.py)
const COLORS = {
  "Single-pass": "#2563eb", "ReAct": "#dc2626", "Parallel Specialists": "#059669",
  "Triage + Critique": "#d97706", "Locator-Extractor": "#7c3aed", "Reference": "#8a94a0",
};
const SVGNS = "http://www.w3.org/2000/svg";

const state = {
  systems: [],
  designs: new Set(DESIGNS),
  openOnly: false,
  hideClaude: false,
  showReference: true,
  query: "",
  sortKey: "composite",
  sortAsc: false,
};

const $ = (sel) => document.querySelector(sel);
const fmt = (x) => (x == null ? "—" : x.toFixed(3));
const money = (x) => (x == null ? "self-hosted" : `$${x < 0.1 ? x.toFixed(3) : x.toFixed(2)}`);
const colorOf = (s) => (s.reference ? COLORS.Reference : COLORS[s.design] || "#64748b");
const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const nameOf = (s) => s.system + (s.claude ? "*" : "");

function visible(s) {
  if (s.reference && !state.showReference) return false;
  if (!state.designs.has(s.design)) return false;
  if (state.openOnly && !s.open_weights) return false;
  if (state.hideClaude && s.claude) return false;
  if (state.query) {
    const q = state.query.toLowerCase();
    if (!`${s.system} ${s.model} ${s.provider} ${s.design}`.toLowerCase().includes(q)) return false;
  }
  return true;
}

function sorted(list) {
  const k = state.sortKey;
  const val = (s) => {
    if (k === "rank") return s.rank == null ? 0 : s.rank; // reference first, then rank 1, 2, ...
    if (k === "system" || k === "design") return s[k].toLowerCase();
    return s[k] == null ? -Infinity : s[k];
  };
  const missing = (s) => k !== "rank" && k !== "system" && k !== "design" && s[k] == null;
  return [...list].sort((a, b) => {
    if (missing(a) !== missing(b)) return missing(a) ? 1 : -1; // e.g. self-hosted cost: always last
    const va = val(a), vb = val(b);
    const c = va < vb ? -1 : va > vb ? 1 : 0;
    return state.sortAsc ? c : -c;
  });
}

// ── highlight cards ────────────────────────────────────────────────────────
function renderCards() {
  const ranked = state.systems.filter((s) => !s.reference).sort((a, b) => a.rank - b.rank);
  const open = ranked.find((s) => s.open_weights);
  const picks = [["#1", ranked[0], "first"], ["#2", ranked[1]], ["#3", ranked[2]], ["Best open weights", open]];
  $("#highlights").innerHTML = picks.filter(([, s]) => s).map(([label, s, cls]) => `
    <article class="card ${cls || ""}">
      <div class="label">${label}</div>
      <div class="name">${esc(nameOf(s))}</div>
      <div class="score">${fmt(s.composite)} <small>[${fmt(s.ci[0])}, ${fmt(s.ci[1])}]</small></div>
      <div class="meta">${esc(s.design)} · ${esc(s.provider)} · ${money(s.cost)} per paper</div>
    </article>`).join("");
}

// ── filters ────────────────────────────────────────────────────────────────
function renderChips() {
  const box = $("#design-chips");
  const all = document.createElement("button");
  all.className = "chip"; all.type = "button"; all.textContent = "All designs";
  all.addEventListener("click", () => { state.designs = new Set(DESIGNS); update(); });
  box.append(all);
  for (const d of DESIGNS) {
    const b = document.createElement("button");
    b.className = "chip"; b.type = "button"; b.dataset.design = d;
    b.innerHTML = `<span class="dot" style="background:${COLORS[d]}"></span>${esc(d)}`;
    // a click shows only that design; shift-click adds or removes it
    b.addEventListener("click", (e) => {
      if (e.shiftKey) {
        state.designs.has(d) ? state.designs.delete(d) : state.designs.add(d);
      } else {
        state.designs = state.designs.size === 1 && state.designs.has(d) ? new Set(DESIGNS) : new Set([d]);
      }
      update();
    });
    box.append(b);
  }
}

function syncChips() {
  const allOn = state.designs.size === DESIGNS.length;
  for (const b of document.querySelectorAll("#design-chips .chip")) {
    const d = b.dataset.design;
    b.setAttribute("aria-pressed", d ? String(!allOn && state.designs.has(d)) : String(allOn));
  }
}

// ── table ──────────────────────────────────────────────────────────────────
const CI_MIN = 0.3, CI_MAX = 0.95;
const pct = (x) => `${(100 * (x - CI_MIN)) / (CI_MAX - CI_MIN)}%`;

function renderTable() {
  const rows = sorted(state.systems.filter(visible));
  const body = $("#board tbody");
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="8" class="empty">No system matches these filters.</td></tr>`;
  } else {
    body.innerHTML = rows.map((s) => {
      const c = colorOf(s);
      const badges = (s.open_weights ? `<span class="badge open">open</span>` : "") +
        (s.reference ? `<span class="badge ref">reference</span>` : "");
      return `<tr class="${s.reference ? "reference" : ""}">
        <td class="num">${s.rank ?? "—"}</td>
        <td><span class="sys">${esc(nameOf(s))}</span>${badges}<span class="sys-sub">${esc(s.model)} · ${esc(s.provider)}</span></td>
        <td><span class="design"><span class="dot" style="background:${c}"></span>${esc(s.design)}</span></td>
        <td class="num">${fmt(s.core)}</td>
        <td class="num">${fmt(s.rai)}</td>
        <td class="num"><div class="comp"><b>${fmt(s.composite)}</b>
          <span class="ci" title="95% CI [${fmt(s.ci[0])}, ${fmt(s.ci[1])}]"><span class="track"></span>
            <span class="range" style="left:${pct(s.ci[0])};width:calc(${pct(s.ci[1])} - ${pct(s.ci[0])});background:${c}"></span>
            <span class="pt" style="left:${pct(s.composite)};background:${c}"></span></span></div></td>
        <td class="num">${fmt(s.paper_composite)}</td>
        <td class="num">${money(s.cost)}</td>
      </tr>`;
    }).join("");
  }
  for (const th of document.querySelectorAll("#board th")) {
    th.classList.toggle("sorted", th.dataset.key === state.sortKey);
    th.classList.toggle("asc", th.dataset.key === state.sortKey && state.sortAsc);
  }
  const ranked = state.systems.filter((s) => !s.reference).length;
  $("#table-foot").textContent = `Showing ${rows.length} of ${state.systems.length} rows (${ranked} ranked systems). ` +
    "* = built on a Claude model. Bars show the 95% confidence interval of the composite. Click a column to sort.";
}

// ── plots ──────────────────────────────────────────────────────────────────
function el(tag, attrs = {}, parent) {
  const n = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (parent) parent.append(n);
  return n;
}

function scatter(svg, points, { x, y, xLog = false, xTicks, yTicks, xLabel, yLabel, xFmt, diag = false }) {
  const W = 520, H = 340, m = { l: 48, r: 14, t: 10, b: 40 };
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.innerHTML = "";
  const tx = xLog ? (v) => Math.log10(v) : (v) => v;
  const [x0, x1] = [tx(x[0]), tx(x[1])];
  const sx = (v) => m.l + ((tx(v) - x0) / (x1 - x0)) * (W - m.l - m.r);
  const sy = (v) => H - m.b - ((v - y[0]) / (y[1] - y[0])) * (H - m.t - m.b);
  const g = el("g", { class: "grid" }, svg), ax = el("g", { class: "axis" }, svg);
  for (const t of yTicks) {
    el("line", { x1: m.l, x2: W - m.r, y1: sy(t), y2: sy(t) }, g);
    el("text", { x: m.l - 6, y: sy(t) + 4, "text-anchor": "end" }, ax).textContent = t.toFixed(1);
  }
  for (const t of xTicks) {
    el("line", { x1: sx(t), x2: sx(t), y1: m.t, y2: H - m.b }, g);
    el("text", { x: sx(t), y: H - m.b + 16, "text-anchor": "middle" }, ax).textContent = xFmt(t);
  }
  if (diag) el("line", { class: "diag", x1: sx(Math.max(x[0], y[0])), y1: sy(Math.max(x[0], y[0])),
    x2: sx(Math.min(x[1], y[1])), y2: sy(Math.min(x[1], y[1])) }, svg);
  el("text", { class: "axis-label", x: (W + m.l) / 2, y: H - 6, "text-anchor": "middle" }, svg).textContent = xLabel;
  el("text", { class: "axis-label", x: 12, y: (H - m.b) / 2, transform: `rotate(-90 12 ${(H - m.b) / 2})`,
    "text-anchor": "middle" }, svg).textContent = yLabel;
  const tip = $("#tooltip");
  for (const p of points) {
    const c = el("circle", { cx: sx(p.x), cy: sy(p.y), r: p.s.rank === 1 ? 7 : 5.5, fill: colorOf(p.s) }, svg);
    if (!visible(p.s)) c.classList.add("dim");
    c.addEventListener("mousemove", (e) => {
      tip.hidden = false;
      tip.innerHTML = `<b>${esc(nameOf(p.s))}</b><br>${esc(p.s.design)} · composite ${fmt(p.s.composite)}` +
        `<br>core ${fmt(p.s.core)} · RAI ${fmt(p.s.rai)} · ${money(p.s.cost)}`;
      tip.style.left = `${Math.min(e.clientX + 12, window.innerWidth - 290)}px`;
      tip.style.top = `${e.clientY + 12}px`;
    });
    c.addEventListener("mouseleave", () => { tip.hidden = true; });
  }
}

function renderPlots() {
  const all = state.systems;
  const withCost = all.filter((s) => s.cost != null);
  scatter($("#plot-cost"), withCost.map((s) => ({ s, x: s.cost, y: s.composite })), {
    x: [0.005, 1.2], xLog: true, xTicks: [0.01, 0.03, 0.1, 0.3, 1], y: [0.3, 0.9], yTicks: [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9],
    xLabel: "US$ per paper", yLabel: "Composite", xFmt: (t) => `$${t}`,
  });
  scatter($("#plot-corerai"), all.map((s) => ({ s, x: s.core, y: s.rai })), {
    x: [0.45, 0.95], xTicks: [0.5, 0.6, 0.7, 0.8, 0.9], y: [0.25, 0.9], yTicks: [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9],
    xLabel: "Core (10 fields)", yLabel: "Responsible AI (20 fields)", xFmt: (t) => t.toFixed(1), diag: true,
  });
  $("#legend").innerHTML = [...DESIGNS, "Reference"]
    .map((d) => `<span><i style="background:${COLORS[d]}"></i>${esc(d)}</span>`).join("") +
    `<span class="muted">Faded points are hidden by the filters.</span>`;
}

// ── wiring ─────────────────────────────────────────────────────────────────
function update() {
  syncChips();
  renderTable();
  renderPlots();
}

function wire() {
  $("#f-open").addEventListener("change", (e) => { state.openOnly = e.target.checked; update(); });
  $("#f-noclaude").addEventListener("change", (e) => { state.hideClaude = e.target.checked; update(); });
  $("#f-reference").addEventListener("change", (e) => { state.showReference = e.target.checked; update(); });
  $("#f-search").addEventListener("input", (e) => { state.query = e.target.value.trim(); update(); });
  for (const th of document.querySelectorAll("#board th")) {
    th.addEventListener("click", () => {
      const k = th.dataset.key;
      if (state.sortKey === k) state.sortAsc = !state.sortAsc;
      else { state.sortKey = k; state.sortAsc = k === "system" || k === "design" || k === "cost" || k === "rank"; }
      update();
    });
  }
  $("#copy-bib").addEventListener("click", async (e) => {
    try {
      await navigator.clipboard.writeText($("#bib").textContent);
      e.target.textContent = "Copied";
    } catch {
      e.target.textContent = "Select and copy";
    }
    setTimeout(() => { e.target.textContent = "Copy"; }, 1500);
  });
}

async function main() {
  wire();
  renderChips();
  try {
    const res = await fetch("data/leaderboard.json", { cache: "no-cache" });
    const data = await res.json();
    state.systems = data.systems;
    const judged = data.systems[0];
    $("#judge-note").textContent = `Judge: ${judged.judge}, all rows judged on ${judged.judged_on}.`;
    $("#judge-detail").textContent = `Every row, including the paper's systems, was re-judged on ${judged.judged_on} ` +
      `with the paper's judge prompt (${judged.judge}); the "Paper" column is the composite reported in the paper, ` +
      "judged earlier on a different provider.";
    $("#built").textContent = `Data updated ${data.built}`;
    renderCards();
    update();
  } catch (err) {
    $("#board tbody").innerHTML = `<tr><td colspan="8" class="empty">Could not load the leaderboard data.</td></tr>`;
    console.error(err);
  }
}

main();
