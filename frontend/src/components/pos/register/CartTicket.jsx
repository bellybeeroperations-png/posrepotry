import { useState } from "react";
import { fmtHKD } from "@/lib/api";
import {
  Plus, Minus, Trash2, Pause, Play, Flame, Lock, ArrowLeftRight,
  ShoppingBag, Truck, UtensilsCrossed, User as UserIcon,
} from "lucide-react";
import { api } from "@/lib/api";

const COURSES = ["starter", "main", "dessert", "drink", "side", "other"];
const ORDER_TYPES = [
  ["dine_in", UtensilsCrossed, "Dine-In"],
  ["pick_up", ShoppingBag, "Pick-Up"],
  ["delivery", Truck, "Delivery"],
];

export default function CartTicket({
  order, setOrder, totals, activeHH, combos,
  onSave, onPay, onRepeat, onRemoveLine, onFireCourse,
  onSearchMember, members, memberQ, onAttachMember,
}) {
  return (
    <div className="col-span-4 flex flex-col rounded-xl border border-[var(--border)] bg-[var(--surface)] overflow-hidden">
      <TicketHeader order={order} setOrder={setOrder} onSearchMember={onSearchMember}
        memberQ={memberQ} members={members} onAttachMember={onAttachMember} />
      <FireCourseBar onFire={onFireCourse} disabled={!order?.id} />
      <OrderTypeTabs order={order} setOrder={setOrder} />
      <TicketLines order={order} setOrder={setOrder} onRemove={onRemoveLine} totals={totals} />
      <TicketTotals order={order} setOrder={setOrder} totals={totals}
        onSave={onSave} onPay={onPay} onRepeat={onRepeat} />
    </div>
  );
}

function TicketHeader({ order, setOrder, onSearchMember, memberQ, members, onAttachMember }) {
  return (
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
      <MemberInput order={order} setOrder={setOrder} onSearchMember={onSearchMember}
        memberQ={memberQ} members={members} onAttachMember={onAttachMember} />
    </div>
  );
}

