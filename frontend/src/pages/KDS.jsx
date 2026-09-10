import { useEffect, useState, useMemo } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Flame, Check, ChefHat, Wine } from "lucide-react";

const STATIONS = [
  ["all", "All", Flame],
  ["kitchen", "Kitchen", ChefHat],
  ["bar", "Bar", Wine],
];

function elapsed(iso) {
  if (!iso) return { min: 0, sec: 0 };
  const ms = Date.now() - new Date(iso).getTime();
  const min = Math.floor(ms / 60000);
  const sec = Math.floor((ms % 60000) / 1000);
  return { min, sec };
}

function ageColor(min) {
  if (min < 5) return "border-[var(--emerald)] bg-[var(--emerald)]/10";
  if (min < 10) return "border-[var(--amber)] bg-[var(--amber)]/10";
  return "border-[var(--rose)] bg-[var(--rose)]/15 animate-pulse";
}

export default function KDS() {
  const [station, setStation] = useState("all");
  const [tickets, setTickets] = useState([]);
  const [_, setTick] = useState(0);

  const load = () => api.get("/kds", { params: { station } }).then((r) => setTickets(r.data));
  useEffect(() => { load(); }, [station]);
  useEffect(() => {
    const t = setInterval(load, 4000);
    const c = setInterval(() => setTick(x => x + 1), 1000);
    return () => { clearInterval(t); clearInterval(c); };
  }, [station]);

  const bump = async (t) => {
    try {
      await api.post(`/orders/${t.order_id}/bump/${t.line_index}`);
      setTickets(tickets.filter(x => !(x.order_id === t.order_id && x.line_index === t.line_index)));
      toast.success(`Bumped: ${t.name}`);
    } catch { toast.error("Bump failed"); }
  };

  const stats = useMemo(() => {
    const now = Date.now();
    const over10 = tickets.filter(t => (now - new Date(t.fired_at).getTime()) / 60000 > 10).length;
    return { total: tickets.length, over10, food: tickets.filter(t => t.kind === "food").length, drink: tickets.filter(t => t.kind === "drink").length };
  }, [tickets]);

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <h1 className="font-display text-2xl font-black">Kitchen Display · KDS</h1>
        <div className="ml-auto flex gap-2">
          {STATIONS.map(([v, l, Icon]) => (
            <button
              key={v}
              data-testid={`kds-station-${v}`}
              onClick={() => setStation(v)}
              className={`px-4 py-2 rounded-lg font-mono text-xs uppercase tracking-widest border flex items-center gap-2 ${
                station === v ? "bg-[var(--cyan)] text-black border-transparent" : "bg-[var(--surface)] text-white border-[var(--border)]"
              }`}
            >
              <Icon size={14} /> {l}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3 mb-4">
        <StatCard label="Active Tickets" value={stats.total} color="#00F2FE" testid="kds-total" />
        <StatCard label="Food" value={stats.food} color="#F59E0B" testid="kds-food" />
        <StatCard label="Drinks" value={stats.drink} color="#A855F7" testid="kds-drink" />
        <StatCard label=">10m Late" value={stats.over10} color="#F43F5E" testid="kds-late" />
      </div>

      {tickets.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--border)] p-14 text-center">
          <Flame size={40} className="mx-auto text-[var(--muted)] mb-3" />
          <div className="font-display font-black text-xl mb-1">All caught up</div>
          <div className="text-sm text-[var(--muted)]">No fired items awaiting the {station === "all" ? "line" : station}.</div>
        </div>
      ) : (
        <div className="grid grid-cols-4 gap-3">
          {tickets.map(t => {
            const { min, sec } = elapsed(t.fired_at);
            return (
              <div
                key={`${t.order_id}-${t.line_index}`}
                data-testid={`kds-ticket-${t.order_id}-${t.line_index}`}
                className={`p-4 rounded-xl border-2 ${ageColor(min)} flex flex-col`}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="text-[10px] font-mono uppercase text-[var(--muted)]">
                      {t.table} · {t.course}
                    </div>
                    <div className="font-display font-black text-lg leading-tight mt-0.5">
                      {t.qty}× {t.name}
                    </div>
                  </div>
                  <div className="font-mono font-black text-xl tabular-nums">
                    {min}:{sec.toString().padStart(2, "0")}
                  </div>
                </div>
                {t.modifiers?.length > 0 && (
                  <div className="mt-2 text-xs text-[var(--amber)]">+ {t.modifiers.join(", ")}</div>
                )}
                {t.notes && (
                  <div className="mt-1 text-xs italic text-[var(--muted)]">"{t.notes}"</div>
                )}
                <button
                  data-testid={`kds-bump-${t.order_id}-${t.line_index}`}
                  onClick={() => bump(t)}
                  className="mt-auto btn-neon py-2 rounded-lg text-sm mt-3 flex items-center justify-center gap-2"
                >
                  <Check size={16} /> Bump
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, color, testid }) {
  return (
    <div data-testid={testid} className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
      <div className="text-[10px] font-mono uppercase text-[var(--muted)]">{label}</div>
      <div className="font-display font-black text-2xl mt-1" style={{ color }}>{value}</div>
    </div>
  );
}
