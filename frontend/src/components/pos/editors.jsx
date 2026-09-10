import { useState, useEffect } from "react";
import { X, Plus, Trash2 } from "lucide-react";
import { fmtHKD } from "@/lib/api";

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function ProductEditor({ product, categories, onClose, onSave }) {
  const [name, setName] = useState(product?.name || "");
  const [categoryId, setCategoryId] = useState(product?.category_id || categories[0]?.id || "");
  const [price, setPrice] = useState(product?.price ?? 100);
  const [kind, setKind] = useState(product?.kind || "food");
  const [course, setCourse] = useState(product?.course || "main");
  const [description, setDescription] = useState(product?.description || "");
  const [hh, setHh] = useState(!!product?.happy_hour_eligible);
  const [variants, setVariants] = useState(product?.variants || []);
  const [modifiers, setModifiers] = useState(product?.modifiers || []);

  const submit = () => {
    onSave({
      name, category_id: categoryId, price: parseFloat(price) || 0, kind, course,
      description, happy_hour_eligible: hh, variants, modifiers,
    });
  };

  return (
    <Overlay onClose={onClose} title={product ? "Edit Product" : "New Product"} wide>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Name">
          <input data-testid="edit-prod-name" value={name} onChange={(e) => setName(e.target.value)} className={inp} />
        </Field>
        <Field label="Category">
          <select data-testid="edit-prod-category" value={categoryId} onChange={(e) => setCategoryId(e.target.value)} className={inp}>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </Field>
        <Field label="Price (HKD)">
          <input data-testid="edit-prod-price" type="number" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} className={inp} />
        </Field>
        <Field label="Kind">
          <select value={kind} onChange={(e) => setKind(e.target.value)} className={inp}>
            <option value="food">Food</option><option value="drink">Drink</option>
          </select>
        </Field>
        <Field label="Course">
          <select value={course} onChange={(e) => setCourse(e.target.value)} className={inp}>
            {["starter","main","dessert","drink","side","other"].map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </Field>
        <Field label="Happy Hour Eligible">
          <button
            data-testid="edit-prod-hh"
            onClick={() => setHh(!hh)}
            className={`w-full py-2 rounded-md border text-sm ${hh ? "bg-[var(--amber)]/20 border-[var(--amber)] text-[var(--amber)]" : "bg-[var(--surface-2)] border-[var(--border)] text-[var(--muted)]"}`}
          >
            {hh ? "YES · Auto-discount applies" : "NO"}
          </button>
        </Field>
      </div>

      <MatrixGrid
        label="Variants"
        subLabel="(e.g. Pint, Tower, Bucket · Medium Rare, Well Done)"
        rows={variants} setRows={setVariants}
        testId="variants"
      />
      <MatrixGrid
        label="Modifiers"
        subLabel="(e.g. Extra Lime, No Ice, Add Bacon)"
        rows={modifiers} setRows={setModifiers}
        testId="modifiers"
      />

      <Footer onClose={onClose} onSave={submit} testid="edit-prod-save" />
    </Overlay>
  );
}

