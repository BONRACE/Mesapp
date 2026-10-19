/* EcoKolekt — marché des matières recyclées : catalogue, commandes, paiement, annonces du vendeur. */
(function () {
  "use strict";
  var EK = window.EK, esc = EK.esc, $ = EK.$, $$ = EK.$$, V = (EK.views = EK.views || {});
  var GRADES = { raw: "Brut", sorted: "Trié", clean: "Trié et propre", baled: "Pressé en balles" };
  var canSell = function () { var r = EK.session.user.role; return r === "collector" || r === "recycler"; };
  var canBuy = function () { var r = EK.session.user.role; return r !== "admin"; };

  /* ---- Catalogue ---- */
  V.market = function (el) {
    var f = { category: "", search: "", sort: "-created_at" }, cats = [], pos = null;
    el.innerHTML = '<div class="page-head"><div><h1>Marché</h1><p>Matières triées, vendues par les collecteurs et recycleurs de Cotonou.</p></div>' + (canSell() ? '<a class="btn btn--primary" href="#/sell">' + EK.icon("plus") + " Vendre</a>" : "") + "</div>" +
      '<div id="pb" class="pills"></div><div class="row row--wrap"><input class="input grow" id="q" type="search" placeholder="Rechercher (PET, carton, aluminium…)" aria-label="Rechercher" style="max-width:420px"><select class="input" id="so" style="width:auto" aria-label="Trier">' +
      '<option value="-created_at">Plus récentes</option><option value="unit_price">Prix croissant</option><option value="-unit_price">Prix décroissant</option><option value="-quantity_kg">Plus gros stock</option><option value="distance">Plus proches</option></select></div>' +
      '<div id="cp" class="pills"></div><div id="ls">' + EK.skeleton(6) + "</div>";
    EK.api.get("/waste/categories/").then(function (c) {
      cats = EK.api.items(c).filter(function (x) { return x.is_recyclable; });
      $("#cp").innerHTML = '<button class="pill" data-c="" aria-pressed="true">Tout</button>' + cats.map(function (c) { return '<button class="pill" data-c="' + c.id + '" aria-pressed="false">' + esc(c.name.split(" (")[0]) + "</button>"; }).join("");
      $$("#cp .pill").forEach(function (b) { b.onclick = function () { f.category = b.dataset.c; $$("#cp .pill").forEach(function (x) { x.setAttribute("aria-pressed", x === b); }); load(); }; });
    }).catch(function () { /* filtres facultatifs */ });
    EK.api.get("/market/prices/", null, { auth: false }).then(function (rows) {
      $("#pb").innerHTML = rows.map(function (r) { return '<span class="chip">' + EK.dot(r.color) + " " + esc(r.name.split(" (")[0]) + " · dès " + EK.fmt.fcfa(r.min_price) + "/kg</span>"; }).join("");
    }).catch(function () { /* cours facultatifs */ });

    var t;
    $("#q").oninput = function () { clearTimeout(t); var v = this.value; t = setTimeout(function () { f.search = v; load(); }, 300); };
    $("#so").onchange = function () {
      f.sort = this.value;
      if (f.sort === "distance" && !pos) EK.locate().then(function (p) { pos = p; load(); }).catch(function (e) { EK.fail(e); $("#so").value = "-created_at"; f.sort = "-created_at"; });
      else load();
    };

    function load() {
      var u = EK.session.user, params = { category: f.category, search: f.search };
      if (f.sort === "distance") { var p = pos || (u.latitude != null && { lat: u.latitude, lng: u.longitude }); if (p) { params.lat = p.lat; params.lng = p.lng; params.sort = "distance"; } }
      else params.ordering = f.sort;
      EK.api.get("/market/listings/", params).then(function (d) {
        var items = EK.api.items(d);
        $("#ls").innerHTML = items.length ? '<div class="grid grid--cards">' + items.map(card).join("") + "</div>" : EK.empty("market", "Aucune annonce", "Essayez une autre catégorie ou revenez plus tard.");
        $$("[data-buy]").forEach(function (b) { b.onclick = function () { orderModal(items.filter(function (x) { return String(x.id) === b.dataset.buy; })[0]); }; });
      }).catch(function (e) { $("#ls").innerHTML = EK.empty("x", "Chargement impossible", e.message); });
    }
    function card(l) {
      var c = l.category_detail || {};
      return '<article class="card listing"><div class="top"><div><div class="row small muted">' + EK.dot(c.color) + esc(c.name || "") + '</div><h3 style="margin-top:4px">' + esc(l.title) + '</h3></div><div class="price num">' + EK.fmt.n(l.unit_price) + "<small> FCFA/kg</small></div></div>" +
        '<div class="meta">' + EK.chip(GRADES[l.grade] || l.grade) + EK.chip(EK.fmt.kg(l.quantity_kg) + " dispo") + EK.chip("min. " + EK.fmt.kg(l.min_order_kg)) + (l.distance_m != null ? EK.chip(EK.fmt.dist(l.distance_m)) : "") + "</div>" +
        '<div class="small muted">' + esc(l.seller_name) + (l.address ? " · " + esc(l.address) : "") + "</div>" +
        (l.is_mine ? '<span class="chip chip--info">Votre annonce</span>' : canBuy() ? '<button class="btn btn--primary btn--sm" data-buy="' + l.id + '"' + (l.in_stock ? "" : " disabled") + ">" + (l.in_stock ? "Commander" : "Stock épuisé") + "</button>" : "") + "</article>";
    }
    load();
  };

  function orderModal(l) {
    var min = Number(l.min_order_kg), max = Number(l.quantity_kg), q = Math.min(Math.max(min, 50), max);
    var m = EK.modal('<div class="row row--between"><h2>Commander</h2><button class="btn btn--ghost btn--sm" data-close aria-label="Fermer">' + EK.icon("x") + "</button></div>" +
      "<div><strong>" + esc(l.title) + '</strong><div class="small muted">' + esc(l.seller_name) + " · " + EK.fmt.fcfa(l.unit_price) + "/kg</div></div>" +
      '<div class="field"><span class="lbl">Quantité (kg)</span><div class="stepper"><button type="button" data-d="-10" aria-label="Moins">−</button><input id="qty" type="number" min="' + min + '" max="' + max + '" step="1" value="' + q + '" aria-label="Quantité en kg"><button type="button" data-d="10" aria-label="Plus">+</button></div><span class="hint">Minimum ' + EK.fmt.kg(min) + ", maximum " + EK.fmt.kg(max) + ".</span></div>" +
      '<div class="field"><label for="da">Adresse de livraison / enlèvement</label><input class="input" id="da" maxlength="255" placeholder="Quartier, repère"></div>' +
      '<div class="sum"><div><span>Matière</span><span class="num" id="s1"></span></div><div class="tot"><span>Total à payer</span><span class="num" id="s2"></span></div></div>' +
      '<div class="field"><span class="lbl">Paiement</span><div class="pills" id="pm"><button class="pill" data-m="mobile_money" aria-pressed="true">Mobile Money</button><button class="pill" data-m="card" aria-pressed="false">Carte bancaire</button></div></div>' +
      '<div class="err" id="e" aria-live="polite"></div><button class="btn btn--primary btn--lg btn--block" id="go">Commander et payer</button>' +
      '<p class="hint">Votre argent est conservé par la plateforme jusqu\'à la confirmation de réception.</p>');
    var method = "mobile_money";
    function sum() { var v = parseFloat($("#qty", m.el).value) || 0; $("#s1", m.el).textContent = EK.fmt.kg(v); $("#s2", m.el).textContent = EK.fmt.fcfa(v * l.unit_price); }
    $$("[data-d]", m.el).forEach(function (b) { b.onclick = function () { var i = $("#qty", m.el); i.value = Math.min(max, Math.max(min, (parseFloat(i.value) || min) + Number(b.dataset.d))); sum(); }; });
    $("#qty", m.el).oninput = sum;
    $$("#pm .pill", m.el).forEach(function (b) { b.onclick = function () { method = b.dataset.m; $$("#pm .pill", m.el).forEach(function (x) { x.setAttribute("aria-pressed", x === b); }); }; });
    sum();
    $("#go", m.el).onclick = function () {
      var btn = this, err = $("#e", m.el); err.textContent = "";
      EK.busy(btn, true, "Création…");
      EK.api.post("/market/orders/", { listing: l.id, quantity_kg: $("#qty", m.el).value, delivery_address: $("#da", m.el).value.trim() })
        .then(function (o) { return EK.pay(o.id, method); })
        .then(function () { m.close(); })
        .catch(function (e) { EK.busy(btn, false); err.textContent = e.message; });
    };
  }

  /* Lance le paiement d'une commande : page de la passerelle, ou simulateur en démo */
  EK.pay = function (orderId, method) {
    return EK.api.post("/payments/initiate/", { order: orderId, method: method || "mobile_money" }).then(function (p) {
      if (p.provider === "mock") location.hash = "#/pay/" + p.id;
      else window.location.href = p.checkout_url;
    });
  };

  /* ---- Commandes ---- */
  V.orders = function (el, ctx) {
    var side = ctx.query.as === "seller" ? "seller" : "buyer";
    el.innerHTML = '<div class="page-head"><div><h1>Commandes</h1><p>Achats, ventes et suivi des paiements.</p></div></div>' +
      (canSell() ? '<div class="pills" id="tb"><button class="pill" data-s="buyer" aria-pressed="' + (side === "buyer") + '">Mes achats</button><button class="pill" data-s="seller" aria-pressed="' + (side === "seller") + '">Mes ventes</button></div>' : "") + '<div id="ls">' + EK.skeleton(3) + "</div>";
    $$("#tb .pill").forEach(function (b) { b.onclick = function () { location.hash = "#/orders?as=" + b.dataset.s; }; });
    function load() {
      EK.api.get("/market/orders/", side === "seller" ? { as: "seller" } : {}).then(function (d) {
        var items = EK.api.items(d);
        $("#ls").innerHTML = items.length ? '<div class="grid grid--cards">' + items.map(card).join("") + "</div>" : EK.empty("orders", "Aucune commande", side === "seller" ? "Vos ventes apparaîtront ici." : "Parcourez le marché pour passer votre première commande.", '<a class="btn btn--primary btn--sm" href="#/market">Voir le marché</a>');
        $$("[data-a]", $("#ls")).forEach(function (b) { b.onclick = function () { act(b.dataset.a, b.closest("[data-id]").dataset.id, b); }; });
      }).catch(function (e) { $("#ls").innerHTML = EK.empty("x", "Chargement impossible", e.message); });
    }
    function card(o) {
      var seller = o.role === "seller", btns = "";
      if (!seller && o.status === "pending_payment") btns = '<button class="btn btn--primary btn--sm" data-a="pay">Payer</button><button class="btn btn--danger btn--sm" data-a="cancel">Annuler</button>';
      if (!seller && o.status === "shipped") btns = '<button class="btn btn--primary btn--sm" data-a="deliver">Confirmer la réception</button>';
      if (seller && o.status === "paid") btns = '<button class="btn btn--primary btn--sm" data-a="ship">Marquer comme expédiée</button>';
      return '<article class="card stack" data-id="' + esc(o.id) + '"><div class="row row--between"><div class="row">' + EK.dot(o.category_color) + "<strong>" + esc(o.listing_title) + "</strong></div>" + EK.chip(o.status_label, EK.orderStatusClass[o.status]) + "</div>" +
        '<div class="small muted">' + EK.fmt.kg(o.quantity_kg) + " × " + EK.fmt.fcfa(o.unit_price) + " · " + (seller ? "Acheteur : " + esc(o.buyer_name) : "Vendeur : " + esc(o.seller_name)) + " · " + EK.fmt.date(o.created_at) + "</div>" +
        '<div class="row row--between"><b class="num" style="font-size:1.2rem">' + EK.fmt.fcfa(seller ? o.seller_net : o.total) + "</b>" + (seller ? '<span class="hint">net après commission</span>' : "") + "</div>" +
        (o.delivery_address ? '<div class="small muted">' + EK.icon("pin") + " " + esc(o.delivery_address) + "</div>" : "") + (btns ? '<div class="row row--wrap">' + btns + "</div>" : "") + "</article>";
    }
    function act(a, id, btn) {
      var p = a === "pay" ? EK.pay(id) : EK.api.post("/market/orders/" + id + "/" + a + "/");
      EK.busy(btn, true);
      p.then(function () { if (a !== "pay") { EK.toast({ cancel: "Commande annulée.", deliver: "Réception confirmée, le vendeur est payé.", ship: "Marquée comme expédiée." }[a]); load(); } })
        .catch(function (e) { EK.busy(btn, false); EK.fail(e); });
    }
    load();
  };

  /* ---- Simulateur de passerelle (PAYMENT_DEFAULT_PROVIDER=mock) ---- */
  V.pay = function (el, ctx) {
    var id = ctx.params[0];
    el.innerHTML = EK.skeleton(1);
    EK.api.get("/payments/" + id + "/").then(function (p) {
      if (p.status !== "pending") { el.innerHTML = result(p); return; }
      el.innerHTML = '<div class="card stack" style="max-width:460px;margin:auto"><span class="chip chip--on">Mode démonstration</span><h1>Paiement</h1><div class="kpi"><span class="v num">' + EK.fmt.fcfa(p.amount) + '</span><span class="l">Commande ' + esc(String(p.order).slice(0, 8)) + "</span></div>" +
        '<p class="muted">En production, vous êtes redirigé vers la page de votre opérateur (MTN, Moov, carte). Ici, choisissez le résultat à simuler.</p>' +
        '<button class="btn btn--primary btn--lg" data-o="success">Simuler un paiement réussi</button><button class="btn btn--danger" data-o="failed">Simuler un échec</button></div>';
      $$("[data-o]", el).forEach(function (b) {
        b.onclick = function () {
          EK.busy(b, true);
          EK.api.post("/payments/mock/" + id + "/confirm/", { outcome: b.dataset.o }).then(function (r) { el.innerHTML = result(r); }).catch(function (e) { EK.busy(b, false); EK.fail(e); });
        };
      });
    }).catch(function (e) { el.innerHTML = EK.empty("x", "Paiement introuvable", e.message); });
    function result(p) {
      var ok = p.status === "succeeded";
      return '<div class="card stack" style="max-width:460px;margin:auto;text-align:center;justify-items:center"><div class="avatar" style="width:64px;height:64px;' + (ok ? "" : "background:var(--danger);color:#fff") + '">' + EK.icon(ok ? "check" : "x") + "</div><h1>" + (ok ? "Paiement confirmé" : "Paiement non abouti") + '</h1><p class="muted">' + (ok ? "Le vendeur est prévenu et prépare votre commande." : "Aucun montant n'a été débité. Vous pouvez réessayer depuis vos commandes.") + '</p><a class="btn btn--primary" href="#/orders">Voir mes commandes</a></div>';
    }
  };

  /* ---- Espace vendeur ---- */
  V.sell = function (el) {
    el.innerHTML = '<div class="page-head"><div><h1>Mes annonces</h1><p>Vendez vos matières triées aux recycleurs.</p></div><button class="btn btn--primary" id="nw">' + EK.icon("plus") + ' Nouvelle annonce</button></div><div id="kp" class="grid grid--kpi"></div><div id="ls">' + EK.skeleton(3) + "</div>";
    var cats = [];
    EK.api.get("/waste/categories/").then(function (c) { cats = EK.api.items(c).filter(function (x) { return x.is_recyclable; }); });
    $("#nw").onclick = function () { form(null); };
    function load() {
      EK.api.get("/market/earnings/").then(function (e) {
        $("#kp").innerHTML = '<div class="kpi kpi--hero"><span class="v num">' + EK.fmt.n(e.net_xof) + '</span><span class="l">FCFA nets encaissés</span></div><div class="kpi"><span class="v num">' + EK.fmt.n(e.kg_sold) + '</span><span class="l">kg vendus</span></div><div class="kpi"><span class="v num">' + e.to_ship + '</span><span class="l">à expédier</span></div><div class="kpi"><span class="v num">' + e.active_listings + '</span><span class="l">annonces actives</span></div>';
      }).catch(function () { /* facultatif */ });
      EK.api.get("/market/listings/", { mine: 1 }).then(function (d) {
        var items = EK.api.items(d).filter(function (l) { return l.is_active; });
        $("#ls").innerHTML = items.length ? '<div class="grid grid--cards">' + items.map(function (l) {
          return '<article class="card stack" data-id="' + l.id + '"><div class="row row--between"><strong>' + esc(l.title) + '</strong><b class="num">' + EK.fmt.n(l.unit_price) + ' F/kg</b></div><div class="small muted">' + EK.fmt.kg(l.quantity_kg) + " en stock · " + (GRADES[l.grade] || "") + '</div><div class="row"><button class="btn btn--line btn--sm" data-ed>Modifier</button><button class="btn btn--danger btn--sm" data-rm>Retirer</button></div></article>';
        }).join("") + "</div>" : EK.empty("market", "Aucune annonce", "Publiez votre première matière : photo non requise, un prix et un stock suffisent.");
        $$("[data-ed]").forEach(function (b) { b.onclick = function () { form(items.filter(function (x) { return String(x.id) === b.closest("[data-id]").dataset.id; })[0]); }; });
        $$("[data-rm]").forEach(function (b) { b.onclick = function () { if (confirm("Retirer cette annonce du marché ?")) EK.api.del("/market/listings/" + b.closest("[data-id]").dataset.id + "/").then(function () { EK.toast("Annonce retirée."); load(); }).catch(EK.fail); }; });
      }).catch(function (e) { $("#ls").innerHTML = EK.empty("x", "Chargement impossible", e.message); });
    }
    function form(l) {
      var u = EK.session.user;
      var m = EK.modal('<div class="row row--between"><h2>' + (l ? "Modifier l'annonce" : "Nouvelle annonce") + '</h2><button class="btn btn--ghost btn--sm" data-close aria-label="Fermer">' + EK.icon("x") + "</button></div>" +
        '<form id="f" class="stack" novalidate><div class="field"><label for="c">Matière</label><select class="input" id="c">' + cats.map(function (c) { return '<option value="' + c.id + '"' + (l && l.category === c.id ? " selected" : "") + ">" + esc(c.name) + "</option>"; }).join("") + "</select></div>" +
        '<div class="field"><label for="t">Titre</label><input class="input" id="t" maxlength="120" required value="' + esc(l ? l.title : "") + '" placeholder="Ex. Bouteilles PET transparentes, triées"></div>' +
        '<div class="field"><label for="g">État</label><select class="input" id="g">' + Object.keys(GRADES).map(function (g) { return '<option value="' + g + '"' + ((l ? l.grade : "sorted") === g ? " selected" : "") + ">" + GRADES[g] + "</option>"; }).join("") + "</select></div>" +
        '<div class="grid" style="grid-template-columns:1fr 1fr"><div class="field"><label for="q">Stock (kg)</label><input class="input" id="q" type="number" min="1" step="1" required value="' + (l ? Number(l.quantity_kg) : "") + '"></div><div class="field"><label for="p">Prix (FCFA/kg)</label><input class="input" id="p" type="number" min="1" step="1" required value="' + (l ? l.unit_price : "") + '"></div></div>' +
        '<div class="field"><label for="mo">Commande minimale (kg)</label><input class="input" id="mo" type="number" min="1" step="1" value="' + (l ? Number(l.min_order_kg) : 10) + '"></div>' +
        '<div class="field"><label for="ad">Lieu d\'enlèvement</label><input class="input" id="ad" maxlength="255" value="' + esc(l ? l.address : "") + '" placeholder="Quartier"></div>' +
        '<div class="field"><label for="d">Description (facultatif)</label><textarea class="input" id="d" maxlength="1500">' + esc(l ? l.description : "") + "</textarea></div>" +
        '<div class="err" id="e" aria-live="polite"></div><button class="btn btn--primary btn--lg btn--block" id="go">' + (l ? "Enregistrer" : "Publier") + "</button></form>");
      $("#f", m.el).onsubmit = function (ev) {
        ev.preventDefault();
        var body = { category: Number($("#c", m.el).value), title: $("#t", m.el).value.trim(), grade: $("#g", m.el).value, quantity_kg: $("#q", m.el).value, unit_price: Number($("#p", m.el).value), min_order_kg: $("#mo", m.el).value || 10, address: $("#ad", m.el).value.trim(), description: $("#d", m.el).value.trim() };
        if (!l && u.latitude != null) { body.latitude = u.latitude; body.longitude = u.longitude; }
        var btn = $("#go", m.el); EK.busy(btn, true, "Enregistrement…");
        (l ? EK.api.patch("/market/listings/" + l.id + "/", body) : EK.api.post("/market/listings/", body)).then(function () { m.close(); EK.toast(l ? "Annonce mise à jour." : "Annonce publiée."); load(); })
          .catch(function (e) { EK.busy(btn, false); $("#e", m.el).textContent = e.message; });
      };
    }
    load();
  };
})();
