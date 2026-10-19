/* EcoKolekt — helpers d'interface : échappement, formats, icônes, modale, toasts, cartes. */
(function () {
  "use strict";
  var EK = (window.EK = window.EK || {});

  EK.esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };
  var esc = EK.esc;
  EK.$ = function (sel, root) { return (root || document).querySelector(sel); };
  EK.$$ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };

  /* Formats */
  var nf = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });
  EK.fmt = {
    n: function (v) { return nf.format(Number(v) || 0); },
    fcfa: function (v) { return nf.format(Math.round(Number(v) || 0)) + " FCFA"; },
    kg: function (v) { return nf.format(Number(v) || 0) + " kg"; },
    dist: function (m) { return m == null ? "" : m < 1000 ? Math.round(m) + " m" : nf.format(m / 1000) + " km"; },
    dur: function (s) { var m = Math.round((s || 0) / 60); return m < 60 ? m + " min" : Math.floor(m / 60) + " h " + (m % 60 ? String(m % 60).padStart(2, "0") : ""); },
    date: function (iso) {
      if (!iso) return "";
      return new Date(iso).toLocaleDateString("fr-FR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
    },
    initials: function (name) {
      return String(name || "?").split(/\s+/).slice(0, 2).map(function (w) { return w[0]; }).join("").toUpperCase();
    },
  };

  /* Icônes (traits 1.8, 24×24) */
  var P = {
    home: "M3 11.5 12 4l9 7.5M5.5 10v9.5h13V10M10 19.5v-5h4v5",
    plus: "M12 5v14M5 12h14",
    pin: "M12 21s6.5-5.6 6.5-11a6.5 6.5 0 0 0-13 0C5.5 15.4 12 21 12 21ZM12 12.3a2.3 2.3 0 1 0 0-4.6 2.3 2.3 0 0 0 0 4.6",
    route: "M6 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4ZM18 9a2 2 0 1 0 0-4 2 2 0 0 0 0 4ZM8 17h6.5a3.5 3.5 0 0 0 0-7h-5a3.5 3.5 0 0 1 0-7H16",
    qr: "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h2.5v2.5H14zM18 14h2v2h-2zM14 18.5h2v1.5h-2zM17.5 18h2.5v2h-2.5z",
    market: "M4 9l1.5-4.5h13L20 9M4 9v10.5h16V9M4 9c0 1.7 1.3 3 3 3s3-1.3 3-3c0 1.7 1.3 3 3 3s3-1.3 3-3c0 1.7 1.3 3 3 3",
    orders: "M7 4h10l2 3v13H5V7zM5 7h14M9 11h6M9 15h4",
    user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM4.5 20c.8-3.6 3.6-5.5 7.5-5.5s6.7 1.9 7.5 5.5",
    out: "M14 4h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-4M10 16l-4-4 4-4M6 12h10",
    chart: "M4 20V10M10 20V4M16 20v-7M21 20H3",
    leaf: "M5 19c0-8 5-13 15-13 0 9-4.5 14-12 14M5 19c2-4 5-7 9-9",
    check: "M5 12.5l4.5 4.5L19 7.5",
    shield: "M12 3.5 19 6v5.5c0 4.3-2.9 7.5-7 9-4.1-1.5-7-4.7-7-9V6l7-2.5ZM9 12l2.2 2.2L15.2 10",
    truck: "M3 7h11v9H3zM14 10h4l3 3v3h-7M7 19a1.7 1.7 0 1 0 0-3.4A1.7 1.7 0 0 0 7 19ZM17 19a1.7 1.7 0 1 0 0-3.4 1.7 1.7 0 0 0 0 3.4Z",
    scan: "M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3M4 12h16",
    list: "M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01",
    sync: "M20 11a8 8 0 0 0-14.5-3.5M4 4v4h4M4 13a8 8 0 0 0 14.5 3.5M20 20v-4h-4",
    users: "M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7ZM2.5 20c.6-3.3 3.1-5 6.5-5s5.9 1.7 6.5 5M16 4.4a3.5 3.5 0 0 1 0 6.2M18 15.3c1.9.6 3 2 3.5 4.7",
    x: "M6 6l12 12M18 6 6 18",
    phone: "M7 3h10a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zM10.5 18h3",
    wallet: "M4 7.5A2.5 2.5 0 0 1 6.5 5H18v3M4 7.5V17a2 2 0 0 0 2 2h13a1 1 0 0 0 1-1v-9a1 1 0 0 0-1-1H6.5A2.5 2.5 0 0 1 4 7.5ZM16 13.5h.01",
  };
  EK.icon = function (name, cls) {
    return '<svg class="ic ' + (cls || "") + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="' + (P[name] || "") + '"/></svg>';
  };
  EK.logo = '<svg viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="9" fill="#0b4a32"/><path d="M9 21c0-7 5-11 14-11 0 8-4 13-11 13" fill="#d4a62f"/><path d="M9 24c1.5-5 4-8 8-10" stroke="#0b4a32" stroke-width="1.6" stroke-linecap="round" fill="none"/></svg>';

  /* Libellés */
  EK.roleLabel = { citizen: "Ménage", collector: "Collecteur", recycler: "Recycleur", admin: "Administration" };
  EK.pickupStatus = {
    pending: ["En attente", "chip--on"], assigned: ["Collecteur assigné", "chip--info"], en_route: ["En route", "chip--on"],
    collected: ["Collecté", "chip--ok"], cancelled: ["Annulé", "chip--bad"],
  };
  EK.orderStatusClass = { pending_payment: "chip--on", paid: "chip--info", shipped: "chip--info", delivered: "chip--ok", cancelled: "chip--bad", expired: "chip--bad" };
  EK.chip = function (label, cls) { return '<span class="chip ' + (cls || "") + '">' + esc(label) + "</span>"; };

  /* Toasts */
  EK.toast = function (msg, bad) {
    var box = EK.$("#toasts");
    if (!box) { box = document.createElement("div"); box.id = "toasts"; box.className = "toasts"; box.setAttribute("role", "status"); document.body.appendChild(box); }
    var t = document.createElement("div");
    t.className = "toast" + (bad ? " toast--bad" : "");
    t.textContent = msg;
    box.appendChild(t);
    setTimeout(function () { t.remove(); }, bad ? 5200 : 3200);
  };
  EK.fail = function (e) { EK.toast(e && e.message ? e.message : "Erreur inattendue.", true); };

  /* Modale : renvoie { el, close } ; onClose appelé une fois (arrêt caméra, etc.) */
  EK.modal = function (html, onClose) {
    var prev = document.activeElement;
    var m = document.createElement("div");
    m.className = "modal";
    m.setAttribute("role", "dialog");
    m.setAttribute("aria-modal", "true");
    m.innerHTML = '<div class="modal__box">' + html + "</div>";
    document.body.appendChild(m);
    var closed = false;
    function close() {
      if (closed) return;
      closed = true;
      document.removeEventListener("keydown", key);
      m.remove();
      onClose && onClose();
      prev && prev.focus && prev.focus();
    }
    function key(e) { if (e.key === "Escape") close(); }
    document.addEventListener("keydown", key);
    m.addEventListener("mousedown", function (e) { if (e.target === m) close(); });
    EK.$$("[data-close]", m).forEach(function (b) { b.addEventListener("click", close); });
    var first = EK.$("input, select, textarea, button", m);
    first && first.focus();
    return { el: m, close: close };
  };

  /* Bouton en attente */
  EK.busy = function (btn, on, label) {
    if (!btn) return;
    if (on) { btn.dataset.l = btn.innerHTML; btn.disabled = true; btn.innerHTML = '<span class="spin"></span>' + (label ? " " + esc(label) : ""); }
    else { btn.disabled = false; btn.innerHTML = btn.dataset.l || btn.innerHTML; }
  };

  EK.empty = function (icon, title, text, cta) {
    return '<div class="empty">' + EK.icon(icon) + "<strong>" + esc(title) + "</strong><p>" + esc(text || "") + "</p>" + (cta || "") + "</div>";
  };
  EK.skeleton = function (n) { return '<div class="grid grid--cards">' + new Array((n || 3) + 1).join('<div class="skel"></div>') + "</div>"; };

  /* Géolocalisation */
  EK.locate = function () {
    return new Promise(function (resolve, reject) {
      if (!navigator.geolocation) return reject(new Error("Géolocalisation indisponible sur cet appareil."));
      navigator.geolocation.getCurrentPosition(
        function (p) { resolve({ lat: p.coords.latitude, lng: p.coords.longitude }); },
        function () { reject(new Error("Position refusée. Placez le repère à la main sur la carte.")); },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 15000 }
      );
    });
  };

  /* Cartes Leaflet (centrées sur Cotonou par défaut) */
  EK.COTONOU = [6.3703, 2.3912];
  EK.makeMap = function (el, center, zoom) {
    if (!window.L) { el.innerHTML = '<div class="empty">La carte n\'a pas pu se charger.</div>'; return null; }
    var map = L.map(el, { zoomControl: true, attributionControl: true }).setView(center || EK.COTONOU, zoom || 13);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap" }).addTo(map);
    var gone = false;
    map.on("unload", function () { gone = true; });
    setTimeout(function () { if (!gone) map.invalidateSize(); }, 150);
    return map;
  };
  EK.pinIcon = function (label, gold) {
    return L.divIcon({ className: "", html: '<div class="pin' + (gold ? " pin--gold" : "") + '"><b>' + esc(label || "") + "</b></div>", iconSize: [26, 26], iconAnchor: [13, 26] });
  };
  EK.truckIcon = function () {
    return L.divIcon({ className: "", html: '<div class="truck">' + EK.icon("truck") + "</div>", iconSize: [32, 32], iconAnchor: [16, 16] });
  };
})();