function MatrixGrid({ label, subLabel, rows, setRows, testId }) {
  const add = () => setRows([...rows, { name: "", price_delta: 0 }]);
  const upd = (i, k, v) => setRows(rows.map((r, idx) => idx === i ? { ...r, [k]: k === "price_delta" ? parseFloat(v) || 0 : v } : r));
  const del = (i) => setRows(rows.filter((_, idx) => idx !== i));
  return (
    <div className="mt-4">
      <div className="flex items-center gap-2 mb-2">
        <div className="text-xs font-mono uppercase tracking-widest text-[var(--muted)]">{label}</div>
        <div className="text-[10px] font-mono text-[var(--muted)] opacity-60">{subLabel}</div>
        <button data-testid={`add-${testId}`} onClick={add} className="ml-auto text-[var(--cyan)] text-xs flex items-center gap-1 hover:underline">
          <Plus size={12} /> Add
        </button>
      </div>
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] divide-y divide-[var(--border)]">
        <div className="grid grid-cols-[1fr_180px_40px] text-[10px] font-mono uppercase text-[var(--muted)] px-3 py-2">
          <div>Name</div><div>Price Δ (HKD)</div><div></div>
        </div>
        {rows.length === 0 && <div className="px-3 py-4 text-xs text-[var(--muted)]">No {label.toLowerCase()} — tap "Add"</div>}
        {rows.map((r, i) => (
          <div key={r._k ?? `row-${i}`} className="grid grid-cols-[1fr_180px_40px] gap-2 px-3 py-2 items-center">
            <input data-testid={`${testId}-name-${i}`} value={r.name} onChange={(e) => upd(i, "name", e.target.value)} placeholder="e.g. Pint" className="bg-[var(--surface)] border border-[var(--border)] rounded px-2 py-1 text-sm" />
            <input data-testid={`${testId}-delta-${i}`} type="number" step="0.01" value={r.price_delta} onChange={(e) => upd(i, "price_delta", e.target.value)} className="bg-[var(--surface)] border border-[var(--border)] rounded px-2 py-1 text-sm font-mono" />
            <button onClick={() => del(i)} className="text-[var(--rose)]"><Trash2 size={14} /></button>
          </div>
        ))}
      </div>
    </div>
  );
}

export function CategoryEditor({ category, onClose, onSave }) {
  const [name, setName] = useState(category?.name || "");
  const [kind, setKind] = useState(category?.kind || "drink");
  const [color, setColor] = useState(category?.color || "#00F2FE");
  const COLORS = ["#00F2FE", "#FFB800", "#A855F7", "#F43F5E", "#10B981", "#06B6D4", "#EC4899", "#F59E0B"];
  return (
    <Overlay onClose={onClose} title={category ? "Edit Category" : "New Category"}>
      <Field label="Name">
        <input data-testid="edit-cat-name" value={name} onChange={(e) => setName(e.target.value)} className={inp} />
      </Field>
      <Field label="Kind">
        <select value={kind} onChange={(e) => setKind(e.target.value)} className={inp}>
          <option value="drink">Drink</option><option value="food">Food</option>
        </select>
      </Field>
      <Field label="Color">
        <div className="flex gap-2 flex-wrap">
          {COLORS.map((c) => (
            <button key={c} onClick={() => setColor(c)} className={`w-8 h-8 rounded-lg border-2 ${color === c ? "border-white" : "border-transparent"}`} style={{ background: c }} />
          ))}
        </div>
      </Field>
      <Footer onClose={onClose} onSave={() => onSave({ name, kind, color })} testid="edit-cat-save" />
    </Overlay>
  );
}

