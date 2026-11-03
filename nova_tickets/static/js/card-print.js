// Bouton « Imprimer » : charge le PDF de la carte dans un cadre invisible puis ouvre la boîte d'impression.
// Si le navigateur refuse (cadre PDF non imprimable), on ouvre simplement le PDF dans un nouvel onglet.
document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-print-pdf]");
  if (!btn) return;
  e.preventDefault();
  const url = btn.dataset.printPdf + "?inline=1";
  const frame = document.createElement("iframe");
  frame.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0";
  frame.src = url;
  frame.onload = () => { try { frame.contentWindow.focus(); frame.contentWindow.print(); } catch (err) { window.open(url, "_blank"); } };
  document.body.appendChild(frame);
  setTimeout(() => frame.remove(), 60000);
});
