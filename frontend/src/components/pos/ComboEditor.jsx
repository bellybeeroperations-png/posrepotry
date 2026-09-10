import { useState } from "react";
import { fmtHKD } from "@/lib/api";
import { X, Search, Plus, Trash2, Clock } from "lucide-react";
import ComboScheduleFields from "@/components/pos/combo/ComboScheduleFields";

const SLOT_LABELS = ["Slot A", "Slot B", "Slot C", "Slot D"];

export function ComboEditor({ combo, products, onClose, onSave }) {
  const [name, setName] = useState(combo?.name || "");
  const [type, setType] = useState(combo?.discount_type || "percent");
  const [value, setValue] = useState(combo?.discount_value ?? 15);
  const [active, setActive] = useState(combo?.active ?? true);
  const initialSlots = combo?.slots?.length
    ? combo.slots
    : (combo?.product_ids?.length
        ? [{ operator: "or", min_qty: 1, max_qty: 99, product_ids: combo.product_ids }]
        : [{ operator: "or", min_qty: 1, max_qty: 1, product_ids: [] }]);
  const [slots, setSlots] = useState(initialSlots);
  // Deal-of-the-night rotator
  const [schedEnabled, setSchedEnabled] = useState(!!combo?.schedule);
  const [days, setDays] = useState(combo?.schedule?.days || []);
  const [startT, setStartT] = useState(combo?.schedule?.start_time || "17:00");
  const [endT, setEndT] = useState(combo?.schedule?.end_time || "19:00");

  const updSlot = (i, k, v) => setSlots(slots.map((s, idx) => idx === i ? { ...s, [k]: v } : s));
  const toggleProd = (i, pid) => updSlot(i, "product_ids",
    slots[i].product_ids.includes(pid) ? slots[i].product_ids.filter(x => x !== pid) : [...slots[i].product_ids, pid]);
  const addSlot = () => slots.length < 4 && setSlots([...slots, { _k: `s-${Date.now()}-${Math.random()}`, operator: "or", min_qty: 1, max_qty: 1, product_ids: [] }]);
  const delSlot = (i) => setSlots(slots.filter((_, idx) => idx !== i));

  const canSave = name && slots.every(s => s.product_ids.length >= 1);

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl w-full max-w-3xl max-h-[92vh] overflow-y-auto p-6 relative">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display font-black text-xl">{combo ? "Edit Combo" : "New Advanced Combo"}</h2>
          <button onClick={onClose} className="text-[var(--muted)]"><X size={20} /></button>
        </div>

        <div className="grid grid-cols-[1fr_140px_140px] gap-3 mb-4">
          <Field label="Combo name">
            <input data-testid="combo-name" value={name} onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Beer + Wings Combo" className={inp} />
          </Field>
          <Field label="Discount">
            <select value={type} onChange={(e) => setType(e.target.value)} className={inp}>
              <option value="percent">Percent %</option>
              <option value="cash">Cash HKD</option>
            </select>
          </Field>
          <Field label={type === "percent" ? "% off" : "HKD off"}>
            <input data-testid="combo-value" type="number" step="0.01" value={value}
              onChange={(e) => setValue(parseFloat(e.target.value) || 0)} className={inp} />
          </Field>
        </div>

        <div className="flex items-center gap-2 mb-4">
          <button data-testid="combo-active" onClick={() => setActive(!active)}
            className={`px-3 py-1.5 rounded-md text-xs font-mono uppercase border ${
              active ? "bg-[var(--emerald)]/20 border-[var(--emerald)] text-[var(--emerald)]"
                     : "bg-[var(--surface-2)] border-[var(--border)] text-[var(--muted)]"
            }`}>
            {active ? "Active" : "Paused"}
          </button>
          <button data-testid="combo-schedule-toggle" onClick={() => setSchedEnabled(!schedEnabled)}
            className={`px-3 py-1.5 rounded-md text-xs font-mono uppercase border flex items-center gap-1 ${
              schedEnabled ? "bg-[var(--amber)]/20 border-[var(--amber)] text-[var(--amber)]"
                           : "bg-[var(--surface-2)] border-[var(--border)] text-[var(--muted)]"
            }`}>
            <Clock size={12} /> {schedEnabled ? "Scheduled" : "Always-on"}
          </button>
        </div>

        {schedEnabled && (
          <ComboScheduleFields
            days={days} setDays={setDays}
            startT={startT} setStartT={setStartT}
            endT={endT} setEndT={setEndT}
          />
        )}

        <div className="space-y-4">
          {slots.map((slot, i) => (
            <SlotEditor
              key={slot._k ?? `slot-${i}`} idx={i} slot={slot} products={products}
              onUpdate={(k, v) => updSlot(i, k, v)}
              onToggleProd={(pid) => toggleProd(i, pid)}
              onDelete={slots.length > 1 ? () => delSlot(i) : null}
            />
          ))}
        </div>

        {slots.length < 4 && (
          <button data-testid="combo-add-slot" onClick={addSlot}
            className="mt-3 px-3 py-2 rounded-lg border border-dashed border-[var(--cyan)] text-[var(--cyan)] text-xs font-mono uppercase flex items-center gap-1">
            <Plus size={12} /> Add {SLOT_LABELS[slots.length]}
          </button>
        )}

        <div className="flex gap-2 mt-5">
          <button onClick={onClose} className="flex-1 py-2.5 rounded-lg bg-[var(--surface-2)] border border-[var(--border)]">Cancel</button>
          <button data-testid="combo-save"
            onClick={() => onSave({
              name, slots, product_ids: [],
              discount_type: type, discount_value: value, active,
              schedule: schedEnabled ? { days, start_time: startT, end_time: endT } : null,
            })}
            disabled={!canSave}
            className="flex-1 btn-neon py-2.5 rounded-lg disabled:opacity-40">
            Save Combo
          </button>
        </div>
      </div>
    </div>
  );
}

