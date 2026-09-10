import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, fmtHKD } from "@/lib/api";
import { Sparkles, Search, MapPin } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export default function MobileMenu() {
  const { tableId } = useParams();
  const [data, setData] = useState(null);
  const [q, setQ] = useState("");
  const [activeCat, setActiveCat] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${BACKEND_URL}/api/public/menu/${tableId}`);
        if (!r.ok) throw new Error("Not found");
        const d = await r.json();
        setData(d);
        setActiveCat(d.categories[0]?.id || null);
      } catch (e) {
        setData({ error: "Table not found" });
      }
    })();
  }, [tableId]);

  if (!data) return <FullScreenSpinner />;
  if (data.error) return <div className="min-h-screen flex items-center justify-center text-[var(--muted)]">{data.error}</div>;

  const activeHhIds = new Set();
  (data.active_hh || []).forEach(h => (h.category_ids || []).forEach(id => activeHhIds.add(id)));
  const hhPercent = (data.active_hh?.[0]?.percent_off) || 0;

  const filtered = (data.products || []).filter(p => {
    const inCat = !activeCat || p.category_id === activeCat;
    const inQ = !q || p.name.toLowerCase().includes(q.toLowerCase());
    return inCat && inQ;
  });

  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--text)] noise pb-20" data-testid="mobile-menu">
      <div className="max-w-md mx-auto px-4">
        {/* Header */}
        <div className="pt-6 pb-4 sticky top-0 bg-[var(--bg)]/80 backdrop-blur-md z-20 -mx-4 px-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-display font-black text-3xl">
                <span className="text-[var(--cyan)]">HK</span>
                <span className="text-white">·</span>
                <span className="text-[var(--amber)]">BAR</span>
              </div>
              <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-[var(--muted)] mt-1">
                Advanced POS · Hong Kong
              </div>
            </div>
            <div className="text-right">
              <div className="text-[10px] font-mono uppercase text-[var(--muted)] flex items-center gap-1 justify-end">
                <MapPin size={10} /> Your Table
              </div>
              <div className="font-display font-black text-2xl text-[var(--cyan)]">
                {data.table?.name}
              </div>
              {data.area && <div className="text-[10px] font-mono text-[var(--muted)]">{data.area.name}</div>}
            </div>
          </div>

          {data.active_hh?.length > 0 && (
            <div className="mt-3 px-3 py-2 rounded-lg border border-[var(--amber)]/50 bg-[var(--amber)]/10 flex items-center gap-2 text-xs">
              <Sparkles size={14} className="text-[var(--amber)]" />
              <span className="font-mono uppercase font-bold text-[var(--amber)] tracking-widest">Happy Hour</span>
              <span className="text-[var(--muted)]">-{hhPercent}% until {data.active_hh[0].end_time}</span>
            </div>
          )}

          <div className="mt-3 relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted)]" />
            <input
              data-testid="menu-search"
              placeholder="Search menu…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="w-full bg-[var(--surface)] border border-[var(--border)] rounded-lg pl-9 pr-3 py-2.5 text-sm text-white focus:border-[var(--cyan)] focus:outline-none"
            />
          </div>

          <div className="flex gap-1.5 mt-3 overflow-x-auto pb-1 -mx-1 px-1">
            {data.categories.map(c => (
              <button
                key={c.id}
                data-testid={`m-cat-${c.name}`}
                onClick={() => setActiveCat(c.id)}
                className={`px-3 py-1.5 rounded-full text-xs font-mono uppercase whitespace-nowrap border transition ${
                  activeCat === c.id
                    ? "text-black border-transparent"
                    : "bg-[var(--surface)] text-[var(--muted)] border-[var(--border)]"
                }`}
                style={activeCat === c.id ? { background: c.color } : {}}
              >
                {c.name}
              </button>
            ))}
          </div>
        </div>

        {/* Product list */}
        <div className="space-y-2 mt-3">
          {filtered.map(p => {
            const hh = activeHhIds.has(p.category_id) && p.happy_hour_eligible && hhPercent > 0;
            const price = hh ? p.price * (1 - hhPercent / 100) : p.price;
            return (
              <div key={p.id} data-testid={`m-prod-${p.name}`} className="p-3 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
                <div className="flex justify-between gap-3">
                  <div className="flex-1">
                    <div className="font-display font-bold">{p.name}</div>
                    <div className="text-[10px] font-mono uppercase text-[var(--muted)]">{p.course}</div>
                    {p.description && <div className="text-xs text-[var(--muted)] mt-1">{p.description}</div>}
                    {p.variants?.length > 0 && (
                      <div className="mt-1 text-[10px] font-mono text-[var(--muted)]">
                        {p.variants.map(v => v.name).join(" · ")}
                      </div>
                    )}
                  </div>
                  <div className="text-right shrink-0">
                    {hh ? (
                      <>
                        <div className="font-mono font-black text-[var(--amber)]">{fmtHKD(price)}</div>
                        <div className="text-[10px] font-mono line-through text-[var(--muted)]">{fmtHKD(p.price)}</div>
                        <div className="text-[9px] font-mono uppercase text-[var(--amber)] font-bold">-{hhPercent}%</div>
                      </>
                    ) : (
                      <div className="font-mono font-black text-[var(--amber)]">{fmtHKD(p.price)}</div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
          {filtered.length === 0 && (
            <div className="text-center text-[var(--muted)] text-sm py-8">No items match your search.</div>
          )}
        </div>

        <div className="mt-8 pt-6 border-t border-[var(--border)] text-center text-[10px] font-mono text-[var(--muted)]">
          Please order at the bar or ask your server.
          <br />10% service charge applies to all orders.
        </div>
      </div>
    </div>
  );
}

function FullScreenSpinner() {
  return (
    <div className="min-h-screen flex items-center justify-center text-[var(--muted)] font-mono text-xs uppercase tracking-widest">
      Loading menu…
    </div>
  );
}