export function HappyHourEditor({ hh, categories, onClose, onSave }) {
  const [name, setName] = useState(hh?.name || "");
  const [start, setStart] = useState(hh?.start_time || "16:00");
  const [end, setEnd] = useState(hh?.end_time || "21:00");
  const [percent, setPercent] = useState(hh?.percent_off ?? 20);
  const [days, setDays] = useState(hh?.days || [0,1,2,3,4,5,6]);
  const [catIds, setCatIds] = useState(hh?.category_ids || []);
  const toggleDay = (d) => setDays(days.includes(d) ? days.filter(x => x !== d) : [...days, d]);
  const toggleCat = (c) => setCatIds(catIds.includes(c) ? catIds.filter(x => x !== c) : [...catIds, c]);
  return (
    <Overlay onClose={onClose} title={hh ? "Edit Happy Hour" : "New Happy Hour"} wide>
      <Field label="Name">
        <input data-testid="edit-hh-name" value={name} onChange={(e) => setName(e.target.value)} className={inp} />
      </Field>
      <Field label="Preset Tiers">
        <div className="grid grid-cols-3 gap-2">
          {[
            ["Opening", "15:00", "18:00", 10],
            ["Evening", "18:00", "21:00", 20],
            ["Late-night", "21:00", "03:00", 30],
          ].map(([label, s, e, pct]) => (
            <button key={label} data-testid={`hh-preset-${label}`}
              onClick={() => { setStart(s); setEnd(e); setPercent(pct); if (!name) setName(`${label} Hour`); }}
              className="p-2 rounded-md border border-[var(--border)] bg-[var(--surface-2)] text-left hover:border-[var(--amber)]">
              <div className="text-xs font-semibold">{label}</div>
              <div className="text-[10px] font-mono text-[var(--muted)]">{s}–{e} · -{pct}%</div>
            </button>
          ))}
        </div>
      </Field>
      <div className="grid grid-cols-3 gap-4">
        <Field label="Start (24h)"><input data-testid="edit-hh-start" type="time" value={start} onChange={(e) => setStart(e.target.value)} className={inp} /></Field>
        <Field label="End (24h)"><input data-testid="edit-hh-end" type="time" value={end} onChange={(e) => setEnd(e.target.value)} className={inp} /></Field>
        <Field label="Percent Off"><input data-testid="edit-hh-percent" type="number" value={percent} onChange={(e) => setPercent(parseFloat(e.target.value) || 0)} className={inp} /></Field>
      </div>
      <Field label="Days">
        <div className="flex gap-2">
          {DAY_NAMES.map((d, i) => (
            <button key={d} onClick={() => toggleDay(i)} data-testid={`hh-day-${d}`}
              className={`flex-1 py-2 rounded-md border text-xs font-mono uppercase ${days.includes(i) ? "bg-[var(--amber)]/20 border-[var(--amber)] text-[var(--amber)]" : "bg-[var(--surface-2)] border-[var(--border)] text-[var(--muted)]"}`}>
              {d}
            </button>
          ))}
        </div>
      </Field>
      <Field label="Eligible Categories">
        <div className="grid grid-cols-3 gap-2 max-h-48 overflow-y-auto">
          {categories.map((c) => (
            <button key={c.id} onClick={() => toggleCat(c.id)} data-testid={`hh-cat-${c.name}`}
              className={`p-2 rounded-md border text-left ${catIds.includes(c.id) ? "bg-[var(--cyan)]/15 border-[var(--cyan)] text-[var(--cyan)]" : "bg-[var(--surface-2)] border-[var(--border)] text-[var(--muted)]"}`}>
              <div className="w-2 h-2 rounded-full mb-1" style={{ background: c.color }} />
              <div className="text-xs font-semibold">{c.name}</div>
            </button>
          ))}
        </div>
      </Field>
      <Footer onClose={onClose} onSave={() => onSave({ name, start_time: start, end_time: end, percent_off: percent, days, category_ids: catIds })} testid="edit-hh-save" />
    </Overlay>
  );
}

// ------ shared bits ------
const inp = "w-full bg-[var(--surface-2)] border border-[var(--border)] rounded-md px-3 py-2 text-sm text-white focus:border-[var(--cyan)] focus:outline-none";
const Field = ({ label, children }) => (
  <div className="mb-3">
    <div className="text-[10px] font-mono uppercase tracking-widest text-[var(--muted)] mb-1">{label}</div>
    {children}
  </div>
);
const Footer = ({ onClose, onSave, testid }) => (
  <div className="flex gap-2 mt-6 sticky bottom-0 bg-[var(--surface)] pt-4 -mx-6 px-6 pb-1 border-t border-[var(--border)]">
    <button onClick={onClose} className="flex-1 py-2.5 rounded-lg bg-[var(--surface-2)] border border-[var(--border)]">Cancel</button>
    <button data-testid={testid} onClick={onSave} className="flex-1 btn-neon py-2.5 rounded-lg">Save</button>
  </div>
);

function Overlay({ children, onClose, title, wide }) {
  useEffect(() => {
    const esc = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div className={`bg-[var(--surface)] border border-[var(--border)] rounded-xl w-full ${wide ? "max-w-3xl" : "max-w-lg"} max-h-[90vh] overflow-y-auto p-6 relative`}>
        <div className="flex items-center justify-between mb-5">
          <h2 className="font-display font-black text-xl">{title}</h2>
          <button onClick={onClose} className="text-[var(--muted)] hover:text-white"><X size={20} /></button>
        </div>
        {children}
      </div>
    </div>
  );
}
