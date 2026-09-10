import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { X, Calendar, Phone, User as UserIcon, Users } from "lucide-react";

export function ReservationModal({ table, onClose, onSaved }) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [size, setSize] = useState(2);
  const now = new Date();
  const soon = new Date(now.getTime() + 30 * 60000);
  const [when, setWhen] = useState(soon.toISOString().slice(0, 16));
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);

  const save = async () => {
    if (!name || !phone) return toast.error("Name & phone required");
    setBusy(true);
    try {
      await api.post("/reservations", {
        table_id: table.id, guest_name: name, phone, party_size: parseInt(size, 10),
        reserved_for: new Date(when).toISOString(), notes,
      });
      toast.success(`Table ${table.name} reserved for ${name}`);
      onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="font-display font-black text-xl">Reserve Table {table.name}</div>
            <div className="text-xs font-mono uppercase text-[var(--muted)]">{table.seats} seats</div>
          </div>
          <button onClick={onClose} className="text-[var(--muted)]"><X size={20} /></button>
        </div>
        <div className="space-y-3">
          <Field icon={UserIcon} label="Guest name">
            <input data-testid="res-name" value={name} onChange={(e) => setName(e.target.value)}
              className="w-full bg-[var(--surface-2)] border border-[var(--border)] rounded-md px-3 py-2 text-sm text-white" />
          </Field>
          <Field icon={Phone} label="Phone">
            <input data-testid="res-phone" value={phone} onChange={(e) => setPhone(e.target.value)}
              className="w-full bg-[var(--surface-2)] border border-[var(--border)] rounded-md px-3 py-2 text-sm text-white" />
          </Field>
          <div className="grid grid-cols-2 gap-2">
            <Field icon={Users} label="Party size">
              <input data-testid="res-size" type="number" min="1" value={size} onChange={(e) => setSize(e.target.value)}
                className="w-full bg-[var(--surface-2)] border border-[var(--border)] rounded-md px-3 py-2 text-sm text-white" />
            </Field>
            <Field icon={Calendar} label="Reserved for">
              <input data-testid="res-when" type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)}
                className="w-full bg-[var(--surface-2)] border border-[var(--border)] rounded-md px-3 py-2 text-sm text-white" />
            </Field>
          </div>
          <Field label="Notes (optional)">
            <input data-testid="res-notes" value={notes} onChange={(e) => setNotes(e.target.value)}
              placeholder="Birthday, allergies, seating preference..."
              className="w-full bg-[var(--surface-2)] border border-[var(--border)] rounded-md px-3 py-2 text-sm text-white" />
          </Field>
        </div>
        <div className="flex gap-2 mt-5">
          <button onClick={onClose} className="flex-1 py-2.5 rounded-lg bg-[var(--surface-2)] border border-[var(--border)]">Cancel</button>
          <button data-testid="res-save" onClick={save} disabled={busy} className="flex-1 btn-neon py-2.5 rounded-lg">
            Reserve
          </button>
        </div>
      </div>
    </div>
  );
}

export function TableActionModal({ table, onClose, onSeat, onCancel, onReserve, onOpen, onQR, onMerge, otherOccupied }) {
  const [pickMerge, setPickMerge] = useState(false);
  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl w-full max-w-sm p-6" onClick={e => e.stopPropagation()}>
        <div className="font-display font-black text-2xl">Table {table.name}</div>
        <div className="text-xs font-mono uppercase text-[var(--muted)] mb-4">
          {table.status.replace("_", " ")} · {table.seats} seats
        </div>
        {table.reservation && (
          <div className="mb-4 p-3 rounded-lg border border-[var(--purple)]/40 bg-[var(--purple)]/10 text-sm">
            <div className="font-semibold">{table.reservation.guest_name}</div>
            <div className="text-xs text-[var(--muted)]">
              {table.reservation.phone} · {table.reservation.party_size} pax
            </div>
            <div className="text-xs font-mono text-[var(--purple)] mt-1">
              Reserved for {new Date(table.reservation.reserved_for).toLocaleString("en-HK", { timeZone: "Asia/Hong_Kong" })}
            </div>
          </div>
        )}

        {pickMerge && table.status === "occupied" && (
          <div data-testid="merge-picker" className="mb-3 rounded-lg border border-[var(--cyan)]/40 bg-[var(--cyan)]/5 p-3">
            <div className="text-[10px] font-mono uppercase text-[var(--cyan)] mb-2">Merge INTO which tab?</div>
            {(otherOccupied || []).length === 0 && (
              <div className="text-xs text-[var(--muted)]">No other occupied tables to merge with.</div>
            )}
            <div className="grid grid-cols-2 gap-2">
              {(otherOccupied || []).map((t) => (
                <button key={t.id} data-testid={`merge-target-${t.name}`}
                  onClick={() => onMerge(t)}
                  className="p-2 rounded-lg border border-[var(--cyan)]/40 bg-[var(--surface-2)] text-left hover:border-[var(--cyan)]">
                  <div className="font-display font-bold text-sm">Table {t.name}</div>
                  <div className="text-[10px] font-mono text-[var(--muted)]">
                    {t.current_order?.guests || 0} pax · HK${t.current_order?.total || 0}
                  </div>
                </button>
              ))}
            </div>
            <button onClick={() => setPickMerge(false)} className="mt-2 text-[10px] font-mono uppercase text-[var(--muted)]">Cancel merge</button>
          </div>
        )}

        {!pickMerge && (
          <div className="space-y-2">
            {(table.status === "available" || table.status === "reserved") && (
              <button data-testid="action-open-order" onClick={onOpen} className="w-full btn-neon py-3 rounded-lg">
                {table.reservation ? "Seat & Open Order" : "Open New Order"}
              </button>
            )}
            {table.status === "occupied" && (
              <>
                <button data-testid="action-continue-order" onClick={onOpen} className="w-full btn-neon py-3 rounded-lg">
                  Continue Order
                </button>
                {onMerge && (
                  <button data-testid="action-merge" onClick={() => setPickMerge(true)}
                    className="w-full py-3 rounded-lg bg-[var(--cyan)]/15 border border-[var(--cyan)] text-[var(--cyan)] font-semibold">
                    Merge Into Another Tab…
                  </button>
                )}
              </>
            )}
            {table.status === "available" && !table.reservation && (
              <button data-testid="action-reserve" onClick={onReserve}
                className="w-full py-3 rounded-lg bg-[var(--purple)]/15 border border-[var(--purple)] text-[var(--purple)] font-semibold">
                Reserve
              </button>
            )}
            <button data-testid="action-qr" onClick={onQR}
              className="w-full py-3 rounded-lg bg-[var(--surface-2)] border border-[var(--border)] text-[var(--cyan)] font-semibold">
              Menu QR Code
            </button>
            {table.reservation && (
              <button data-testid="action-cancel-res" onClick={onCancel}
                className="w-full py-3 rounded-lg bg-[var(--rose)]/10 border border-[var(--rose)] text-[var(--rose)] font-semibold">
                Cancel Reservation
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

const Field = ({ icon: Icon, label, children }) => (
  <div>
    <div className="text-[10px] font-mono uppercase tracking-widest text-[var(--muted)] mb-1 flex items-center gap-1">
      {Icon && <Icon size={10} />} {label}
    </div>
    {children}
  </div>
);
