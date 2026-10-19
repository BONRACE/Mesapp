/* EcoKolekt — administration : indicateurs, validation des professionnels, carte des collecteurs en direct. */
(function () {
  "use strict";
  var EK = window.EK, esc = EK.esc, $ = EK.$, $$ = EK.$$, V = (EK.views = EK.views || {});

  V.admin = function (el) {
    var map, layer, timer;
    el.innerHTML = '<div class="page-head"><div><h1>Pilotage</h1><p>Vue d\'ensemble de la collecte et du marché.</p></div><button class="btn btn--line" id="aa">' + EK.icon("sync") + ' Affecter les demandes en attente</button></div>' +
      '<div id="kp" class="grid grid--kpi">' + EK.skeleton(1) + '</div><div class="grid grid--2"><section class="card"><h2>Collecté par catégorie</h2><p class="muted small" style="margin-bottom:14px">Poids validé par scan de QR</p><div id="bk"></div></section>' +
      '<section class="card"><div class="row row--between"><h2>Profils à valider</h2><span id="pc" class="chip"></span></div><div id="ap" class="list"></div></section></div>' +
      '<section class="card card--pad0"><div style="padding:20px 20px 0"><h2>Collecteurs en service</h2><p class="muted small" id="lc"></p></div><div id="map" class="map map--tall" style="border:0;border-radius:0;margin-top:12px"></div></section>';
    map = EK.makeMap($("#map"), EK.COTONOU, 12);
    if (map) layer = L.layerGroup().addTo(map);

    $("#aa").onclick = function () {
      var b = this; EK.busy(b, true);
      EK.api.post("/waste/pickups/auto-assign/").then(function (r) { EK.busy(b, false); EK.toast(r.assigned + " demande(s) affectée(s)."); stats(); live(); }).catch(function (e) { EK.busy(b, false); EK.fail(e); });
    };
    function stats() {
      EK.api.get("/admin/stats/").then(function (s) {
        var u = s.users || {}, pk = s.pickups_by_status || {};
        $("#kp").innerHTML = '<div class="kpi kpi--hero"><span class="v num">' + EK.fmt.n(s.kg_collected) + '</span><span class="l">kg collectés</span></div>' +
          '<div class="kpi"><span class="v num">' + EK.fmt.n((u.citizen || 0)) + '</span><span class="l">ménages inscrits</span></div><div class="kpi"><span class="v num">' + EK.fmt.n(u.collector || 0) + '</span><span class="l">collecteurs</span></div>' +
          '<div class="kpi"><span class="v num">' + (pk.pending || 0) + '</span><span class="l">demandes en attente</span></div><div class="kpi"><span class="v num">' + EK.fmt.n(s.market.gmv_xof) + '</span><span class="l">FCFA échangés</span></div><div class="kpi"><span class="v num">' + EK.fmt.n(s.market.commission_xof) + '</span><span class="l">FCFA de commission</span></div>';
        $("#bk").innerHTML = EK.bars(s.kg_by_category);
      }).catch(function (e) { $("#kp").innerHTML = EK.empty("x", "Chargement impossible", e.message); });
    }
    function approvals() {
      EK.api.get("/admin/users/", { is_approved: "false" }).then(function (d) {
        var items = EK.api.items(d);
        $("#pc").textContent = items.length;
        $("#ap").innerHTML = items.length ? items.map(function (u) {
          return '<div class="item" data-id="' + esc(u.id) + '"><div class="avatar">' + esc(EK.fmt.initials(u.full_name)) + '</div><div class="grow"><div class="t">' + esc(u.full_name || u.phone) + '</div><div class="s">' + esc(EK.roleLabel[u.role] || u.role) + " · " + esc(u.phone) + '</div></div><button class="btn btn--primary btn--sm" data-ok>Valider</button></div>';
        }).join("") : EK.empty("check", "Tout est à jour", "Aucun profil en attente.");
        $$("[data-ok]").forEach(function (b) { b.onclick = function () { EK.api.post("/admin/users/" + b.closest("[data-id]").dataset.id + "/approve/", { approved: true }).then(function () { EK.toast("Profil validé."); approvals(); stats(); }).catch(EK.fail); }; });
      }).catch(function () { $("#ap").innerHTML = ""; });
    }
    function live() {
      EK.api.get("/routing/collectors/live/").then(function (rows) {
        if (!map) return;
        $("#lc").textContent = rows.length + " collecteur(s) en service";
        layer.clearLayers();
        var pts = rows.map(function (c) {
          var ll = [c.lat, c.lng];
          L.marker(ll, { icon: EK.truckIcon(), opacity: c.stale ? 0.5 : 1 }).addTo(layer).bindPopup("<b>" + esc(c.name || "Collecteur") + "</b><br>" + c.active_pickups + " arrêt(s) · capacité " + EK.fmt.kg(c.capacity_kg) + (c.stale ? "<br>Position ancienne" : ""));
          return ll;
        });
        if (pts.length) map.fitBounds(L.latLngBounds(pts), { padding: [40, 40], maxZoom: 14 });
      }).catch(function () { /* carte facultative */ });
    }
    stats(); approvals(); live();
    timer = setInterval(live, 20000);
    return function () { clearInterval(timer); map && map.remove(); map = layer = null; };
  };
})();
