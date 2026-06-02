/*
 * pyssg document-graph renderer.
 *
 * One script drives two views of the same `graph.json` ({nodes, links, config}):
 *
 *   - Global: container `#kb-graph`, data inlined as `<script id="graph-data">`
 *     (preferred) or fetched from `/graph.json`. Optional 3D mode via a lazily
 *     loaded force-graph bundle.
 *   - Local:  container `#kb-local-graph[data-node-id]`, the neighbourhood of the
 *     current page out to `data-depth` hops, fetched from `/graph.json`.
 *
 * 2D rendering uses cytoscape (loaded by the host page from a CDN). The renderer
 * is a dumb consumer of the declared `config` (colours, sizing, depth): no
 * filtering happens here. Interaction design follows the prior art in
 * magiskboy/wiki; this is a clean-room reimplementation.
 *
 * No build step: plain ES5-ish browser JavaScript, no modules, no dependencies
 * beyond the globals it feature-detects (`cytoscape`, and for 3D `ForceGraph3D`).
 */
(function () {
  "use strict";

  var GRAPH_JSON_URL = "/graph.json";
  // 3D libraries, loaded only when the 3D toggle is first used.
  var LIB_THREE = "https://unpkg.com/three@0.157.0/build/three.min.js";
  var LIB_SPRITETEXT = "https://unpkg.com/three-spritetext@1.8.2/dist/three-spritetext.min.js";
  var LIB_FG3D = "https://unpkg.com/3d-force-graph@1.73.4/dist/3d-force-graph.min.js";

  // Deterministic fallback palette for groups without an explicit colour.
  var PALETTE = [
    "#4f9e6a", "#3b6ea5", "#9b6dd6", "#c75d56", "#c9a23a",
    "#2f8f9d", "#b14a8a", "#7a5cc0", "#5f7088", "#a06b3a",
  ];
  var TAG_COLOR = "#8a909b";

  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  function loadData() {
    var embedded = document.getElementById("graph-data");
    if (embedded) {
      try {
        return Promise.resolve(JSON.parse(embedded.textContent));
      } catch (e) {
        return Promise.reject(e);
      }
    }
    return fetch(GRAPH_JSON_URL).then(function (r) {
      if (!r.ok) throw new Error("graph.json " + r.status);
      return r.json();
    });
  }

  // -- shared helpers ---------------------------------------------------------

  function hashCode(str) {
    var h = 0;
    for (var i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) | 0;
    return Math.abs(h);
  }

  // Read a host-theme CSS variable so the graph follows the site's palette (and
  // its light/dark mode). Falls back to a sensible default on the standalone
  // global page, which does not load the theme stylesheet.
  function cssVar(name, fallback) {
    try {
      var v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
      return v || fallback;
    } catch (e) {
      return fallback;
    }
  }

  function colorFor(node, config) {
    if (node.kind === "tag") return TAG_COLOR;
    var colors = (config && config.colors) || {};
    if (colors[node.group]) return colors[node.group];
    return PALETTE[hashCode(node.group || "") % PALETTE.length];
  }

  function degreeOf(node) {
    return (node.inDegree || 0) + (node.outDegree || 0);
  }

  function sizeScale(nodes, config) {
    var degs = nodes.map(degreeOf);
    var lo = degs.length ? Math.min.apply(null, degs) : 0;
    var hi = degs.length ? Math.max.apply(null, degs) : 1;
    var sMin = (config && config.sizeMin) || 8;
    var sMax = (config && config.sizeMax) || 40;
    return function (node) {
      if (hi === lo) return (sMin + sMax) / 2;
      return sMin + ((degreeOf(node) - lo) / (hi - lo)) * (sMax - sMin);
    };
  }

  function cyElements(nodes, links, size, config) {
    var els = [];
    nodes.forEach(function (n) {
      els.push({
        data: {
          id: n.id,
          label: n.title,
          url: n.url || "",
          kind: n.kind || "page",
          color: colorFor(n, config),
          size: size(n),
        },
      });
    });
    var present = {};
    nodes.forEach(function (n) { present[n.id] = true; });
    links.forEach(function (e, i) {
      if (!present[e.source] || !present[e.target]) return;
      els.push({
        data: {
          id: "e" + i,
          source: e.source,
          target: e.target,
          bidi: !!e.bidirectional,
        },
      });
    });
    return els;
  }

  function styleSheet(currentId, showLabels) {
    var text = cssVar("--body-font-color", "#1c1e21");
    var bg = cssVar("--body-background", "#ffffff");
    var accent = cssVar("--color-link", "#c75d56");
    var edge = cssVar("--muted-font-color", "#b9bcc4");
    return [
      {
        selector: "node",
        style: {
          "background-color": "data(color)",
          width: "data(size)",
          height: "data(size)",
          label: "data(label)",
          color: text,
          "font-size": 10,
          "text-valign": "bottom",
          "text-margin-y": 3,
          "text-opacity": showLabels ? 1 : 0,
          "text-background-color": bg,
          "text-background-opacity": showLabels ? 0.7 : 0,
          "text-background-padding": 2,
          "min-zoomed-font-size": 7,
          "border-width": 0,
          "transition-property": "opacity, text-opacity, border-width",
          "transition-duration": "0.12s",
        },
      },
      { selector: 'node[kind = "tag"]', style: { shape: "round-rectangle", "font-style": "italic" } },
      { selector: "node.hl, node:selected", style: { "text-opacity": 1, "text-background-opacity": 0.85 } },
      { selector: "node:selected", style: { "border-width": 3, "border-color": accent } },
      currentId
        ? { selector: 'node[id = "' + currentId.replace(/"/g, '\\"') + '"]', style: {
            "border-width": 3, "border-color": accent, "text-opacity": 1, "text-background-opacity": 0.85 } }
        : { selector: "node.__never__", style: {} },
      {
        selector: "edge",
        style: {
          width: 1,
          "line-color": edge,
          "curve-style": "bezier",
          opacity: 0.45,
          "transition-property": "opacity, line-color, width",
          "transition-duration": "0.12s",
        },
      },
      { selector: "edge.hl", style: { "line-color": accent, opacity: 0.95, width: 2 } },
      { selector: ".faded", style: { opacity: 0.1, "text-opacity": 0 } },
    ];
  }

  function makeCy(container, els, currentId, padding, showLabels) {
    var cy = cytoscape({
      container: container,
      elements: els,
      style: styleSheet(currentId, showLabels),
      minZoom: 0.2,
      maxZoom: 3,
      wheelSensitivity: 0.2,
    });
    // Run the force layout explicitly (not via the constructor) so the
    // layoutstop handler is attached before it fires, then centre the result.
    var layout = cy.layout({
      name: "cose",
      animate: false,
      padding: padding || 30,
      nodeDimensionsIncludeLabels: true,
    });
    var fit = function () { cy.resize(); cy.fit(undefined, padding || 30); };
    layout.one("layoutstop", fit);
    layout.run();
    // The CSS (which sizes the container) may still be loading when a deferred
    // script runs, leaving the container at zero height; re-fit once everything
    // has loaded and whenever the viewport changes.
    window.addEventListener("load", fit);
    window.addEventListener("resize", fit);
    // Re-apply the palette when the host theme toggles light/dark.
    if (window.MutationObserver) {
      var mo = new MutationObserver(function () { cy.style(styleSheet(currentId, showLabels)); });
      mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    }
    return cy;
  }

  function wireFocus(cy, opts) {
    opts = opts || {};
    cy.on("mouseover", "node", function (ev) {
      var nb = ev.target.closedNeighborhood();
      cy.elements().addClass("faded");
      nb.removeClass("faded").addClass("hl");
    });
    cy.on("mouseout", "node", function () {
      if (!cy.$(":selected").length) cy.elements().removeClass("faded hl");
    });
    cy.on("tap", "node", function (ev) {
      var url = ev.target.data("url");
      if (url) {
        window.location.href = url;
      } else if (opts.onSelect) {
        opts.onSelect(ev.target);
      }
    });
  }

  // -- global view ------------------------------------------------------------

  function initGlobal(container, data) {
    var nodes = data.nodes || [];
    var links = data.links || [];
    var config = data.config || {};
    var size = sizeScale(nodes, config);
    var cy = makeCy(container, cyElements(nodes, links, size, config), null, 40, false);
    wireFocus(cy);

    var search = document.getElementById("graph-search");
    if (search) {
      search.addEventListener("input", function () {
        var q = search.value.trim().toLowerCase();
        if (!q) { cy.elements().removeClass("faded hl"); return; }
        var hits = cy.nodes().filter(function (n) {
          return n.data("label").toLowerCase().indexOf(q) !== -1;
        });
        cy.elements().addClass("faded");
        hits.removeClass("faded").addClass("hl");
        if (hits.length) cy.animate({ fit: { eles: hits, padding: 80 } }, { duration: 250 });
      });
    }
    var reset = document.getElementById("graph-reset");
    if (reset) reset.addEventListener("click", function () {
      cy.$(":selected").unselect();
      cy.elements().removeClass("faded hl");
      if (search) search.value = "";
      cy.animate({ fit: { padding: 30 } }, { duration: 250 });
    });

    setup3D(cy, nodes, links, config, size);
  }

  // -- 3D view (lazily loaded) ------------------------------------------------

  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      var existing = document.querySelector('script[data-g3d="' + src + '"]');
      if (existing) {
        if (existing.dataset.loaded === "1") return resolve();
        existing.addEventListener("load", resolve);
        existing.addEventListener("error", reject);
        return;
      }
      var s = document.createElement("script");
      s.src = src;
      s.async = false;
      s.setAttribute("data-g3d", src);
      s.onload = function () { s.dataset.loaded = "1"; resolve(); };
      s.onerror = function () { reject(new Error("failed to load " + src)); };
      document.head.appendChild(s);
    });
  }

  function setup3D(cy, nodes, links, config, size) {
    var btn = document.getElementById("graph-3d-toggle");
    var el3d = document.getElementById("kb-graph-3d");
    var el2d = document.getElementById("kb-graph");
    if (!btn || !el3d || !el2d) return;
    var fg = null;
    var on = false;

    btn.addEventListener("click", function () {
      if (on) {
        el3d.hidden = true;
        el2d.hidden = false;
        on = false;
        btn.setAttribute("aria-pressed", "false");
        return;
      }
      btn.setAttribute("aria-pressed", "true");
      ensure3D()
        .then(function () {
          el2d.hidden = true;
          el3d.hidden = false;
          on = true;
          if (!fg) fg = build3D(el3d, nodes, links, config);
        })
        .catch(function (err) {
          btn.setAttribute("aria-pressed", "false");
          if (window.console) console.error("3D init failed", err);
        });
    });
  }

  function ensure3D() {
    if (window.ForceGraph3D) return Promise.resolve();
    return loadScript(LIB_THREE)
      .then(function () { return loadScript(LIB_SPRITETEXT); })
      .then(function () { return loadScript(LIB_FG3D); });
  }

  function build3D(container, nodes, links, config) {
    var n3d = nodes.map(function (n) {
      return {
        id: n.id, name: n.title, url: n.url || "",
        color: colorFor(n, config), val: 1 + Math.sqrt(degreeOf(n) || 1),
      };
    });
    var l3d = links.map(function (e) { return { source: e.source, target: e.target }; });
    var fg = window.ForceGraph3D()(container)
      .graphData({ nodes: n3d, links: l3d })
      .nodeColor(function (n) { return n.color; })
      .nodeVal(function (n) { return n.val; })
      .nodeLabel(function (n) { return n.name; })
      .linkOpacity(0.35)
      .onEngineStop(function () { fg.zoomToFit(400, 40); })
      .onNodeClick(function (n) { if (n.url) window.location.href = n.url; });
    if (window.SpriteText) {
      fg.nodeThreeObjectExtend(true).nodeThreeObject(function (n) {
        var s = new window.SpriteText(n.name);
        s.textHeight = 4;
        s.color = "#666";
        s.position.set(0, 8, 0);
        return s;
      });
    }
    return fg;
  }

  // -- local view -------------------------------------------------------------

  function neighbourhood(centerId, links, depth) {
    var adj = {};
    links.forEach(function (e) {
      (adj[e.source] = adj[e.source] || []).push(e.target);
      (adj[e.target] = adj[e.target] || []).push(e.source);
    });
    var keep = {};
    keep[centerId] = true;
    var frontier = [centerId];
    for (var d = 0; d < depth; d++) {
      var next = [];
      frontier.forEach(function (id) {
        (adj[id] || []).forEach(function (other) {
          if (!keep[other]) { keep[other] = true; next.push(other); }
        });
      });
      frontier = next;
    }
    return keep;
  }

  function initLocal(container, data) {
    var centerId = container.getAttribute("data-node-id");
    var depth = parseInt(container.getAttribute("data-depth"), 10) || 1;
    var config = data.config || {};
    var allNodes = data.nodes || [];
    var allLinks = data.links || [];
    var index = {};
    allNodes.forEach(function (n) { index[n.id] = n; });
    if (!index[centerId]) { container.hidden = true; return; }

    var keep = neighbourhood(centerId, allLinks, depth);
    var nodes = allNodes.filter(function (n) { return keep[n.id]; });
    var links = allLinks.filter(function (e) { return keep[e.source] && keep[e.target]; });
    if (nodes.length <= 1) { container.hidden = true; return; }

    var size = sizeScale(nodes, config);
    var cy = makeCy(container, cyElements(nodes, links, size, config), centerId, 20, true);
    wireFocus(cy);
  }

  // -- bootstrap --------------------------------------------------------------

  ready(function () {
    var global = document.getElementById("kb-graph");
    var local = document.getElementById("kb-local-graph");
    if (!global && !local) return;
    if (typeof cytoscape === "undefined") {
      if (window.console) console.error("pyssg graph: cytoscape not loaded");
      return;
    }
    loadData()
      .then(function (data) {
        if (global) initGlobal(global, data);
        if (local) initLocal(local, data);
      })
      .catch(function (err) {
        if (window.console) console.error("pyssg graph: failed to load data", err);
        if (local) local.hidden = true;
      });
  });
})();
