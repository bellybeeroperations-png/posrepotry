import { useState } from "react";
import { X, CreditCard, User as UserIcon, Users } from "lucide-react";

export default function PreauthModal({ table, onClose, onOpened }) {
  const [name, setName] = useState("");
  const [last4, setLast4] = useState("");
  const [hold, setHold] = useState(500);
  const [size, setSize] = useState(table?.seats || 2);
  const [busy, setBusy] = useState(false);
  const [stripeReady, setStripeReady] = useState(false);
  const [stripeInfo, setStripeInfo] = useState(null);

  const canOpen = name.trim() && /^\d{4}$/.test(last4);

  const createStripeHold = async () => {
    setBusy(true);
    try {
      const r = await (await import("@/lib/api")).api.post("/tabs/preauth/setup-intent", {
        customer_name: name.trim() || "Guest",
        metadata: { hold_amount: String(hold) },
      });
      setStripeInfo(r.data);
      setStripeReady(true);
    } catch (e) { console.error(e); }
    finally { setBusy(false); }
  };

  const submit = async () => {
    setBusy(true);
    try {
      await onOpened({
        customer_name: name.trim(),
        card_last4: last4,
        hold_amount: parseFloat(hold) || 0,
        table_id: table?.id || null,
        party_size: parseInt(size, 10) || 1,
      });
    } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="font-display font-black text-xl flex items-center gap-2">
              <CreditCard className="text-[var(--cyan)]" size={20} /> Preauth Tab
            </div>
            <div className="text-[10px] font-mono uppercase text-[var(--muted)]">
              {table ? `Table ${table.name}` : "Standing / bar tab"} · card-on-file style
            </div>
          </div>
          <button onClick={onClose} className="text-[var(--muted)]"><X size={20} /></button>
        </div>
        <div className="space-y-3">
          <Field icon={UserIcon} label="Guest name">
            <input data-testid="preauth-name" value={name} onChange={(e) => setName(e.target.value)}
              className={inp} placeholder="e.g. Michael Cheung" />
          </Field>
          <Field icon={CreditCard} label="Card last 4">
            <input data-testid="preauth-last4" value={last4} inputMode="numeric" maxLength="4"
              onChange={(e) => setLast4(e.target.value.replace(/\D/g, "").slice(0, 4))}
              className={`${inp} font-mono tracking-widest`} placeholder="1234" />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Hold amount HKD">
              <input data-testid="preauth-hold" type="number" min="0" value={hold}
                onChange={(e) => setHold(e.target.value)} className={inp} />
            </Field>
            <Field icon={Users} label="Party size">
              <input data-testid="preauth-size" type="number" min="1" value={size}
                onChange={(e) => setSize(e.target.value)} className={inp} />
            </Field>
          </div>
          <div className="p-2.5 rounded-lg bg-[var(--cyan)]/10 border border-[var(--cyan)]/30 text-[10px] font-mono text-[var(--cyan)] leading-relaxed">
            {stripeReady ? (
              <>Stripe SetupIntent <span className="font-black">{stripeInfo?.setup_intent_id?.slice(0, 12)}…</span> created ✓ · At last call, auto-close charges the on-file card.</>
            ) : (
              <>Click <span className="font-black">Create Card Hold</span> to reserve a real Stripe SetupIntent (test-mode) — or open the tab with the last-4 only.</>
            )}
          </div>
        </div>
        <div className="flex gap-2 mt-4">
          <button onClick={onClose} className="px-4 py-2.5 rounded-lg bg-[var(--surface-2)] border border-[var(--border)]">Cancel</button>
          <button data-testid="preauth-stripe" onClick={createStripeHold} disabled={busy || !name.trim() || stripeReady}
            className="flex-1 py-2.5 rounded-lg bg-[var(--surface-2)] border border-[var(--cyan)] text-[var(--cyan)] disabled:opacity-40">
            {stripeReady ? "Hold Created ✓" : (busy ? "Creating…" : "Create Card Hold")}
          </button>
          <button data-testid="preauth-open" onClick={submit} disabled={!canOpen || busy}
            className="flex-1 btn-neon py-2.5 rounded-lg disabled:opacity-40">
            {busy ? "Opening…" : "Open Tab"}
          </button>
        </div>
      </div>
    </div>
  );
}

const inp = "w-full bg-[var(--surface-2)] border border-[var(--border)] rounded-md px-3 py-2 text-sm text-white focus:border-[var(--cyan)] focus:outline-none";
const Field = ({ icon: Icon, label, children }) => (
  <div>
    <div className="text-[10px] font-mono uppercase tracking-widest text-[var(--muted)] mb-1 flex items-center gap-1">
      {Icon && <Icon size={10} />} {label}
    </div>
    {children}
  </div>
);
