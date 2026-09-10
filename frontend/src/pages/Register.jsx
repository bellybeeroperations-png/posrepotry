import { useEffect, useMemo, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { api, fmtHKD } from "@/lib/api";
import { toast } from "sonner";
import {
  Plus, Minus, Trash2, Percent, DollarSign, Flame, Pause, Play, User,
  ShoppingBag, Truck, UtensilsCrossed, CreditCard, Wallet, Banknote, Coins,
} from "lucide-react";
import Receipt from "@/components/pos/Receipt";

const COURSES = ["starter", "main", "dessert", "drink", "side", "other"];

export default function Register() {
  const [sp] = useSearchParams();
  const nav = useNavigate();
  const [categories, setCategories] = useState([]);
  const [products, setProducts] = useState([]);
  const [activeCat, setActiveCat] = useState(null);
  const [order, setOrder] = useState(null);
  const [variantModal, setVariantModal] = useState(null);
  const [payModal, setPayModal] = useState(false);
  const [receiptOrder, setReceiptOrder] = useState(null);
  const [members, setMembers] = useState([]);
  const [memberQ, setMemberQ] = useState("");
  const [activeHH, setActiveHH] = useState([]); // list of active happy hours

  const orderId = sp.get("order");
  const tableId = sp.get("table");
  const areaId = sp.get("area");

  // Compute HH discount for a product given active rules
  const hhFor = (p) => {
    if (!p?.happy_hour_eligible) return 0;
    let best = 0;
    for (const h of activeHH) {
      if ((h.category_ids || []).includes(p.category_id)) {
        best = Math.max(best, h.percent_off || 0);
      }
    }
    return best;
  };
  const hhPrice = (p, base = p.price) => {
    const pct = hhFor(p);
    return pct ? +(base * (1 - pct / 100)).toFixed(2) : base;
  };

  useEffect(() => {
    api.get("/categories").then((r) => {
      setCategories(r.data);
      if (r.data[0]) setActiveCat(r.data[0].id);
    });
    api.get("/products").then((r) => setProducts(r.data));
    const loadHH = () => api.get("/happy-hours/active").then((r) => setActiveHH(r.data.active || []));
    loadHH();
    const t = setInterval(loadHH, 60000); // refresh every minute
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (orderId) {
      api.get(`/orders/${orderId}`).then((r) => setOrder(r.data));
    } else {
      setOrder({
        order_type: tableId ? "dine_in" : "pick_up",
        table_id: tableId,
        area_id: areaId,
        guests: 2, lines: [],
        discount_type: "none", discount_value: 0,
        service_charge_pct: 10, notes: "",
        subtotal: 0, discount: 0, service_charge: 0, total: 0,
        status: "draft",
      });
    }
  }, [orderId, tableId, areaId]);

  const filteredProducts = products.filter((p) => !activeCat || p.category_id === activeCat);

  const totals = useMemo(() => {
    if (!order) return { subtotal: 0, discount: 0, service: 0, total: 0 };
    const sub = order.lines.reduce((s, l) => s + l.price * l.qty, 0);
    let disc = 0;
    if (order.discount_type === "percent") disc = sub * (order.discount_value / 100);
    else if (order.discount_type === "cash") disc = Math.min(order.discount_value, sub);
    const net = sub - disc;
    const svc = net * (order.service_charge_pct / 100);
    return { subtotal: sub, discount: disc, service: svc, total: net + svc };
  }, [order]);

  const addProduct = (p) => {
    if (p.variants?.length > 0) return setVariantModal(p);
    pushLine(p, null, [], hhPrice(p));
  };

  const pushLine = (p, variant, mods, unitPrice) => {
    setOrder((o) => {
      const key = `${p.id}|${variant || ""}|${mods.join(",")}`;
      const existing = o.lines.findIndex((l) => `${l.product_id}|${l.variant || ""}|${l.modifiers.join(",")}` === key && !l.held);
      let lines;
      if (existing >= 0) {
        lines = [...o.lines];
        lines[existing] = { ...lines[existing], qty: lines[existing].qty + 1 };
      } else {
        lines = [...o.lines, {
          product_id: p.id, name: p.name + (variant ? ` (${variant})` : ""),
          price: unitPrice, qty: 1, variant, modifiers: mods,
          course: p.course, held: false, notes: "",
        }];
      }
      return { ...o, lines };
    });
  };

  const qtyChange = (i, d) => setOrder((o) => {
    const lines = [...o.lines];
    lines[i].qty = Math.max(1, lines[i].qty + d);
    return { ...o, lines };
  });
  const removeLine = (i) => setOrder((o) => ({ ...o, lines: o.lines.filter((_, idx) => idx !== i) }));
  const toggleHold = (i) => setOrder((o) => {
    const lines = [...o.lines];
    lines[i].held = !lines[i].held;
    return { ...o, lines };
  });

  const saveOrder = async () => {
    if (!order.lines.length) return toast.error("No items");
    try {
      let res;
      if (order.id) {
        res = await api.patch(`/orders/${order.id}`, {
          lines: order.lines, discount_type: order.discount_type,
          discount_value: order.discount_value, member_id: order.member_id, notes: order.notes,
        });
      } else {
        res = await api.post("/orders", {
          order_type: order.order_type, table_id: order.table_id, area_id: order.area_id,
          member_id: order.member_id, guests: order.guests, lines: order.lines,
          discount_type: order.discount_type, discount_value: order.discount_value,
          service_charge_pct: 10, notes: order.notes,
        });
      }
      setOrder(res.data);
      toast.success("Order saved");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save failed");
    }
  };

  const fireCourse = async (course) => {
    if (!order?.id) return toast.error("Save order first");
    const r = await api.post(`/orders/${order.id}/fire`, null, { params: { course } });
    toast.success(`Fired ${r.data.fired} ${course} item(s)`);
    const upd = await api.get(`/orders/${order.id}`);
    setOrder(upd.data);
  };

  const searchMember = async (q) => {
    setMemberQ(q);
    if (q.length < 2) return setMembers([]);
    const r = await api.get("/members", { params: { q } });
    setMembers(r.data.slice(0, 8));
  };

  const attachMember = (m) => {
    setOrder((o) => ({ ...o, member_id: m.id, member_name: m.name }));
    setMembers([]);
    setMemberQ("");
    toast.success(`Member: ${m.name}`);
  };

  if (!order) return <div className="text-[var(--muted)]">Loading…</div>;

  return (
    <div className="h-full grid grid-cols-12 gap-4">
      {/* Categories */}
      <div className="col-span-2 flex flex-col gap-2 overflow-y-auto">
        <div className="text-xs font-mono uppercase tracking-widest text-[var(--muted)] mb-1">
          Categories
        </div>
        {categories.map((c) => (
          <button
            key={c.id}
            data-testid={`cat-${c.name}`}
            onClick={() => setActiveCat(c.id)}
            className={`text-left p-3 rounded-lg border transition ${
              activeCat === c.id
                ? "bg-[var(--surface-2)] border-[var(--cyan)] text-white"
                : "bg-[var(--surface)] border-[var(--border)] text-[var(--muted)] hover:text-white"
            }`}
          >
            <div className="w-2 h-2 rounded-full mb-1" style={{ background: c.color }} />
            <div className="font-display font-bold text-sm">{c.name}</div>
            <div className="text-[10px] font-mono uppercase opacity-70">{c.kind}</div>
          </button>
        ))}
      </div>

      {/* Products grid */}
      <div className="col-span-6 flex flex-col overflow-hidden">
        {activeHH.length > 0 && (
          <div data-testid="hh-banner" className="mb-3 px-3 py-2 rounded-lg border border-[var(--amber)]/50 bg-[var(--amber)]/10 flex items-center gap-2 text-xs">
            <span className="pulse-dot" style={{ background: "#FFB800", boxShadow: "0 0 12px #FFB800" }} />
            <span className="font-mono uppercase tracking-widest text-[var(--amber)] font-bold">
              Happy Hour Live
            </span>
            <span className="text-[var(--muted)]">
              {activeHH.map(h => `${h.name} -${h.percent_off}%`).join(" · ")}
            </span>
            <span className="ml-auto text-[var(--muted)]">Ends {activeHH[0]?.end_time}</span>
          </div>
        )}
        <div className="flex items-center gap-2 mb-3">
          <div className="flex bg-[var(--surface)] rounded-lg border border-[var(--border)] p-1">
            {[["dine_in", UtensilsCrossed, "Dine-In"], ["pick_up", ShoppingBag, "Pick-Up"], ["delivery", Truck, "Delivery"]].map(
              ([v, Icon, label]) => (
                <button
                  key={v}
                  data-testid={`ordtype-${v}`}
                  onClick={() => setOrder((o) => ({ ...o, order_type: v }))}
                  className={`px-3 py-1.5 rounded-md text-xs font-mono uppercase flex items-center gap-1.5 ${
                    order.order_type === v ? "bg-[var(--cyan)] text-black" : "text-[var(--muted)]"
                  }`}
                >
                  <Icon size={12} /> {label}
                </button>
              )
            )}
          </div>
          <div className="ml-auto flex gap-2">
            {COURSES.map((c) => (
              <button
                key={c}
                data-testid={`fire-${c}`}
                onClick={() => fireCourse(c)}
                className="px-3 py-1.5 rounded-md text-xs font-mono uppercase bg-[var(--surface)] border border-[var(--border)] text-[var(--amber)] hover:border-[var(--amber)] flex items-center gap-1"
              >
                <Flame size={12} /> {c}
              </button>
            ))}
          </div>
        </div>
        <div className="grid grid-cols-3 gap-3 overflow-y-auto flex-1 pr-1">
          {filteredProducts.map((p) => {
            const pct = hhFor(p);
            const dp = hhPrice(p);
            return (
              <button
                key={p.id}
                data-testid={`prod-${p.name}`}
                onClick={() => addProduct(p)}
                className={`p-4 rounded-xl border text-left transition group ${
                  pct ? "border-[var(--amber)]/60 bg-[var(--amber)]/5 hover:bg-[var(--amber)]/10" : "border-[var(--border)] bg-[var(--surface)] hover:border-[var(--cyan)] hover:bg-[var(--surface-2)]"
                }`}
              >
                <div className="font-display font-bold text-white leading-tight">{p.name}</div>
                <div className="text-xs font-mono text-[var(--muted)] mt-1 uppercase">{p.course}</div>
                {pct ? (
                  <div className="mt-2 flex items-baseline gap-2">
                    <span className="font-mono font-bold text-[var(--amber)]">{fmtHKD(dp)}</span>
                    <span className="text-[10px] font-mono text-[var(--muted)] line-through">{fmtHKD(p.price)}</span>
                    <span className="text-[9px] font-mono uppercase bg-[var(--amber)] text-black px-1 rounded font-black">-{pct}%</span>
                  </div>
                ) : (
                  <div className="mt-2 font-mono font-bold text-[var(--amber)]">{fmtHKD(p.price)}</div>
                )}
                {p.happy_hour_eligible && !pct && (
                  <div className="mt-1 inline-block text-[9px] font-mono uppercase bg-[var(--amber)]/15 text-[var(--amber)] px-1.5 py-0.5 rounded">
                    Happy Hr Eligible
                  </div>
                )}
              </button>
            );
          })}
          {filteredProducts.length === 0 && (
            <div className="col-span-3 text-[var(--muted)] text-sm">No products in this category.</div>
          )}
        </div>
      </div>

      {/* Bill */}
      <div className="col-span-4 flex flex-col rounded-xl border border-[var(--border)] bg-[var(--surface)] overflow-hidden">
        <div className="p-4 border-b border-[var(--border)]">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-display font-black text-lg text-white">Order Ticket</div>
              <div className="text-[10px] font-mono text-[var(--muted)] uppercase">
                {order.id ? `#${order.id.slice(-6)}` : "New"} · {order.order_type}
              </div>
            </div>
            <div className="text-right">
              <div className="text-[10px] font-mono text-[var(--muted)] uppercase">Guests</div>
              <div className="flex items-center gap-1">
                <button data-testid="guests-minus" onClick={() => setOrder((o) => ({ ...o, guests: Math.max(1, o.guests - 1) }))} className="w-6 h-6 rounded bg-[var(--surface-2)]">-</button>
                <div className="w-6 text-center font-mono">{order.guests}</div>
                <button data-testid="guests-plus" onClick={() => setOrder((o) => ({ ...o, guests: o.guests + 1 }))} className="w-6 h-6 rounded bg-[var(--surface-2)]">+</button>
              </div>
            </div>
          </div>
          <div className="mt-3 relative">
            <input
              data-testid="member-search"
              value={order.member_name || memberQ}
              onChange={(e) => { setOrder((o) => ({ ...o, member_id: null, member_name: null })); searchMember(e.target.value); }}
              placeholder="Attach member (name/phone)"
              className="w-full bg-[var(--surface-2)] border border-[var(--border)] rounded-md px-3 py-2 text-sm"
            />
            {members.length > 0 && (
              <div className="absolute top-full left-0 right-0 bg-[var(--surface-2)] border border-[var(--border)] rounded-md mt-1 z-10 max-h-60 overflow-y-auto">
                {members.map((m) => (
                  <button
                    key={m.id}
                    data-testid={`member-pick-${m.name}`}
                    onClick={() => attachMember(m)}
                    className="w-full text-left px-3 py-2 hover:bg-[var(--surface)] flex items-center justify-between"
                  >
                    <span>{m.name} <span className="text-xs text-[var(--muted)]">{m.phone}</span></span>
                    <span className="text-[10px] font-mono uppercase text-[var(--amber)]">{m.tier}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
          {order.lines.length === 0 && (
            <div className="text-center text-[var(--muted)] text-sm py-10">Tap products to add</div>
          )}
          {order.lines.map((l, i) => (
            <div key={i} className={`p-2 rounded-lg border ${l.held ? "border-dashed border-[var(--amber)] bg-[var(--amber)]/5" : "border-[var(--border)] bg-[var(--surface-2)]"}`}>
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1">
                  <div className="font-semibold text-sm text-white">{l.name}</div>
                  {l.modifiers?.length > 0 && (
                    <div className="text-[10px] text-[var(--muted)]">+ {l.modifiers.join(", ")}</div>
                  )}
                  <div className="text-[10px] font-mono uppercase text-[var(--muted)] mt-0.5">
                    {l.course} {l.held && "· HELD"}
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-mono text-sm text-[var(--amber)]">{fmtHKD(l.price * l.qty)}</div>
                  <div className="flex items-center gap-1 mt-1 justify-end">
                    <button data-testid={`line-hold-${i}`} onClick={() => toggleHold(i)} className="w-6 h-6 rounded bg-[var(--surface)] text-[var(--amber)]">
                      {l.held ? <Play size={12} /> : <Pause size={12} />}
                    </button>
                    <button data-testid={`line-minus-${i}`} onClick={() => qtyChange(i, -1)} className="w-6 h-6 rounded bg-[var(--surface)]"><Minus size={12} /></button>
                    <span className="w-5 text-center text-xs font-mono">{l.qty}</span>
                    <button data-testid={`line-plus-${i}`} onClick={() => qtyChange(i, 1)} className="w-6 h-6 rounded bg-[var(--surface)]"><Plus size={12} /></button>
                    <button data-testid={`line-del-${i}`} onClick={() => removeLine(i)} className="w-6 h-6 rounded bg-[var(--surface)] text-[var(--rose)]"><Trash2 size={12} /></button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="p-3 border-t border-[var(--border)] space-y-2">
          <div className="flex gap-2">
            <div className="flex-1 flex bg-[var(--surface-2)] rounded-md border border-[var(--border)] p-1">
              {[["none", "None"], ["percent", "%"], ["cash", "HK$"]].map(([v, l]) => (
                <button
                  key={v}
                  data-testid={`disc-${v}`}
                  onClick={() => setOrder((o) => ({ ...o, discount_type: v, discount_value: 0 }))}
                  className={`flex-1 py-1 text-xs font-mono rounded ${order.discount_type === v ? "bg-[var(--cyan)] text-black" : "text-[var(--muted)]"}`}
                >
                  {l}
                </button>
              ))}
            </div>
            {order.discount_type !== "none" && (
              <input
                data-testid="disc-value"
                type="number" min="0" value={order.discount_value}
                onChange={(e) => setOrder((o) => ({ ...o, discount_value: parseFloat(e.target.value) || 0 }))}
                className="w-24 bg-[var(--surface-2)] border border-[var(--border)] rounded-md px-2 text-sm"
              />
            )}
          </div>
          <div className="text-xs font-mono space-y-1 text-[var(--muted)]">
            <div className="flex justify-between"><span>Subtotal</span><span data-testid="totals-subtotal">{fmtHKD(totals.subtotal)}</span></div>
            {totals.discount > 0 && <div className="flex justify-between text-[var(--rose)]"><span>Discount</span><span>-{fmtHKD(totals.discount)}</span></div>}
            <div className="flex justify-between"><span>Service (10%)</span><span data-testid="totals-service">{fmtHKD(totals.service)}</span></div>
            <div className="flex justify-between text-white text-lg font-display font-black pt-1 border-t border-[var(--border)]">
              <span>TOTAL</span><span data-testid="totals-total">{fmtHKD(totals.total)}</span>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <button data-testid="btn-save-order" onClick={saveOrder} className="btn-amber py-2.5 rounded-lg text-sm">
              Save / Send
            </button>
            <button
              data-testid="btn-pay"
              onClick={async () => {
                if (!order.id) await saveOrder();
                setPayModal(true);
              }}
              disabled={!order.lines.length}
              className="btn-neon py-2.5 rounded-lg text-sm disabled:opacity-40"
            >
              Pay {fmtHKD(totals.total)}
            </button>
          </div>
        </div>
      </div>

      {variantModal && (
        <VariantModal
          product={variantModal}
          hhPercent={hhFor(variantModal)}
          onClose={() => setVariantModal(null)}
          onPick={(variant, mods, price) => {
            pushLine(variantModal, variant, mods, price);
            setVariantModal(null);
          }}
        />
      )}

      {payModal && (
        <PaymentModal
          total={totals.total}
          guests={order.guests}
          onClose={() => setPayModal(false)}
          onPay={async (payload) => {
            try {
              const res = await api.post(`/orders/${order.id}/pay`, payload);
              toast.success("Payment complete");
              setPayModal(false);
              setReceiptOrder(res.data);
            } catch (e) {
              toast.error(e?.response?.data?.detail || "Payment failed");
            }
          }}
        />
      )}

      {receiptOrder && (
        <Receipt
          order={receiptOrder}
          memberName={order?.member_name}
          onClose={() => { setReceiptOrder(null); nav("/floorplan"); }}
        />
      )}
    </div>
  );
}

function VariantModal({ product, onClose, onPick, hhPercent = 0 }) {
  const [variant, setVariant] = useState(product.variants[0]?.name || null);
  const [mods, setMods] = useState([]);
  const vObj = product.variants.find((v) => v.name === variant);
  const rawPrice = product.price + (vObj?.price_delta || 0) + mods.reduce((s, m) => {
    const mo = product.modifiers.find((x) => x.name === m);
    return s + (mo?.price_delta || 0);
  }, 0);
  const price = hhPercent ? +(rawPrice * (1 - hhPercent / 100)).toFixed(2) : rawPrice;
  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl w-full max-w-md p-6">
        <div className="font-display font-black text-xl mb-1">{product.name}</div>
        <div className="text-xs font-mono uppercase text-[var(--muted)] mb-4">Choose variant & modifiers</div>
        {product.variants.length > 0 && (
          <>
            <div className="text-xs font-mono uppercase text-[var(--muted)] mb-2">Variant</div>
            <div className="grid grid-cols-2 gap-2 mb-4">
              {product.variants.map((v) => (
                <button
                  key={v.name}
                  data-testid={`variant-${v.name}`}
                  onClick={() => setVariant(v.name)}
                  className={`p-3 rounded-lg border text-left ${
                    variant === v.name ? "border-[var(--cyan)] bg-[var(--cyan)]/10" : "border-[var(--border)] bg-[var(--surface-2)]"
                  }`}
                >
                  <div className="font-semibold text-sm">{v.name}</div>
                  <div className="text-xs font-mono text-[var(--amber)]">
                    {v.price_delta >= 0 ? "+" : ""}{fmtHKD(v.price_delta)}
                  </div>
                </button>
              ))}
            </div>
          </>
        )}
        {product.modifiers.length > 0 && (
          <>
            <div className="text-xs font-mono uppercase text-[var(--muted)] mb-2">Modifiers</div>
            <div className="grid grid-cols-2 gap-2 mb-4">
              {product.modifiers.map((m) => {
                const active = mods.includes(m.name);
                return (
                  <button
                    key={m.name}
                    data-testid={`mod-${m.name}`}
                    onClick={() => setMods((x) => active ? x.filter((n) => n !== m.name) : [...x, m.name])}
                    className={`p-2 rounded-lg border text-left ${
                      active ? "border-[var(--amber)] bg-[var(--amber)]/10" : "border-[var(--border)] bg-[var(--surface-2)]"
                    }`}
                  >
                    <div className="text-xs font-semibold">{m.name}</div>
                    <div className="text-[10px] font-mono text-[var(--amber)]">
                      {m.price_delta >= 0 ? "+" : ""}{fmtHKD(m.price_delta)}
                    </div>
                  </button>
                );
              })}
            </div>
          </>
        )}
        <div className="flex gap-2 mt-4">
          <button onClick={onClose} className="flex-1 py-2 rounded-lg bg-[var(--surface-2)]">Cancel</button>
          <button data-testid="variant-add" onClick={() => onPick(variant, mods, price)} className="flex-1 btn-neon py-2 rounded-lg">
            Add · {fmtHKD(price)}
          </button>
        </div>
      </div>
    </div>
  );
}

function PaymentModal({ total, guests, onClose, onPay }) {
  const [mode, setMode] = useState("single"); // single | split
  const [method, setMethod] = useState("cash");
  const [amount, setAmount] = useState(total);
  const [tip, setTip] = useState(0);
  const [splits, setSplits] = useState([{ method: "cash", amount: total }]);
  const [splitMode, setSplitMode] = useState("equal"); // equal | by_seat | custom
  const change = method === "cash" ? Math.max(0, amount - total) : 0;
  const methods = [
    ["cash", Banknote, "Cash"], ["card", CreditCard, "Card"],
    ["octopus", Coins, "Octopus"], ["wallet", Wallet, "Wallet"],
  ];
  const splitTotal = splits.reduce((s, x) => s + (parseFloat(x.amount) || 0), 0);
  const splitDiff = +(splitTotal - total).toFixed(2);

  const applySplitMode = (m) => {
    setSplitMode(m);
    if (m === "equal") {
      const n = splits.length || 2;
      const per = +(total / n).toFixed(2);
      const arr = Array.from({ length: n }, (_, i) => ({ method: splits[i]?.method || "card", amount: per }));
      // adjust last to fix rounding
      const rem = +(total - per * n).toFixed(2);
      arr[arr.length - 1].amount = +(per + rem).toFixed(2);
      setSplits(arr);
    } else if (m === "by_seat") {
      const per = +(total / guests).toFixed(2);
      const arr = Array.from({ length: guests }, (_, i) => ({ method: "card", amount: per, label: `Seat ${i + 1}` }));
      const rem = +(total - per * guests).toFixed(2);
      if (arr.length) arr[arr.length - 1].amount = +(per + rem).toFixed(2);
      setSplits(arr);
    }
    // custom: keep whatever's there
  };

  const setSplit = (i, k, v) =>
    setSplits(splits.map((s, idx) => (idx === i ? { ...s, [k]: k === "amount" ? parseFloat(v) || 0 : v } : s)));
  const addSplit = () => setSplits([...splits, { method: "card", amount: 0 }]);
  const delSplit = (i) => setSplits(splits.filter((_, idx) => idx !== i));

  const submit = () => {
    if (mode === "split") {
      onPay({ method: "split", amount: splitTotal, tip, splits });
    } else {
      onPay({ method, amount, tip, splits: [] });
    }
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl w-full max-w-lg p-6">
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="font-display font-black text-2xl">Payment</div>
            <div className="text-xs font-mono uppercase text-[var(--muted)]">Order total</div>
          </div>
          <div className="text-3xl font-display font-black text-[var(--cyan)]">{fmtHKD(total)}</div>
        </div>

        <div className="flex gap-1 mb-4 p-1 bg-[var(--surface-2)] rounded-lg">
          <button data-testid="pay-mode-single" onClick={() => setMode("single")}
            className={`flex-1 py-2 rounded-md text-sm font-semibold ${mode === "single" ? "bg-[var(--cyan)] text-black" : "text-[var(--muted)]"}`}>
            Single Payment
          </button>
          <button data-testid="pay-mode-split" onClick={() => { setMode("split"); applySplitMode(splitMode); }}
            className={`flex-1 py-2 rounded-md text-sm font-semibold ${mode === "split" ? "bg-[var(--amber)] text-black" : "text-[var(--muted)]"}`}>
            Split Bill
          </button>
        </div>

        {mode === "single" ? (
          <>
            <div className="grid grid-cols-4 gap-2 mb-4">
              {methods.map(([v, Icon, label]) => (
                <button key={v} data-testid={`pay-method-${v}`} onClick={() => setMethod(v)}
                  className={`p-3 rounded-lg border flex flex-col items-center gap-1 ${
                    method === v ? "border-[var(--cyan)] bg-[var(--cyan)]/10" : "border-[var(--border)] bg-[var(--surface-2)]"
                  }`}>
                  <Icon size={20} />
                  <span className="text-[10px] font-mono uppercase">{label}</span>
                </button>
              ))}
            </div>
            <label className="text-xs font-mono uppercase text-[var(--muted)]">Amount received</label>
            <input data-testid="pay-amount" type="number" value={amount}
              onChange={(e) => setAmount(parseFloat(e.target.value) || 0)}
              className="w-full mt-1 mb-3 bg-[var(--surface-2)] border border-[var(--border)] rounded-md px-3 py-2 font-mono text-lg" />
            <label className="text-xs font-mono uppercase text-[var(--muted)]">Tip</label>
            <input data-testid="pay-tip" type="number" value={tip}
              onChange={(e) => setTip(parseFloat(e.target.value) || 0)}
              className="w-full mt-1 bg-[var(--surface-2)] border border-[var(--border)] rounded-md px-3 py-2 font-mono" />
            {method === "cash" && (
              <div className="mt-3 text-sm font-mono">Change: <span className="text-[var(--amber)] font-bold">{fmtHKD(change)}</span></div>
            )}
          </>
        ) : (
          <>
            <div className="flex gap-1 mb-3 text-[10px] font-mono uppercase">
              {[["equal", "Equal Parts"], ["by_seat", `By Seat (${guests})`], ["custom", "Custom"]].map(([v, l]) => (
                <button key={v} data-testid={`split-mode-${v}`} onClick={() => applySplitMode(v)}
                  className={`flex-1 py-2 rounded-md border ${splitMode === v ? "bg-[var(--amber)] text-black border-transparent" : "bg-[var(--surface-2)] text-[var(--muted)] border-[var(--border)]"}`}>
                  {l}
                </button>
              ))}
            </div>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {splits.map((s, i) => (
                <div key={i} className="grid grid-cols-[80px_1fr_100px_36px] gap-2 items-center">
                  <span className="text-xs font-mono text-[var(--muted)]">{s.label || `Split ${i + 1}`}</span>
                  <select data-testid={`split-method-${i}`} value={s.method} onChange={(e) => setSplit(i, "method", e.target.value)}
                    className="bg-[var(--surface-2)] border border-[var(--border)] rounded-md px-2 py-1.5 text-sm">
                    {methods.map(([v, , l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                  <input data-testid={`split-amount-${i}`} type="number" step="0.01" value={s.amount}
                    onChange={(e) => setSplit(i, "amount", e.target.value)}
                    disabled={splitMode !== "custom"}
                    className="bg-[var(--surface-2)] border border-[var(--border)] rounded-md px-2 py-1.5 text-sm font-mono text-right disabled:opacity-70" />
                  {splitMode === "custom" && splits.length > 1 && (
                    <button onClick={() => delSplit(i)} className="text-[var(--rose)]"><Trash2 size={14} /></button>
                  )}
                </div>
              ))}
            </div>
            {splitMode === "custom" && (
              <button data-testid="split-add" onClick={addSplit} className="mt-2 text-xs text-[var(--cyan)] flex items-center gap-1">
                <Plus size={12} /> Add split
              </button>
            )}
            <div className="mt-3 p-2 rounded-md bg-[var(--surface-2)] border border-[var(--border)] flex items-center justify-between text-xs font-mono">
              <span>Splits sum</span>
              <span className={splitDiff < -0.01 ? "text-[var(--rose)] font-bold" : "text-[var(--amber)] font-bold"} data-testid="split-sum">
                {fmtHKD(splitTotal)} {splitDiff !== 0 && `(${splitDiff > 0 ? "+" : ""}${fmtHKD(splitDiff)})`}
              </span>
            </div>
          </>
        )}

        <div className="flex gap-2 mt-4">
          <button onClick={onClose} className="flex-1 py-2.5 rounded-lg bg-[var(--surface-2)]">Cancel</button>
          <button data-testid="pay-confirm" onClick={submit}
            disabled={mode === "split" && splitDiff < -0.01}
            className="flex-1 btn-neon py-2.5 rounded-lg disabled:opacity-40">
            Confirm
          </button>
        </div>
      </div>
    </div>
  );
}
