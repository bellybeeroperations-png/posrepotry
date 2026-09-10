import { useState } from "react";
import { fmtHKD } from "@/lib/api";
import { X, Search } from "lucide-react";

export function ComboEditor({ combo, products, onClose, onSave }) {
  const [name, setName] = useState(combo?.name || "");
  const [pids, setPids] = useState(combo?.product_ids || []);
  const [type, setType] = useState(combo?.discount_type || "percent");
  const [value, setValue] = useState(combo?.discount_value ?? 15);
  const [active, setActive] = useState(combo?.active ?? true);
  const [q, setQ] = useState("");

  const filtered = products.filter(p => !q || p.name.toLowerCase().includes(q.toLowerCase()));
  const toggle = (id) => setPids(pids.includes(id) ? pids.filter(x => x !== id) : [...pids, id]);

  const selectedNames = products.filter(p => pids.includes(p.id)).map(p => p.name);

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6 relative">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display font-black text-xl">{combo ? "Edit Combo" : "New Combo Deal"}</h2>
          <button onClick={onClose} className="text-[var(--muted)]"><X size={20} /></button>
        </div>

        <Field label="Combo name">
          <input data-testid="combo-name" value={name} onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Beer + Wings Combo" className={inp} />
        </Field>

        <div className="grid grid-cols-2 gap-3 mt-3">
          <Field label="Discount type">
            <select value={type} onChange={(e) => setType(e.target.value)} className={inp}>
              <option value="percent">Percent (%)</option>
              <option value="cash">Cash (HKD)</option>
            </select>
          </Field>
          <Field label={type === "percent" ? "Percent off" : "HKD off"}>
            <input data-testid="combo-value" type="number" step="0.01" value={value}
              onChange={(e) => setValue(parseFloat(e.target.value) || 0)} className={inp} />
          </Field>
        </div>

        <div className="mt-3 flex items-center gap-2">
          <button data-testid="combo-active" onClick={() => setActive(!active)}
            className={`px-3 py-1.5 rounded-md text-xs font-mono uppercase border ${
              active ? "bg-[var(--emerald)]/20 border-[var(--emerald)] text-[var(--emerald)]"
                     : "bg-[var(--surface-2)] border-[var(--border)] text-[var(--muted)]"
            }`}>
            {active ? "Active" : "Paused"}
          </button>
        </div>

        <div className="mt-4">
          <div className="flex items-center gap-2 mb-2">
            <div className="text-xs font-mono uppercase tracking-widest text-[var(--muted)]">Required Products (all must be in ticket)</div>
            <span className="ml-auto text-[10px] font-mono text-[var(--cyan)]">{pids.length} selected</span>
          </div>
          {selectedNames.length > 0 && (
            <div className="text-xs mb-2 text-[var(--cyan)] flex flex-wrap gap-1">
              {selectedNames.map((n, i) => <span key={i} className="px-1.5 py-0.5 rounded bg-[var(--cyan)]/15 border border-[var(--cyan)]/40">{n}</span>)}
            </div>
          )}
          <div className="relative mb-2">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted)]" />
            <input placeholder="Search products…" value={q} onChange={(e) => setQ(e.target.value)}
              className={`${inp} pl-9`} />
          </div>
          <div className="max-h-64 overflow-y-auto grid grid-cols-2 gap-1.5">
            {filtered.map(p => (
              <button
                key={p.id}
                data-testid={`combo-prod-${p.name}`}
                onClick={() => toggle(p.id)}
                className={`p-2 rounded-md border text-left ${
                  pids.includes(p.id) ? "bg-[var(--cyan)]/15 border-[var(--cyan)] text-white"
                                      : "bg-[var(--surface-2)] border-[var(--border)] text-[var(--muted)]"
                }`}>
                <div className="text-xs font-semibold">{p.name}</div>
                <div className="text-[10px] font-mono text-[var(--amber)]">{fmtHKD(p.price)}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="flex gap-2 mt-5">
          <button onClick={onClose} className="flex-1 py-2.5 rounded-lg bg-[var(--surface-2)] border border-[var(--border)]">Cancel</button>
          <button data-testid="combo-save"
            onClick={() => onSave({ name, product_ids: pids, discount_type: type, discount_value: value, active })}
            disabled={!name || pids.length < 2}
            className="flex-1 btn-neon py-2.5 rounded-lg disabled:opacity-40">
            Save Combo
          </button>
        </div>
      </div>
    </div>
  );
}

const inp = "w-full bg-[var(--surface-2)] border border-[var(--border)] rounded-md px-3 py-2 text-sm text-white focus:border-[var(--cyan)] focus:outline-none";
const Field = ({ label, children }) => (
  <div>
    <div className="text-[10px] font-mono uppercase tracking-widest text-[var(--muted)] mb-1">{label}</div>
    {children}
  </div>
);
