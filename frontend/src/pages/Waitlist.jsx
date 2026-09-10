import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Phone, MessageSquare, Trash2, ChevronRight, Users as UsersIcon, Clock } from "lucide-react";

export default function Waitlist() {
  const [rows, setRows] = useState([]);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [size, setSize] = useState(2);
  const [wait, setWait] = useState(15);
  const [now, setNow] = useState(Date.now());

  const load = useCallback(async () => setRows((await api.get("/waitlist")).data), []);
  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    const c = setInterval(() => setNow(Date.now()), 30000);
    return () => { clearInterval(t); clearInterval(c); };
  }, [load]);

  const add = async () => {
    if (!name || !phone) return toast.error("Name & phone required");
    try {
      await api.post("/waitlist", { name, phone, party_size: parseInt(size, 10), quoted_wait_min: parseInt(wait, 10) });
      toast.success(`${name} added to waitlist`);
      setName(""); setPhone(""); setSize(2); setWait(15);
      load();
    } catch { toast.error("Failed"); }
  };

  const notify = async (w) => {
    try {
      const r = await api.post(`/waitlist/${w.id}/notify`);
      toast.success(`SMS sent to ${r.data.mocked_sms_to} · "${r.data.message}"`, { duration: 5000 });
      load();
    } catch { toast.error("Failed"); }
  };
  const seat = async (w) => { await api.post(`/waitlist/${w.id}/seat`); toast.success("Seated"); load(); };
  const cancel = async (w) => {
    if (!confirm(`Remove ${w.name}?`)) return;
    await api.delete(`/waitlist/${w.id}`); load();
  };

  const waiting = rows.filter(r => r.status === "waiting");
  const notified = rows.filter(r => r.status === "notified");
  const totalCovers = rows.reduce((s, r) => s + (r.party_size || 0), 0);
  const avgWait = waiting.length ? Math.round(waiting.reduce((s, r) => {
    const mins = Math.max(0, (now - new Date(r.added_at).getTime()) / 60000);
    return s + mins;
  }, 0) / waiting.length) : 0;

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <h1 className="font-display text-2xl font-black">Waitlist</h1>
      </div>

      <div className="grid grid-cols-4 gap-3 mb-4">
        <Stat label="Waiting" value={waiting.length} color="#FFB800" testid="wait-count" />
        <Stat label="Notified" value={notified.length} color="#00F2FE" testid="wait-notified" />
        <Stat label="Total Covers" value={totalCovers} color="#A855F7" testid="wait-covers" />
        <Stat label="Avg Wait" value={`${avgWait}m`} color="#10B981" testid="wait-avg" />
      </div>

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5">
          <div className="font-display font-black text-lg mb-3">Add to Waitlist</div>
          <div className="space-y-3">
            <FormField label="Name">
              <input data-testid="wait-name" value={name} onChange={(e) => setName(e.target.value)} className={inp} />
            </FormField>
            <FormField label="Phone">
              <input data-testid="wait-phone" value={phone} onChange={(e) => setPhone(e.target.value)} className={inp} />
            </FormField>
            <div className="grid grid-cols-2 gap-2">
              <FormField label="Party Size">
                <input data-testid="wait-size" type="number" min="1" value={size} onChange={(e) => setSize(e.target.value)} className={inp} />
              </FormField>
              <FormField label="Quote (min)">
                <input data-testid="wait-quote" type="number" min="1" value={wait} onChange={(e) => setWait(e.target.value)} className={inp} />
              </FormField>
            </div>
            <button data-testid="wait-add" onClick={add} className="w-full btn-neon py-2.5 rounded-lg mt-2 flex items-center justify-center gap-2">
              <Plus size={16} /> Add to Queue
            </button>
          </div>
        </div>

        <div className="col-span-8 space-y-2">
          {rows.length === 0 && (
            <div className="p-8 rounded-xl border border-dashed border-[var(--border)] text-center text-[var(--muted)]">
              No one waiting — the floor is yours.
            </div>
          )}
          {rows.map(w => {
            const mins = Math.round((now - new Date(w.added_at).getTime()) / 60000);
            const overdue = mins > w.quoted_wait_min;
            return (
              <div key={w.id} data-testid={`wait-row-${w.name}`}
                className={`p-4 rounded-xl border flex items-center gap-4 ${
                  w.status === "notified"
                    ? "border-[var(--cyan)]/40 bg-[var(--cyan)]/5"
                    : overdue
                    ? "border-[var(--rose)]/40 bg-[var(--rose)]/5"
                    : "border-[var(--border)] bg-[var(--surface)]"
                }`}>
                <div className="w-10 h-10 rounded-full bg-[var(--surface-2)] flex items-center justify-center font-bold">
                  {w.name?.[0]}
                </div>
                <div>
                  <div className="font-semibold">{w.name}</div>
                  <div className="text-xs text-[var(--muted)] flex items-center gap-2">
                    <Phone size={10} /> {w.phone}
                    <span>·</span>
                    <UsersIcon size={10} /> {w.party_size} pax
                  </div>
                </div>
                <div className="ml-auto flex items-center gap-4">
                  <div className="text-right">
                    <div className="text-[10px] font-mono uppercase text-[var(--muted)]">Wait</div>
                    <div className={`font-mono font-black ${overdue ? "text-[var(--rose)]" : ""}`}>
                      {mins}/{w.quoted_wait_min}m
                    </div>
                  </div>
                  {w.status === "waiting" && (
                    <button data-testid={`wait-notify-${w.name}`} onClick={() => notify(w)}
                      className="px-3 py-2 rounded-lg bg-[var(--cyan)]/15 border border-[var(--cyan)] text-[var(--cyan)] text-xs font-mono uppercase flex items-center gap-1.5">
                      <MessageSquare size={12} /> Text
                    </button>
                  )}
                  {w.status === "notified" && (
                    <span className="text-[10px] font-mono uppercase text-[var(--cyan)] flex items-center gap-1">
                      <MessageSquare size={10} /> Notified
                    </span>
                  )}
                  <button data-testid={`wait-seat-${w.name}`} onClick={() => seat(w)}
                    className="px-3 py-2 rounded-lg btn-neon text-xs uppercase font-mono flex items-center gap-1.5">
                    <ChevronRight size={12} /> Seat
                  </button>
                  <button data-testid={`wait-cancel-${w.name}`} onClick={() => cancel(w)}
                    className="w-8 h-8 rounded bg-[var(--surface-2)] text-[var(--rose)] flex items-center justify-center">
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

const inp = "w-full bg-[var(--surface-2)] border border-[var(--border)] rounded-md px-3 py-2 text-sm text-white focus:border-[var(--cyan)] focus:outline-none";
const FormField = ({ label, children }) => (
  <div>
    <div className="text-[10px] font-mono uppercase tracking-widest text-[var(--muted)] mb-1">{label}</div>
    {children}
  </div>
);
const Stat = ({ label, value, color, testid }) => (
  <div data-testid={testid} className="p-3 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
    <div className="text-[10px] font-mono uppercase text-[var(--muted)]">{label}</div>
    <div className="font-display font-black text-2xl mt-1" style={{ color }}>{value}</div>
  </div>
);
