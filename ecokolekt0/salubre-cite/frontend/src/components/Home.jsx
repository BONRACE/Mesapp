import { ArrowRight, QrCode, Navigation, Recycle, ShieldCheck, Smartphone, Database, Home as HomeIcon, Truck, Factory, Building2 } from "lucide-react";
import { ROLES, MATERIALS, fmtXOF } from "../data/recyclables";

const ROLE_ICONS = { menage: HomeIcon, collecteur: Truck, centre: Factory, acheteur: Building2 };

export function Hero({ go, setActiveRole, children }) {
  return (
    <section className="relative overflow-hidden bg-[var(--deep)] text-[#eaf4f3]">
      <Contours />
      {children}
      <div className="relative z-10 mx-auto max-w-7xl px-6 pb-14 pt-10 md:pt-14">
        <p className="label rise text-[17px] text-[var(--sky)]">
          Collecte Urbaine · PostGIS Temps Réel · QR HMAC-SHA256 · Bourse Circulaire
        </p>
        <h1 className="display rise mt-4 max-w-5xl !leading-[.94] text-[58px] sm:text-[92px] lg:text-[118px]">
          Chaque déchet tracé,<br />
          chaque kilo <span className="text-[var(--ochre)]">valorisé.</span>
        </h1>
        <p className="rise mt-5 max-w-2xl text-[18px] text-white/85">
          La plateforme multi-rôles qui relie ménages, tricycles de collecte, centres de tri et recycleurs industriels avec routage GPS dynamique et paiement Mobile Money.
        </p>
        <div className="rise mt-8 flex flex-wrap items-center gap-3.5">
          <button
            onClick={() => go("auth")}
            className="label group flex items-center gap-2 rounded-full bg-[var(--ochre)] px-7 py-3.5 text-[19px] text-white transition hover:bg-[var(--clay)]"
          >
            Inscription OTP en 30 s <ArrowRight size={19} className="transition group-hover:translate-x-1" />
          </button>
          <button
            onClick={() => go("dashboard")}
            className="label rounded-full border border-white/30 px-7 py-3.5 text-[19px] text-white transition hover:bg-white/10"
          >
            Ouvrir le Poste GPS
          </button>
          <button
            onClick={() => go("backend")}
            className="label rounded-full border border-cyan-300/50 px-6 py-3.5 text-[18px] text-[var(--sky)] transition hover:bg-white/10"
          >
            Code FastAPI & PostGIS
          </button>
        </div>

        <CycleSvg onPickRole={(r) => { setActiveRole(r); go("dashboard"); }} />
      </div>
      <MaterialTicker />
    </section>
  );
}

function Contours() {
  return (
    <svg className="pointer-events-none absolute inset-0 h-full w-full opacity-[.12]" preserveAspectRatio="none" viewBox="0 0 100 100" aria-hidden>
      {Array.from({ length: 14 }, (_, i) => (
        <path key={i} d={`M-5 ${8 + i * 7} Q 45 ${i * 7 - 5} 105 ${14 + i * 7}`} stroke="var(--sky)" strokeWidth=".18" fill="none" />
      ))}
    </svg>
  );
}

function CycleSvg({ onPickRole }) {
  const xs = [90, 390, 690, 990];
  const steps = [
    ["menage", "1. MÉNAGE", "Bac QR scanné"],
    ["collecteur", "2. COLLECTEUR", "Tournée GPS ≥ 70 %"],
    ["centre", "3. CENTRE DE TRI", "Pesée & compactage"],
    ["acheteur", "4. RECYCLEUR", "Achat en bourse"],
  ];
  return (
    <div className="mt-12 hidden md:block">
      <svg viewBox="0 0 1080 128" className="w-full" aria-label="Chaîne de valeur circulaire Salubre">
        <path d="M90 50 H990" stroke="rgba(255,255,255,.18)" strokeWidth="2.5" />
        <path d="M90 50 H990" stroke="var(--ochre)" strokeWidth="3" className="flow" fill="none" />
        {[0, 1, 2].map((i) => (
          <circle key={i} r="6" fill="var(--sky)">
            <animateMotion dur="6.6s" begin={`-${i * 2.2}s`} repeatCount="indefinite" path="M90 50 H990" />
          </circle>
        ))}
        {steps.map(([id, title, sub], i) => (
          <g key={id} transform={`translate(${xs[i]} 50)`} className="cursor-pointer" onClick={() => onPickRole(id)}>
            <circle r="22" fill="var(--deep)" stroke="var(--ochre)" strokeWidth="3" />
            <text y="7" textAnchor="middle" fill="#fff" fontFamily="Khand" fontWeight="700" fontSize="19">{i + 1}</text>
            <text y="54" textAnchor="middle" fill="#fff" fontFamily="Khand" fontWeight="700" fontSize="20" letterSpacing="1.2">{title}</text>
            <text y="76" textAnchor="middle" fill="#cae5e4" fontFamily="Hind" fontSize="14">{sub}</text>
          </g>
        ))}
      </svg>
    </div>
  );
}

