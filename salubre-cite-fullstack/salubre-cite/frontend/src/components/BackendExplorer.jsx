import { useState } from "react";
import { Database, Server, Copy, Check } from "lucide-react";
import { ARCHITECTURE_NOTES, MODELS_CODE, ENDPOINTS_CODE } from "../data/backendSpec";

export default function BackendExplorer() {
  const [tab, setTab] = useState("models");
  const [copied, setCopied] = useState(false);
  const code = tab === "models" ? MODELS_CODE : ENDPOINTS_CODE;

  const copy = () => {
    navigator.clipboard?.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div className="mx-auto max-w-7xl px-6 py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <span className="label rounded-full bg-[var(--card)] px-3.5 py-1 text-[14px] text-[var(--teal-dark)]">
            Backend Python · FastAPI + PostgreSQL / PostGIS
          </span>
          <h1 className="display mt-3 text-[54px] text-[var(--deep)] md:text-[74px]">
            Modèles & <span className="text-[var(--ochre)]">Endpoints REST.</span>
          </h1>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setTab("models")}
            className={`label flex items-center gap-2 rounded-full px-5 py-2.5 text-[16px] ${
              tab === "models" ? "bg-[var(--deep)] text-white" : "bg-[var(--card)] text-[var(--ink)]"
            }`}
          >
            <Database size={17} /> models.py (PostGIS)
          </button>
          <button
            onClick={() => setTab("endpoints")}
            className={`label flex items-center gap-2 rounded-full px-5 py-2.5 text-[16px] ${
              tab === "endpoints" ? "bg-[var(--deep)] text-white" : "bg-[var(--card)] text-[var(--ink)]"
            }`}
          >
            <Server size={17} /> main.py (Endpoints FastAPI)
          </button>
        </div>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {ARCHITECTURE_NOTES.map((n) => (
          <div key={n.title} className="rounded-[20px] bg-white p-5 shadow-[0_18px_50px_-42px_rgba(5,69,68,.5)]">
            <h3 className="display text-[26px] text-[var(--deep)]">{n.title}</h3>
            <p className="mt-1.5 text-[14px] text-[var(--muted)]">{n.detail}</p>
          </div>
        ))}
      </div>

      <div className="mt-6 overflow-hidden rounded-[26px] bg-[var(--deep)] text-white">
        <div className="flex items-center justify-between border-b border-white/10 px-6 py-3.5">
          <span className="mono text-[13px] text-[#ffe5be]">
            {tab === "models" ? "backend/app/models.py — SQLAlchemy 2.0 + GeoAlchemy2" : "backend/app/main.py — FastAPI (OTP, PostGIS, QR HMAC, Paiement)"}
          </span>
          <button
            onClick={copy}
            className="label flex items-center gap-1.5 rounded-full bg-white/10 px-3.5 py-1 text-[14px] text-white hover:bg-white/20"
          >
            {copied ? <Check size={15} /> : <Copy size={15} />} {copied ? "Copié" : "Copier le code"}
          </button>
        </div>
        <pre className="mono overflow-x-auto p-6 text-[13px] leading-relaxed text-[#eaf4f3]">
          {code}
        </pre>
      </div>
    </div>
  );
}
