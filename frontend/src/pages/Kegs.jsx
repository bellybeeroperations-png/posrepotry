import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Beer, RefreshCw, Ban, AlertTriangle, Plus, Trash2, TrendingUp } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

export default function Kegs() {
  const [kegs, setKegs] = useState([]);
  const [products, setProducts] = useState([]);
  const [selKeg, setSelKeg] = useState(null);

  const load = useCallback(async () => {
    const [k, p] = await Promise.all([api.get("/kegs"), api.get("/products")]);
    setKegs(k.data); setProducts(p.data);
  }, []);
  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [load]);

  const install = async (k) => {
    if (!confirm(`Install fresh keg for ${k.name}?`)) return;
    await api.post(`/kegs/${k.id}/new`);
    toast.success("Fresh keg installed"); load();
  };
  const blown = async (k) => {
    if (!confirm(`Mark ${k.name} as blown?`)) return;
    await api.post(`/kegs/${k.id}/blown`);
    toast.error(`${k.name} blown`); load();
  };
  const del = async (k) => {
    if (!confirm(`Delete keg ${k.name}?`)) return;
    await api.delete(`/kegs/${k.id}`); load();
  };
  const add = async () => {
    const name = prompt("Tap name?", `Tap ${kegs.length + 1}`);
    if (!name) return;
    const pname = prompt("Beer name (must exist in Menu products)?");
    const p = products.find(x => x.name.toLowerCase() === (pname || "").toLowerCase());
    if (!p) return toast.error("Product not found");
    await api.post("/kegs", { name, product_id: p.id, size_ml: 30000, ml_per_pour: 568, threshold_pct: 10 });
    toast.success("Keg added"); load();
  };

  const alerts = kegs.filter(k => k.alert).length;
  const blown_ = kegs.filter(k => k.status === "blown").length;

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <h1 className="font-display text-2xl font-black">Keg Watch · {kegs.length} taps</h1>
        <div className="ml-auto flex gap-2">
          <button data-testid="btn-add-keg" onClick={add} className="btn-neon px-4 py-2 rounded-lg text-xs uppercase flex items-center gap-2">
            <Plus size={14} /> Add Keg
          </button>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3 mb-4">
        <Kpi label="Total Taps" value={kegs.length} color="#00F2FE" testid="kegs-total" />
        <Kpi label="Alerts (<10%)" value={alerts} color="#F43F5E" testid="kegs-alerts" />
        <Kpi label="Blown" value={blown_} color="#94A3B8" testid="kegs-blown" />
        <Kpi label="On Tap" value={kegs.filter(k => k.status === "on").length} color="#10B981" testid="kegs-on" />
      </div>

      <div className="grid grid-cols-3 gap-3">
        {kegs.map(k => {
          const pct = k.pct_remaining || 0;
          const barColor = pct <= k.threshold_pct ? "#F43F5E" : pct < 30 ? "#FFB800" : "#10B981";
          const isBlown = k.status === "blown";
          return (
            <div
              key={k.id}
              data-testid={`keg-${k.name}`}
              className={`p-4 rounded-xl border ${
                isBlown ? "border-[var(--muted)]/30 bg-[var(--surface)] opacity-70"
                        : k.alert ? "border-[var(--rose)] bg-[var(--rose)]/5 animate-pulse" : "border-[var(--border)] bg-[var(--surface)]"
              }`}
            >
              <div className="flex items-center gap-2">
                <Beer size={16} className="text-[var(--amber)]" />
                <div className="font-display font-bold text-white">{k.name}</div>
                {k.alert && <AlertTriangle size={14} className="ml-auto text-[var(--rose)]" />}
                {isBlown && <span className="ml-auto text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-[var(--rose)] text-white font-black">BLOWN</span>}
              </div>
              <div className="text-[10px] font-mono uppercase text-[var(--muted)] mt-1">{k.product?.name || "unlinked"}</div>

              <div className="mt-3">
                <div className="flex items-center justify-between text-[10px] font-mono">
                  <span className="text-[var(--muted)]">{Math.round((k.current_ml || 0) / 1000)}L / {Math.round(k.size_ml / 1000)}L</span>
                  <span data-testid={`keg-pct-${k.name}`} style={{ color: barColor }} className="font-bold">{pct}%</span>
                </div>
                <div className="mt-1 h-2 rounded-full bg-[var(--surface-2)] overflow-hidden">
                  <div className="h-full transition-all" style={{ width: `${Math.max(2, pct)}%`, background: barColor }} />
                </div>
                <div className="text-[10px] font-mono text-[var(--muted)] mt-1">
                  {Math.floor((k.current_ml || 0) / (k.ml_per_pour || 568))} pours remaining · {k.ml_per_pour}ml/pour
                </div>
              </div>

              <div className="grid grid-cols-3 gap-1 mt-3">
                <button data-testid={`keg-new-${k.name}`} onClick={() => install(k)}
                  className="py-1.5 rounded bg-[var(--surface-2)] border border-[var(--border)] text-[10px] font-mono uppercase text-[var(--emerald)] flex items-center justify-center gap-1">
                  <RefreshCw size={10} /> New
                </button>
                <button data-testid={`keg-blown-${k.name}`} onClick={() => blown(k)}
                  disabled={isBlown}
                  className="py-1.5 rounded bg-[var(--surface-2)] border border-[var(--border)] text-[10px] font-mono uppercase text-[var(--rose)] disabled:opacity-40 flex items-center justify-center gap-1">
                  <Ban size={10} /> Blown
                </button>
                <button data-testid={`keg-del-${k.name}`} onClick={() => del(k)}
                  className="py-1.5 rounded bg-[var(--surface-2)] border border-[var(--border)] text-[10px] font-mono uppercase text-[var(--muted)] flex items-center justify-center gap-1">
                  <Trash2 size={10} /> Del
                </button>
              </div>
              <button data-testid={`keg-chart-${k.name}`} onClick={() => setSelKeg(k)}
                className="mt-2 w-full py-1.5 rounded bg-[var(--cyan)]/10 border border-[var(--cyan)]/40 text-[10px] font-mono uppercase text-[var(--cyan)] flex items-center justify-center gap-1">
                <TrendingUp size={10} /> 7-day velocity
              </button>
            </div>
          );
        })}
        {kegs.length === 0 && (
          <div className="col-span-3 p-10 rounded-xl border border-dashed border-[var(--border)] text-center text-[var(--muted)]">
            No kegs yet — add your first tap.
          </div>
        )}
      </div>

      {selKeg && <KegAnalyticsModal keg={selKeg} onClose={() => setSelKeg(null)} />}
    </div>
  );
}