function SlotEditor({ idx, slot, products, onUpdate, onToggleProd, onDelete }) {
  const [q, setQ] = useState("");
  const filtered = products.filter(p => !q || p.name.toLowerCase().includes(q.toLowerCase()));
  const picked = products.filter(p => slot.product_ids.includes(p.id));

  return (
    <div data-testid={`slot-${idx}`} className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-3">
      <div className="flex items-center gap-2 mb-2">
        <div className="w-7 h-7 rounded-full bg-[var(--cyan)] text-black font-display font-black text-sm flex items-center justify-center">
          {String.fromCharCode(65 + idx)}
        </div>
        <div className="font-display font-bold">{SLOT_LABELS[idx]}</div>
        <div className="flex gap-1 ml-2 bg-[var(--surface)] rounded-md border border-[var(--border)] p-0.5">
          {["or", "and"].map(op => (
            <button key={op} data-testid={`slot-${idx}-op-${op}`}
              onClick={() => onUpdate("operator", op)}
              className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase font-bold ${
                slot.operator === op ? "bg-[var(--amber)] text-black" : "text-[var(--muted)]"
              }`}>
              {op}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1 ml-2 text-[10px] font-mono">
          <span className="text-[var(--muted)]">min</span>
          <input data-testid={`slot-${idx}-min`} type="number" min="0" value={slot.min_qty}
            onChange={(e) => onUpdate("min_qty", parseInt(e.target.value) || 0)}
            className="w-12 bg-[var(--surface)] border border-[var(--border)] rounded px-1 py-0.5 text-center" />
          <span className="text-[var(--muted)]">max</span>
          <input data-testid={`slot-${idx}-max`} type="number" min="1" value={slot.max_qty}
            onChange={(e) => onUpdate("max_qty", parseInt(e.target.value) || 1)}
            className="w-12 bg-[var(--surface)] border border-[var(--border)] rounded px-1 py-0.5 text-center" />
        </div>
        {onDelete && (
          <button data-testid={`slot-${idx}-del`} onClick={onDelete} className="ml-auto text-[var(--rose)]">
            <Trash2 size={14} />
          </button>
        )}
      </div>
      <div className="text-[10px] font-mono text-[var(--muted)] mb-1.5 pl-9">
        {slot.operator === "or"
          ? `Any of these products · qty ${slot.min_qty}–${slot.max_qty}`
          : `ALL of these products · each capped at ${slot.max_qty}`}
      </div>
      {picked.length > 0 && (
        <div className="pl-9 mb-2 flex flex-wrap gap-1">
          {picked.map(p => (
            <span key={p.id} className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--cyan)]/15 border border-[var(--cyan)]/40 text-[var(--cyan)]">{p.name}</span>
          ))}
        </div>
      )}
      <div className="pl-9 relative mb-2">
        <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-[var(--muted)]" />
        <input placeholder="Search products…" value={q} onChange={(e) => setQ(e.target.value)}
          className="w-full bg-[var(--surface)] border border-[var(--border)] rounded-md pl-7 pr-2 py-1 text-xs" />
      </div>
      <div className="pl-9 max-h-40 overflow-y-auto grid grid-cols-3 gap-1">
        {filtered.map(p => (
          <button key={p.id} data-testid={`slot-${idx}-prod-${p.name}`}
            onClick={() => onToggleProd(p.id)}
            className={`p-1.5 rounded border text-left ${
              slot.product_ids.includes(p.id) ? "bg-[var(--cyan)]/15 border-[var(--cyan)]"
                                              : "bg-[var(--surface)] border-[var(--border)]"
            }`}>
            <div className="text-[10px] font-semibold truncate">{p.name}</div>
            <div className="text-[9px] font-mono text-[var(--amber)]">{fmtHKD(p.price)}</div>
          </button>
        ))}
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
