(() => {
  "use strict";

  const DOT_PATH = "orbit_from_engine_run_rcx_core_v1.dot";
  const SVG_OBJ_ID = "orbitSvgObj";
  const LIST_ID = "nodeList";
  const FILTER_ID = "nodeFilter";
  const STATUS_ID = "statusLine";

  function $(id) { return document.getElementById(id); }

  function setStatus(msg) {
    const el = $(STATUS_ID);
    if (el) el.textContent = msg;
  }

  function escapeHtml(s) {
    return String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  // Very small DOT parser:
  // - nodes:   "id" [label="..."];
  // - edges:   "a" -> "b";
  // If label missing, fall back to id.
  function parseDot(dotText) {
    const nodes = new Map(); // id -> {id,label}
    const edges = []; // {from,to}

    // Node lines
    // Handles: "n0" [label="foo"];
    const nodeRe = /^\s*"([^"]+)"\s*\[(.*?)\]\s*;?\s*$/gm;
    let m;
    while ((m = nodeRe.exec(dotText)) !== null) {
      const id = m[1];
      const attrs = m[2] || "";
      let label = id;

      // label="..."; (allow escaped quotes \" inside)
      const labelRe = /label\s*=\s*"((?:[^"\\]|\\.)*)"/;
      const lm = labelRe.exec(attrs);
      if (lm && lm[1] != null) {
        label = lm[1].replaceAll('\\"', '"');
      }

      if (!nodes.has(id)) nodes.set(id, { id, label });
    }

    // Edge lines
    const edgeRe = /^\s*"([^"]+)"\s*->\s*"([^"]+)"\s*;?\s*$/gm;
    while ((m = edgeRe.exec(dotText)) !== null) {
      const from = m[1];
      const to = m[2];
      edges.push({ from, to });
      if (!nodes.has(from)) nodes.set(from, { id: from, label: from });
      if (!nodes.has(to)) nodes.set(to, { id: to, label: to });
    }

    return {
      nodes: Array.from(nodes.values()).sort((a, b) => a.label.localeCompare(b.label)),
      edges
    };
  }

  function getSvgDoc() {
    const obj = $(SVG_OBJ_ID);
    if (!obj) return null;
    // object must be loaded before contentDocument exists
    return obj.contentDocument || null;
  }

  function clearHighlights(svgDoc) {
    if (!svgDoc) return;
    svgDoc.querySelectorAll(".rcx-hl").forEach(el => el.classList.remove("rcx-hl"));
  }

  // Try to highlight:
  // 1) Find text nodes whose textContent matches the node label exactly.
  // 2) Climb to nearest <g> and highlight it (preferred), else highlight the text itself.
  function highlightByLabel(svgDoc, label) {
    if (!svgDoc) return 0;

    clearHighlights(svgDoc);

    const texts = Array.from(svgDoc.querySelectorAll("text"));
    const hits = texts.filter(t => (t.textContent || "").trim() === label.trim());

    for (const t of hits) {
      let g = t.closest("g");
      (g || t).classList.add("rcx-hl");
    }

    // Also try substring match if exact yielded nothing (Graphviz sometimes inserts spacing)
    if (hits.length === 0) {
      const softHits = texts.filter(t => (t.textContent || "").includes(label));
      for (const t of softHits) {
        let g = t.closest("g");
        (g || t).classList.add("rcx-hl");
      }
      return softHits.length;
    }

    return hits.length;
  }

  function injectSvgStyles(svgDoc) {
    if (!svgDoc) return;
    if (svgDoc.getElementById("rcxInjectedStyles")) return;

    const style = svgDoc.createElementNS("http://www.w3.org/2000/svg", "style");
    style.setAttribute("id", "rcxInjectedStyles");
    style.textContent = `
      .rcx-hl polygon, .rcx-hl path, .rcx-hl ellipse, .rcx-hl circle, .rcx-hl rect {
        stroke: #d00 !important;
        stroke-width: 2.25 !important;
      }
      .rcx-hl text {
        fill: #d00 !important;
        font-weight: 700 !important;
      }
    `;
    // Put it near top if possible
    const svg = svgDoc.querySelector("svg");
    if (svg) svg.insertBefore(style, svg.firstChild);
  }

  function renderNodeList(model) {
    const list = $(LIST_ID);
    const filter = $(FILTER_ID);
    if (!list || !filter) return;

    function draw(items) {
      list.innerHTML = items.map(n => {
        const label = escapeHtml(n.label);
        const id = escapeHtml(n.id);
        return `<button class="nodebtn" data-label="${label}" data-id="${id}" title="${id}">${label}</button>`;
      }).join("\n");
    }

    draw(model.nodes);

    filter.addEventListener("input", () => {
      const q = filter.value.trim().toLowerCase();
      if (!q) {
        draw(model.nodes);
        setStatus(`Loaded ${model.nodes.length} nodes.`);
        return;
      }
      const filtered = model.nodes.filter(n =>
        n.label.toLowerCase().includes(q) || n.id.toLowerCase().includes(q)
      );
      draw(filtered);
      setStatus(`Showing ${filtered.length}/${model.nodes.length} nodes (filter: "${filter.value}").`);
    });

    list.addEventListener("click", (ev) => {
      const btn = ev.target.closest("button.nodebtn");
      if (!btn) return;

      const label = btn.getAttribute("data-label") || "";
      const id = btn.getAttribute("data-id") || "";

      const svgDoc = getSvgDoc();
      if (!svgDoc) {
        setStatus(`SVG not loaded yet. Click again in a second. (node: ${label || id})`);
        return;
      }

      injectSvgStyles(svgDoc);
      const hitCount = highlightByLabel(svgDoc, label || id);

      // Scroll SVG container into view (best effort)
      const svgWrap = document.querySelector(".svgwrap");
      if (svgWrap) svgWrap.scrollIntoView({ behavior: "smooth", block: "start" });

      setStatus(`Selected: ${label || id}  |  highlight hits: ${hitCount}`);
    });

    setStatus(`Loaded ${model.nodes.length} nodes.`);
  }

  async function boot() {
    try {
      setStatus("Loading DOT…");
      const res = await fetch(DOT_PATH, { cache: "no-store" });
      if (!res.ok) throw new Error(`fetch(${DOT_PATH}) failed: ${res.status}`);
      const dotText = await res.text();
      const model = parseDot(dotText);

      renderNodeList(model);

      // Hook SVG load to inject highlight styles once
      const obj = $(SVG_OBJ_ID);
      if (obj) {
        obj.addEventListener("load", () => {
          const svgDoc = getSvgDoc();
          if (svgDoc) injectSvgStyles(svgDoc);
        });
      }
    } catch (e) {
      console.error(e);
      setStatus("FAIL: " + (e && e.message ? e.message : String(e)));
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
