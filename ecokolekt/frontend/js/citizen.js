/* EcoKolekt — espace ménage : tableau de bord, demande de collecte, suivi, QR, points d'apport. */
(function () {
  "use strict";
  var EK = window.EK, esc = EK.esc, $ = EK.$, $$ = EK.$$, V = (EK.views = EK.views || {});

  EK.dot = function (c) { return '<span class="dot" style="background:' + esc(c || "#9aa39c") + '"></span>'; };

  EK.bars = function (rows) {
    var max = Math.max.apply(null, rows.map(function (r) { return Number(r.kg) || 0; }).concat([1]));
    if (!rows.length) return '<p class="muted">Rien de collecté pour le moment.</p>';
    return '<div class="bars">' + rows.map(function (r) {
      return '<div class="bar"><span>' + esc(r.category__name) + '</span><div class="track"><div class="fill" style="width:' + Math.round((Number(r.kg) / max) * 100) + "%;background:" + esc(r.category__color) + '"></div></div><b class="num">' + EK.fmt.kg(r.kg) + "</b></div>";
    }).join("") + "</div>";
  };

  EK.pickupCard = function (p, withActions) {
    var s = EK.pickupStatus[p.status] || [p.status, ""];
    var live = ["pending", "assigned", "en_route"].indexOf(p.status) >= 0;
    return '<article class="card stack" data-id="' + esc(p.id) + '"><div class="row row--between"><div class="row">' + EK.dot(p.category_detail && p.category_detail.color) +
      "<strong>" + esc(p.category_detail ? p.category_detail.name : "Déchets") + "</strong></div>" + EK.chip(s[0], s[1]) + "</div>" +
      '<div class="small muted">' + esc(p.address || "Position sur la carte") + " · ~" + EK.fmt.kg(p.estimated_weight_kg) + (p.actual_weight_kg ? " · pesé " + EK.fmt.kg(p.actual_weight_kg) : "") + "</div>" +
      '<div class="small muted">' + EK.fmt.date(p.created_at) + (p.points_awarded ? ' · <b style="color:var(--ok)">+' + p.points_awarded + " points</b>" : "") + "</div>" +
      (withActions && live ? '<div class="row row--wrap"><button class="btn btn--primary btn--sm" data-act="qr">' + EK.icon("qr") + ' Mon QR code</button>' +
        (p.status !== "pending" ? '<button class="btn btn--line btn--sm" data-act="track">' + EK.icon("truck") + " Suivre</button>" : "") +
        (p.status === "pending" || p.status === "assigned" ? '<button class="btn btn--danger btn--sm" data-act="cancel">Annuler</button>' : "") + "</div>" : "") + "</article>";
  };

  /* QR (le point d'accès exige le jeton : on récupère l'image en blob) */
  EK.showQR = function (p) {
    var m = EK.modal('<div class="row row--between"><h2>Code de collecte</h2><button class="btn btn--ghost btn--sm" data-close aria-label="Fermer">' + EK.icon("x") + "</button></div>" +
      '<div class="qrbox"><div class="skel" style="width:260px;height:260px"></div><p class="muted">Montrez ce code au collecteur à son arrivée. Il ne fonctionne qu\'une seule fois et seulement avec le collecteur assigné.</p></div>');
    var url;
    EK.api.blob("/waste/pickups/" + p.id + "/qr/").then(function (b) {
      url = URL.createObjectURL(b);
      $(".qrbox", m.el).innerHTML = '<img alt="QR code de votre collecte" src="' + url + '"><p class="muted">Montrez ce code au collecteur à son arrivée. Usage unique, valable uniquement avec le collecteur assigné.</p>';
    }).catch(function () { $(".qrbox", m.el).innerHTML = "<p>Ce code n'est plus actif.</p>"; });
    var close = m.close;
    m.close = function () { url && URL.revokeObjectURL(url); close(); };
  };

  EK.trackPickup = function (p) {
    var timer, map, truck, home;
    var m = EK.modal('<div class="row row--between"><h2>Suivi du collecteur</h2><button class="btn btn--ghost btn--sm" data-close aria-label="Fermer">' + EK.icon("x") + "</button></div>" +
      '<div id="tm" class="map"></div><div id="ti" class="muted">Recherche de la position…</div>', function () { clearInterval(timer); map && map.remove(); map = truck = home = null; });
    map = EK.makeMap($("#tm", m.el), [p.lat, p.lng], 14);
    if (map) home = L.marker([p.lat, p.lng], { icon: EK.pinIcon("⌂") }).addTo(map);
    function poll() {
      EK.api.get("/waste/pickups/" + p.id + "/tracking/").then(function (t) {
        var c = t.collector, info = $("#ti", m.el);
        if (!info) return;
        if (!c || c.lat == null) { info.textContent = "Collecteur pas encore en route."; return; }
        info.innerHTML = "<b>" + esc(c.name || "Votre collecteur") + "</b> · à " + EK.fmt.dist(c.distance_m) + (c.eta_seconds != null ? " · arrivée ~" + EK.fmt.dur(c.eta_seconds) : "") + (c.stops_before ? " · " + c.stops_before + " arrêt(s) avant vous" : "");
        if (map) {
          if (!truck) truck = L.marker([c.lat, c.lng], { icon: EK.truckIcon() }).addTo(map); else truck.setLatLng([c.lat, c.lng]);
          map.fitBounds(L.latLngBounds([[c.lat, c.lng], [p.lat, p.lng]]), { padding: [40, 40], maxZoom: 16 });
        }
        if (t.status === "collected") { info.textContent = "Collecte terminée. Merci !"; clearInterval(timer); }
      }).catch(function () { /* on réessaie au prochain tour */ });
    }
    poll(); timer = setInterval(poll, 12000);
  };

  function bindPickupActions(root, items, reload) {
    $$("[data-act]", root).forEach(function (b) {
      b.onclick = function () {
        var id = b.closest("[data-id]").dataset.id;
        var p = items.filter(function (x) { return x.id === id; })[0];
        if (b.dataset.act === "qr") EK.showQR(p);
        else if (b.dataset.act === "track") EK.trackPickup(p);
        else if (b.dataset.act === "cancel" && confirm("Annuler cette demande de collecte ?")) {
          EK.api.post("/waste/pickups/" + id + "/cancel/").then(function () { EK.toast("Demande annulée."); reload(); }).catch(EK.fail);
        }
      };
    });
  }

  /* ---- Tableau de bord ménage ---- */
  V.citizenHome = function (el) {
    el.innerHTML = EK.skeleton(3);
    Promise.all([EK.api.get("/waste/pickups/summary/"), EK.api.get("/waste/pickups/", { page_size: 4 })]).then(function (r) {
      var s = r[0], items = EK.api.items(r[1]).slice(0, 4), u = EK.session.user;
      var first = (u.full_name || "").split(" ")[0];
      el.innerHTML = '<div class="hero-card"><h1>Bonjour' + (first ? " " + esc(first) : "") + "</h1><p>Un sac prêt à partir ? Un collecteur proche de chez vous passe le récupérer.</p>" +
        '<a class="btn btn--gold" href="#/request">' + EK.icon("plus") + " Demander une collecte</a></div>" +
        '<div class="grid grid--kpi"><div class="kpi kpi--hero"><span class="v num">' + EK.fmt.n(s.eco_points) + '</span><span class="l">points éco</span></div>' +
        '<div class="kpi"><span class="v num">' + EK.fmt.n(s.kg_collected) + '</span><span class="l">kg collectés</span></div>' +
        '<div class="kpi"><span class="v num">' + s.collected + '</span><span class="l">collectes réussies</span></div>' +
        '<div class="kpi"><span class="v num">' + s.requests_total + '</span><span class="l">demandes au total</span></div></div>' +
        '<div class="grid grid--2"><section class="card"><h2>Ce que vous triez</h2><p class="muted small" style="margin-bottom:14px">Poids collecté par catégorie</p>' + EK.bars(s.kg_by_category) + "</section>" +
        '<section class="card"><div class="row row--between"><h2>Dernières demandes</h2><a href="#/pickups" class="small"><b>Tout voir</b></a></div><div class="list" id="rec">' +
        (items.length ? items.map(function (p) {
          var st = EK.pickupStatus[p.status] || [p.status, ""];
          return '<div class="item">' + EK.dot(p.category_detail && p.category_detail.color) + '<div class="grow"><div class="t">' + esc(p.category_detail ? p.category_detail.name : "") + '</div><div class="s">' + EK.fmt.date(p.created_at) + "</div></div>" + EK.chip(st[0], st[1]) + "</div>";
        }).join("") : EK.empty("leaf", "Aucune demande pour l'instant", "Votre première collecte prend moins d'une minute.")) + "</div></section></div>";
    }).catch(function (e) { el.innerHTML = EK.empty("x", "Chargement impossible", e.message); });
  };

  /* ---- Nouvelle demande ---- */
  V.request = function (el) {
    var u = EK.session.user;
    var st = { cat: null, w: 10, pos: u.latitude != null ? { lat: u.latitude, lng: u.longitude } : null, cats: [] }, map, marker;
    el.innerHTML = '<div class="page-head"><div><h1>Demander une collecte</h1><p>Trois informations suffisent.</p></div></div><div id="rq">' + EK.skeleton(2) + "</div>";
    EK.api.get("/waste/categories/").then(function (cats) {
      st.cats = EK.api.items(cats);
      $("#rq").innerHTML = '<form class="grid grid--2" id="f" novalidate>' +
        '<div class="stack"><section class="card stack"><h2>1. Que souhaitez-vous faire collecter ?</h2><div class="cats" id="cats">' +
        st.cats.map(function (c) { return '<button type="button" class="cat" data-id="' + c.id + '" aria-pressed="false">' + EK.dot(c.color) + esc(c.name) + "</button>"; }).join("") + "</div>" +
        '<div class="small muted" id="pts"></div></section>' +
        '<section class="card stack"><h2>2. Quel poids environ ?</h2><div class="pills" id="wp">' + [5, 10, 20, 50, 100].map(function (w) { return '<button type="button" class="pill" data-w="' + w + '" aria-pressed="' + (w === 10) + '">' + w + " kg</button>"; }).join("") + "</div>" +
        '<div class="field"><label for="w">Ou précisez</label><input class="input" id="w" type="number" min="0.5" max="500" step="0.5" value="10" inputmode="decimal"></div></section></div>' +
        '<div class="stack"><section class="card stack"><h2>3. Où passer ?</h2><div id="map" class="map"></div>' +
        '<div class="row row--wrap"><button type="button" class="btn btn--line btn--sm" id="me">' + EK.icon("pin") + ' Ma position</button><span class="hint">Touchez la carte ou glissez le repère.</span></div>' +
        '<div class="field"><label for="ad">Repère (rue, portail, couleur…)</label><input class="input" id="ad" maxlength="255" placeholder="Ex. Cadjèhoun, portail vert face à la pharmacie"></div>' +
        '<div class="field"><label for="nt">Un mot pour le collecteur (facultatif)</label><input class="input" id="nt" maxlength="300"></div></section>' +
        '<div class="err" id="e" aria-live="polite"></div><button class="btn btn--primary btn--lg btn--block" id="go">Envoyer ma demande</button></div></form>';
      initMap(); bind();
    }).catch(function (e) { $("#rq").innerHTML = EK.empty("x", "Chargement impossible", e.message); });

    function setPos(p, recenter) {
      st.pos = p;
      if (!map) return;
      if (marker) marker.setLatLng([p.lat, p.lng]);
      if (map && recenter) map.setView([p.lat, p.lng], 16);
    }
    function initMap() {
      var c = st.pos ? [st.pos.lat, st.pos.lng] : EK.COTONOU;
      map = EK.makeMap($("#map"), c, st.pos ? 16 : 13);
      if (!map) return;
      if (!st.pos) st.pos = { lat: c[0], lng: c[1] };
      marker = L.marker(c, { draggable: true, icon: EK.pinIcon("⌂", true) }).addTo(map);
      marker.on("dragend", function () { var l = marker.getLatLng(); st.pos = { lat: l.lat, lng: l.lng }; });
      map.on("click", function (e) { setPos({ lat: e.latlng.lat, lng: e.latlng.lng }); });
    }
    function bind() {
      $$(".cat").forEach(function (b) {
        b.onclick = function () {
          st.cat = st.cats.filter(function (c) { return String(c.id) === b.dataset.id; })[0];
          $$(".cat").forEach(function (x) { x.setAttribute("aria-pressed", x === b); });
          refreshPts();
        };
      });
      $$("#wp .pill").forEach(function (b) {
        b.onclick = function () { $("#w").value = b.dataset.w; sync(); };
      });
      $("#w").oninput = sync;
      $("#me").onclick = function () { EK.locate().then(function (p) { setPos(p, true); }).catch(EK.fail); };
      $("#f").onsubmit = submit;
      if (!st.pos) EK.locate().then(function (p) { setPos(p, true); }).catch(function () { /* position manuelle */ });
    }
    function sync() {
      st.w = parseFloat($("#w").value) || 0;
      $$("#wp .pill").forEach(function (b) { b.setAttribute("aria-pressed", Number(b.dataset.w) === st.w); });
      refreshPts();
    }
    function refreshPts() {
      $("#pts").textContent = st.cat && st.w ? "Points prévus : environ " + Math.round(st.cat.points_per_kg * st.w) + " une fois la collecte validée." : "";
    }
    function submit(ev) {
      ev.preventDefault();
      var e = $("#e"); e.textContent = "";
      if (!st.cat) { e.textContent = "Choisissez une catégorie."; return; }
      if (!(st.w > 0 && st.w <= 500)) { e.textContent = "Indiquez un poids entre 0,5 et 500 kg."; return; }
      if (!st.pos) { e.textContent = "Placez le repère sur la carte."; return; }
      var btn = $("#go"); EK.busy(btn, true, "Envoi…");
      EK.api.post("/waste/pickups/", {
        category: st.cat.id, estimated_weight_kg: st.w, address: $("#ad").value.trim(), notes: $("#nt").value.trim(),
        latitude: Number(st.pos.lat.toFixed(6)), longitude: Number(st.pos.lng.toFixed(6)),
      }).then(function (p) {
        EK.toast(p.status === "assigned" ? "Un collecteur est assigné." : "Demande envoyée, nous cherchons un collecteur.");
        location.hash = "#/pickups";
        setTimeout(function () { EK.showQR(p); }, 300);
      }).catch(function (er) { EK.busy(btn, false); e.textContent = er.message; });
    }
    return function () { map && map.remove(); map = marker = null; };
  };

  /* ---- Mes collectes ---- */
  V.pickups = function (el) {
    var filter = "";
    el.innerHTML = '<div class="page-head"><div><h1>Mes collectes</h1><p>Suivez vos demandes et présentez votre QR code.</p></div><a class="btn btn--primary" href="#/request">' + EK.icon("plus") + ' Nouvelle demande</a></div>' +
      '<div class="pills" id="fl">' + [["", "Toutes"], ["pending", "En attente"], ["assigned", "Assignées"], ["en_route", "En route"], ["collected", "Collectées"]].map(function (f) { return '<button class="pill" data-f="' + f[0] + '" aria-pressed="' + (f[0] === "") + '">' + f[1] + "</button>"; }).join("") + '</div><div id="ls">' + EK.skeleton(3) + "</div>";
    function load() {
      EK.api.get("/waste/pickups/", { status: filter }).then(function (d) {
        var items = EK.api.items(d), box = $("#ls");
        if (!box) return;
        box.innerHTML = items.length ? '<div class="grid grid--cards">' + items.map(function (p) { return EK.pickupCard(p, true); }).join("") + "</div>" : EK.empty("leaf", "Aucune collecte ici", "Vos demandes apparaîtront dans cette liste.", '<a class="btn btn--primary" href="#/request">Demander une collecte</a>');
        bindPickupActions(box, items, load);
      }).catch(function (e) { $("#ls").innerHTML = EK.empty("x", "Chargement impossible", e.message); });
    }
    $$("#fl .pill").forEach(function (b) { b.onclick = function () { filter = b.dataset.f; $$("#fl .pill").forEach(function (x) { x.setAttribute("aria-pressed", x === b); }); load(); }; });
    load();
    var t = setInterval(load, 20000);
    return function () { clearInterval(t); };
  };

  /* ---- Points d'apport ---- */
  V.points = function (el) {
    var map;
    el.innerHTML = '<div class="page-head"><div><h1>Points d\'apport</h1><p>Bacs de quartier, centres de tri et points d\'apport volontaire.</p></div></div><div id="map" class="map map--tall"></div><div id="ls" class="card"></div>';
    var u = EK.session.user, c = u.latitude != null ? [u.latitude, u.longitude] : EK.COTONOU;
    map = EK.makeMap($("#map"), c, 13);
    EK.api.get("/waste/points/", { lat: c[0], lng: c[1] }).then(function (pts) {
      pts = EK.api.items(pts);
      if (!map) return;
      pts.forEach(function (p) { L.marker([p.latitude, p.longitude], { icon: EK.pinIcon("♻") }).addTo(map).bindPopup("<b>" + esc(p.name) + "</b><br>" + esc(p.address)); });
      if (!$("#ls")) return;
      $("#ls").innerHTML = '<div class="list">' + pts.map(function (p) {
        return '<div class="item"><div class="seq">' + EK.icon("pin") + '</div><div class="grow"><div class="t">' + esc(p.name) + '</div><div class="s">' + esc(p.address) + " · " + p.categories.map(function (k) { return esc(k.name.split(" ")[0]); }).join(", ") + "</div></div><b class=\"num\">" + EK.fmt.dist(p.distance_m) + "</b></div>";
      }).join("") + "</div>";
    }).catch(function (e) { var b = $("#ls"); b && (b.innerHTML = EK.empty("x", "Chargement impossible", e.message)); });
    return function () { map && map.remove(); map = null; };
  };
})();
