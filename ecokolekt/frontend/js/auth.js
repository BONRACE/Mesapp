/* EcoKolekt — connexion / inscription par téléphone + OTP, puis profil en deux temps. */
(function () {
  "use strict";
  var EK = window.EK, esc = EK.esc, $ = EK.$, $$ = EK.$$;
  EK.views = EK.views || {};

  var PREFIXES = [["+229", "BJ Bénin"], ["+228", "TG Togo"], ["+225", "CI Côte d'Ivoire"], ["+221", "SN Sénégal"], ["+233", "GH Ghana"], ["+234", "NG Nigeria"]];
  var ROLES = [
    { id: "citizen", icon: "home", t: "Je suis un ménage", d: "Je demande des collectes et je gagne des points éco." },
    { id: "collector", icon: "truck", t: "Je suis collecteur", d: "Je reçois des tournées optimisées et je vends mes matières." },
    { id: "recycler", icon: "market", t: "Je suis recycleur", d: "J'achète des matières triées, avec paiement sécurisé." },
  ];
  var VEHICLES = [["foot", "À pied / pousse-pousse"], ["moto", "Moto / tricycle"], ["truck", "Camion"]];

  function fullPhone(prefix, raw) {
    var v = String(raw || "").trim();
    if (v.charAt(0) === "+") return "+" + v.replace(/\D/g, "");
    var d = v.replace(/\D/g, "");
    if (prefix === "+234" || prefix === "+233") d = d.replace(/^0/, "");
    return prefix + d;
  }

  var ART = '<aside class="auth__art" aria-hidden="true"><a class="brand" href="index.html" style="color:#f3eedf">' + EK.logo + "EcoKolekt</a>" +
    "<h2>Votre quartier trie. Un collecteur passe.</h2><p>Une collecte géolocalisée, un QR code qui prouve le passage, un marché pour revendre ce qui est trié.</p>" +
    '<svg class="route" viewBox="0 0 1200 420" preserveAspectRatio="xMidYMax slice"><path class="route-base" d="M-40 360 C 160 300, 260 220, 420 250 S 640 380, 800 280 S 1000 120, 1240 60"/><path class="route-draw" d="M-40 360 C 160 300, 260 220, 420 250 S 640 380, 800 280 S 1000 120, 1240 60"/></svg></aside>';

  function shell(step, total, body) {
    var dots = "";
    for (var i = 0; i < total; i++) dots += "<i" + (i <= step ? ' class="on"' : "") + "></i>";
    return '<div class="auth">' + ART + '<main class="auth__panel"><div class="auth__box">' +
      '<a class="brand" href="index.html">' + EK.logo + "EcoKolekt</a>" +
      '<div class="steps" role="progressbar" aria-valuemin="1" aria-valuemax="' + total + '" aria-valuenow="' + (step + 1) + '">' + dots + "</div>" + body + "</div></main></div>";
  }

  EK.views.auth = function (root, mode, query) {
    var st = { step: 0, prefix: "+229", phone: "", role: null, timer: null };
    try { st.role = query.role || sessionStorage.getItem("ek.role") || null; } catch (e) { st.role = query.role || null; }
    if (["citizen", "collector", "recycler"].indexOf(st.role) < 0) st.role = null;
    var needProfile = false;

    function stop() { clearInterval(st.timer); }

    /* ---- Étape 1 : téléphone ---- */
    function phoneStep() {
      stop();
      var signup = mode === "signup";
      root.innerHTML = shell(0, 4,
        "<div><h1>" + (signup ? "Créez votre compte" : "Content de vous revoir") + '</h1><p class="muted" style="margin-top:6px">' +
        "Entrez votre numéro. Nous vous envoyons un code par SMS, sans mot de passe à retenir.</p></div>" +
        '<form id="f" class="stack" novalidate><div class="field"><label for="ph">Numéro de téléphone</label>' +
        '<div class="phone-field"><select id="pf" aria-label="Indicatif">' +
        PREFIXES.map(function (p) { return '<option value="' + p[0] + '"' + (p[0] === st.prefix ? " selected" : "") + ">" + p[0] + "</option>"; }).join("") +
        '</select><input id="ph" type="tel" inputmode="tel" autocomplete="tel-national" placeholder="01 97 12 34 56" value="' + esc(st.phone) + '" required></div>' +
        '<div class="err" id="e" aria-live="polite"></div></div>' +
        '<button class="btn btn--primary btn--lg btn--block" id="go">Recevoir mon code</button></form>' +
        '<p class="hint">' + (signup ? 'Déjà inscrit ? <a href="#/login"><b>Se connecter</b></a>' : 'Pas encore de compte ? <a href="#/signup"><b>S\'inscrire</b></a>') +
        " · En continuant, vous acceptez d'être contacté par SMS pour la vérification.</p>");
      $("#pf").onchange = function () { st.prefix = this.value; };
      $("#ph").focus();
      $("#f").onsubmit = function (ev) {
        ev.preventDefault();
        st.phone = $("#ph").value;
        var btn = $("#go"); $("#e").textContent = "";
        EK.busy(btn, true, "Envoi…");
        EK.api.post("/auth/otp/request/", { phone: fullPhone(st.prefix, st.phone) }, { auth: false })
          .then(function (d) { st.e164 = d.phone; st.resend = d.resend_in || 60; st.dev = d.dev_code || null; otpStep(); })
          .catch(function (e) { EK.busy(btn, false); $("#e").textContent = e.data && e.data.retry_after ? e.message : e.message; });
      };
    }

    /* ---- Étape 2 : code ---- */
    function otpStep() {
      stop();
      root.innerHTML = shell(1, 4,
        '<div><h1>Entrez le code</h1><p class="muted" style="margin-top:6px">Envoyé au <b class="num">' + esc(st.e164) + '</b>. <a href="#" id="chg"><b>Modifier</b></a></p></div>' +
        '<div class="stack"><div class="otp" id="otp" role="group" aria-label="Code à 6 chiffres">' +
        [0, 1, 2, 3, 4, 5].map(function (i) { return '<input inputmode="numeric" maxlength="1" autocomplete="' + (i ? "off" : "one-time-code") + '" aria-label="Chiffre ' + (i + 1) + '" data-i="' + i + '">'; }).join("") +
        '</div><div class="err" id="e" style="text-align:center" aria-live="polite"></div>' +
        (st.dev ? '<button class="btn btn--line btn--sm" id="dev" type="button">Mode démo : code ' + esc(st.dev) + " (toucher pour remplir)</button>" : "") +
        '<div class="row row--between"><span class="hint" id="cd"></span><button class="btn btn--ghost btn--sm" id="again" type="button" disabled>Renvoyer le code</button></div></div>');
      var boxes = $$("#otp input"), busy = false;
      $("#chg").onclick = function (e) { e.preventDefault(); phoneStep(); };
      function code() { return boxes.map(function (b) { return b.value; }).join(""); }
      function fill(s) { s = String(s).replace(/\D/g, "").slice(0, 6); boxes.forEach(function (b, i) { b.value = s[i] || ""; }); if (s.length === 6) submit(); else (boxes[s.length] || boxes[5]).focus(); }
      boxes.forEach(function (b, i) {
        b.addEventListener("input", function () {
          if (b.value.length > 1) return fill(b.value);
          b.value = b.value.replace(/\D/g, "");
          if (b.value && i < 5) boxes[i + 1].focus();
          if (code().length === 6) submit();
        });
        b.addEventListener("keydown", function (e) { if (e.key === "Backspace" && !b.value && i) boxes[i - 1].focus(); });
        b.addEventListener("paste", function (e) { e.preventDefault(); fill((e.clipboardData || window.clipboardData).getData("text")); });
      });
      boxes[0].focus();
      if (st.dev) $("#dev").onclick = function () { fill(st.dev); };

      var left = st.resend;
      function tick() {
        $("#cd").textContent = left > 0 ? "Nouveau code possible dans " + left + " s" : "";
        $("#again").disabled = left > 0;
        if (left-- <= 0) clearInterval(st.timer);
      }
      tick(); st.timer = setInterval(tick, 1000);
      $("#again").onclick = function () {
        EK.api.post("/auth/otp/request/", { phone: st.e164 }, { auth: false })
          .then(function (d) { st.dev = d.dev_code || null; st.resend = d.resend_in || 60; EK.toast("Nouveau code envoyé."); otpStep(); })
          .catch(EK.fail);
      };

      function submit() {
        if (busy) return;
        busy = true; $("#e").textContent = "";
        EK.api.post("/auth/otp/verify/", { phone: st.e164, code: code() }, { auth: false }).then(function (d) {
          stop(); EK.session.set(d);
          needProfile = !d.user.profile_completed;
          if (needProfile) roleStep(); else done();
        }).catch(function (e) {
          busy = false; $("#e").textContent = e.message;
          var o = $("#otp"); o.classList.add("is-bad"); setTimeout(function () { o.classList.remove("is-bad"); }, 450);
          boxes.forEach(function (b) { b.value = ""; }); boxes[0].focus();
        });
      }
    }

    /* ---- Étape 3 : rôle ---- */
    function roleStep() {
      root.innerHTML = shell(2, 4,
        '<div><h1>Comment utiliserez-vous EcoKolekt ?</h1><p class="muted" style="margin-top:6px">Vous pourrez toujours demander de l\'aide à l\'équipe pour changer plus tard.</p></div>' +
        '<div class="role-grid" role="radiogroup" aria-label="Profil">' + ROLES.map(function (r) {
          return '<button class="role-card" role="radio" aria-checked="' + (st.role === r.id) + '" data-r="' + r.id + '"><span class="ico">' + EK.icon(r.icon) + "</span><span><strong>" + r.t + '</strong><span class="d">' + r.d + "</span></span></button>";
        }).join("") + '</div><button class="btn btn--primary btn--lg btn--block" id="next"' + (st.role ? "" : " disabled") + ">Continuer</button>");
      $$(".role-card").forEach(function (c) {
        c.onclick = function () {
          st.role = c.dataset.r;
          $$(".role-card").forEach(function (x) { x.setAttribute("aria-checked", x === c); });
          $("#next").disabled = false;
        };
      });
      $("#next").onclick = detailsStep;
    }

    /* ---- Étape 4 : détails ---- */
    function detailsStep() {
      var pro = st.role !== "citizen", pos = null;
      var extra = "";
      if (st.role === "collector") {
        extra = '<div class="field"><label for="veh">Votre moyen de collecte</label><select class="input" id="veh">' +
          VEHICLES.map(function (v) { return '<option value="' + v[0] + '"' + (v[0] === "moto" ? " selected" : "") + ">" + v[1] + "</option>"; }).join("") + "</select></div>" +
          '<div class="field"><label for="cap">Capacité de charge (kg)</label><input class="input" id="cap" type="number" inputmode="numeric" min="10" max="20000" value="200"><span class="hint">Sert à ne pas surcharger votre tournée.</span></div>';
      } else if (st.role === "recycler") {
        extra = '<div class="field"><label for="co">Nom de votre structure</label><input class="input" id="co" maxlength="140" placeholder="Ex. Plastic Bénin SARL"></div>' +
          '<div class="field"><label for="ad">Adresse</label><input class="input" id="ad" maxlength="255" placeholder="Quartier, rue"></div>';
      }
      root.innerHTML = shell(3, 4,
        '<div><h1>Presque fini</h1><p class="muted" style="margin-top:6px">' + (pro ? "Votre profil sera vérifié par l'équipe avant de pouvoir opérer." : "Il ne reste que votre prénom.") + "</p></div>" +
        '<form id="f" class="stack" novalidate><div class="field"><label for="nm">Nom complet</label><input class="input" id="nm" autocomplete="name" maxlength="120" placeholder="Prénom Nom" required></div>' + extra +
        '<div class="field"><span class="lbl">Votre position</span><button class="btn btn--line" type="button" id="loc">' + EK.icon("pin") + ' Utiliser ma position</button><span class="hint" id="lh">Facultatif. Elle facilite vos demandes et vos tournées.</span></div>' +
        '<div class="err" id="e" aria-live="polite"></div><button class="btn btn--primary btn--lg btn--block" id="go">Terminer</button></form>');
      $("#nm").focus();
      $("#loc").onclick = function () {
        EK.locate().then(function (p) { pos = p; $("#lh").textContent = "Position enregistrée."; }).catch(function (e) { $("#lh").textContent = e.message; });
      };
      $("#f").onsubmit = function (ev) {
        ev.preventDefault();
        var name = $("#nm").value.trim();
        if (name.length < 2) { $("#e").textContent = "Indiquez votre nom."; return; }
        var body = { full_name: name, role: st.role };
        if (st.role === "collector") { body.vehicle_type = $("#veh").value; body.capacity_kg = parseInt($("#cap").value, 10) || 200; }
        if (st.role === "recycler") { body.company_name = $("#co").value.trim(); body.address = $("#ad").value.trim(); }
        if (pos) { body.latitude = pos.lat; body.longitude = pos.lng; }
        var btn = $("#go"); EK.busy(btn, true, "Création…");
        EK.api.patch("/me/", body).then(function (u) { EK.session.user = u; done(); })
          .catch(function (e) { EK.busy(btn, false); $("#e").textContent = e.message; });
      };
    }

    function done() {
      try { sessionStorage.removeItem("ek.role"); } catch (e) { /* ignore */ }
      EK.loadMe().then(function () { location.hash = "#/"; }).catch(function () { location.hash = "#/"; });
    }

    if (query.profile) { st.e164 = EK.session.user && EK.session.user.phone; roleStep(); } else phoneStep();
    return stop;
  };

  /* Compte professionnel en attente de validation */
  EK.views.pending = function (root) {
    root.innerHTML = '<div class="auth__panel" style="min-height:100vh"><div class="auth__box" style="text-align:center;justify-items:center">' +
      '<a class="brand" href="index.html">' + EK.logo + "EcoKolekt</a>" + '<div class="avatar" style="width:64px;height:64px">' + EK.icon("shield") + "</div>" +
      "<h1>Profil en cours de vérification</h1><p class=\"muted\">L'équipe valide les comptes professionnels pour protéger les ménages et les acheteurs. Vous recevrez un SMS dès que c'est fait.</p>" +
      '<button class="btn btn--primary" id="re">Vérifier maintenant</button><button class="btn btn--ghost" id="lo">Se déconnecter</button></div></div>';
    $("#re").onclick = function () { EK.loadMe().then(function (u) { if (u.is_approved) location.hash = "#/"; else EK.toast("Toujours en cours de vérification."); }).catch(EK.fail); };
    $("#lo").onclick = EK.logout;
  };
})();
