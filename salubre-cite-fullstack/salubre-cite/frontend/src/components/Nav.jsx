import { ROLES } from "../data/recyclables";

const LINKS = [
  ["home", "Accueil"],
  ["dashboard", "Poste de Pilotage"],
  ["qr", "QR & Collecte"],
  ["market", "Bourse Matières"],
  ["backend", "API & PostGIS"],
];

export default function Nav({ page, go, user, activeRole, setActiveRole, dark }) {
  const fg = dark ? "text-[#eaf4f3]" : "text-[var(--ink)]";
  return (
    <header className={`relative z-20 ${dark ? "border-b border-white/10" : "bg-[var(--bg)] border-b border-[#d5e4e4]"}`}>
      <div className={`mx-auto flex max-w-7xl flex-wrap items-center gap-4 px-6 py-4 ${fg}`}>
        <button onClick={() => go("home")} className="flex items-center gap-2.5">
          <LogoMark />
          <span className="display text-[28px] tracking-wide">SALUBRE<span className="text-[var(--ochre)]">·</span>CITÉ</span>
        </button>
        <nav className="ml-4 hidden gap-1 lg:flex">
          {LINKS.map(([id, label]) => (
            <button
              key={id}
              onClick={() => go(id)}
              className={`label rounded-full px-4 py-1.5 text-[16px] transition ${
                page === id
                  ? dark
                    ? "bg-white/15 text-white"
                    : "bg-[var(--deep)] text-white"
                  : "opacity-80 hover:opacity-100"
              }`}
            >
              {label}
            </button>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2.5">
          <label className="sr-only" htmlFor="role-switch">Rôle actif</label>
          <select
            id="role-switch"
            value={activeRole}
            onChange={(e) => setActiveRole(e.target.value)}
            className={`h-10 cursor-pointer rounded-full border px-3.5 text-[14px] font-semibold outline-none ${
              dark ? "border-white/25 bg-white/10 text-white" : "border-[#cde0e0] bg-white text-[var(--ink)]"
            }`}
          >
            {ROLES.map((r) => (
              <option key={r.id} value={r.id} className="text-black">
                Vue : {r.short}
              </option>
            ))}
          </select>
          {user ? (
            <button
              onClick={() => go("dashboard")}
              className="rounded-full bg-[var(--ochre)] px-4 py-2 text-[14px] font-semibold text-white"
            >
              {user.name.split(" ")[0]} · {user.ecoPoints} pts
            </button>
          ) : (
            <button
              onClick={() => go("auth")}
              className="label rounded-full bg-[var(--ochre)] px-5 py-2 text-[16px] text-white transition hover:bg-[var(--clay)]"
            >
              Connexion OTP
            </button>
          )}
        </div>
      </div>
    </header>
  );
}

export function LogoMark({ size = 30 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
      <rect width="32" height="32" rx="9" fill="var(--teal)" />
      <path d="M9 12h14l-2 13H11L9 12Z" stroke="#fff" strokeWidth="2" fill="none" strokeLinejoin="round" />
      <path d="M7 9h18M13 6h6" stroke="var(--ochre)" strokeWidth="2.4" strokeLinecap="round" />
      <circle cx="16" cy="18.5" r="2.3" fill="#fff" />
    </svg>
  );
}
