import { useEffect, useState } from "react";
import { api, fmtHKD } from "@/lib/api";
import { toast } from "sonner";
import { Truck, RefreshCw, PhoneCall, Flame, Zap } from "lucide-react";

const PLATFORM_STYLE = {
  foodpanda:  { bg: "bg-[var(--rose)]/10",   border: "border-[var(--rose)]/40",   text: "text-[var(--rose)]",   label: "foodpanda" },
  deliveroo:  { bg: "bg-[var(--emerald)]/10", border: "border-[var(--emerald)]/40", text: "text-[var(--emerald)]", label: "Deliveroo" },
  keeta:      { bg: "bg-[var(--amber)]/10",  border: "border-[var(--amber)]/40",  text: "text-[var(--amber)]",  label: "KeeTa" },
};

export default function Delivery() {
  const [orders, setOrders] = useState([]);
  const [busy, setBusy] = useState(false);

  const load = () => api.get("/delivery/inbox").then((r) => setOrders(r.data));
  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  const simulate = async () => {
    setBusy(true);
    try {
      const r = await api.post("/delivery/simulate");
      toast.success(`${r.data.delivery.platform.toUpperCase()} order ingested · ${fmtHKD(r.data.total)}`);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };

  const open = orders.filter((o) => o.status === "open").length;
  const revenue = orders.reduce((s, o) => s + (o.total || 0), 0);

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <h1 className="font-display text-3xl font-black flex items-center gap-2">
          <Truck className="text-[var(--cyan)]" /> Delivery Inbox
        </h1>
        <div className="ml-auto flex gap-2">
          <button data-testid="btn-delivery-refresh" onClick={load}
            className="px-4 py-2 rounded-lg font-mono text-xs uppercase border bg-[var(--surface)] text-white border-[var(--border)] flex items-center gap-2">
            <RefreshCw size={12} /> Refresh
          </button>
          <button data-testid="btn-delivery-simulate" onClick={simulate} disabled={busy}
            className="btn-neon px-4 py-2 rounded-lg text-xs uppercase flex items-center gap-2 disabled:opacity-40">
            <Zap size={12} /> Simulate Order
          </button>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3 mb-4">
        <Kpi label="Open" value={open} data-testid="kpi-delivery-open" />
        <Kpi label="Total Today" value={orders.length} data-testid="kpi-delivery-total" />
        <Kpi label="Gross" value={fmtHKD(revenue)} data-testid="kpi-delivery-gross" />
        <div className="p-3 rounded-xl border border-dashed border-[var(--border)] bg-[var(--surface)] text-[10px] font-mono uppercase text-[var(--muted)] flex items-center px-4">
          MOCKED integration — simulate ingests as if from Foodpanda / Deliveroo / KeeTa
        </div>
      </div>

      {orders.length === 0 && (
        <div className="p-10 rounded-xl border border-dashed border-[var(--border)] text-center text-[var(--muted)]">
          No delivery orders yet. Tap <span className="text-[var(--cyan)]">Simulate Order</span> to bring one in.
        </div>
      )}

      <div className="grid grid-cols-3 gap-3">
        {orders.map((o) => {
          const p = PLATFORM_STYLE[o.delivery?.platform] || PLATFORM_STYLE.foodpanda;
          const ago = Math.max(0, Math.round((Date.now() - new Date(o.delivery?.ingested_at).getTime()) / 60000));
          return (
            <div key={o.id} data-testid={`delivery-card-${o.delivery?.external_id}`}
              className={`p-4 rounded-xl border ${p.border} ${p.bg}`}>
              <div className="flex items-center gap-2">
                <span className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded-full border ${p.border} ${p.text} font-bold`}>
                  {p.label}
                </span>
                <span className="text-[10px] font-mono uppercase text-[var(--muted)]">#{o.delivery?.external_id}</span>
                <span className="ml-auto text-[10px] font-mono uppercase text-[var(--muted)] flex items-center gap-1">
                  <Flame size={10} className="text-[var(--amber)]" /> fired {ago}m ago
                </span>
              </div>
              <div className="mt-2 font-display font-black text-lg">{o.delivery?.customer_name}</div>
              <div className="text-[10px] font-mono text-[var(--muted)] flex items-center gap-1">
                <PhoneCall size={9} /> {o.delivery?.customer_phone || "n/a"}
              </div>
              <div className="mt-3 space-y-0.5">
                {o.lines?.map((l, i) => (
                  <div key={i} className="text-xs flex justify-between">
                    <span>{l.qty}× {l.name}</span>
                    <span className="font-mono text-[var(--muted)]">{fmtHKD(l.price * l.qty)}</span>
                  </div>
                ))}
              </div>
              <div className="mt-3 pt-2 border-t border-[var(--border)] flex justify-between items-baseline">
                <span className="text-[10px] font-mono uppercase text-[var(--muted)]">Total</span>
                <span className="font-mono font-black text-xl text-[var(--amber)]">{fmtHKD(o.total || 0)}</span>
              </div>
              <div className="mt-1 text-[9px] font-mono uppercase text-[var(--muted)]">
                {o.status === "open" ? "On KDS" : o.status}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Kpi({ label, value, ...rest }) {
  return (
    <div {...rest} className="p-3 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
      <div className="text-[10px] font-mono uppercase text-[var(--muted)]">{label}</div>
      <div className="font-display font-black text-2xl text-white">{value}</div>
    </div>
  );
}