function KegAnalyticsModal({ keg, onClose }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    api.get(`/kegs/${keg.id}/pours`, { params: { days: 7 } }).then(r => setData(r.data));
  }, [keg.id]);

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl w-full max-w-2xl p-6" onClick={e => e.stopPropagation()}>
        <div className="flex items-center gap-2 mb-1">
          <TrendingUp size={18} className="text-[var(--cyan)]" />
          <div className="font-display font-black text-xl">{keg.name}</div>
          <button onClick={onClose} className="ml-auto text-[var(--muted)] hover:text-white">×</button>
        </div>
        <div className="text-xs font-mono uppercase text-[var(--muted)] mb-4">7-day pour velocity</div>
        {data && (
          <>
            <div className="grid grid-cols-3 gap-2 mb-4">
              <div className="p-2 rounded bg-[var(--surface-2)] border border-[var(--border)]">
                <div className="text-[10px] font-mono uppercase text-[var(--muted)]">Total (7d)</div>
                <div className="font-display font-black text-xl text-[var(--cyan)]" data-testid="keg-total-ml">{data.total_pints} pints</div>
              </div>
              <div className="p-2 rounded bg-[var(--surface-2)] border border-[var(--border)]">
                <div className="text-[10px] font-mono uppercase text-[var(--muted)]">Daily avg</div>
                <div className="font-display font-black text-xl">{(data.total_pints / 7).toFixed(1)}</div>
              </div>
              <div className="p-2 rounded bg-[var(--surface-2)] border border-[var(--border)]">
                <div className="text-[10px] font-mono uppercase text-[var(--muted)]">Peak day</div>
                <div className="font-display font-black text-xl">
                  {Math.max(0, ...data.days.map(d => d.pints))} pints
                </div>
              </div>
            </div>
            <div data-testid="keg-chart">
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={data.days}>
                  <XAxis dataKey="day" stroke="#94A3B8" fontSize={10}
                    tickFormatter={(d) => d.slice(5)} />
                  <YAxis stroke="#94A3B8" fontSize={10} />
                  <Tooltip contentStyle={{ background: "#121824", border: "1px solid #26334D" }}
                    formatter={(v) => [`${(v/568).toFixed(1)} pints`, "Pours"]} />
                  <Line type="monotone" dataKey="ml" stroke="#00F2FE" strokeWidth={2} dot={{ fill: "#00F2FE", r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

const Kpi = ({ label, value, color, testid }) => (
  <div data-testid={testid} className="p-3 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
    <div className="text-[10px] font-mono uppercase text-[var(--muted)]">{label}</div>
    <div className="font-display font-black text-2xl mt-1" style={{ color }}>{value}</div>
  </div>
);
