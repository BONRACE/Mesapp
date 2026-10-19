/* EcoKolekt — routeur (hash), coque de l'application et navigation par rôle. */
(function () {
  "use strict";
  var EK = window.EK, esc = EK.esc, $ = EK.$, V = EK.views;
  var root = $("#app"), cleanup = null, shellFor = null;

  /* Navigation par rôle : [chemin, libellé, icône] */
  var NAV = {
    citizen: [["/", "Accueil", "home"], ["/request", "Demander", "plus"], ["/pickups", "Mes collectes", "list", "Collectes"], ["/points", "Points d'apport", "pin", "Points"]],
    collector: [["/", "Ma tournée", "route", "Tournée"], ["/available", "Demandes", "list"], ["/market", "Marché", "market"], ["/sell", "Mes annonces", "wallet", "Annonces"], ["/orders", "Commandes", "orders"]],
    recycler: [["/", "Accueil", "home"], ["/market", "Marché", "market"], ["/sell", "Mes annonces", "wallet", "Annonces"], ["/orders", "Commandes", "orders"]],
    admin: [["/", "Pilotage", "chart"], ["/market", "Marché", "market"], ["/orders", "Commandes", "orders"]],
  };
  var PUBLIC = /^\/(login|signup)$/;

  EK.logout = function () {
    var stop = EK.gps && EK.gps.on ? EK.gps.stop() : Promise.resolve();
    Promise.resolve(stop).catch(function () { /* hors ligne : on se déconnecte quand même */ }).then(function () {
      EK.session.clear(); shellFor = null; location.hash = "#/login";
    });
  };
  EK.onLogout = function () { shellFor = null; location.hash = "#/login"; };

  function parse() {
    var h = location.hash.replace(/^#/, "") || "/";
    var i = h.indexOf("?"), path = i < 0 ? h : h.slice(0, i), query = {};
    if (i >= 0) new URLSearchParams(h.slice(i + 1)).forEach(function (v, k) { query[k] = v; });
    return { path: path || "/", query: query, params: [] };
  }

  function drawShell(u) {
    var items = NAV[u.role] || NAV.citizen;
    var links = items.map(function (n) { return '<a href="#' + n[0] + '" data-p="' + n[0] + '">' + EK.icon(n[2]) + "<span>" + n[1] + "</span></a>"; }).join("");
    var tabs = items.slice(0, 5).map(function (n) { return '<a href="#' + n[0] + '" data-p="' + n[0] + '">' + EK.icon(n[2]) + "<span>" + (n[3] || n[1].split(" ")[0]) + "</span></a>"; }).join("");
    root.innerHTML = '<div class="shell"><aside class="side"><a class="brand" href="index.html">' + EK.logo + "EcoKolekt</a><nav class=\"nav\" aria-label=\"Navigation\">" + links + "</nav>" +
      '<div class="side__user"><div class="avatar">' + esc(EK.fmt.initials(u.full_name || u.phone)) + '</div><div class="grow" style="min-width:0"><b style="display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + esc(u.full_name || u.phone) + "</b><small>" + esc(EK.roleLabel[u.role]) + '</small></div><button id="lo" aria-label="Se déconnecter" title="Se déconnecter">' + EK.icon("out") + "</button></div></aside>" +
      '<main class="main" id="main" tabindex="-1"><div class="mobile-top"><a class="brand" href="index.html">' + EK.logo + "EcoKolekt</a><button id=\"lo2\" aria-label=\"Se déconnecter\">" + EK.icon("out") + '</button></div><div id="view"></div></main>' +
      '<nav class="tabbar" aria-label="Navigation">' + tabs + "</nav></div>";
    $("#lo").onclick = $("#lo2").onclick = EK.logout;
    shellFor = u.id;
  }

  function markActive(path) {
    EK.$$("[data-p]").forEach(function (a) {
      var p = a.dataset.p, on = p === "/" ? path === "/" : path === p || path.indexOf(p + "/") === 0;
      if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
  }

  /* Accueil recycleur */
  V.recyclerHome = function (el) {
    el.innerHTML = EK.skeleton(3);
    Promise.all([EK.api.get("/market/earnings/"), EK.api.get("/market/orders/"), EK.api.get("/market/prices/", null, { auth: false })]).then(function (r) {
      var e = r[0], orders = EK.api.items(r[1]).slice(0, 5), prices = r[2], u = EK.session.user;
      el.innerHTML = '<div class="hero-card"><h1>' + esc((u.recycler && u.recycler.company_name) || u.full_name || "Bienvenue") + "</h1><p>Approvisionnez-vous en matières triées auprès des collecteurs de Cotonou, payez en Mobile Money.</p>" +
        '<a class="btn btn--gold" href="#/market">' + EK.icon("market") + " Parcourir le marché</a></div>" +
        '<div class="grid grid--kpi"><div class="kpi kpi--hero"><span class="v num">' + EK.fmt.n(e.net_xof) + '</span><span class="l">FCFA nets de ventes</span></div><div class="kpi"><span class="v num">' + EK.fmt.n(e.kg_sold) + '</span><span class="l">kg vendus</span></div><div class="kpi"><span class="v num">' + e.to_ship + '</span><span class="l">à expédier</span></div><div class="kpi"><span class="v num">' + e.active_listings + '</span><span class="l">annonces actives</span></div></div>' +
        '<div class="grid grid--2"><section class="card"><h2>Cours du jour</h2><div class="list">' + (prices.length ? prices.map(function (p) { return '<div class="item">' + EK.dot(p.color) + '<div class="grow t">' + esc(p.name) + '</div><b class="num">' + EK.fmt.fcfa(p.avg_price) + '/kg</b></div>'; }).join("") : '<p class="muted">Aucune annonce active.</p>') + "</div></section>" +
        '<section class="card"><div class="row row--between"><h2>Dernières commandes</h2><a class="small" href="#/orders"><b>Tout voir</b></a></div><div class="list">' + (orders.length ? orders.map(function (o) { return '<div class="item"><div class="grow"><div class="t">' + esc(o.listing_title) + '</div><div class="s">' + EK.fmt.kg(o.quantity_kg) + " · " + EK.fmt.fcfa(o.total) + "</div></div>" + EK.chip(o.status_label, EK.orderStatusClass[o.status]) + "</div>"; }).join("") : EK.empty("orders", "Aucune commande", "")) + "</div></section></div>";
    }).catch(function (e) { el.innerHTML = EK.empty("x", "Chargement impossible", e.message); });
  };

  function pick(u, path) {
    var m, r = u.role;
    if (path === "/") return { admin: V.admin, collector: V.collectorHome, recycler: V.recyclerHome }[r] || V.citizenHome;
    var allowed = {
      "/request": ["citizen"], "/pickups": ["citizen"], "/points": ["citizen"], "/available": ["collector"],
      "/sell": ["collector", "recycler"], "/market": ["citizen", "collector", "recycler", "admin"], "/orders": ["collector", "recycler", "admin"],
    };
    var fn = { "/request": V.request, "/pickups": V.pickups, "/points": V.points, "/available": V.available, "/sell": V.sell, "/market": V.market, "/orders": V.orders }[path];
    if (fn && allowed[path].indexOf(r) >= 0) return fn;
    if ((m = path.match(/^\/pay\/([^/]+)$/))) return { fn: V.pay, params: [m[1]] };
    return null;
  }

  function route() {
    EK.navId++;
    if (cleanup) { try { cleanup(); } catch (e) { /* nettoyage best-effort */ } cleanup = null; }
    var ctx = parse();

    if (PUBLIC.test(ctx.path)) {
      if (ctx.query.role) { try { sessionStorage.setItem("ek.role", ctx.query.role); } catch (e) { /* ignore */ } }
      if (EK.session.access && EK.session.user && EK.session.user.profile_completed) { location.hash = "#/"; return; }
      shellFor = null; document.title = (ctx.path === "/signup" ? "Créer un compte" : "Connexion") + " — EcoKolekt";
      cleanup = V.auth(root, ctx.path === "/signup" ? "signup" : "login", ctx.query);
      return;
    }
    if (!EK.session.access) { location.hash = "#/login"; return; }

    var ready = EK.session.user ? Promise.resolve(EK.session.user) : EK.loadMe();
    ready.then(function (u) {
      if (!u.profile_completed) { shellFor = null; cleanup = V.auth(root, "signup", { profile: 1 }); return; }
      if (u.role !== "admin" && !u.is_approved) { shellFor = null; V.pending(root); return; }
      if (shellFor !== u.id) drawShell(u);
      var hit = pick(u, ctx.path);
      if (!hit) { $("#view").innerHTML = EK.empty("x", "Page introuvable", "Ce lien n'existe pas ou n'est pas disponible pour votre profil.", '<a class="btn btn--primary" href="#/">Retour à l\'accueil</a>'); markActive(ctx.path); return; }
      ctx.params = hit.params || [];
      var fn = hit.fn || hit;
      markActive(ctx.path);
      cleanup = fn($("#view"), ctx) || null;
      var h = $("#view h1"); document.title = (h ? h.textContent + " — " : "") + "EcoKolekt";
      window.scrollTo(0, 0);
    }).catch(function (e) {
      if (e.status === 401) { EK.session.clear(); location.hash = "#/login"; }
      else root.innerHTML = '<div class="auth__panel">' + EK.empty("x", "Connexion au serveur impossible", e.message, '<button class="btn btn--primary" onclick="location.reload()">Réessayer</button>') + "</div>";
    });
  }

  window.addEventListener("hashchange", route);
  route();
})();
