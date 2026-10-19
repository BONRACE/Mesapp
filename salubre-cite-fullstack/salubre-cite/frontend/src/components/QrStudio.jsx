import { useMemo, useState } from "react";
import { ShieldCheck, ShieldAlert, QrCode, CheckCircle2, RefreshCw } from "lucide-react";
import { BINS } from "../modules/routing";
import { buildSignedToken, verifySignedToken, makeQrMatrix } from "../modules/qr";

export default function QrStudio({ selectedBin, onAwardPoints }) {
  const initialBin = selectedBin || BINS[1];
  const [binId, setBinId] = useState(initialBin.id);
  const currentBin = BINS.find((b) => b.id === binId) || BINS[1];
  const [household, setHousehold] = useState(currentBin.household);
  const [weightKg, setWeightKg] = useState(currentBin.weightKg || 120);
  const [nonce, setNonce] = useState(1760864400);

  const signed = useMemo(
    () => buildSignedToken({ binId: currentBin.id, household, zone: currentBin.zone, ts: nonce }),
    [currentBin, household, nonce]
  );

  const [scanInput, setScanInput] = useState("");
  const effectiveToken = scanInput || signed.token;
  const matrix = useMemo(() => makeQrMatrix(effectiveToken), [effectiveToken]);
  const check = useMemo(() => verifySignedToken(effectiveToken, household), [effectiveToken, household]);
  const [scanHistory, setScanHistory] = useState([
    { id: "SCN-901", bin: "BAC-104", zone: "Dantokpa", kg: 185, points: 925, status: "HMAC Valide" },
    { id: "SCN-902", bin: "BAC-108", zone: "Ganhi", kg: 140, points: 700, status: "HMAC Valide" },
  ]);

  const handleSelectBin = (id) => {
    setBinId(id);
    const found = BINS.find((b) => b.id === id);
    if (found) {
      setHousehold(found.household);
      setWeightKg(found.weightKg || 85);
      setScanInput("");
    }
  };

  const confirmScan = () => {
    if (!check.valid) return;
    const pts = Math.round(weightKg * 5);
    setScanHistory((prev) => [
      { id: `SCN-${903 + prev.length}`, bin: currentBin.id, zone: currentBin.zone, kg: weightKg, points: pts, status: "HMAC Valide" },
      ...prev,
    ]);
    if (onAwardPoints) onAwardPoints(pts);
  };

  return (
    <div className="mx-auto max-w-7xl px-6 py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <span className="label rounded-full bg-[var(--card)] px-3.5 py-1 text-[14px] text-[var(--teal-dark)]">
            Traçabilité Cryptographique · HMAC-SHA256
          </span>
          <h1 className="display mt-3 text-[54px] text-[var(--deep)] md:text-[74px]">
            QR Codes <span className="text-[var(--ochre)]">Sécurisés.</span>
          </h1>
        </div>
        <p className="max-w-md text-[16px] text-[var(--muted)]">
          Chaque bac est identifié par un jeton signé. Toute altération du code ou du poids casse la signature HMAC.
        </p>
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1.1fr_1fr]">
        {/* Générateur QR */}
        <section className="rounded-[26px] bg-white p-6 shadow-[0_24px_60px_-42px_rgba(5,69,68,.5)] md:p-8">
          <div className="flex items-center justify-between">
            <h2 className="display text-[36px] text-[var(--deep)]">1. Émission du Pass Bac</h2>
            <button
              onClick={() => { setNonce((n) => n + 60); setScanInput(""); }}
              className="label flex items-center gap-1.5 rounded-full bg-[var(--card)] px-3.5 py-1.5 text-[14px] text-[var(--teal-dark)]"
            >
              <RefreshCw size={14} /> Régénérer sel
            </button>
          </div>

          <div className="mt-5 grid gap-3.5 sm:grid-cols-2">
            <div className="field">
              <select id="qr-bin" value={binId} onChange={(e) => handleSelectBin(e.target.value)}>
                {BINS.filter((b) => b.id !== "BAC-101").map((b) => (
                  <option key={b.id} value={b.id}>{b.id} · {b.name}</option>
                ))}
              </select>
              <label htmlFor="qr-bin">Bac connecté PostGIS</label>
            </div>
            <div className="field">
              <input id="qr-house" placeholder=" " value={household} onChange={(e) => { setHousehold(e.target.value); setScanInput(""); }} />
              <label htmlFor="qr-house">Ménage / Détenteur du bac</label>
            </div>
          </div>

          <div className="mt-6 grid items-center gap-6 rounded-2xl bg-[var(--card)] p-5 sm:grid-cols-[190px_1fr]">
            <div className="mx-auto rounded-2xl bg-white p-3.5 shadow-sm">
              <svg viewBox="0 0 21 21" className="h-40 w-40" shapeRendering="crispEdges" aria-label="QR Code signé">
                {matrix.map((row, r) =>
                  row.map((cell, c) =>
                    cell ? <rect key={`${r}-${c}`} x={c} y={r} width="1" height="1" fill="#054544" /> : null
                  )
                )}
              </svg>
            </div>
            <div>
              <span className="label rounded-full bg-[var(--deep)] px-3 py-1 text-[13px] text-[#ffe5be]">
                Signature HMAC : {signed.sig}
              </span>
              <p className="display mt-3 text-[30px] text-[var(--deep)]">{currentBin.name}</p>
              <p className="text-[14px] text-[var(--muted)]">
                Quartier {currentBin.zone} · Flux : {currentBin.type}
              </p>
              <p className="mono mt-3 break-all rounded-xl bg-white p-2.5 text-[12px] text-[var(--ink)]">
                {signed.token}
              </p>
            </div>
          </div>
        </section>

        {/* Terminal de scan & validation */}
        <section className="rounded-[26px] bg-[var(--deep)] p-6 text-white md:p-8">
          <h2 className="display text-[36px] text-white">2. Terminal Scan Collecteur</h2>
          <p className="mt-1 text-[15px] text-[#cae5e4]">
            Vérifie la signature <code className="mono">POST /api/v1/qr/scan</code> et crédite les éco-points au pesage.
          </p>

          <div className="mt-5 space-y-3.5">
            <div>
              <label htmlFor="token-in" className="label text-[14px] text-[#cae5e4]">Jeton QR lu par la douchette / caméra</label>
              <input
                id="token-in"
                value={effectiveToken}
                onChange={(e) => setScanInput(e.target.value)}
                className="mono mt-1.5 w-full rounded-xl border border-white/20 bg-white/10 px-3.5 py-2.5 text-[13px] text-white outline-none focus:border-[var(--ochre)]"
              />
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <div className="flex-1">
                <label htmlFor="w-in" className="label text-[14px] text-[#cae5e4]">Pesée embarquée (kg)</label>
                <input
                  id="w-in"
                  type="number"
                  min="1"
                  value={weightKg}
                  onChange={(e) => setWeightKg(Math.max(1, +e.target.value))}
                  className="mono mt-1 w-full rounded-xl border border-white/20 bg-white/10 px-3.5 py-2 text-[16px] text-white outline-none"
                />
              </div>
              <button
                type="button"
                onClick={() => setScanInput(signed.token.slice(0, -4) + "FFFF")}
                className="label mt-5 rounded-xl border border-white/25 px-3.5 py-2.5 text-[14px] text-[#ffe5be] hover:bg-white/10"
              >
                Simuler QR falsifié
              </button>
              <button
                type="button"
                onClick={() => setScanInput("")}
                className="label mt-5 rounded-xl border border-white/25 px-3.5 py-2.5 text-[14px] text-white hover:bg-white/10"
              >
                Restaurer QR valide
              </button>
            </div>

            <div className={`mt-4 flex items-center gap-3 rounded-2xl p-4 ${check.valid ? "bg-[#0d5e5b]" : "bg-[#6e2b1d]"}`}>
              {check.valid ? <ShieldCheck size={26} className="shrink-0 text-[#ffe5be]" /> : <ShieldAlert size={26} className="shrink-0 text-[#ffe5be]" />}
              <div className="text-[14px]">
                <p className="font-semibold">
                  {check.valid ? `Signature authentique · +${Math.round(weightKg * 5)} éco-points` : "Alerte Sécurité : Jeton rejeté"}
                </p>
                <p className="text-[#cae5e4]">
                  {check.valid ? `Bac ${check.binId} (${check.zone}) prêt à être crédité.` : check.reason}
                </p>
              </div>
            </div>

            <button
              type="button"
              disabled={!check.valid}
              onClick={confirmScan}
              className="label mt-2 flex w-full items-center justify-center gap-2 rounded-2xl bg-[var(--ochre)] py-3.5 text-[19px] text-white transition hover:bg-[var(--clay)] disabled:opacity-40"
            >
              <CheckCircle2 size={19} /> Valider la pesée & créditer les points
            </button>
          </div>

          <div className="mt-6 border-t border-white/15 pt-4">
            <p className="label text-[14px] text-[#cae5e4]">Derniers scans enregistrés</p>
            <div className="mt-2 space-y-1.5 text-[13px]">
              {scanHistory.slice(0, 3).map((s) => (
                <div key={s.id} className="flex items-center justify-between rounded-xl bg-white/10 px-3 py-2">
                  <span className="mono">{s.id} · {s.bin} ({s.zone})</span>
                  <span>{s.kg} kg → <b className="text-[#ffe5be]">+{s.points} pts</b></span>
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