function MemberInput({ order, setOrder, onSearchMember, memberQ, members, onAttachMember }) {
  return (
    <div className="mt-3 relative">
      <input
        data-testid="member-search"
        value={order.member_name || memberQ}
        onChange={(e) => {
          setOrder((o) => ({ ...o, member_id: null, member_name: null }));
          onSearchMember(e.target.value);
        }}
        placeholder="Attach member (name/phone)"
        className="w-full bg-[var(--surface-2)] border border-[var(--border)] rounded-md px-3 py-2 text-sm"
      />
      {members.length > 0 && (
        <div className="absolute top-full left-0 right-0 bg-[var(--surface-2)] border border-[var(--border)] rounded-md mt-1 z-10 max-h-60 overflow-y-auto">
          {members.map((m) => (
            <button key={m.id} data-testid={`member-pick-${m.name}`} onClick={() => onAttachMember(m)}
              className="w-full text-left px-3 py-2 hover:bg-[var(--surface)] flex items-center justify-between">
              <span>{m.name} <span className="text-xs text-[var(--muted)]">{m.phone}</span></span>
              <span className="text-[10px] font-mono uppercase text-[var(--amber)]">{m.tier}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function OrderTypeTabs({ order, setOrder }) {
  return (
    <div className="px-3 py-2 border-b border-[var(--border)] flex justify-center">
      <div className="flex bg-[var(--surface)] rounded-lg border border-[var(--border)] p-1">
        {ORDER_TYPES.map(([v, Icon, label]) => (
          <button key={v} data-testid={`ordtype-${v}`} onClick={() => setOrder((o) => ({ ...o, order_type: v }))}
            className={`px-3 py-1.5 rounded-md text-xs font-mono uppercase flex items-center gap-1.5 ${
              order.order_type === v ? "bg-[var(--cyan)] text-black" : "text-[var(--muted)]"
            }`}>
            <Icon size={12} /> {label}
          </button>
        ))}
      </div>
    </div>
  );
}

function FireCourseBar({ onFire, disabled }) {
  return (
    <div className="px-3 py-2 border-b border-[var(--border)] flex gap-1 overflow-x-auto">
      <div className="text-[10px] font-mono uppercase text-[var(--muted)] flex items-center px-1">Fire:</div>
      {COURSES.map((c) => (
        <button key={c} data-testid={`fire-${c}`} onClick={() => onFire(c)} disabled={disabled}
          className="px-2 py-1 rounded text-[10px] font-mono uppercase bg-[var(--surface-2)] border border-[var(--border)] text-[var(--amber)] hover:border-[var(--amber)] flex items-center gap-1 disabled:opacity-40">
          <Flame size={10} /> {c}
        </button>
      ))}
    </div>
  );
}

function TicketLines({ order, setOrder, onRemove, totals }) {
  const qtyChange = (i, d) =>
    setOrder((o) => {
      const lines = o.lines.map((l, idx) =>
        idx === i ? { ...l, qty: Math.max(1, l.qty + d) } : l
      );
      return { ...o, lines };
    });
  const toggleHold = (i) =>
    setOrder((o) => {
      const lines = o.lines.map((l, idx) => (idx === i ? { ...l, held: !l.held } : l));
      return { ...o, lines };
    });
  const cycleSeat = (i) =>
    setOrder((o) => {
      const guests = Math.max(1, o.guests || 1);
      const lines = o.lines.map((l, idx) => {
        if (idx !== i) return l;
        const cur = l.seat || 1;
        return { ...l, seat: (cur % guests) + 1 };
      });
      return { ...o, lines };
    });

  const hhSet = totals?.hh_locked || new Set();
  const comboSet = totals?.combo_locked || new Set();
  const comboMap = totals?.combo_line_map || {};

  return (
    <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
      {order.lines.length === 0 && (
        <div className="text-center text-[var(--muted)] text-sm py-10">Tap products to add</div>
      )}
      {order.lines.map((l, i) => {
        const hhLocked = hhSet.has(l.product_id);
        const comboLocked = comboSet.has(l.product_id);
        const seat = l.seat || 1;
        return (
        <div key={`${l.product_id}-${l.variant || ""}-${i}`}
          data-testid={`cart-line-${i}`}
          className={`p-2 rounded-lg border ${
            l.held ? "border-dashed border-[var(--amber)] bg-[var(--amber)]/5" :
            comboLocked ? "border-[var(--cyan)]/60 bg-[var(--cyan)]/5" :
            hhLocked ? "border-[var(--amber)]/50 bg-[var(--amber)]/5" :
            "border-[var(--border)] bg-[var(--surface-2)]"
          }`}>
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1">
              <div className="font-semibold text-sm text-white flex items-center gap-1.5">
                <button data-testid={`line-seat-${i}`} onClick={() => cycleSeat(i)}
                  title="Cycle seat #"
                  className="px-1.5 py-0.5 rounded bg-[var(--purple)]/20 border border-[var(--purple)]/40 text-[var(--purple)] text-[10px] font-mono flex items-center gap-1 hover:bg-[var(--purple)]/30">
                  <ArrowLeftRight size={9} /> S{seat}
                </button>
                <span>{l.name}</span>
              </div>
              {l.modifiers?.length > 0 && (
                <div className="text-[10px] text-[var(--muted)]">+ {l.modifiers.join(", ")}</div>
              )}
              <div className="text-[10px] font-mono uppercase text-[var(--muted)] mt-0.5 flex items-center gap-1 flex-wrap">
                <span>{l.course}</span>
                {l.held && <span>· HELD</span>}
                {hhLocked && (
                  <span data-testid={`lock-hh-${i}`}
                    className="ml-1 px-1.5 py-0.5 rounded bg-[var(--amber)]/20 border border-[var(--amber)]/50 text-[var(--amber)] flex items-center gap-1">
                    <Lock size={9} /> HH -{l.hh_pct}%
                  </span>
                )}
                {comboLocked && (
                  <span data-testid={`lock-combo-${i}`}
                    className="ml-1 px-1.5 py-0.5 rounded bg-[var(--cyan)]/20 border border-[var(--cyan)]/50 text-[var(--cyan)] flex items-center gap-1">
                    <Lock size={9} /> COMBO · {comboMap[l.product_id]}
                  </span>
                )}
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
                <button data-testid={`line-del-${i}`} onClick={() => onRemove(i)} className="w-6 h-6 rounded bg-[var(--surface)] text-[var(--rose)]"><Trash2 size={12} /></button>
              </div>
            </div>
          </div>
        </div>
      );})}
      {(hhSet.size > 0 || comboSet.size > 0) && (
        <div data-testid="exclusivity-note"
          className="mt-2 px-2 py-1.5 rounded border border-dashed border-[var(--border)] text-[10px] font-mono uppercase text-[var(--muted)] flex items-center gap-1">
          <Lock size={10} /> Locked lines skip manual discounts &amp; other combos
        </div>
      )}
    </div>
  );
}

function TicketTotals({ order, setOrder, totals, onSave, onPay, onRepeat }) {
  return (
    <div className="p-3 border-t border-[var(--border)] space-y-2">
      <div className="flex gap-2">
        <div className="flex-1 flex bg-[var(--surface-2)] rounded-md border border-[var(--border)] p-1">
          {[["none", "None"], ["percent", "%"], ["cash", "HK$"]].map(([v, l]) => (
            <button key={v} data-testid={`disc-${v}`} onClick={() => setOrder((o) => ({ ...o, discount_type: v, discount_value: 0 }))}
              className={`flex-1 py-1 text-xs font-mono rounded ${order.discount_type === v ? "bg-[var(--cyan)] text-black" : "text-[var(--muted)]"}`}>
              {l}
            </button>
          ))}
        </div>
        {order.discount_type !== "none" && (
          <input data-testid="disc-value" type="number" min="0" value={order.discount_value}
            onChange={(e) => setOrder((o) => ({ ...o, discount_value: parseFloat(e.target.value) || 0 }))}
            className="w-24 bg-[var(--surface-2)] border border-[var(--border)] rounded-md px-2 text-sm" />
        )}
      </div>
      <div className="text-xs font-mono space-y-1 text-[var(--muted)]">
        <div className="flex justify-between"><span>Subtotal</span><span data-testid="totals-subtotal">{fmtHKD(totals.subtotal)}</span></div>
        {totals.discount > 0 && <div className="flex justify-between text-[var(--rose)]"><span>Discount</span><span>-{fmtHKD(totals.discount)}</span></div>}
        {totals.combos_applied?.map((c, i) => (
          <div key={c.name || i} data-testid={`combo-line-${i}`} className="flex justify-between text-[var(--cyan)]">
            <span>Combo · {c.name}</span>
            <span>-{fmtHKD(c.discount)}</span>
          </div>
        ))}
        <div className="flex justify-between"><span>Service (10%)</span><span data-testid="totals-service">{fmtHKD(totals.service)}</span></div>
        <div className="flex justify-between text-white text-lg font-display font-black pt-1 border-t border-[var(--border)]">
          <span>TOTAL</span><span data-testid="totals-total">{fmtHKD(totals.total)}</span>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <button data-testid="btn-repeat-round" onClick={onRepeat} disabled={!order.lines.length}
          className="py-2.5 rounded-lg text-xs uppercase font-mono bg-[var(--surface-2)] border border-[var(--border)] disabled:opacity-40">
          Repeat
        </button>
        <button data-testid="btn-save-order" onClick={onSave} className="btn-amber py-2.5 rounded-lg text-sm">
          Save / Send
        </button>
        <button data-testid="btn-pay" onClick={onPay} disabled={!order.lines.length}
          className="btn-neon py-2.5 rounded-lg text-sm disabled:opacity-40">
          Pay
        </button>
      </div>
    </div>
  );
}
