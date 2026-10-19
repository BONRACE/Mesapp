import { useMemo, useState } from "react";
import { Truck, QrCode, Recycle, CheckCircle2, Flame, Navigation } from "lucide-react";
import { BINS, solveTour } from "../modules/routing";
import { ROLES, fmtXOF } from "../data/recyclables";

const W = 860, H = 430;
const LNG_MIN = 2.33, LNG_MAX = 2.475, LAT_MIN = 6.345, LAT_MAX = 6.403;
const project = (lng, lat) => [
  48 + ((lng - LNG_MIN) / (LNG_MAX - LNG_MIN)) * (W - 96),
  H - 46 - ((lat - LAT_MIN) / (LAT_MAX - LAT_MIN)) * (H - 88),
];

export default function Dashboard({ activeRole, setActiveRole, user, go, onScanBin }) {
  const [threshold, setThreshold] = useState(70);
  const [speed, setSpeed] = useState(26);
  const [collectedIds, setCollectedIds] = useState([]);

  const tour = useMemo(() => solveTour({ threshold, vehicleSpeedKmh: speed }), [threshold, speed]);
  const polyPoints = [...tour.stops, tour.returnDepot]
    .map((b) => project(b.lng, b.lat).join(","))
    .join(" ");
  const pathD =
    "M " +
    [...tour.stops, tour.returnDepot]
      .map((b) => project(b.lng, b.lat).join(" "))
      .join(" L ");

  const roleMeta = ROLES.find((r) => r.id === activeRole) || ROLES[0];

  const toggleCollected = (bin) => {
    setCollectedIds((prev) => (prev.includes(bin.id) ? prev : [...prev, bin.id]));
    if (onScanBin) onScanBin(bin);
  };

  return (
    <div className="mx-auto max-w-7xl px-6 py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <span className="label rounded-full bg-[var(--card)] px-3.5 py-1 text-[14px] text-[var(--teal-dark)]">
            Poste de Pilotage Multi-Rôles · PostGIS SRID 4326
          </span>
          <h1 className="display mt-3 text-[54px] text-[var(--deep)] md:text-[74px]">
            Tournée GPS & <span className="text-[var(--ochre)]">Télérelève.</span>
          </h1>
        </div>
        <div className="flex flex-wrap gap-1.5 rounded-2xl bg-[var(--card)] p-1.5">
          {ROLES.map((r) => (
            <button
              key={r.id}
              onClick={() => setActiveRole(r.id)}
              className={`label rounded-xl px-4 py-2 text-[15px] transition ${
                activeRole === r.id ? "bg-[var(--deep)] text-white" : "text-[var(--ink)] hover:bg-white"
              }`}
            >
              {r.short}
            </button>
          ))}
        </div>
      </div>

      {/* Bandeau contextuel au rôle */}
      <div className="mt-6 grid gap-4 sm:grid-cols-4">
        <KpiCard
          label={`Profil actif : ${roleMeta.short}`}
          value={user ? user.name.split(" ")[0] : "Mode Démo"}
          sub={roleMeta.desc.slice(0, 56) + "…"}
        />
        <KpiCard
          label="Bacs à collecter (≥ seuil)"
          value={`${tour.stops.length - 1} / ${BINS.length - 1}`}
          sub={`Seuil PostGIS ST_DWithin : ${threshold} %`}
        />
        <KpiCard
          label="Tonnage & Distance"
          value={`${tour.totalKg} kg · ${tour.totalKm} km`}
          sub={`Durée estimée : ${tour.durationMin} min (${tour.fuelLiters} L)`}
        />
        <KpiCard
          label="CO₂ évité & Valeur lot"
          value={`${tour.co2SavedKg} kg CO₂`}
          sub={`Valeur matière ~ ${fmtXOF(tour.totalKg * 195)}`}
          accent
        />
      </div>

      {/* Grille principale : contrôles VRP + Carte PostGIS interactive */}
      <div className="mt-6 grid gap-6 lg:grid-cols-[330px_1fr]">
        <aside className="space-y-4">
          <div className="rounded-[22px] bg-white p-5 shadow-[0_20px_55px_-40px_rgba(5,69,68,.55)]">
            <p className="label text-[16px] text-[var(--teal-dark)]">Paramètres Moteur PostGIS</p>
            <label htmlFor="fill-slider" className="mt-3 block text-[15px] text-[var(--ink)]">
              Seuil de remplissage : <b>{threshold} %</b>
            </label>
            <input
              id="fill-slider"
              type="range"
              min="40"
              max="90"
              step="5"
              value={threshold}
              onChange={(e) => setThreshold(+e.target.value)}
              className="mt-2 w-full accent-[var(--teal)]"
            />

            <label htmlFor="speed-slider" className="mt-4 block text-[15px] text-[var(--ink)]">
              Vitesse moyenne tricycle/camion : <b>{speed} km/h</b>
            </label>
            <input
              id="speed-slider"
              type="range"
              min="15"
              max="45"
              step="1"
              value={speed}
              onChange={(e) => setSpeed(+e.target.value)}
              className="mt-2 w-full accent-[var(--ochre)]"
            />

            <div className="mt-5 flex flex-col gap-2">
              <button
                onClick={() => go("qr")}
                className="label flex items-center justify-center gap-2 rounded-xl bg-[var(--deep)] py-3 text-[16px] text-white hover:bg-[var(--teal)]"
              >
                <QrCode size={17} /> Générer / Scanner un QR signé
              </button>
              <button
                onClick={() => go("market")}
                className="label flex items-center justify-center gap-2 rounded-xl bg-[var(--card)] py-3 text-[16px] text-[var(--deep)] hover:bg-[var(--ochre)] hover:text-white"
              >
                <Recycle size={17} /> Vendre en Bourse Matières
              </button>
            </div>
          </div>

          <div className="rounded-[22px] bg-[var(--card)] p-5">
            <p className="label text-[15px] text-[var(--teal-dark)]">Requête Spatiale Exécutée</p>
            <pre className="mono mt-2 overflow-x-auto rounded-xl bg-[var(--deep)] p-3 text-[12px] leading-relaxed text-[#cae5e4]">
{`SELECT code, label, fill_level,
  ST_DistanceSphere(geom,
    ST_MakePoint(2.462, 6.369)) AS m
FROM smart_bins
WHERE fill_level >= ${threshold}
ORDER BY m ASC;`}
            </pre>
          </div>
        </aside>

        <section className="overflow-hidden rounded-[26px] bg-[var(--deep)] text-white">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 px-5 py-3.5">
            <div className="flex items-center gap-2">
              <Navigation size={18} className="text-[var(--ochre)]" />
              <span className="label text-[16px]">Carte télémétrique Grand Nokoué · Cotonou</span>
            </div>
            <div className="flex items-center gap-4 text-[13px] text-[#cae5e4]">
              <span className="flex items-center gap-1.5"><i className="inline-block h-2.5 w-2.5 rounded-full bg-[#e06d53]" /> ≥ 80 % Urgent</span>
              <span className="flex items-center gap-1.5"><i className="inline-block h-2.5 w-2.5 rounded-full bg-[#ffe5be]" /> 65–79 % À collecter</span>
              <span className="flex items-center gap-1.5"><i className="inline-block h-2.5 w-2.5 rounded-full bg-[#4fb6ca]" /> &lt; 65 % Stable</span>
            </div>
          </div>

          <svg viewBox={`0 0 ${W} ${H}`} className="block w-full" role="img" aria-label="Carte GPS PostGIS des bacs connectés de Cotonou">
            {/* Grille géodésique */}
            {[0.2, 0.4, 0.6, 0.8].map((t, i) => (
              <g key={i}>
                <line x1={W * t} y1={0} x2={W * t} y2={H} stroke="#7fc9c9" strokeOpacity=".12" />
                <line x1={0} y1={H * t} x2={W} y2={H * t} stroke="#7fc9c9" strokeOpacity=".12" />
              </g>
            ))}
            {/* Littoral Golfe de Guinée & Lagune de Cotonou */}
            <path d={`M 0 ${H - 38} Q ${W * 0.45} ${H - 58} ${W} ${H - 28} L ${W} ${H} L 0 ${H} Z`} fill="#032f2e" />
            <path d={`M ${W * 0.64} 0 Q ${W * 0.68} ${H * 0.5} ${W * 0.72} ${H - 36}`} stroke="#4fb6ca" strokeOpacity=".28" strokeWidth="14" fill="none" />

            {/* Tracé optimisé VRP */}
            <polyline points={polyPoints} fill="none" stroke="var(--ochre)" strokeWidth="6" strokeLinejoin="round" strokeLinecap="round" opacity=".32" />
            <path key={pathD} d={pathD} fill="none" stroke="#ffe5be" strokeWidth="3" strokeLinejoin="round" className="flow" />
            <g key={"veh-" + pathD}>
              <circle r="8" fill="#fff" stroke="var(--ochre)" strokeWidth="3" />
              <animateMotion dur="9s" repeatCount="indefinite" path={pathD} />
            </g>

            {/* Points Bacs */}
            {BINS.map((b) => {
              const [x, y] = project(b.lng, b.lat);
              const stopIdx = tour.stops.findIndex((s) => s.id === b.id);
              const inTour = stopIdx !== -1;
              const isDone = collectedIds.includes(b.id);
              const color = isDone ? "#4fb6ca" : b.id === "BAC-101" ? "#ffffff" : b.fill >= 80 ? "#e06d53" : b.fill >= 65 ? "#ffe5be" : "#4fb6ca";
              return (
                <g key={b.id} className="cursor-pointer" onClick={() => toggleCollected(b)}>
                  {b.fill >= 80 && !isDone && (
                    <circle cx={x} cy={y} r="13" fill="none" stroke="#e06d53" strokeWidth="2" className="pulse-ring" />
                  )}
                  <circle cx={x} cy={y} r={inTour ? 9 : 6} fill={color} stroke="#054544" strokeWidth="2" />
                  {inTour && (
                    <text x={x} y={y + 4} textAnchor="middle" fontSize="11" fontFamily="Khand" fontWeight="700" fill="#054544">
                      {stopIdx === 0 ? "D" : stopIdx}
                    </text>
                  )}
                  <text
                    x={x + 12}
                    y={y - 6}
                    fontSize="14"
                    fontFamily="Khand"
                    fontWeight="600"
                    fill="#ffffff"
                    stroke="#054544"
                    strokeWidth="3"
                    paintOrder="stroke"
                  >
                    {b.zone} ({isDone ? "Collecté" : `${b.fill}%`})
                  </text>
                </g>
              );
            })}
            <text x="20" y={H - 12} fontSize="13" fontFamily="Khand" fill="#8fd4d4" letterSpacing="2.5">
              GOLFE DE GUINÉE · SRID 4326 · CLIQUEZ SUR UN BAC POUR VALIDER LA COLLECTE
            </text>
          </svg>

          {/* Feuille de route ordonnée */}
          <div className="border-t border-white/10 bg-[#043837] px-5 py-4">
            <p className="label text-[14px] text-[#cae5e4]">Ordre d’arrêt calculé ({tour.stops.length - 1} étapes)</p>
            <div className="mt-2.5 flex flex-wrap gap-2">
              {tour.stops.slice(1).map((b, i) => {
                const done = collectedIds.includes(b.id);
                return (
                  <button
                    key={b.id}
                    onClick={() => toggleCollected(b)}
                    className={`flex items-center gap-2 rounded-xl px-3 py-1.5 text-[14px] transition ${
                      done ? "bg-[var(--teal)] text-white" : "bg-white/10 text-white hover:bg-white/20"
                    }`}
                  >
                    <span className="mono font-semibold">{i + 1}.</span>
                    <span>{b.name}</span>
                    <span className="mono text-[12px] text-[#ffe5be]">{b.fill}%</span>
                    {done && <CheckCircle2 size={15} />}
                  </button>
                );
              })}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

function KpiCard({ label, value, sub, accent }) {
  return (
    <div className={`rounded-[20px] p-5 ${accent ? "bg-[var(--deep)] text-white" : "bg-white shadow-[0_18px_50px_-42px_rgba(5,69,68,.5)]"}`}>
      <p className={`text-[13px] font-semibold uppercase tracking-wider ${accent ? "text-[#cae5e4]" : "text-[var(--muted)]"}`}>{label}</p>
      <p className="display mt-1.5 text-[34px]">{value}</p>
      <p className={`mt-1 text-[13px] ${accent ? "text-[#cae5e4]" : "text-[var(--muted)]"}`}>{sub}</p>
    </div>
  );
}
