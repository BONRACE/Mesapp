/* EcoKolekt — page d'accueil : QR décoratifs, compteurs, apparition au scroll. */
(function () {
  "use strict";
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var hasIO = "IntersectionObserver" in window;
  document.documentElement.classList.add("js");

  /* QR décoratifs (motif pseudo-aléatoire reproductible, pas un vrai code). */
  function rng(seed) {
    var s = seed >>> 0;
    return function () {
      s = (s * 1664525 + 1013904223) >>> 0;
      return s / 4294967296;
    };
  }
  function finder(x, y) {
    var out = "";
    for (var i = 0; i < 7; i++) for (var j = 0; j < 7; j++) {
      var edge = i === 0 || j === 0 || i === 6 || j === 6;
      var core = i >= 2 && i <= 4 && j >= 2 && j <= 4;
      if (edge || core) out += '<rect class="on" x="' + (x + i) + '" y="' + (y + j) + '" width="1" height="1"/>';
    }
    return out;
  }
  function inFinder(i, j) {
    return (i < 8 && j < 8) || (i > 16 && j < 8) || (i < 8 && j > 16);
  }
  function drawQR(svg) {
    var rand = rng(parseInt(svg.getAttribute("data-qr"), 10) || 1);
    var cells = "";
    for (var i = 0; i < 25; i++) for (var j = 0; j < 25; j++) {
      if (!inFinder(i, j) && rand() > 0.52) cells += '<rect class="on" x="' + i + '" y="' + j + '" width="1" height="1"/>';
    }
    svg.insertAdjacentHTML("beforeend", cells + finder(0, 0) + finder(18, 0) + finder(0, 18));
  }
  var qrs = document.querySelectorAll("svg[data-qr]");
  for (var q = 0; q < qrs.length; q++) drawQR(qrs[q]);

  /* Compteurs */
  var fmt = new Intl.NumberFormat("fr-FR");
  function render(el, v) {
    el.textContent = fmt.format(Math.round(v)) + (el.getAttribute("data-suffix") || "");
  }
  function count(el) {
    var target = parseFloat(el.getAttribute("data-count")) || 0;
    if (reduce) return render(el, target);
    var t0 = null, dur = 1400;
    function tick(t) {
      if (t0 === null) t0 = t;
      var p = Math.min((t - t0) / dur, 1);
      render(el, target * (1 - Math.pow(1 - p, 3)));
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }
  var counters = document.querySelectorAll("[data-count]");
  function showAll() {
    for (var i = 0; i < counters.length; i++) render(counters[i], parseFloat(counters[i].getAttribute("data-count")) || 0);
  }

  if (!hasIO) {
    showAll();
    var rv = document.querySelectorAll(".reveal");
    for (var r = 0; r < rv.length; r++) rv[r].classList.add("is-in");
  } else {
    var co = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { count(e.target); co.unobserve(e.target); }
      });
    }, { threshold: 0.6 });
    counters.forEach(function (c) { co.observe(c); });

    var ro = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("is-in"); ro.unobserve(e.target); }
      });
    }, { threshold: 0.15, rootMargin: "0px 0px -6% 0px" });
    document.querySelectorAll(".reveal").forEach(function (el) { ro.observe(el); });
  }

  var yr = document.getElementById("yr");
  if (yr) yr.textContent = String(new Date().getFullYear());
})();
