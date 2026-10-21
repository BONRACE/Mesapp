/* NovaTickets — petits comportements d'interface (aucune dépendance). */
(function () {
  "use strict";
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
  const fcfa = (n) => Math.round(n).toLocaleString("fr-FR").replace(/[  ]/g, " ") + " FCFA";

  // --- Menu mobile ---------------------------------------------------------------
  const toggle = $("#nav-toggle"), menu = $("#mobile-menu");
  if (toggle && menu) {
    toggle.addEventListener("click", () => {
      const open = menu.classList.toggle("hidden") === false;
      toggle.setAttribute("aria-expanded", String(open));
    });
  }

  // --- Sélecteur de pays : drapeau + indicatif dynamique -------------------------
  const dataEl = $("#countries-data");
  $$("[data-country-picker]").forEach((wrap) => {
    const select = $("select", wrap);
    if (!select || !dataEl) return;
    const countries = JSON.parse(dataEl.textContent);
    const byCode = Object.fromEntries(countries.map((c) => [c.code, c]));
    const form = wrap.closest("form");
    const dialEl = form && $("[data-dial]", form);
    const phone = form && $('input[name="phone"]', form);

    select.classList.add("sr-only");
    select.tabIndex = -1;
    select.setAttribute("aria-hidden", "true");

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "nt-input flex items-center justify-between gap-2 text-left";
    btn.setAttribute("aria-haspopup", "listbox");
    const panel = document.createElement("div");
    panel.className = "nt-country-list hidden rounded-xl border border-slate-200 bg-white p-2 shadow-lift";
    const search = document.createElement("input");
    search.type = "search";
    search.placeholder = "Rechercher un pays ou un indicatif…";
    search.className = "nt-input mb-2";
    const list = document.createElement("ul");
    list.setAttribute("role", "listbox");
    panel.append(search, list);
    wrap.append(btn, panel);

    const flag = (code) => `<span class="fi fi-${code.toLowerCase()} h-4 w-5 rounded-sm"></span>`;
    function paint() {
      const c = byCode[select.value] || countries[0];
      btn.innerHTML = `<span class="flex items-center gap-2">${flag(c.code)}<span>${c.name}</span></span><span class="text-sm font-semibold text-brand-800">${c.dial}</span>`;
      if (dialEl) dialEl.textContent = c.dial;
      if (phone) phone.placeholder = "Numéro mobile (" + c.dial + " …)";
    }
    function render(filter) {
      const q = (filter || "").toLowerCase().replace("+", "");
      list.innerHTML = "";
      countries
        .filter((c) => !q || c.name.toLowerCase().includes(q) || c.dial.replace("+", "").startsWith(q) || c.code.toLowerCase() === q)
        .forEach((c) => {
          const li = document.createElement("li");
          li.setAttribute("role", "option");
          li.setAttribute("aria-selected", String(c.code === select.value));
          li.className = "nt-country-opt flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 text-sm hover:bg-brand-50";
          li.innerHTML = `${flag(c.code)}<span class="flex-1">${c.name}</span><span class="font-semibold text-slate-500">${c.dial}</span>`;
          li.addEventListener("click", () => {
            select.value = c.code;
            select.dispatchEvent(new Event("change", { bubbles: true }));
            close();
          });
          list.append(li);
        });
    }
    function open() { render(""); panel.classList.remove("hidden"); search.value = ""; search.focus(); }
    function close() { panel.classList.add("hidden"); paint(); }
    btn.addEventListener("click", () => (panel.classList.contains("hidden") ? open() : close()));
    search.addEventListener("input", () => render(search.value));
    document.addEventListener("click", (e) => { if (!wrap.contains(e.target)) panel.classList.add("hidden"); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") panel.classList.add("hidden"); });
    select.addEventListener("change", paint);
    paint();
  });

  // --- Formulaire dynamique : types de tickets -----------------------------------
  $$("[data-formset]").forEach((root) => {
    const prefix = root.dataset.prefix;
    const total = $(`#id_${prefix}-TOTAL_FORMS`, root);
    const rows = $("[data-rows]", root);
    const tpl = $("template[data-empty-row]", root);

    function refresh() {
      const visible = $$("[data-row]", rows).filter((r) => r.style.display !== "none");
      visible.forEach((r) => { const b = $("[data-remove-row]", r); if (b) b.disabled = visible.length <= 1; });
    }
    $("[data-add-row]", root).addEventListener("click", () => {
      const idx = parseInt(total.value, 10);
      const html = tpl.innerHTML.replaceAll("__prefix__", idx);
      const holder = document.createElement("div");
      holder.innerHTML = html.trim();
      rows.append(holder.firstElementChild);
      total.value = idx + 1;
      refresh();
      const first = $("input[type=text]", rows.lastElementChild);
      if (first) first.focus();
    });
    root.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-remove-row]");
      if (!btn) return;
      const row = btn.closest("[data-row]");
      const del = $('input[type=checkbox][name$="-DELETE"]', row);
      const idField = $('input[name$="-id"]', row);
      if (idField && idField.value && del) { del.checked = true; row.style.display = "none"; }
      else { row.remove(); renumber(); }
      refresh();
    });
    // Renumérote les lignes neuves après suppression (Django attend des index contigus).
    function renumber() {
      const all = $$("[data-row]", rows);
      all.forEach((row, i) => {
        $$("input,select,textarea,label", row).forEach((el) => {
          ["name", "id", "for"].forEach((attr) => {
            const v = el.getAttribute(attr);
            if (v) el.setAttribute(attr, v.replace(new RegExp(`${prefix}-\\d+-`), `${prefix}-${i}-`));
          });
        });
      });
      total.value = all.length;
    }
    refresh();
  });

  // --- Achat : total, « pour un ami » --------------------------------------------
  $$("[data-buy-form]").forEach((form) => {
    const qty = $('input[name="quantity"]', form);
    const totalEl = $("[data-total]", form);
    const friend = $('input[name="for_friend"]', form);
    const friendBox = $("[data-friend-fields]", form);
    function update() {
      const sel = $('input[name="ticket_type"]:checked', form);
      const n = parseInt(qty.value || "0", 10) || 0;
      totalEl.textContent = sel ? (parseInt(sel.dataset.price, 10) * n === 0 ? "Gratuit" : fcfa(parseInt(sel.dataset.price, 10) * n)) : "—";
      if (friendBox) friendBox.classList.toggle("hidden", !friend.checked);
    }
    form.addEventListener("input", update);
    form.addEventListener("change", update);
    if (!$('input[name="ticket_type"]:checked', form)) {
      const first = $('input[name="ticket_type"]:not(:disabled)', form);
      if (first) first.checked = true;
    }
    update();
  });

  // --- Paiement : masquer le numéro pour la carte bancaire ----------------------------
  $$("[data-checkout]").forEach((form) => {
    const wrap = $("[data-phone-wrap]", form);
    function update() {
      const sel = $('input[name="method"]:checked', form);
      wrap.classList.toggle("hidden", !!sel && sel.value === "card");
    }
    form.addEventListener("change", update);
    update();
  });

  // --- Cartes de visite : aperçu en direct ---------------------------------------
  $$("[data-card-form]").forEach((form) => {
    const img = $("[data-preview]", form);
    const loading = $("[data-preview-loading]", form);
    const url = form.dataset.previewUrl;
    let side = "recto", timer = null, seq = 0, lastUrl = null;

    async function refresh() {
      const mine = ++seq;
      const fd = new FormData(form);
      fd.set("side", side);
      if (form.dataset.cardId) fd.set("card", form.dataset.cardId);
      loading.classList.remove("hidden"); loading.classList.add("grid");
      try {
        const res = await fetch(url, { method: "POST", body: fd, credentials: "same-origin" });
        if (!res.ok) throw new Error(res.status);
        const blob = await res.blob();
        if (mine !== seq) return;
        const next = URL.createObjectURL(blob);
        img.src = next;
        if (lastUrl) URL.revokeObjectURL(lastUrl);
        lastUrl = next;
      } catch (e) { /* on garde l'aperçu précédent */ }
      finally { if (mine === seq) { loading.classList.add("hidden"); loading.classList.remove("grid"); } }
    }
    const schedule = () => { clearTimeout(timer); timer = setTimeout(refresh, 350); };
    form.addEventListener("input", schedule);
    form.addEventListener("change", schedule);
    $$("[data-side]", form).forEach((b) => b.addEventListener("click", () => {
      side = b.dataset.side;
      $$("[data-side]", form).forEach((x) => {
        const on = x === b;
        x.classList.toggle("bg-white", on); x.classList.toggle("shadow-sm", on); x.classList.toggle("text-slate-600", !on);
      });
      refresh();
    }));
    refresh();
  });
})();