function MaterialTicker() {
  const list = [...MATERIALS, ...MATERIALS];
  return (
    <div className="relative z-10 overflow-hidden bg-[var(--earth)] py-3 text-[#ffe5be]">
      <div className="ticker flex w-max gap-10 whitespace-nowrap">
        {list.map((m, i) => (
          <span key={i} className="label text-[17px]">
            {m.category} <b className="text-white">{fmtXOF(m.pricePerTonXOF)}/t</b>{" "}
            <span className="text-[#e6d3b0]">· pureté {m.purity} · {m.center}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

export default function Home({ go, setActiveRole }) {
  return (
    <>
      <section className="mx-auto max-w-7xl px-6 py-16">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <h2 className="display text-[52px] text-[var(--deep)] md:text-[68px]">
            Quatre rôles,<br />une boucle propre.
          </h2>
          <p className="max-w-md text-[16px] text-[var(--muted)]">
            Cliquez sur un profil pour ouvrir directement son tableau de bord dédié ou lancer son parcours d’inscription OTP.
          </p>
        </div>
        <div className="mt-9 grid gap-5 md:grid-cols-4">
          {ROLES.map((r) => {
            const Icon = ROLE_ICONS[r.id];
            return (
              <div
                key={r.id}
                className="group flex flex-col justify-between rounded-[22px] bg-[var(--card)] p-6 transition hover:-translate-y-1 hover:bg-[var(--deep)] hover:text-white"
              >
                <div>
                  <Icon size={32} className="text-[var(--teal-dark)] transition group-hover:text-[var(--ochre)]" />
                  <h3 className="display mt-6 text-[34px]">{r.short}</h3>
                  <p className="mt-2 text-[15px] leading-relaxed opacity-85">{r.desc}</p>
                </div>
                <div className="mt-6 flex items-center justify-between border-t border-black/10 pt-4 group-hover:border-white/15">
                  <button
                    onClick={() => { setActiveRole(r.id); go("dashboard"); }}
                    className="label text-[16px] text-[var(--teal-dark)] group-hover:text-[var(--sky)]"
                  >
                    Voir Dashboard →
                  </button>
                  <button
                    onClick={() => { setActiveRole(r.id); go("auth"); }}
                    className="label rounded-full bg-white/80 px-3 py-1 text-[14px] text-[var(--deep)]"
                  >
                    OTP
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="bg-[var(--card)]">
        <div className="mx-auto grid max-w-7xl gap-8 px-6 py-14 md:grid-cols-4">
          {[
            [Smartphone, "Auth Téléphone + OTP", "Connexion sans mot de passe en 6 chiffres SMS/WhatsApp + jeton JWT par rôle."],
            [Navigation, "Routage GPS PostGIS", "Sélection automatique des bacs remplis à ≥ 70 % et calcul de tournée minimale."],
            [QrCode, "QR Codes HMAC-SHA256", "Chaque bac possède un QR signé infalsifiable créditant les éco-points au pesage."],
            [Recycle, "Bourse & Mobile Money", "Vente directe de lots PET, PEHD, alu et compost via FedaPay, KkiaPay ou Stripe."],
          ].map(([Icon, title, text]) => (
            <div key={title} className="flex gap-3.5">
              <Icon size={26} className="mt-1 shrink-0 text-[var(--ochre)]" />
              <div>
                <h3 className="display text-[28px] text-[var(--deep)]">{title}</h3>
                <p className="mt-1 text-[15px] text-[var(--muted)]">{text}</p>
              </div>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
