/* Maré — the living mark. The sea drawn as a stipple of tiny squares (after Franey):
   the marks are the form, the untouched ground is the light. One ink, no glow, no circles.
   Motion is the tide — a bounded sinusoidal drift, never accelerating away.
     <canvas class="mare-mark" data-mark></canvas>   → the moving sea (a horizon band)
     <canvas class="mare-mark" data-bars="3,7,5,9"></canvas> → a still column chart, same grammar
   Colour comes from the --stipple-rgb token, so it themes for free. */
(function () {
  "use strict";
  var reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  function ink(el) { return getComputedStyle(el).getPropertyValue("--stipple-rgb").trim() || "36,86,104"; }

  function Sea(canvas) {
    var ctx = canvas.getContext("2d"), W = 0, H = 0, pts = [], t = 0, running = false;
    function resize() {
      var dpr = Math.min(window.devicePixelRatio || 1, 2), r = canvas.getBoundingClientRect();
      W = Math.max(1, r.width); H = Math.max(1, r.height);
      canvas.width = W * dpr; canvas.height = H * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    function seed() {
      pts = []; var n = Math.max(320, Math.round(W * H * 0.0033));
      for (var i = 0; i < n; i++) {
        var x = Math.random() * W;
        var crest = H * 0.42 + Math.sin(x * 0.012) * H * 0.09 + Math.sin(x * 0.033) * H * 0.035;
        var below = Math.random(), y = crest + below * (H - crest);
        var depth = (y - crest) / (H - crest + 1);
        var lip = Math.max(0, 1 - Math.abs(y - crest) / (H * 0.06));
        pts.push({ x: x, y: y, a: 0.1 + depth * 0.66 * (0.4 + Math.random() * 0.6) + lip * 0.22, s: Math.random() < 0.14 ? 2 : 1 });
      }
    }
    function paint(animate) {
      ctx.clearRect(0, 0, W, H); var rgb = ink(canvas);
      for (var i = 0; i < pts.length; i++) {
        var p = pts[i];
        if (animate) {
          p.x += Math.cos(p.y * 0.01 + t) * 0.26;
          p.y += Math.sin(p.x * 0.012 + t * 0.7) * 0.14;
          if (p.x < -2) p.x = W + 2; else if (p.x > W + 2) p.x = -2;
        }
        ctx.fillStyle = "rgba(" + rgb + "," + p.a + ")"; ctx.fillRect(p.x, p.y, p.s, p.s);
      }
    }
    function frame() { if (!running) return; if (!canvas.isConnected) { running = false; return; } t += 0.006; paint(true); requestAnimationFrame(frame); }
    this.start = function () { if (reduced) return paint(false); if (running) return; running = true; requestAnimationFrame(frame); };
    this.stop = function () { running = false; };
    this.redraw = function () { if (reduced || !running) paint(false); };
    this.reinit = function () { resize(); seed(); if (reduced || !running) paint(false); };
    this.canvas = canvas;
    resize(); seed();
  }

  function Bars(canvas) {
    var ctx = canvas.getContext("2d"), W = 0, H = 0;
    var vals = (canvas.getAttribute("data-bars") || "").split(",").map(Number).filter(function (v) { return v === v; });
    function resize() {
      var dpr = Math.min(window.devicePixelRatio || 1, 2), r = canvas.getBoundingClientRect();
      W = Math.max(1, r.width); H = Math.max(1, r.height);
      canvas.width = W * dpr; canvas.height = H * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    this.draw = function () {
      ctx.clearRect(0, 0, W, H); if (!vals.length) return;
      var rgb = ink(canvas), max = Math.max.apply(null, vals), cell = 4, gap = 2, step = W / vals.length;
      for (var i = 0; i < vals.length; i++) {
        var bx = i * step + (step - cell) / 2, rows = Math.max(1, Math.round((vals[i] / max) * (H / (cell + gap))));
        for (var j = 0; j < rows; j++) { ctx.fillStyle = "rgba(" + rgb + "," + (0.3 + 0.55 * (j / rows)) + ")"; ctx.fillRect(bx, H - (j + 1) * (cell + gap), cell, cell); }
      }
    };
    this.reinit = function () { resize(); this.draw(); };
    this.canvas = canvas;
    resize();
  }

  var seas = [], bars = [];
  /* A canvas can arrive after load (React mounts, SPA navigations) — attach lives per
     element, and a MutationObserver keeps the promise that dropping a mark in is enough. */
  function attach(c) {
    var inst = c.__mareMark;
    if (inst) {
      // A re-added canvas re-wakes; it may have been swept while detached.
      if (inst.start) { if (seas.indexOf(inst) < 0) seas.push(inst); inst.reinit(); inst.start(); }
      else { if (bars.indexOf(inst) < 0) bars.push(inst); inst.reinit(); }
      return;
    }
    if (c.hasAttribute("data-mark")) { var o = new Sea(c); c.__mareMark = o; seas.push(o); o.start(); }
    else if (c.hasAttribute("data-bars")) { var b = new Bars(c); c.__mareMark = b; bars.push(b); b.draw(); }
  }
  function scan(root) {
    if (root.matches && root.matches("canvas[data-mark], canvas[data-bars]")) attach(root);
    if (root.querySelectorAll) root.querySelectorAll("canvas[data-mark], canvas[data-bars]").forEach(attach);
  }
  function sweep() {
    seas = seas.filter(function (o) { if (o.canvas.isConnected) return true; o.stop(); return false; });
    bars = bars.filter(function (b) { return b.canvas.isConnected; });
  }
  function init() {
    scan(document);
    new MutationObserver(function (muts) {
      var removed = false;
      for (var i = 0; i < muts.length; i++) {
        if (muts[i].removedNodes.length) removed = true;
        for (var j = 0; j < muts[i].addedNodes.length; j++) scan(muts[i].addedNodes[j]);
      }
      if (removed) sweep();
    }).observe(document.documentElement, { childList: true, subtree: true });
  }
  window.MareMark = { remark: function () { seas.forEach(function (o) { o.redraw(); }); bars.forEach(function (b) { b.draw(); }); } };
  var rt; window.addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(function () { seas.forEach(function (o) { o.reinit(); }); bars.forEach(function (b) { b.reinit(); }); }, 150); });
  document.addEventListener("visibilitychange", function () { seas.forEach(function (o) { document.hidden ? o.stop() : o.start(); }); });
  if (document.readyState !== "loading") init(); else document.addEventListener("DOMContentLoaded", init);
})();
