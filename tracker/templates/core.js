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

  // ---------- filters (ids shared with the original dashboard) ----------
  var F = {};
  var listeners = [];
  var years = deals.map(year).filter(Boolean);
  var minY = Math.min.apply(null, years), maxY = Math.max.apply(null, years);

  function fill(select, values, labeler) {
    values.forEach(function (v) { select.appendChild(el("option", { value: v, text: labeler ? labeler(v) : v })); });
  }
  function bindFilters() {
    ["q", "f-status", "f-area", "f-hq", "f-type", "f-from", "f-to"].forEach(function (id) { F[id] = document.getElementById(id); });
    if (!F.q) return;
    fill(F["f-status"], ["active", "pending", "completed", "terminated"].filter(function (s) { return deals.some(function (d) { return d.status === s; }); }), function (s) { return STATUS_LABEL[s]; });
    fill(F["f-area"], uniq(deals.map(function (d) { return d.therapeutic_area; })));
    fill(F["f-hq"], uniq(deals.map(function (d) { return d.licensee_hq; })));
    fill(F["f-type"], uniq(deals.map(function (d) { return d.deal_type; })));
    for (var y = minY; y <= maxY; y++) { F["f-from"].appendChild(el("option", { value: y, text: y })); F["f-to"].appendChild(el("option", { value: y, text: y })); }
    readUrl();
    Object.keys(F).forEach(function (k) {
      F[k].addEventListener(k === "q" ? "input" : "change", changed);
    });
    var reset = document.getElementById("reset");
    if (reset) reset.addEventListener("click", function () { setFilters({}); changed(); });
  }
  function setFilters(o) {
    F.q.value = o.q || ""; F["f-status"].value = o.status || ""; F["f-area"].value = o.area || "";
    F["f-hq"].value = o.hq || ""; F["f-type"].value = o.type || "";
    F["f-from"].value = o.from || minY; F["f-to"].value = o.to || maxY;
  }
  // Filter state lives in the URL hash so a view can be shared.
  function readUrl() {
    var o = {};
    location.hash.replace(/^#/, "").split("&").forEach(function (kv) {
      var p = kv.split("="); if (p[0]) o[p[0]] = decodeURIComponent(p[1] || "");
    });
    setFilters(o);
  }
  function writeUrl() {
    var o = { q: F.q.value.trim(), status: F["f-status"].value, area: F["f-area"].value, hq: F["f-hq"].value, type: F["f-type"].value,
      from: +F["f-from"].value === minY ? "" : F["f-from"].value, to: +F["f-to"].value === maxY ? "" : F["f-to"].value };
    var s = Object.keys(o).filter(function (k) { return o[k]; }).map(function (k) { return k + "=" + encodeURIComponent(o[k]); }).join("&");
    try { history.replaceState(null, "", s ? "#" + s : location.pathname + location.search); } catch (e) {}
  }
  function changed() { writeUrl(); listeners.forEach(function (fn) { fn(filtered()); }); }
  function onChange(fn) { listeners.push(fn); }
  function isFiltered() {
    return !!(F.q.value.trim() || F["f-status"].value || F["f-area"].value || F["f-hq"].value || F["f-type"].value ||
      +F["f-from"].value !== minY || +F["f-to"].value !== maxY);
  }
  function filtered() {
    if (!F.q) return deals.slice();
    var q = F.q.value.trim().toLowerCase(), from = +F["f-from"].value, to = +F["f-to"].value;
    return deals.filter(function (d) {
      var y = year(d);
      if (y < from || y > to) return false;
      if (F["f-status"].value && d.status !== F["f-status"].value) return false;
      if (F["f-area"].value && d.therapeutic_area !== F["f-area"].value) return false;
      if (F["f-hq"].value && d.licensee_hq !== F["f-hq"].value) return false;
      if (F["f-type"].value && d.deal_type !== F["f-type"].value) return false;
      if (q && JSON.stringify(d).toLowerCase().indexOf(q) < 0) return false;
      return true;
    });
  }
  function range() { return { from: +F["f-from"].value || minY, to: +F["f-to"].value || maxY }; }

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
      ["Deal type", d.deal_type], ["Territory", d.territory], ["Target", d.target], ["Modality", d.modality],
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
      if (btn) { btn.setAttribute("aria-pressed", dark ? "true" : "false"); btn.textContent = dark ? "Light" : "Dark"; }
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
    byYear: byYear, topBy: topBy, kpis: kpis, sorter: sorter, detailFields: detailFields, sourceLinks: sourceLinks, events: events,
    timeline: timeline, bindTheme: bindTheme, tooltip: tooltip
  };
})();
