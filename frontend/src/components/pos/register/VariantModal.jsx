import { useState } from "react";
import { fmtHKD } from "@/lib/api";
import { X } from "lucide-react";

export default function VariantModal({ product, hhPercent = 0, onClose, onPick }) {
  const [variant, setVariant] = useState(product.variants[0]?.name || null);
  const [mods, setMods] = useState([]);
  const vObj = product.variants.find((v) => v.name === variant);
  const rawPrice =
    product.price +
    (vObj?.price_delta || 0) +
    mods.reduce((s, m) => s + (product.modifiers.find((x) => x.name === m)?.price_delta || 0), 0);
  const price = hhPercent ? +(rawPrice * (1 - hhPercent / 100)).toFixed(2) : rawPrice;

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl w-full max-w-md p-6 relative">
        <button onClick={onClose} className="absolute top-3 right-3 text-[var(--muted)]"><X size={18} /></button>
        <div className="font-display font-black text-xl mb-1">{product.name}</div>
        <div className="text-xs font-mono uppercase text-[var(--muted)] mb-4">
          Choose variant & modifiers {hhPercent > 0 && <span className="text-[var(--amber)]">· Happy Hour -{hhPercent}%</span>}
        </div>
        {product.variants.length > 0 && (
          <>
            <div className="text-xs font-mono uppercase text-[var(--muted)] mb-2">Variant</div>
            <div className="grid grid-cols-2 gap-2 mb-4">
              {product.variants.map((v) => (
                <button
                  key={v.name}
                  data-testid={`variant-${v.name}`}
                  onClick={() => setVariant(v.name)}
                  className={`p-3 rounded-lg border text-left ${
                    variant === v.name ? "border-[var(--cyan)] bg-[var(--cyan)]/10" : "border-[var(--border)] bg-[var(--surface-2)]"
                  }`}
                >
                  <div className="font-semibold text-sm">{v.name}</div>
                  <div className="text-xs font-mono text-[var(--amber)]">
                    {v.price_delta >= 0 ? "+" : ""}{fmtHKD(v.price_delta)}
                  </div>
                </button>
              ))}
            </div>
          </>
        )}
        {product.modifiers.length > 0 && (
          <>
            <div className="text-xs font-mono uppercase text-[var(--muted)] mb-2">Modifiers</div>
            <div className="grid grid-cols-2 gap-2 mb-4">
              {product.modifiers.map((m) => {
                const active = mods.includes(m.name);
                return (
                  <button
                    key={m.name}
                    data-testid={`mod-${m.name}`}
                    onClick={() => setMods((x) => (active ? x.filter((n) => n !== m.name) : [...x, m.name]))}
                    className={`p-2 rounded-lg border text-left ${
                      active ? "border-[var(--amber)] bg-[var(--amber)]/10" : "border-[var(--border)] bg-[var(--surface-2)]"
                    }`}
                  >
                    <div className="text-xs font-semibold">{m.name}</div>
                    <div className="text-[10px] font-mono text-[var(--amber)]">
                      {m.price_delta >= 0 ? "+" : ""}{fmtHKD(m.price_delta)}
                    </div>
                  </button>
                );
              })}
            </div>
          </>
        )}
        <div className="flex gap-2 mt-4">
          <button onClick={onClose} className="flex-1 py-2 rounded-lg bg-[var(--surface-2)]">Cancel</button>
          <button data-testid="variant-add" onClick={() => onPick(variant, mods, price)} className="flex-1 btn-neon py-2 rounded-lg">
            Add · {fmtHKD(price)}
          </button>
        </div>
      </div>
    </div>
  );
}
