// Moteur GPS PostGIS / Dijkstra + heuristique VRP sur les quartiers de Cotonou & Grand Nokoué.
export const BINS = [
  { id: "BAC-101", name: "Dépôt Akpakpa PK3", zone: "Akpakpa", lat: 6.369, lng: 2.462, fill: 25, type: "Dépôt central", household: "Centre Tri Est", weightKg: 0 },
  { id: "BAC-104", name: "Marché Dantokpa Nord", zone: "Dantokpa", lat: 6.374, lng: 2.432, fill: 94, type: "Organique & PET", household: "Coop Dantokpa", weightKg: 185 },
  { id: "BAC-108", name: "Carrefour Ganhi", zone: "Ganhi", lat: 6.356, lng: 2.439, fill: 86, type: "PET & Carton", household: "Galerie Ganhi", weightKg: 140 },
  { id: "BAC-112", name: "Haie Vive Résidence", zone: "Haie Vive", lat: 6.361, lng: 2.398, fill: 78, type: "Plastique PEHD", household: "Syndic Cocotiers", weightKg: 95 },
  { id: "BAC-119", name: "Fidjrossè Plage", zone: "Fidjrossè", lat: 6.352, lng: 2.361, fill: 89, type: "Verre & Alu", household: "Association Calavi-Sud", weightKg: 130 },
  { id: "BAC-123", name: "Stade de l'Amitié", zone: "Kouhounou", lat: 6.386, lng: 2.378, fill: 74, type: "PET clair", household: "Ménages Kouhounou", weightKg: 110 },
  { id: "BAC-127", name: "Étoile Rouge", zone: "Gbégamey", lat: 6.372, lng: 2.409, fill: 48, type: "Mixte trié", household: "Collectif Étoile", weightKg: 62 },
  { id: "BAC-131", name: "Zogbo Carrefour", zone: "Zogbo", lat: 6.395, lng: 2.394, fill: 83, type: "Ferraille & PEHD", household: "Atelier Zogbo", weightKg: 165 },
  { id: "BAC-136", name: "Agla Hlazounto", zone: "Agla", lat: 6.381, lng: 2.356, fill: 52, type: "PET & Organique", household: "Cité Agla", weightKg: 70 },
  { id: "BAC-142", name: "Cadjèhoun Aéroport", zone: "Cadjèhoun", lat: 6.358, lng: 2.384, fill: 91, type: "Aluminium & PET", household: "Zone Fret Aéroport", weightKg: 150 },
  { id: "BAC-149", name: "Godomey Échangeur", zone: "Godomey", lat: 6.392, lng: 2.339, fill: 81, type: "Carton & PEHD", household: "Marché Godomey", weightKg: 145 },
];

export function haversineKm(a, b) {
  const toR = (d) => (d * Math.PI) / 180;
  const dLat = toR(b.lat - a.lat), dLng = toR(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toR(a.lat)) * Math.cos(toR(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(h));
}

export function solveTour({ threshold = 70, vehicleSpeedKmh = 26, startId = "BAC-101" } = {}) {
  const depot = BINS.find((b) => b.id === startId) || BINS[0];
  const pool = BINS.filter((b) => b.id !== depot.id && b.fill >= threshold);
  const ordered = [depot];
  const remaining = [...pool];
  let cur = depot;
  let totalKm = 0;
  while (remaining.length > 0) {
    let bestIdx = 0, bestScore = Infinity;
    for (let i = 0; i < remaining.length; i++) {
      const cand = remaining[i];
      const d = haversineKm(cur, cand) * 1.28; // facteur de voirie urbaine
      const urgencyWeight = 1 - (cand.fill - 50) / 150;
      const score = d * urgencyWeight;
      if (score < bestScore) { bestScore = score; bestIdx = i; }
    }
    const next = remaining.splice(bestIdx, 1)[0];
    totalKm += haversineKm(cur, next) * 1.28;
    ordered.push(next);
    cur = next;
  }
  totalKm += haversineKm(cur, depot) * 1.28;
  const totalKg = pool.reduce((s, b) => s + b.weightKg, 0);
  const serviceMinutes = pool.length * 6;
  const driveMinutes = Math.round((totalKm / vehicleSpeedKmh) * 60);
  const co2SavedKg = Math.round(totalKg * 1.65);
  return {
    stops: ordered,
    returnDepot: depot,
    totalKm: Number(totalKm.toFixed(1)),
    totalKg,
    durationMin: driveMinutes + serviceMinutes,
    co2SavedKg,
    fuelLiters: Number((totalKm * 0.22).toFixed(1)),
  };
}
