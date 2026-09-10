import { useMemo, useEffect, useRef, useState } from "react";
import { api, fmtHKD } from "@/lib/api";
import { TrendingUp, Zap } from "lucide-react";
import { toast } from "sonner";

/**
 * Live combo heat-map for the Register.
 * Takes the current cart totals + full combo list and returns "+1 <product> → -X%"
 * chips for the top 3 combos that are exactly one product-tap away from firing.
 * Also fires an upsell-nudge log entry when a hint renders / is tapped.
 */
export default function RegisterUpsellStrip({ order, totals, combos, products, onAdd }) {
  const hints = useMemo(() => {
    if (!order?.lines?.length || !combos?.length || !products?.length) return [];
    const hhLocked = totals?.hh_locked || new Set();
    const comboLocked = totals?.combo_locked || new Set();
    const promoLocked = new Set([...hhLocked, ...comboLocked]);

    const qtys = {};
    order.lines.forEach((l) => {
      if (l.product_id && !hhLocked.has(l.product_id) && !comboLocked.has(l.product_id) && (l.qty || 0) > 0) {
        qtys[l.product_id] = (qtys[l.product_id] || 0) + l.qty;
      }
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

    const prodById = Object.fromEntries(products.map((p) => [p.id, p]));
    const out = [];
    for (const c of combos) {
      if (c.active === false) continue;
      if (matches(c, qtys)) continue;
      const involved = c.slots?.length
        ? new Set(c.slots.flatMap((s) => s.product_ids || []))
        : new Set(c.product_ids || []);
      for (const pid of involved) {
        if (promoLocked.has(pid)) continue;
        const p = prodById[pid];
        if (!p || p.eightysix) continue;
        const trial = { ...qtys, [pid]: (qtys[pid] || 0) + 1 };
        if (matches(c, trial)) {
          const value = c.discount_type === "percent"
            ? Math.round((totals?.subtotal || 0) * (c.discount_value / 100))
            : c.discount_value;
          const net = value - (p.price || 0);
          out.push({ combo: c.name, product: p, discount_type: c.discount_type, discount_value: c.discount_value, value, net });
          break; // one hint per combo
        }
      }
    }
    out.sort((a, b) => b.net - a.net);
    return out.slice(0, 3);
  }, [order, totals, combos, products]);

  // Log 'shown' nudges (deduped server-side within 60s); remember metadata so we
  // can fire 'dismissed' if the ticket closes without the hint being accepted.
  const pendingRef = useRef(new Map()); // key -> {combo_name, product_id, product_name, potential_discount, order_id, table_id}
  useEffect(() => {
    hints.forEach((h) => {
      const key = `${order?.id || "draft"}-${h.combo}-${h.product.id}`;
      if (pendingRef.current.has(key)) return;
      const meta = {
        order_id: order?.id || null,
        table_id: order?.table_id || null,
        combo_name: h.combo,
        product_id: h.product.id,
        product_name: h.product.name,
        potential_discount: h.value,
        source: "register",
      };
      pendingRef.current.set(key, meta);
      api.post("/upsell/log", { ...meta, status: "shown" })
        .catch((err) => console.warn("[upsell/log shown]", err));
    });
  }, [hints, order?.id, order?.table_id]);

  // Flush every still-pending nudge as 'dismissed' the moment the ticket closes
  // (paid or voided) — this makes the leaderboard's conversion % honest.
  const prevStatusRef = useRef(order?.status);
  useEffect(() => {
    const prev = prevStatusRef.current;
    const cur = order?.status;
    prevStatusRef.current = cur;
    if ((cur === "paid" || cur === "voided") && prev !== cur && pendingRef.current.size > 0) {
      for (const meta of pendingRef.current.values()) {
        api.post("/upsell/log", { ...meta, status: "dismissed" })
          .catch((err) => console.warn("[upsell/log dismissed]", err));
      }
      pendingRef.current.clear();
    }
  }, [order?.status]);

  // Peak-Rush Auto-Flash — if the top hint sits idle for 90s, flash it + toast
  const [flashKey, setFlashKey] = useState(null);
  const topHint = hints[0];
  const topKey = topHint ? `${topHint.combo}-${topHint.product.id}` : null;
  useEffect(() => {
    setFlashKey(null);
    if (!topHint) return;
    const t = setTimeout(() => {
      setFlashKey(topKey);
      toast(`Push this now: +1 ${topHint.product.name} → ${topHint.combo}`, {
        description: `Worth ${topHint.discount_type === "percent" ? topHint.discount_value + "%" : fmtHKD(topHint.discount_value)} off — one tap away.`,
      });
    }, 90000);
    return () => clearTimeout(t);
  }, [topKey]);  // eslint-disable-line react-hooks/exhaustive-deps

  const accept = (h) => {
    const key = `${order?.id || "draft"}-${h.combo}-${h.product.id}`;
    pendingRef.current.delete(key);  // no longer eligible for dismiss
    api.post("/upsell/log", {
      order_id: order?.id || null,
      table_id: order?.table_id || null,
      combo_name: h.combo,
      product_id: h.product.id,
      product_name: h.product.name,
      potential_discount: h.value,
      source: "register",
      status: "accepted",
    }).catch((err) => console.warn("[upsell/log accepted]", err));
    onAdd?.(h.product);
  };

  if (!hints.length) return null;

  return (
    <div data-testid="register-upsell-strip"
      className="col-span-12 -mb-2 px-3 py-2 rounded-lg border border-[var(--cyan)]/50 bg-[var(--cyan)]/5 flex items-center gap-3 text-xs flex-wrap">
      <span className="pulse-dot" style={{ background: "#00F2FE", boxShadow: "0 0 12px #00F2FE" }} />
      <span className="font-mono uppercase tracking-widest text-[var(--cyan)] font-bold flex items-center gap-1">
        <Zap size={11} /> Upsell heat-map · one more tap
      </span>
      {hints.map((h) => {
        const k = `${h.combo}-${h.product.id}`;
        const flashing = flashKey === k;
        return (
        <button
          key={k}
          data-testid={`upsell-chip-${h.product.name}`}
          onClick={() => accept(h)}
          className={`group px-2 py-1 rounded border font-mono flex items-center gap-1.5 transition ${
            flashing
              ? "border-[var(--amber)] bg-[var(--amber)]/20 animate-pulse ring-2 ring-[var(--amber)]"
              : "border-[var(--cyan)]/40 bg-[var(--surface-2)] hover:border-[var(--cyan)] hover:bg-[var(--cyan)]/10"
          }`}>
          <TrendingUp size={11} className={flashing ? "text-[var(--amber)]" : "text-[var(--cyan)]"} />
          <span className="text-white">+1 {h.product.name}</span>
          <span className={`font-black ${flashing ? "text-[var(--amber)]" : "text-[var(--cyan)]"}`}>
            → -{h.discount_type === "percent" ? `${h.discount_value}%` : fmtHKD(h.discount_value)}
          </span>
          <span className="text-[10px] text-[var(--muted)]">({h.combo})</span>
          {h.net > 0 && (
            <span className="ml-1 px-1 rounded bg-[var(--emerald)]/20 text-[var(--emerald)] text-[9px] font-black">
              +{fmtHKD(h.net)}
            </span>
          )}
        </button>
      );})}
      <span className="ml-auto text-[var(--muted)]">tap a chip to add</span>
    </div>
  );
}
