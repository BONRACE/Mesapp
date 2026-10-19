/* EcoKolekt — espace collecteur : service GPS, tournée dynamique, demandes proches, scan de QR. */
(function () {
  "use strict";
  var EK = window.EK, esc = EK.esc, $ = EK.$, $$ = EK.$$, V = (EK.views = EK.views || {});

  /* Suivi GPS partagé (une seule instance, même si l'on change de page) */
  var gps = (EK.gps = { pos: null, watch: null, timer: null, on: false });
  function push(onDuty) {
    var p = gps.pos || (EK.session.user && EK.session.user.latitude != null ? { lat: EK.session.user.latitude, lng: EK.session.user.longitude } : null);
    if (!p) return Promise.resolve();
    return EK.api.post("/me/location/", { latitude: p.lat, longitude: p.lng, is_on_duty: onDuty });
  }
  gps.start = function () {
    gps.on = true;
    if (navigator.geolocation && gps.watch == null) {
      gps.watch = navigator.geolocation.watchPosition(function (x) { gps.pos = { lat: x.coords.latitude, lng: x.coords.longitude }; }, function () { /* position indisponible */ }, { enableHighAccuracy: true, maximumAge: 10000 });
    }
    clearInterval(gps.timer);
    gps.timer = setInterval(function () { push(true).catch(function () { /* réseau instable : on réessaie */ }); }, 20000);
    return push(true);
  };
  gps.stop = function () {
    gps.on = false;
    clearInterval(gps.timer);
    if (gps.watch != null && navigator.geolocation) navigator.geolocation.clearWatch(gps.watch);
    gps.watch = null;
    return push(false);
  };

  /* ---- Scan de QR ---- */
  EK.scanModal = function (onDone, presetKg) {
    var stream, timer, detector = window.BarcodeDetector ? new window.BarcodeDetector({ formats: ["qr_code"] }) : null;
    function stopCam() { clearInterval(timer); stream && stream.getTracks().forEach(function (t) { t.stop(); }); stream = null; }
    var m = EK.modal('<div class="row row--between"><h2>Valider une collecte</h2><button class="btn btn--ghost btn--sm" data-close aria-label="Fermer">' + EK.icon("x") + "</button></div>" +
      (detector ? '<div class="scan"><video id="vid" playsinline muted></video></div><p class="hint" id="sh">Cadrez le QR code du ménage.</p>' : '<p class="hint">Scanner indisponible sur ce navigateur : saisissez le code affiché sous le QR.</p>') +
      '<form id="f" class="stack" novalidate><div class="field"><label for="tk">Code du QR</label><input class="input" id="tk" autocomplete="off" autocapitalize="off" placeholder="EK1.…" required></div>' +
      '<div class="field"><label for="kg">Poids réel pesé (kg)</label><input class="input" id="kg" type="number" min="0.1" step="0.1" inputmode="decimal" value="' + (presetKg || "") + '" required></div>' +
      '<div class="err" id="e" aria-live="polite"></div><button class="btn btn--primary btn--lg btn--block" id="go">Valider et créditer le ménage</button></form>', stopCam);
    if (detector && navigator.mediaDevices) {
      navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } }).then(function (s) {
        stream = s; var v = $("#vid", m.el); if (!v) return stopCam();
        v.srcObject = s; v.play();
        timer = setInterval(function () {
          detector.detect(v).then(function (r) {
            if (r && r[0]) { $("#tk", m.el).value = r[0].rawValue; $("#sh", m.el).textContent = "Code lu. Entrez le poids."; stopCam(); $("#kg", m.el).focus(); }
          }).catch(function () { /* image non prête */ });
        }, 400);
      }).catch(function () { var h = $("#sh", m.el); h && (h.textContent = "Caméra refusée : saisissez le code à la main."); });
    }
    $("#f", m.el).onsubmit = function (ev) {
      ev.preventDefault();
      var btn = $("#go", m.el), err = $("#e", m.el); err.textContent = "";
      var body = { token: $("#tk", m.el).value.trim(), weight_kg: $("#kg", m.el).value };
      var p = gps.pos;
      if (!p) { err.textContent = "Position GPS indisponible : activez la localisation pour valider la collecte."; return; }
      body.latitude = p.lat; body.longitude = p.lng;
      EK.busy(btn, true, "Validation…");
      EK.api.post("/waste/pickups/scan/", body).then(function (d) {
        EK.toast("Collecte validée : " + EK.fmt.kg(d.pickup.actual_weight_kg) + (d.pickup.points_awarded ? " · +" + d.pickup.points_awarded + " points pour le ménage" : "") + ".");
        m.close(); onDone && onDone(d);
      }).catch(function (e) { EK.busy(btn, false); err.textContent = e.message; });
    };
  };

  /* ---- Tournée ---- */
  V.collectorHome = function (el) {
    var map, layer, driver, destroyed = false;
    var me = EK.session.user, onDuty = !!(me.collector && me.collector.is_on_duty);
    el.innerHTML = '<div class="page-head"><div><h1>Ma tournée</h1><p id="sub">Calcul de l\'itinéraire…</p></div>' +
      '<label class="row" style="cursor:pointer"><span class="switch"><input type="checkbox" id="duty" role="switch" aria-label="En service"' + (onDuty ? " checked" : "") + '></span><b id="dl">' + (onDuty ? "En service" : "Hors service") + "</b></label></div>" +
      '<div id="kp" class="grid grid--kpi"></div><div class="grid grid--2"><div id="map" class="map map--tall"></div><section class="card"><div class="row row--between"><h2>Arrêts</h2><div class="row"><button class="btn btn--line btn--sm" id="re">' + EK.icon("sync") + ' Recalculer</button><button class="btn btn--primary btn--sm" id="sc">' + EK.icon("scan") + " Scanner</button></div></div><div id=\"st\" class=\"list\">" + EK.skeleton(1) + "</div></section></div>";
    map = EK.makeMap($("#map"), me.latitude != null ? [me.latitude, me.longitude] : EK.COTONOU, 13);
    if (map) layer = L.layerGroup().addTo(map);

    if (onDuty) gps.start().catch(function () { /* ignore */ });
    $("#duty").onchange = function () {
      var on = this.checked;
      var go = on ? EK.locate().then(function (p) { gps.pos = p; return gps.start(); }).catch(function () { return gps.start(); }) : gps.stop();
      go.then(function () { $("#dl").textContent = on ? "En service" : "Hors service"; EK.toast(on ? "Vous recevez maintenant des demandes." : "Vous ne recevez plus de demandes."); if (on) load(); })
        .catch(function (e) { EK.fail(e); $("#duty").checked = !on; });
    };
    $("#re").onclick = load;
    $("#sc").onclick = function () { EK.scanModal(load); };

    function kpis() {
      EK.api.get("/waste/pickups/summary/").then(function (s) {
        $("#kp").innerHTML = '<div class="kpi kpi--hero"><span class="v num">' + s.collected_today + '</span><span class="l">collectes aujourd\'hui</span></div><div class="kpi"><span class="v num">' + EK.fmt.n(s.kg_today) + '</span><span class="l">kg aujourd\'hui</span></div>' +
          '<div class="kpi"><span class="v num">' + s.active + '</span><span class="l">arrêts à faire</span></div><div class="kpi"><span class="v num">' + EK.fmt.n(s.kg_total) + '</span><span class="l">kg au total</span></div>';
      }).catch(function () { /* indicateurs facultatifs */ });
    }
    function draw(route) {
      if (!map) return;
      layer.clearLayers();
      var pts = [];
      if (route.origin) { L.marker([route.origin.lat, route.origin.lng], { icon: EK.truckIcon() }).addTo(layer); pts.push([route.origin.lat, route.origin.lng]); }
      if (route.geometry && route.geometry.coordinates) {
        var line = route.geometry.coordinates.map(function (c) { return [c[1], c[0]]; });
        L.polyline(line, { color: "#0b4a32", weight: 6, opacity: 0.85 }).addTo(layer);
        L.polyline(line, { color: "#d4a62f", weight: 2.5, dashArray: "2 8" }).addTo(layer);
      }
      route.stops.forEach(function (s) {
        var ll = [s.pickup.lat, s.pickup.lng]; pts.push(ll);
        L.marker(ll, { icon: EK.pinIcon(String(s.sequence), s.over_capacity) }).addTo(layer).bindPopup(esc(s.pickup.address || "Arrêt " + s.sequence));
      });
      if (pts.length) map.fitBounds(L.latLngBounds(pts), { padding: [40, 40], maxZoom: 16 });
    }
    function load() {
      kpis();
      EK.api.get("/routing/route/").then(function (r) {
        if (destroyed) return;
        draw(r);
        $("#sub").textContent = r.stops.length ? r.stops.length + " arrêt(s) · " + EK.fmt.dist(r.total_distance_m) + " · ~" + EK.fmt.dur(r.total_duration_s) + (r.engine === "osrm" ? " (routes réelles)" : " (estimation)") : "Aucun arrêt pour le moment.";
        $("#st").innerHTML = r.stops.length ? r.stops.map(function (s) {
          var p = s.pickup, cat = p.category_detail || {};
          return '<div class="item" data-id="' + esc(p.id) + '"><div class="seq' + (s.over_capacity ? " seq--warn" : "") + '">' + s.sequence + '</div><div class="grow"><div class="t">' + EK.dot(cat.color) + " " + esc(cat.name || "") + " · ~" + EK.fmt.kg(p.estimated_weight_kg) + '</div><div class="s">' + esc(p.address || p.citizen_name || "") + " · " + EK.fmt.dist(s.leg_distance_m) + " · arrivée ~" + EK.fmt.dur(s.eta_seconds) + (s.over_capacity ? " · <b style=\"color:var(--danger)\">dépasse la capacité</b>" : "") + "</div></div>" +
            '<div class="row">' + (p.citizen_phone ? '<a class="btn btn--ghost btn--sm" href="tel:' + esc(p.citizen_phone) + '" aria-label="Appeler">' + EK.icon("phone") + "</a>" : "") +
            (p.status === "assigned" ? '<button class="btn btn--line btn--sm" data-start>Démarrer</button>' : '<button class="btn btn--primary btn--sm" data-scan="' + esc(p.estimated_weight_kg) + '">Scanner</button>') + "</div></div>";
        }).join("") : EK.empty("route", "Pas d'arrêt", "Mettez-vous en service ou acceptez une demande proche.", '<a class="btn btn--primary btn--sm" href="#/available">Voir les demandes</a>');
        $$("[data-start]").forEach(function (b) { b.onclick = function () { EK.api.post("/waste/pickups/" + b.closest("[data-id]").dataset.id + "/start/").then(load).catch(EK.fail); }; });
        $$("[data-scan]").forEach(function (b) { b.onclick = function () { EK.scanModal(load, b.dataset.scan); }; });
      }).catch(function (e) { $("#sub").textContent = e.message; $("#st").innerHTML = ""; });
    }
    load();
    driver = setInterval(load, 45000);
    return function () { destroyed = true; clearInterval(driver); map && map.remove(); map = layer = null; };
  };

  /* ---- Demandes à prendre ---- */
  V.available = function (el) {
    el.innerHTML = '<div class="page-head"><div><h1>Demandes proches</h1><p>Prenez en charge une demande : elle s\'ajoute à votre tournée.</p></div><button class="btn btn--line" id="rf">' + EK.icon("sync") + ' Actualiser</button></div><div id="ls">' + EK.skeleton(3) + "</div>";
    function load() {
      EK.api.get("/waste/pickups/available/").then(function (d) {
        var items = EK.api.items(d);
        $("#ls").innerHTML = items.length ? '<div class="grid grid--cards">' + items.map(function (p) {
          return '<article class="card stack" data-id="' + esc(p.id) + '"><div class="row row--between"><div class="row">' + EK.dot(p.category_detail.color) + "<strong>" + esc(p.category_detail.name) + "</strong></div>" + (p.distance_m != null ? EK.chip(EK.fmt.dist(p.distance_m)) : "") + "</div>" +
            '<div class="small muted">' + esc(p.address || "Voir sur la carte") + " · ~" + EK.fmt.kg(p.estimated_weight_kg) + '</div><button class="btn btn--primary btn--sm" data-acc>Prendre en charge</button></article>';
        }).join("") + "</div>" : EK.empty("check", "Aucune demande en attente", "Revenez dans un instant, ou passez en service pour être notifié par la tournée.");
        $$("[data-acc]").forEach(function (b) {
          b.onclick = function () {
            EK.busy(b, true);
            EK.api.post("/waste/pickups/" + b.closest("[data-id]").dataset.id + "/accept/").then(function () { EK.toast("Ajouté à votre tournée."); location.hash = "#/"; })
              .catch(function (e) { EK.busy(b, false); EK.fail(e); load(); });
          };
        });
      }).catch(function (e) { $("#ls").innerHTML = EK.empty("x", "Chargement impossible", e.message); });
    }
    $("#rf").onclick = load; load();
  };
})();
