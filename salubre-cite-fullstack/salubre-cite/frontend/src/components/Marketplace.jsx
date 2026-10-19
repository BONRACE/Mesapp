import { useState } from "react";
import { CreditCard, CheckCircle2, X, ShieldCheck } from "lucide-react";
import { MATERIALS, fmtXOF } from "../data/recyclables";

const GATEWAYS = [
  { id: "fedapay", name: "FedaPay · MTN & Moov Money", tag: "UEMOA Instantané" },
  { id: "kkiapay", name: "KkiaPay · Mobile Money & Wave", tag: "Bénin / Côte d'Ivoire" },
  { id: "stripe", name: "Stripe · Carte Visa / Mastercard", tag: "International" },
];

export default function Marketplace() {
  const [cat, setCat] = useState("Tous");
  const [selected, setSelected] = useState(null);
  const [tons, setTons] = useState(3);
  const [gateway, setGateway] = useState("fedapay");
  const [payerPhone, setPayerPhone] = useState("+229 01 97 44 82 10");
  const [receipt, setReceipt] = useState(null);

  const categories = ["Tous", "Plastique PET", "Plastique PEHD", "Métaux Non-Ferreux", "Fibre & Papier", "Biomasse", "Verre"];
  const items = MATERIALS.filter((m) => cat === "Tous" || m.category === cat);

  const openLot = (m) => {
    setSelected(m);
    setTons(m.minOrderTons);
    setReceipt(null);
  };

  const subtotal = selected ? selected.pricePerTonXOF * tons : 0;
  const fee = Math.round(subtotal * 0.04);

  const confirmPay = (e) => {
    e.preventDefault();
    setReceipt({
      ref: `PAY-${gateway.toUpperCase().slice(0, 4)}-2026-884`,
      lot: selected.title,
      tons,
      subtotal,
      fee,
      net: subtotal - fee,
      gateway: GATEWAYS.find((g) => g.id === gateway)?.name,
    });
  };

  return (
    <div className="mx-auto max-w-7xl px-6 py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <span className="label rounded-full bg-[var(--card)] px-3.5 py-1 text-[14px] text-[var(--teal-dark)]">
            Bourse Secondaire · Paiement API Séquestre (Commission 4 %)
          </span>
          <h1 className="display mt-3 text-[54px] text-[var(--deep)] md:text-[74px]">
            Marché des <span className="text-[var(--ochre)]">Matières Recyclées.</span>
          </h1>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {categories.map((c) => (
            <button
              key={c}
              onClick={() => setCat(c)}
              className={`label rounded-full px-3.5 py-1.5 text-[14px] transition ${
                cat === c ? "bg-[var(--deep)] text-white" : "bg-[var(--card)] text-[var(--ink)] hover:bg-white"
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((m) => (
          <div
            key={m.id}
            className="flex flex-col justify-between rounded-[22px] bg-white p-6 shadow-[0_20px_55px_-42px_rgba(5,69,68,.55)]"
          >
            <div>
              <div className="flex items-center justify-between">
                <span className="label rounded-full bg-[var(--card)] px-3 py-1 text-[13px] text-[var(--teal-dark)]">
                  {m.badge}
                </span>
                <span className="mono text-[12px] text-[var(--muted)]">{m.id}</span>
              </div>
              <h3 className="display mt-4 text-[30px] text-[var(--deep)]">{m.title}</h3>
              <p className="mt-1 text-[14px] text-[var(--muted)]">{m.center} · Pureté {m.purity} · Humidité {m.moisture}</p>
              <div className="mt-5 flex items-baseline justify-between border-t border-[#e1ecec] pt-4">
                <div>
                  <span className="display text-[34px] text-[var(--ochre)]">{fmtXOF(m.pricePerTonXOF)}</span>
                  <span className="text-[14px] text-[var(--muted)]"> / tonne</span>
                </div>
                <span className="text-[14px] font-semibold text-[var(--deep)]">
                  Dispo : {m.stockTons} t (min. {m.minOrderTons} t)
                </span>
              </div>
            </div>

            <button
              onClick={() => openLot(m)}
              className="label mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-[var(--deep)] py-3 text-[17px] text-white transition hover:bg-[var(--teal)]"
            >
              <CreditCard size={17} /> Acheter via Passerelle API
            </button>
          </div>
        ))}
      </div>

      {selected && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-[#054544]/60 p-4 backdrop-blur-sm"
          onClick={() => setSelected(null)}
        >
          <div
            className="rise w-full max-w-lg rounded-[26px] bg-white p-6 md:p-8"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-label={selected.title}
          >
            <div className="flex items-start justify-between">
              <div>
                <span className="mono text-[12px] text-[var(--teal-dark)]">POST /api/v1/payments/checkout</span>
                <h2 className="display mt-1 text-[36px] text-[var(--deep)]">{selected.title}</h2>
              </div>
              <button onClick={() => setSelected(null)} aria-label="Fermer" className="rounded-full p-2 hover:bg-[var(--card)]">
                <X size={20} />
              </button>
            </div>

            {receipt ? (
              <div className="mt-5 space-y-4">
                <div className="flex items-center gap-3 rounded-2xl bg-[var(--card)] p-4 text-[var(--deep)]">
                  <CheckCircle2 size={28} className="text-[var(--teal-dark)]" />
                  <div>
                    <p className="font-semibold">Paiement séquestre confirmé · Réf {receipt.ref}</p>
                    <p className="text-[14px] text-[var(--muted)]">{receipt.gateway}</p>
                  </div>
                </div>
                <dl className="space-y-2 text-[15px]">
                  <div className="flex justify-between"><dt>Volume commandé</dt><dd className="font-semibold">{receipt.tons} tonnes</dd></div>
                  <div className="flex justify-between"><dt>Total payé par l'acheteur</dt><dd className="font-semibold">{fmtXOF(receipt.subtotal)}</dd></div>
                  <div className="flex justify-between text-[var(--muted)]"><dt>Commission bourse (4 %)</dt><dd>− {fmtXOF(receipt.fee)}</dd></div>
                  <div className="flex justify-between border-t pt-2 font-semibold text-[var(--deep)]"><dt>Net crédité au centre de tri</dt><dd>{fmtXOF(receipt.net)}</dd></div>
                </dl>
                <button
                  onClick={() => setSelected(null)}
                  className="label w-full rounded-xl bg-[var(--deep)] py-3 text-[18px] text-white"
                >
                  Fermer le reçu
                </button>
              </div>
            ) : (
              <form onSubmit={confirmPay} className="mt-5 space-y-4">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="field">
                    <input
                      id="pay-tons"
                      type="number"
                      min={selected.minOrderTons}
                      max={selected.stockTons}
                      placeholder=" "
                      value={tons}
                      onChange={(e) => setTons(Math.max(1, +e.target.value))}
                    />
                    <label htmlFor="pay-tons">Quantité (tonnes)</label>
                  </div>
                  <div className="field">
                    <input
                      id="pay-phone"
                      placeholder=" "
                      value={payerPhone}
                      onChange={(e) => setPayerPhone(e.target.value)}
                    />
                    <label htmlFor="pay-phone">Numéro Mobile Money / Compte</label>
                  </div>
                </div>

                <div>
                  <p className="label text-[14px] text-[var(--muted)]">Passerelle de paiement API</p>
                  <div className="mt-2 space-y-2">
                    {GATEWAYS.map((g) => (
                      <button
                        type="button"
                        key={g.id}
                        onClick={() => setGateway(g.id)}
                        className={`flex w-full items-center justify-between rounded-xl border px-3.5 py-2.5 text-left text-[14px] ${
                          gateway === g.id ? "border-[var(--teal)] bg-[var(--card)] font-semibold" : "border-[#cde0e0]"
                        }`}
                      >
                        <span>{g.name}</span>
                        <span className="label rounded bg-white px-2 py-0.5 text-[12px] text-[var(--teal-dark)]">{g.tag}</span>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="rounded-xl bg-[var(--card)] p-4 text-[14px]">
                  <div className="flex justify-between"><span>Sous-total ({tons} t)</span><b>{fmtXOF(subtotal)}</b></div>
                  <div className="mt-1 flex justify-between text-[var(--muted)]"><span>Commission plateforme (4 %)</span><span>− {fmtXOF(fee)}</span></div>
                  <div className="mt-2 flex justify-between border-t border-[#cde0e0] pt-2 font-semibold text-[var(--deep)]">
                    <span>Net reversé au Centre de Tri</span><span>{fmtXOF(subtotal - fee)}</span>
                  </div>
                </div>

                <button
                  type="submit"
                  className="label flex w-full items-center justify-center gap-2 rounded-2xl bg-[var(--ochre)] py-3.5 text-[19px] text-white hover:bg-[var(--clay)]"
                >
                  <ShieldCheck size={19} /> Déclencher le paiement {fmtXOF(subtotal)}
                </button>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
