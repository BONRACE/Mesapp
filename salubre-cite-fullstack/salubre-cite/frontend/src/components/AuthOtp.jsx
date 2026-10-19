import { useState } from "react";
import { Smartphone, ShieldCheck, ArrowRight, Check, Sparkles } from "lucide-react";
import { ROLES, fmtXOF } from "../data/recyclables";

const ZONES = ["Akpakpa", "Dantokpa", "Ganhi", "Haie Vive", "Fidjrossè", "Cadjèhoun", "Kouhounou", "Godomey", "Calavi"];

export default function AuthOtp({ initialRole = "menage", onSuccess, go }) {
  const [step, setStep] = useState(1);
  const [role, setRole] = useState(initialRole);
  const [name, setName] = useState("Kossi Ahouansou");
  const [org, setOrg] = useState("Coopérative Akpakpa Propre");
  const [zone, setZone] = useState("Akpakpa");
  const [phone, setPhone] = useState("+229 01 97 44 82 10");
  const [digits, setDigits] = useState(["4", "8", "2", "9", "1", "6"]);
  const [demoCode, setDemoCode] = useState("482916");
  const [err, setErr] = useState("");

  const requestOtp = (e) => {
    e.preventDefault();
    if (name.trim().length < 2) return setErr("Indiquez votre nom ou raison sociale.");
    if (phone.replace(/\D/g, "").length < 8) return setErr("Numéro de téléphone invalide.");
    setErr("");
    const generated = "482916";
    setDemoCode(generated);
    setDigits(generated.split(""));
    setStep(2);
  };

  const verifyOtp = (e) => {
    e.preventDefault();
    const entered = digits.join("");
    if (entered.length !== 6 || entered !== demoCode) {
      return setErr(`Code OTP incorrect. Utilisez le code SMS de démo : ${demoCode}`);
    }
    setErr("");
    onSuccess({
      name,
      org,
      role,
      zone,
      phone,
      ecoPoints: 340,
      jwtPreview: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.${btoa(`${phone}:${role}`).slice(0, 22)}`,
    });
    go("dashboard");
  };

  const setDigitAt = (idx, val) => {
    const clean = val.replace(/\D/g, "").slice(-1);
    setDigits((prev) => prev.map((d, i) => (i === idx ? clean : d)));
  };

  return (
    <div className="mx-auto grid max-w-7xl gap-10 px-6 py-12 lg:grid-cols-[1fr_1.2fr]">
      <div>
        <span className="label rounded-full bg-[var(--card)] px-3.5 py-1 text-[14px] text-[var(--teal-dark)]">
          Standard Nouvelle Génération · Sans mot de passe
        </span>
        <h1 className="display mt-4 text-[64px] text-[var(--deep)] md:text-[84px]">
          Inscription<br />
          <span className="text-[var(--ochre)]">Téléphone + OTP.</span>
        </h1>
        <p className="mt-4 max-w-md text-[17px] text-[var(--muted)]">
          Choisissez votre rôle dans la chaîne de gestion des déchets, recevez un code à 6 chiffres par SMS ou WhatsApp et accédez immédiatement à votre espace PostGIS & QR.
        </p>

        <div className="mt-8 space-y-3 rounded-[22px] bg-[var(--card)] p-5">
          <div className="flex items-center gap-2.5 text-[15px] font-semibold text-[var(--deep)]">
            <ShieldCheck size={20} className="text-[var(--teal-dark)]" />
            Endpoint appelé : <code className="mono text-[13px]">POST /api/v1/auth/otp/{step === 1 ? "request" : "verify"}</code>
          </div>
          <p className="text-[14px] text-[var(--muted)]">
            Jeton OTP temporaire stocké avec TTL de 300 secondes, émission d’un JWT signé HMAC-SHA256 rattaché au profil et à la zone géographique PostGIS.
          </p>
        </div>
      </div>

      <div className="rounded-[26px] bg-white p-6 shadow-[0_28px_70px_-40px_rgba(5,69,68,.45)] md:p-8">
        <div className="mb-6 flex items-center gap-3">
          {[1, 2].map((n) => (
            <div key={n} className="flex items-center gap-2">
              <span className={`display flex h-8 w-8 items-center justify-center rounded-full text-[18px] ${step >= n ? "bg-[var(--deep)] text-white" : "bg-[var(--card)] text-[var(--muted)]"}`}>
                {step > n ? <Check size={16} /> : n}
              </span>
              <span className="label text-[15px] text-[var(--ink)]">
                {n === 1 ? "Profil & Numéro" : "Vérification OTP 6 chiffres"}
              </span>
              {n === 1 && <span className="mx-2 h-0.5 w-8 bg-[#cde0e0]" />}
            </div>
          ))}
        </div>

        {step === 1 ? (
          <form onSubmit={requestOtp} className="space-y-5">
            <div>
              <p className="label text-[15px] text-[var(--muted)]">1. Choisissez votre rôle</p>
              <div className="mt-2.5 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
                {ROLES.map((r) => (
                  <button
                    type="button"
                    key={r.id}
                    onClick={() => setRole(r.id)}
                    className={`rounded-2xl border-[1.5px] p-3 text-left transition ${
                      role === r.id
                        ? "border-[var(--teal)] bg-[var(--deep)] text-white"
                        : "border-[#cde0e0] bg-white hover:border-[var(--teal)]"
                    }`}
                  >
                    <span className="display block text-[22px]">{r.short}</span>
                    <span className="text-[12px] opacity-80">
                      {r.tariff === 0 ? "Prime / kg" : `${fmtXOF(r.tariff)}/mois`}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            <div className="grid gap-3.5 sm:grid-cols-2">
              <div className="field">
                <input id="f-name" placeholder=" " value={name} onChange={(e) => setName(e.target.value)} />
                <label htmlFor="f-name">Nom complet</label>
              </div>
              <div className="field">
                <input id="f-org" placeholder=" " value={org} onChange={(e) => setOrg(e.target.value)} />
                <label htmlFor="f-org">Ménage / Coopérative / Société</label>
              </div>
              <div className="field">
                <input id="f-phone" type="tel" placeholder=" " value={phone} onChange={(e) => setPhone(e.target.value)} />
                <label htmlFor="f-phone">Téléphone (SMS & WhatsApp)</label>
              </div>
              <div className="field">
                <select id="f-zone" value={zone} onChange={(e) => setZone(e.target.value)}>
                  {ZONES.map((z) => <option key={z} value={z}>{z} · Grand Nokoué</option>)}
                </select>
                <label htmlFor="f-zone">Zone PostGIS de rattachement</label>
              </div>
            </div>

            {err && <p className="text-[14px] font-semibold text-[#b5482f]">{err}</p>}

            <button
              type="submit"
              className="label flex w-full items-center justify-center gap-2 rounded-2xl bg-[var(--deep)] py-4 text-[20px] text-white transition hover:bg-[var(--teal)]"
            >
              <Smartphone size={20} /> Recevoir mon code OTP <ArrowRight size={19} />
            </button>
          </form>
        ) : (
          <form onSubmit={verifyOtp} className="space-y-5">
            <div className="rounded-2xl bg-[#f7efe3] p-4 text-[14px] text-[var(--earth)]">
              <div className="flex items-center justify-between">
                <span className="font-semibold">SMS envoyé au {phone}</span>
                <span className="mono rounded bg-white px-2.5 py-0.5 font-semibold text-[var(--deep)]">
                  Code démo : {demoCode}
                </span>
              </div>
              <p className="mt-1 opacity-85">
                Le code est pré-rempli pour vous permettre de tester la validation immédiatement.
              </p>
            </div>

            <div>
              <p className="label text-[15px] text-[var(--muted)]">Code OTP à 6 chiffres</p>
              <div className="mt-2.5 grid grid-cols-6 gap-2.5">
                {digits.map((d, i) => (
                  <input
                    key={i}
                    aria-label={`Chiffre OTP ${i + 1}`}
                    value={d}
                    onChange={(e) => setDigitAt(i, e.target.value)}
                    className="mono h-14 rounded-2xl border-2 border-[var(--teal)] bg-[var(--bg)] text-center text-[24px] font-semibold text-[var(--deep)] outline-none focus:ring-4 focus:ring-teal-500/20"
                  />
                ))}
              </div>
            </div>

            {err && <p className="text-[14px] font-semibold text-[#b5482f]">{err}</p>}

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => setStep(1)}
                className="label rounded-2xl border border-[#cde0e0] px-5 py-3.5 text-[17px] text-[var(--ink)]"
              >
                ← Modifier numéro
              </button>
              <button
                type="submit"
                className="label flex flex-1 items-center justify-center gap-2 rounded-2xl bg-[var(--ochre)] py-3.5 text-[20px] text-white transition hover:bg-[var(--clay)]"
              >
                <Sparkles size={19} /> Valider & Ouvrir mon Dashboard
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
