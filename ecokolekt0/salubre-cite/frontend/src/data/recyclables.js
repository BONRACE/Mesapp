export const MATERIALS = [
  { id: "LOT-PET-01", title: "Balles PET Clair Lavé (Flakes 99 %)", category: "Plastique PET", center: "Centre Tri Akpakpa", purity: "99,2 %", stockTons: 18, minOrderTons: 2, pricePerTonXOF: 265000, moisture: "< 0,8 %", badge: "Qualité Alimentaire" },
  { id: "LOT-HDPE-02", title: "Granulés PEHD Soufflage Bleus & Blancs", category: "Plastique PEHD", center: "Éco-Pôle Godomey", purity: "98,4 %", stockTons: 12, minOrderTons: 1, pricePerTonXOF: 320000, moisture: "< 0,5 %", badge: "Certifié ISO" },
  { id: "LOT-ALU-03", title: "Briquettes Canettes Aluminium Pressées", category: "Métaux Non-Ferreux", center: "Zone Portuaire Ganhi", purity: "97,8 %", stockTons: 9, minOrderTons: 1, pricePerTonXOF: 790000, moisture: "0,2 %", badge: "Prêt Fonderie" },
  { id: "LOT-OCC-04", title: "Carton Ondulé OCC Grade 11 Compacté", category: "Fibre & Papier", center: "Coopérative Dantokpa", purity: "96,0 %", stockTons: 42, minOrderTons: 5, pricePerTonXOF: 95000, moisture: "< 8 %", badge: "Haute Densité" },
  { id: "LOT-COMP-05", title: "Compost Organique Tamisé NPK Naturel", category: "Biomasse", center: "Ferme Pilote Calavi", purity: "100 % Bio", stockTons: 65, minOrderTons: 3, pricePerTonXOF: 72000, moisture: "24 %", badge: "Amendement Sol" },
  { id: "LOT-VER-06", title: "Calcin de Verre Incolore Concassé 4-12 mm", category: "Verre", center: "Fidjrossè Tri Verre", purity: "99,5 %", stockTons: 28, minOrderTons: 4, pricePerTonXOF: 64000, moisture: "0,1 %", badge: "Four Verrerie" },
];

export const ROLES = [
  { id: "menage", name: "Ménage / Producteur", short: "Ménage", tariff: 3500, desc: "Collecte à domicile certifiée par QR signé, suivi temps réel et éco-points convertibles." },
  { id: "collecteur", name: "Collecteur / Tricycle", short: "Collecteur", tariff: 0, desc: "Tournée GPS optimisée sous PostGIS, scan des bacs ≥ 70 % et prime au tonnage validé." },
  { id: "centre", name: "Centre de Tri", short: "Centre de Tri", tariff: 15000, desc: "Réception pesée par pont-bascule, traçabilité des lots et mise en vente sur la bourse." },
  { id: "acheteur", name: "Industriel / Recycleur", short: "Recycleur", tariff: 25000, desc: "Achat en gros de balles PET, PEHD, alu et compost avec paiement séquestre Mobile Money." },
];

export const fmtXOF = (n) =>
  new Intl.NumberFormat("fr-FR", { style: "currency", currency: "XOF", maximumFractionDigits: 0 }).format(Math.round(n));
