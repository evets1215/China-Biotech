/* Shared data layer for the design prototypes: parsing, filters, sorting, formatting.
   Each design reads window.CBT and renders its own layout. */
(function () {
  "use strict";
  var DATA = JSON.parse(document.getElementById("data").textContent);
  var deals = DATA.deals || [], pipeline = DATA.pipeline || [], policy = DATA.policy || [];
  var TODAY = DATA.generated;
  // 2025 onward is imported in full; earlier years hold landmark deals only (see README).
  var FULL_FROM = 2025;

  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    if (attrs) for (var k in attrs) {
      if (attrs[k] == null) continue;
      if (k === "text") n.textContent = attrs[k];
      else if (k === "cls") n.className = attrs[k];
      else n.setAttribute(k, attrs[k]);
    }
    (kids || []).forEach(function (c) { if (c != null) n.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return n;
  }
  function svg(tag, attrs, text) {
    var n = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (var k in attrs) if (attrs[k] != null) n.setAttribute(k, attrs[k]);
    if (text != null) n.textContent = text;
    return n;
  }
  function money(v) {
    if (v == null || v === "") return "n/d";
    v = +v;
    if (v >= 1000) return "$" + (v / 1000).toFixed(v >= 10000 ? 1 : 2).replace(/\.?0+$/, "") + "B";
    return "$" + (v < 10 ? v.toFixed(1).replace(/\.0$/, "") : Math.round(v)) + "M";
  }
  function bn(v) { return "$" + (v / 1000).toFixed(1) + "B"; }
  function year(d) { return parseInt(String(d.announced).slice(0, 4), 10); }
  function uniq(arr) { return Array.from(new Set(arr.filter(Boolean))).sort(); }
  function isUrl(s) { return /^https?:\/\//i.test(String(s)); }
  function host(u) { return String(u).replace(/^https?:\/\/(www\.)?/, "").split("/")[0]; }
  function sum(rows, f) { return rows.reduce(function (a, d) { return a + (+d[f] || 0); }, 0); }
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  function fmtDate(s) {
    s = String(s || ""); var p = s.split("-");
    if (p.length === 1) return s;
    var m = MONTHS[+p[1] - 1] || "";
    return p.length === 2 ? m + " " + p[0] : (+p[2]) + " " + m + " " + p[0];
  }
  // Fractional year for plotting; a month-only date sits mid-month.
  function when(s) {
    var p = String(s || "").split("-");
    var y = +p[0], m = p[1] ? +p[1] - 1 : 6, d = p[2] ? +p[2] : 15;
    return y + (m + (d - 1) / 31) / 12;
  }
  var STATUS_LABEL = { active: "Active", pending: "Pending close", completed: "Completed", terminated: "Terminated" };
  function assetName(d) { return d.asset || d.target || "Undisclosed"; }

  // ---------- filters ----------
  // One filter state for every view. Each facet holds a list of chosen values (empty = all);
  // "up" is a minimum upfront in $M. Designs either render their own controls and call set()/toggle(),
  // or keep plain <select>s with the original ids, which are read as single values.
  var listeners = [];
  var years = deals.map(year).filter(Boolean);
  var minY = Math.min.apply(null, years), maxY = Math.max.apply(null, years);

  var PHASES = ["Preclinical", "Phase 1", "Phase 2", "Phase 3", "Filed or approved", "Not disclosed"];
  function phaseGroup(d) {
    var p = String(d.phase_at_deal || "");
    if (!p) return "Not disclosed";
    if (/preclin/i.test(p)) return "Preclinical";
    if (/phase\s*1/i.test(p)) return "Phase 1";
    if (/phase\s*2/i.test(p)) return "Phase 2";
    if (/phase\s*3/i.test(p)) return "Phase 3";
    if (/\bNDA\b|\bBLA\b|market|approv|filed/i.test(p)) return "Filed or approved";
    return "Not disclosed";
  }
  // Same order as DEAL_FORMATS in tracker/store.py.
  var FORMATS = ["ADC", "Bispecific / multispecific", "T-cell engager", "Monoclonal antibody", "Other biologic", "Small molecule",
    "Peptide", "Nucleic acid", "Cell or gene therapy", "Radiopharmaceutical", "Undisclosed", "Not classified"];
  function ordered(order) { return function (a, b) { var i = order.indexOf(a), j = order.indexOf(b); return (i < 0 ? 99 : i) - (j < 0 ? 99 : j) || a.localeCompare(b); }; }
  var FACETS = {
    status: { label: "Status", get: function (d) { return d.status; }, name: function (v) { return STATUS_LABEL[v] || v; }, sort: ordered(["active", "pending", "completed", "terminated"]) },
    area: { label: "Therapeutic area", get: function (d) { return d.therapeutic_area || "Undisclosed"; } },
    format: { label: "Format", get: function (d) { return d.format || "Not classified"; }, sort: ordered(FORMATS) },
    phase: { label: "Phase at deal", get: phaseGroup, sort: ordered(PHASES) },
    hq: { label: "Licensee HQ", get: function (d) { return d.licensee_hq || "Undisclosed"; } },
    type: { label: "Deal type", get: function (d) { return d.deal_type; } },
    licensee: { label: "Licensee", get: function (d) { return d.licensee; } }
  };
  var KEYS = Object.keys(FACETS);
  var UP_STEPS = [25, 50, 100, 250, 500, 1000];
  function blank() { var s = { q: "", up: 0, from: minY, to: maxY }; KEYS.forEach(function (k) { s[k] = []; }); return s; }
  var S = blank();

  // Search reads named fields only, so "phase" or a source domain cannot match every deal.
  var SEARCH_FIELDS = ["licensor", "licensee", "asset", "target", "indication", "modality", "notes"];
  var hay = new Map();
  deals.forEach(function (d) { hay.set(d, SEARCH_FIELDS.map(function (f) { return d[f] || ""; }).join("\n").toLowerCase()); });

  function pass(d, skip) {
    var y = year(d);
    if (y < S.from || y > S.to) return false;
    for (var i = 0; i < KEYS.length; i++) {
      var k = KEYS[i];
      if (k !== skip && S[k].length && S[k].indexOf(FACETS[k].get(d)) < 0) return false;
    }
    if (skip !== "up" && S.up && !(d.upfront_usd_m >= S.up)) return false;
    var q = S.q.trim().toLowerCase();
    if (q && hay.get(d).indexOf(q) < 0) return false;
    return true;
  }
  function filtered() { return deals.filter(function (d) { return pass(d); }); }
  // Rows that pass every filter except one facet: what a chart of that facet should show.
  function except(key) { return deals.filter(function (d) { return pass(d, key); }); }
  // Options for one facet, each counted against every other active filter.
  function options(key) {
    var f = FACETS[key], seen = {}, n = {};
    deals.forEach(function (d) { seen[f.get(d)] = 1; });
    deals.forEach(function (d) { if (pass(d, key)) { var v = f.get(d); n[v] = (n[v] || 0) + 1; } });
    return Object.keys(seen).filter(Boolean).sort(f.sort || function (a, b) { return a.localeCompare(b); })
      .map(function (v) { return { value: v, label: f.name ? f.name(v) : v, n: n[v] || 0, on: S[key].indexOf(v) >= 0 }; });
  }
  function upOptions() {
    var rows = deals.filter(function (d) { return pass(d, "up"); });
    return [{ value: 0, label: "Any", n: rows.length }].concat(UP_STEPS.map(function (t) {
      return { value: t, label: money(t) + "+", n: rows.filter(function (d) { return d.upfront_usd_m >= t; }).length };
    }));
  }
  function undisclosedUp() { return deals.filter(function (d) { return pass(d, "up") && d.upfront_usd_m == null; }).length; }

  function set(key, val) {
    if (key === "q") S.q = String(val || "");
    else if (key === "up") S.up = +val || 0;
    else if (key === "from" || key === "to") S[key] = Math.min(maxY, Math.max(minY, +val || (key === "from" ? minY : maxY)));
    else if (FACETS[key]) S[key] = (val == null ? [] : [].concat(val)).filter(Boolean);
  }
  function toggle(key, v) { var a = S[key].slice(), i = a.indexOf(v); if (i < 0) a.push(v); else a.splice(i, 1); S[key] = a; }
  function state() { var o = {}; Object.keys(S).forEach(function (k) { o[k] = Array.isArray(S[k]) ? S[k].slice() : S[k]; }); return o; }
  function setFilters(o) {
    S = blank(); o = o || {};
    ["q", "up", "from", "to"].forEach(function (k) { if (o[k] != null && o[k] !== "") set(k, o[k]); });
    KEYS.forEach(function (k) { if (o[k]) set(k, Array.isArray(o[k]) ? o[k] : String(o[k]).split("|")); });
    syncControls();
  }
  function isFiltered() {
    return !!(S.q.trim() || S.up || S.from !== minY || S.to !== maxY || KEYS.some(function (k) { return S[k].length; }));
  }
  function range() { return { from: S.from, to: S.to }; }

  // Plain controls a design may keep: the search box, year and upfront selects, and single-value selects.
  var F = {};
  var LEGACY = { "f-status": "status", "f-area": "area", "f-hq": "hq", "f-type": "type", "f-format": "format", "f-phase": "phase" };
  function fill(select, values, labeler) {
    values.forEach(function (v) { select.appendChild(el("option", { value: v, text: labeler ? labeler(v) : v })); });
  }
  function syncControls() {
    if (F.q && F.q.value !== S.q) F.q.value = S.q;
    if (F["f-from"]) F["f-from"].value = S.from;
    if (F["f-to"]) F["f-to"].value = S.to;
    if (F["f-up"]) F["f-up"].value = S.up;
    Object.keys(LEGACY).forEach(function (id) { if (F[id]) F[id].value = S[LEGACY[id]][0] || ""; });
  }
  function bindFilters() {
    ["q", "f-from", "f-to", "f-up"].concat(Object.keys(LEGACY)).forEach(function (id) {
      var n = document.getElementById(id); if (n && (id === "q" || n.tagName === "SELECT")) F[id] = n;
    });
    if (!F.q) return;
    Object.keys(LEGACY).forEach(function (id) {
      if (F[id]) fill(F[id], options(LEGACY[id]).map(function (o) { return o.value; }), FACETS[LEGACY[id]].name);
    });
    if (F["f-from"]) for (var y = minY; y <= maxY; y++) { F["f-from"].appendChild(el("option", { value: y, text: y })); F["f-to"].appendChild(el("option", { value: y, text: y })); }
    if (F["f-up"]) fill(F["f-up"], [0].concat(UP_STEPS), function (v) { return v ? money(v) + "+" : "Any"; });
    readUrl();
    F.q.addEventListener("input", function () { set("q", F.q.value); changed(); });
    ["f-from", "f-to", "f-up"].forEach(function (id) {
      if (F[id]) F[id].addEventListener("change", function () { set(id.slice(2), F[id].value); changed(); });
    });
    Object.keys(LEGACY).forEach(function (id) {
      if (F[id]) F[id].addEventListener("change", function () { set(LEGACY[id], F[id].value); changed(); });
    });
    var reset = document.getElementById("reset");
    if (reset) reset.addEventListener("click", function () { setFilters({}); changed(); });
    window.addEventListener("hashchange", function () { readUrl(); emit(); });
  }
  // Filter state lives in the URL hash so a view can be shared. Lists join with "|" (company names hold commas).
  function readUrl() {
    var o = {};
    location.hash.replace(/^#/, "").split("&").forEach(function (kv) {
      var p = kv.split("="); if (!p[0]) return;
      try { o[p[0]] = decodeURIComponent(p[1] || ""); } catch (e) { o[p[0]] = p[1] || ""; }
    });
    setFilters(o);
  }
  function writeUrl() {
    var o = { q: S.q.trim(), up: S.up || "", from: S.from === minY ? "" : S.from, to: S.to === maxY ? "" : S.to };
    KEYS.forEach(function (k) { o[k] = S[k].join("|"); });
    var s = Object.keys(o).filter(function (k) { return o[k]; }).map(function (k) { return k + "=" + encodeURIComponent(o[k]); }).join("&");
    try { history.replaceState(null, "", s ? "#" + s : location.pathname + location.search); } catch (e) {}
  }
  function emit() { var rows = filtered(); listeners.forEach(function (fn) { fn(rows); }); }
  function changed() { syncControls(); writeUrl(); emit(); }
  function onChange(fn) { listeners.push(fn); }

  // ---------- export ----------
  var CSV_COLS = [
    ["id", function (d) { return d.id; }], ["announced", function (d) { return d.announced; }],
    ["licensor", function (d) { return d.licensor; }], ["licensee", function (d) { return d.licensee; }],
    ["licensee_hq", function (d) { return d.licensee_hq; }], ["asset", function (d) { return d.asset; }],
    ["target", function (d) { return d.target; }], ["format", function (d) { return d.format; }],
    ["modality", function (d) { return d.modality; }], ["phase_at_deal", function (d) { return d.phase_at_deal; }],
    ["therapeutic_area", function (d) { return d.therapeutic_area; }], ["deal_type", function (d) { return d.deal_type; }],
    ["territory", function (d) { return d.territory; }], ["upfront_usd_m", function (d) { return d.upfront_usd_m; }],
    ["total_value_usd_m", function (d) { return d.total_value_usd_m; }], ["status", function (d) { return d.status; }],
    ["source", function (d) { return (d.sources || []).filter(isUrl)[0]; }]
  ];
  function cell(v) {
    if (v == null) return "";
    if (typeof v === "number") return String(v);
    v = String(v);
    if (/^[=+\-@\t\r]/.test(v)) v = "'" + v; // keep spreadsheets from reading a value as a formula
    return /[",\n\r]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
  }
  function csv(rows) {
    return "﻿" + [CSV_COLS.map(function (c) { return c[0]; }).join(",")]
      .concat(rows.map(function (d) { return CSV_COLS.map(function (c) { return cell(c[1](d)); }).join(","); })).join("\r\n");
  }

  // ---------- aggregates ----------
  function byYear(rows) {
    var r = range(), out = [];
    for (var y = r.from; y <= r.to; y++) out.push({ year: y, n: 0, up: 0, full: y >= FULL_FROM });
    rows.forEach(function (d) { var b = out[year(d) - r.from]; if (b) { b.n++; b.up += +d.upfront_usd_m || 0; } });
    return out;
  }
  function topBy(rows, field, n) {
    var c = {};
    rows.forEach(function (d) { var k = d[field] || "Undisclosed"; c[k] = c[k] || { n: 0, up: 0, total: 0 }; c[k].n++; c[k].up += +d.upfront_usd_m || 0; c[k].total += +d.total_value_usd_m || 0; });
    return Object.keys(c).map(function (k) { return { label: k, n: c[k].n, up: c[k].up, total: c[k].total }; })
      .sort(function (a, b) { return b.n - a.n || b.up - a.up || a.label.localeCompare(b.label); }).slice(0, n || 999);
  }
  function kpis(rows) {
    return {
      count: rows.length,
      active: rows.filter(function (d) { return d.status === "active" || d.status === "pending"; }).length,
      terminated: rows.filter(function (d) { return d.status === "terminated"; }).length,
      completed: rows.filter(function (d) { return d.status === "completed"; }).length,
      upfront: sum(rows, "upfront_usd_m"),
      upfrontN: rows.filter(function (d) { return d.upfront_usd_m != null; }).length,
      total: sum(rows, "total_value_usd_m"),
      options: deals.filter(function (d) { return d.deal_type === "Option" && d.status === "active"; }),
      potential: pipeline.filter(function (p) { return p.stage === "potential"; }),
      future: pipeline.filter(function (p) { return p.stage === "future"; })
    };
  }

  // ---------- sorting ----------
  function sorter(key, dir) {
    return function (a, b) {
      var x = a[key], y = b[key];
      if (key === "asset") { x = a.asset || a.target; y = b.asset || b.target; }
      if (x == null || x === "") return 1; if (y == null || y === "") return -1;
      return (typeof x === "number" ? x - y : String(x).localeCompare(String(y))) * dir;
    };
  }

  // ---------- deal detail ----------
  function detailFields(d) {
    return [
      ["Deal type", d.deal_type], ["Territory", d.territory], ["Target", d.target], ["Format", d.format], ["Modality", d.modality],
      ["Indication", d.indication], ["Phase at deal", d.phase_at_deal], ["Licensee HQ", d.licensee_hq], ["Licensee type", d.licensee_type],
      ["Upfront", d.upfront_usd_m != null ? money(d.upfront_usd_m) : null], ["Equity", d.equity_usd_m != null ? money(d.equity_usd_m) : null],
      ["Milestones", d.milestones_usd_m != null ? money(d.milestones_usd_m) : null], ["Headline value", d.total_value_usd_m != null ? money(d.total_value_usd_m) : null],
      ["Royalties", d.royalties], ["Development status", d.development_status],
      ["Status note", d.status_note ? d.status_note + (d.status_date ? " (" + d.status_date + ")" : "") : null],
      ["Notes", d.notes], ["Data source", d.data_source], ["Last verified", d.last_verified], ["ID", d.id]
    ].filter(function (f) { return f[1]; });
  }
  function sourceLinks(list) {
    var frag = document.createDocumentFragment();
    (list || []).forEach(function (u, i) {
      if (i) frag.appendChild(document.createTextNode(", "));
      frag.appendChild(isUrl(u) ? el("a", { href: u, target: "_blank", rel: "noopener", text: host(u) }) : document.createTextNode(u));
    });
    return frag;
  }
  function events(d) { return (d.events || []).concat(d.catalysts || []).slice().sort(function (a, b) { return String(a.date).localeCompare(String(b.date)); }); }

  function timeline() {
    var cat = [], hist = [];
    deals.forEach(function (d) {
      var label = d.licensor + " to " + d.licensee + (d.asset ? " (" + d.asset + ")" : "");
      (d.catalysts || []).forEach(function (c) { if (c.date >= TODAY) cat.push({ date: c.date, label: label, event: c.event, id: d.id }); });
      (d.events || []).forEach(function (e) { hist.push({ date: e.date, label: label, event: e.event, id: d.id }); });
      if (d.status === "terminated" || d.status === "completed")
        hist.push({ date: String(d.status_date || ""), label: label, event: STATUS_LABEL[d.status] + (d.status_note ? ": " + d.status_note : ""), id: d.id, status: d.status });
    });
    pipeline.forEach(function (p) {
      (p.catalysts || []).forEach(function (c) { if (c.date >= TODAY) cat.push({ date: c.date, label: p.company + " (" + p.asset + ")", event: c.event }); });
    });
    cat.sort(function (a, b) { return a.date.localeCompare(b.date); });
    hist.sort(function (a, b) { return b.date.localeCompare(a.date); });
    return { upcoming: cat, history: hist };
  }

  // ---------- theme toggle ----------
  function bindTheme(storageKey) {
    var root = document.documentElement, btn = document.getElementById("theme");
    try { var saved = localStorage.getItem(storageKey); if (saved) root.setAttribute("data-theme", saved); } catch (e) {}
    function label() {
      var dark = isDark();
      // A fixed name with a pressed state: "Dark theme, pressed" means dark is on.
      if (btn) btn.setAttribute("aria-pressed", dark ? "true" : "false");
    }
    function isDark() {
      var t = root.getAttribute("data-theme");
      return t ? t === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
    }
    if (btn) btn.addEventListener("click", function () {
      var next = isDark() ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem(storageKey, next); } catch (e) {}
      label();
      listeners.forEach(function (fn) { fn(filtered()); });
    });
    // With no saved choice, follow the system setting when it changes.
    var mq = window.matchMedia("(prefers-color-scheme: dark)");
    var follow = function () { if (root.getAttribute("data-theme")) return; label(); listeners.forEach(function (fn) { fn(filtered()); }); };
    if (mq.addEventListener) mq.addEventListener("change", follow); else if (mq.addListener) mq.addListener(follow);
    label();
  }

  // ---------- tooltip ----------
  function tooltip(node) {
    function show(evt, title, sub) {
      node.textContent = "";
      node.appendChild(el("strong", { text: title }));
      if (sub) node.appendChild(el("span", { text: sub }));
      node.hidden = false;
      var r = evt.target.getBoundingClientRect();
      var x = evt.type !== "focus" ? evt.clientX : r.left + r.width / 2;
      var y = evt.type !== "focus" ? evt.clientY : r.top;
      var w = node.offsetWidth, h = node.offsetHeight;
      node.style.transform = "translate(" + Math.max(8, Math.min(window.innerWidth - w - 8, x + 12)) + "px," + Math.max(8, y - h - 12) + "px)";
    }
    function hide() { node.hidden = true; }
    return { show: show, hide: hide, bind: function (target, title, sub) {
      var h = function (e) { show(e, title, sub); };
      target.addEventListener("pointermove", h); target.addEventListener("focus", h);
      target.addEventListener("pointerleave", hide); target.addEventListener("blur", hide);
    } };
  }

  window.CBT = {
    DATA: DATA, deals: deals, pipeline: pipeline, policy: policy, TODAY: TODAY, FULL_FROM: FULL_FROM, minY: minY, maxY: maxY,
    el: el, svg: svg, money: money, bn: bn, year: year, uniq: uniq, isUrl: isUrl, host: host, sum: sum, fmtDate: fmtDate, when: when,
    STATUS_LABEL: STATUS_LABEL, assetName: assetName,
    bindFilters: bindFilters, onChange: onChange, filtered: filtered, isFiltered: isFiltered, range: range, changed: changed, setFilters: setFilters,
    FACETS: FACETS, options: options, upOptions: upOptions, undisclosedUp: undisclosedUp, set: set, toggle: toggle, state: state, except: except,
    phaseGroup: phaseGroup, csv: csv,
    byYear: byYear, topBy: topBy, kpis: kpis, sorter: sorter, detailFields: detailFields, sourceLinks: sourceLinks, events: events,
    timeline: timeline, bindTheme: bindTheme, tooltip: tooltip
  };
})();
