/* ---------- Sélecteur pays + indicatif ---------- */
document.querySelectorAll("[data-country-picker]").forEach((root) => {
  const input = root.querySelector("input[type=hidden]");
  const btn = root.querySelector(".cp-btn");
  const panel = root.querySelector(".cp-panel");
  const search = root.querySelector(".cp-search");
  const items = [...root.querySelectorAll(".cp-list li")];
  const flagEl = root.querySelector(".cp-btn .fi");
  const prefixEl = root.querySelector(".cp-prefix");

  const choose = (li) => {
    input.value = li.dataset.code;
    flagEl.className = "fi fi-" + li.dataset.code.toLowerCase();
    prefixEl.textContent = "+" + li.dataset.dial;
    items.forEach((i) => i.classList.toggle("sel", i === li));
    panel.classList.remove("open");
  };

  const current = items.find((i) => i.dataset.code === input.value) || items.find((i) => i.dataset.code === "BJ") || items[0];
  if (current) choose(current);

  btn.addEventListener("click", (e) => {
    e.preventDefault();
    panel.classList.toggle("open");
    if (panel.classList.contains("open")) { search.value = ""; filter(""); search.focus(); current && items.find((i) => i.classList.contains("sel"))?.scrollIntoView({ block: "center" }); }
  });
  const norm = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const filter = (q) => {
    q = norm(q.trim()).replace(/^\+/, "");
    items.forEach((i) => { i.hidden = !!q && !(norm(i.dataset.name).includes(q) || i.dataset.dial.startsWith(q) || i.dataset.code.toLowerCase() === q); });
  };
  search.addEventListener("input", () => filter(search.value));
  items.forEach((li) => li.addEventListener("click", () => choose(li)));
  document.addEventListener("click", (e) => { if (!root.contains(e.target)) panel.classList.remove("open"); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") panel.classList.remove("open"); });
});

/* ---------- Types de tickets dynamiques (formset) ---------- */
const formset = document.getElementById("tt-formset");
if (formset) {
  const prefix = formset.dataset.prefix;
  const total = document.getElementById(`id_${prefix}-TOTAL_FORMS`);
  const tpl = document.getElementById("tt-empty");
  const list = document.getElementById("tt-rows");

  document.getElementById("tt-add").addEventListener("click", () => {
    const idx = parseInt(total.value, 10);
    const html = tpl.innerHTML.replace(/__prefix__/g, idx);
    const wrap = document.createElement("div");
    wrap.innerHTML = html.trim();
    list.appendChild(wrap.firstElementChild);
    total.value = idx + 1;
  });

  list.addEventListener("click", (e) => {
    const btn = e.target.closest(".tt-remove");
    if (!btn) return;
    const row = btn.closest(".tt-row");
    const del = row.querySelector("input[type=checkbox][name$=DELETE]");
    if (del) { del.checked = true; row.classList.add("removed"); }
    else { row.remove(); }
  });
}

/* ---------- Montant dynamique sur la fiche événement ---------- */
const buy = document.getElementById("buy-form");
if (buy) {
  const out = document.getElementById("buy-total");
  const qty = buy.querySelector("[name=quantity]");
  const fmt = (n) => n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  const update = () => {
    const sel = buy.querySelector("[name=ticket_type]:checked");
    const n = Math.max(1, parseInt(qty.value || "1", 10));
    if (sel) out.textContent = fmt(parseInt(sel.dataset.price, 10) * n) + " " + out.dataset.currency;
  };
  buy.addEventListener("input", update);
  update();
}

/* ---------- Paiement : champ téléphone seulement pour Mobile Money ---------- */
const pay = document.getElementById("pay-form");
if (pay) {
  const phoneBox = document.getElementById("pay-phone-box");
  const note = document.getElementById("pay-card-note");
  const update = () => {
    const sel = pay.querySelector("[name=method]:checked");
    const momo = sel && sel.dataset.kind === "momo";
    phoneBox.style.display = momo ? "block" : "none";
    note.style.display = sel && !momo ? "block" : "none";
  };
  pay.addEventListener("change", update);
  update();
}
