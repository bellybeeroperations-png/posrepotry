import { useEffect, useState, useMemo, useRef } from "react";
import { api, fmtHKD } from "@/lib/api";
import { toast } from "sonner";
import { Zap, Send, X, Beer, Plus, Minus, TrendingUp } from "lucide-react";
import Receipt from "@/components/pos/Receipt";
import { errMsg } from "@/lib/errors";

/**
 * Quick Bar Mode — one-tap bartender screen.
 * Big drink tiles → running tab in-memory → "Send & Pay Cash" creates + fires + pays.
 */
export default function QuickBar() {
  const [products, setProducts] = useState([]);
  const [activeHH, setActiveHH] = useState([]);
  const [cart, setCart] = useState([]);
  const [combos, setCombos] = useState([]);
  const [busy, setBusy] = useState(false);
  const [receipt, setReceipt] = useState(null);

  useEffect(() => {
    api.get("/products").then((r) => setProducts(r.data.filter((p) => p.kind === "drink" && !p.eightysix)));
    api.get("/combos").then((r) => setCombos(r.data));
    const loadHH = () => api.get("/happy-hours/active").then((r) => setActiveHH(r.data.active || []));
    loadHH();
    const t = setInterval(loadHH, 60000);
    return () => clearInterval(t);
  }, []);

  const hhFor = (p) => {
    if (!p.happy_hour_eligible) return 0;
    let best = 0;
    for (const h of activeHH) {
      if ((h.category_ids || []).includes(p.category_id)) best = Math.max(best, h.percent_off || 0);
    }
    return best;
  };
  const priceOf = (p) => {
    const pct = hhFor(p);
    return pct ? +(p.price * (1 - pct / 100)).toFixed(2) : p.price;
  };

  const addTile = (p) => {
    const pct = hhFor(p);
    const price = priceOf(p);
    // If this tile had a heat-map hint, log it as an accepted upsell.
    const hint = tileHint(p);
    if (hint) {
      api.post("/upsell/log", {
        combo_name: hint.combo,
        product_id: p.id,
        product_name: p.name,
        potential_discount: hint.discount_type === "percent" ? Math.round(subtotal * (hint.discount_value / 100)) : hint.discount_value,
        source: "quickbar",
        status: "accepted",
      }).catch(() => {});
      qbShownRef.current.delete(`${hint.combo}-${p.id}`);
    }
    setCart((c) => {
      const idx = c.findIndex((l) => l.product_id === p.id);
      if (idx >= 0) return c.map((l, i) => (i === idx ? { ...l, qty: l.qty + 1 } : l));
      return [...c, { product_id: p.id, name: p.name, price, qty: 1, course: "drink", hh_pct: pct }];
    });
  };
  const bump = (i, d) =>
    setCart((c) => c.map((l, idx) => (idx === i ? { ...l, qty: Math.max(0, l.qty + d) } : l)).filter((l) => l.qty > 0));
  const clear = () => {
    // Any leftover shown-but-not-accepted becomes a dismissed nudge.
    for (const meta of qbShownRef.current.values()) {
      api.post("/upsell/log", { ...meta, status: "dismissed" }).catch(() => {});
    }
    qbShownRef.current.clear();
    setCart([]);
  };

  // QuickBar shown-nudge tracker
  const qbShownRef = useRef(new Map());  // key -> meta

  const subtotal = useMemo(() => cart.reduce((s, l) => s + l.price * l.qty, 0), [cart]);
  const service = +(subtotal * 0.1).toFixed(2);
  const total = +(subtotal + service).toFixed(2);

  // Combo Heat-Map — for each product tile, check if +1 would trip an active combo
  const tileHint = useMemo(() => {
    if (!combos.length) return () => null;
    const hhLocked = new Set(cart.filter((l) => (l.hh_pct || 0) > 0).map((l) => l.product_id));
    const qtys = {};
    cart.forEach((l) => {
      if (l.product_id && !hhLocked.has(l.product_id)) qtys[l.product_id] = (qtys[l.product_id] || 0) + l.qty;
    });
    const matches = (c, q) => {
      const slots = c.slots || [];
      if (!slots.length) {
        const req = c.product_ids || [];
        return req.length > 0 && req.every((pid) => (q[pid] || 0) >= 1);
      }
      return slots.every((s) => {
        const pids = s.product_ids || [];
        if (!pids.length) return false;
        const total = pids.reduce((a, pid) => a + (q[pid] || 0), 0);
        const min = s.min_qty ?? 1, max = s.max_qty ?? 99;
        if (s.operator === "and") return pids.every((pid) => (q[pid] || 0) >= 1 && (q[pid] || 0) <= max);
        return total >= min && total <= max;
      });
    };
    return (p) => {
      if (hhLocked.has(p.id)) return null;
      for (const c of combos) {
        if (!c.active) continue;
        if (matches(c, qtys)) continue;
        const involved = c.slots?.length
          ? new Set(c.slots.flatMap((s) => s.product_ids || []))
          : new Set(c.product_ids || []);
        if (!involved.has(p.id)) continue;
        const trial = { ...qtys, [p.id]: (qtys[p.id] || 0) + 1 };
        if (matches(c, trial)) {
          return { combo: c.name, discount_type: c.discount_type, discount_value: c.discount_value };
        }
      }
      return null;
    };
  }, [combos, cart]);

  const sendAndPay = async (method = "cash") => {
    if (!cart.length) return toast.error("Nothing to send");
    setBusy(true);
    try {
      // 1) Create pick_up order
      const createRes = await api.post("/orders", {
        order_type: "pick_up",
        guests: 1,
        lines: cart,
        discount_type: "none",
        discount_value: 0,
        service_charge_pct: 10,
      });
      const orderId = createRes.data.id;
      // 2) Auto-fire so it lands on KDS immediately
      await api.post(`/orders/${orderId}/fire`);
      // 3) Pay
      const payRes = await api.post(`/orders/${orderId}/pay`, {
        method,
        amount: createRes.data.total,
        tip: 0,
        splits: [],
      });
      toast.success(`Sent + paid ${fmtHKD(createRes.data.total)}`);
      setReceipt(payRes.data);
      // 4) Any shown-but-not-accepted nudge is now dismissed
      const cartPids = new Set(cart.map((l) => l.product_id));
      for (const [k, meta] of qbShownRef.current.entries()) {
        if (!cartPids.has(meta.product_id)) {
          api.post("/upsell/log", { ...meta, status: "dismissed" }).catch(() => {});
        }
      }
      qbShownRef.current.clear();
      setCart([]);
    } catch (e) {
      toast.error(errMsg(e, "Failed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="h-full grid grid-cols-12 gap-4">
      <div className="col-span-8 flex flex-col">
        <div className="mb-3 flex items-center gap-3">
          <h1 className="font-display text-3xl font-black flex items-center gap-2" data-testid="quickbar-title">
            <Zap className="text-[var(--amber)]" /> Quick Bar
          </h1>
          {activeHH.length > 0 && (
            <span data-testid="qb-hh-banner" className="px-3 py-1 rounded-lg border border-[var(--amber)]/40 bg-[var(--amber)]/10 text-xs font-mono uppercase text-[var(--amber)] flex items-center gap-2">
              <span className="pulse-dot" style={{ background: "#FFB800", boxShadow: "0 0 12px #FFB800" }} />
              Happy Hour Live
            </span>
          )}
          <div className="ml-auto text-xs font-mono uppercase text-[var(--muted)]">
            One tap = adds to tab · Fire+Pay in one click
          </div>
        </div>
        <div className="flex-1 overflow-y-auto grid grid-cols-4 gap-3">
          {products.map((p) => {
            const pct = hhFor(p);
            const price = priceOf(p);
            const hint = tileHint(p);
            // Log 'shown' for this hint once per session (dedupe via ref)
            if (hint) {
              const k = `${hint.combo}-${p.id}`;
              if (!qbShownRef.current.has(k)) {
                const meta = {
                  combo_name: hint.combo, product_id: p.id, product_name: p.name,
                  potential_discount: hint.discount_type === "percent" ? Math.round(subtotal * (hint.discount_value / 100)) : hint.discount_value,
                  source: "quickbar",
                };
                qbShownRef.current.set(k, meta);
                api.post("/upsell/log", { ...meta, status: "shown" }).catch(() => {});
              }
            }
            return (
              <button
                key={p.id}
                data-testid={`qb-tile-${p.name}`}
                onClick={() => addTile(p)}
                className="relative aspect-square rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 flex flex-col justify-between hover:border-[var(--cyan)] hover:scale-[1.02] active:scale-[0.98] transition text-left"
              >
                <Beer size={22} className="text-[var(--cyan)]" />
                {pct > 0 && (
                  <span className="absolute top-2 right-2 px-2 py-0.5 rounded-full bg-[var(--amber)] text-black text-[10px] font-mono font-black">
                    -{pct}%
                  </span>
                )}
                {hint && (
                  <span data-testid={`qb-hint-${p.name}`}
                    className="absolute -top-2 left-2 px-1.5 py-0.5 rounded-full bg-[var(--cyan)] text-black text-[9px] font-mono font-black flex items-center gap-0.5 shadow-lg">
                    <TrendingUp size={9} /> +1 → -{hint.discount_type === "percent" ? `${hint.discount_value}%` : fmtHKD(hint.discount_value)}
                  </span>
                )}
                <div>
                  <div className="font-display font-black text-base leading-tight text-white">{p.name}</div>
                  <div className="mt-1 flex items-baseline gap-2">
                    <span className="font-mono font-black text-2xl text-[var(--amber)]">{fmtHKD(price)}</span>
                    {pct > 0 && (
                      <span className="text-[10px] font-mono line-through text-[var(--muted)]">{fmtHKD(p.price)}</span>
                    )}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Running tab */}
      <div className="col-span-4 flex flex-col rounded-xl border border-[var(--border)] bg-[var(--surface)] overflow-hidden">
        <div className="p-4 border-b border-[var(--border)] flex items-center justify-between">
          <div>
            <div className="font-display font-black text-lg text-white">Running Tab</div>
            <div className="text-[10px] font-mono uppercase text-[var(--muted)]">{cart.length} line(s)</div>
          </div>
          <button data-testid="qb-clear" onClick={clear} className="text-xs font-mono uppercase text-[var(--muted)] hover:text-[var(--rose)]">
            <X size={16} /> Clear
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
          {cart.length === 0 && (
            <div className="text-center text-[var(--muted)] text-sm py-10">Tap a drink to start a quick tab</div>
          )}
          {cart.map((l, i) => (
            <div key={`${l.product_id}-${i}`} data-testid={`qb-line-${i}`}
              className="p-2 rounded-lg border border-[var(--border)] bg-[var(--surface-2)] flex items-center justify-between">
              <div>
                <div className="font-semibold text-sm text-white">{l.name}</div>
                <div className="text-[10px] font-mono text-[var(--muted)]">{fmtHKD(l.price)} each</div>
              </div>
              <div className="flex items-center gap-1">
                <button data-testid={`qb-minus-${i}`} onClick={() => bump(i, -1)} className="w-7 h-7 rounded bg-[var(--surface)]"><Minus size={12} /></button>
                <span className="w-6 text-center font-mono">{l.qty}</span>
                <button data-testid={`qb-plus-${i}`} onClick={() => bump(i, 1)} className="w-7 h-7 rounded bg-[var(--surface)]"><Plus size={12} /></button>
                <div className="w-16 text-right font-mono text-[var(--amber)]">{fmtHKD(l.price * l.qty)}</div>
              </div>
            </div>
          ))}
        </div>
        <div className="p-3 border-t border-[var(--border)] space-y-2">
          <div className="text-xs font-mono space-y-1 text-[var(--muted)]">
            <div className="flex justify-between"><span>Subtotal</span><span data-testid="qb-subtotal">{fmtHKD(subtotal)}</span></div>
            <div className="flex justify-between"><span>Service (10%)</span><span>{fmtHKD(service)}</span></div>
            <div className="flex justify-between text-white text-lg font-display font-black pt-1 border-t border-[var(--border)]">
              <span>TOTAL</span><span data-testid="qb-total">{fmtHKD(total)}</span>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <button data-testid="qb-send-cash" onClick={() => sendAndPay("cash")} disabled={busy || !cart.length}
              className="btn-amber py-3 rounded-lg text-sm disabled:opacity-40 flex items-center justify-center gap-2">
              <Send size={14} /> Cash
            </button>
            <button data-testid="qb-send-card" onClick={() => sendAndPay("card")} disabled={busy || !cart.length}
              className="btn-neon py-3 rounded-lg text-sm disabled:opacity-40 flex items-center justify-center gap-2">
              <Send size={14} /> Card
            </button>
          </div>
        </div>
      </div>

      {receipt && <Receipt order={receipt} onClose={() => setReceipt(null)} />}
    </div>
  );
}
