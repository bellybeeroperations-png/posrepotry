import { useEffect, useState } from "react";
import { api, fmtHKD } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Search, Crown, TrendingUp, Printer } from "lucide-react";
import Receipt from "@/components/pos/Receipt";

const TIER_COLOR = { VIP: "#F43F5E", Gold: "#FFB800", Silver: "#94A3B8", Regular: "#26334D" };

export default function CRM() {
  const [members, setMembers] = useState([]);
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(null);
  const [receipt, setReceipt] = useState(null);

  const load = async (query = "") => {
    const r = await api.get("/members", { params: query ? { q: query } : {} });
    setMembers(r.data);
  };
  useEffect(() => { load(); }, []);

  const openMember = async (m) => {
    const { data } = await api.get(`/members/${m.id}`);
    setSel(data);
  };
  const addMember = async () => {
    const name = prompt("Member name?");
    if (!name) return;
    const phone = prompt("Phone?");
    if (!phone) return;
    const tier = prompt("Tier (Regular/Silver/Gold/VIP)?", "Regular");
    try {
      await api.post("/members", { name, phone, tier });
      toast.success("Member added"); load();
    } catch (e) { toast.error("Failed"); }
  };

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <h1 className="font-display text-2xl font-black">Members · CRM</h1>
        <div className="ml-auto flex items-center gap-2">
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted)]" />
            <input
              data-testid="member-list-search"
              value={q}
              onChange={(e) => { setQ(e.target.value); load(e.target.value); }}
              placeholder="Search name/phone"
              className="bg-[var(--surface)] border border-[var(--border)] rounded-lg pl-9 pr-3 py-2 text-sm w-64"
            />
          </div>
          <button data-testid="btn-add-member" onClick={addMember} className="btn-neon px-4 py-2 rounded-lg text-xs uppercase flex items-center gap-2">
            <Plus size={14} /> Add
          </button>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-7 space-y-2">
          {members.map((m) => (
            <button
              key={m.id}
              data-testid={`member-row-${m.name}`}
              onClick={() => openMember(m)}
              className="w-full text-left p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] hover:border-[var(--cyan)] flex items-center gap-3"
            >
              <div className="w-10 h-10 rounded-full flex items-center justify-center font-bold text-black"
                style={{ background: TIER_COLOR[m.tier] || "#94A3B8" }}>
                {m.name?.[0]}
              </div>
              <div className="flex-1">
                <div className="font-semibold">{m.name}</div>
                <div className="text-xs text-[var(--muted)]">{m.phone}</div>
              </div>
              <div className="text-right">
                <div className="text-[10px] font-mono uppercase" style={{ color: TIER_COLOR[m.tier] }}>{m.tier}</div>
                <div className="font-mono font-bold text-[var(--amber)]">{fmtHKD(m.lifetime_spend)}</div>
              </div>
              <div className="text-right text-[10px] font-mono text-[var(--muted)]">
                <div>{m.visits} visits</div>
                <div>{m.points} pts</div>
              </div>
            </button>
          ))}
          {members.length === 0 && (
            <div className="text-[var(--muted)] text-sm">No members found.</div>
          )}
        </div>

        <div className="col-span-5">
          {sel ? (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 sticky top-0">
              <div className="flex items-center gap-3">
                <div className="w-14 h-14 rounded-full flex items-center justify-center font-black text-black text-xl"
                  style={{ background: TIER_COLOR[sel.member.tier] || "#94A3B8" }}>
                  {sel.member.name?.[0]}
                </div>
                <div>
                  <div className="font-display font-black text-xl">{sel.member.name}</div>
                  <div className="text-xs text-[var(--muted)]">{sel.member.phone}</div>
                </div>
                <div className="ml-auto flex items-center gap-1 text-[10px] font-mono uppercase" style={{ color: TIER_COLOR[sel.member.tier] }}>
                  <Crown size={12} /> {sel.member.tier}
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2 mt-4">
                <Metric label="Lifetime" value={fmtHKD(sel.member.lifetime_spend)} />
                <Metric label="Visits" value={sel.member.visits} />
                <Metric label="Avg Dur." value={`${sel.member.avg_duration_min}m`} />
                <Metric label="Points" value={sel.member.points} />
                <Metric label="Fav Items" value={sel.member.favorite_items?.length || 0} />
                <Metric label="Tier" value={sel.member.tier} />
              </div>
              <div className="mt-4">
                <div className="text-[10px] font-mono uppercase text-[var(--muted)] mb-1">Favorite Items</div>
                <div className="flex flex-wrap gap-1">
                  {(sel.member.favorite_items || []).slice(0, 10).map((f, i) => (
                    <span key={f} className="text-[10px] px-2 py-0.5 rounded bg-[var(--surface-2)] border border-[var(--border)]">{f}</span>
                  ))}
                  {(!sel.member.favorite_items || !sel.member.favorite_items.length) && (
                    <span className="text-xs text-[var(--muted)]">No history yet</span>
                  )}
                </div>
              </div>
              <div className="mt-4">
                <div className="text-[10px] font-mono uppercase text-[var(--muted)] mb-1 flex items-center gap-1">
                  <TrendingUp size={12} /> Recent Orders
                </div>
                <div className="space-y-1 max-h-64 overflow-y-auto">
                  {sel.orders.map((o) => (
                    <div key={o.id} data-testid={`crm-order-${o.id}`} className="p-2 rounded bg-[var(--surface-2)] border border-[var(--border)] flex justify-between text-xs items-center">
                      <div>
                        <div className="font-mono text-[10px] text-[var(--muted)]">#{o.id.slice(-6)}</div>
                        <div>{o.lines?.length || 0} items · {o.order_type}</div>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="font-mono font-bold text-[var(--amber)]">{fmtHKD(o.total)}</div>
                        <button
                          data-testid={`crm-receipt-${o.id}`}
                          onClick={() => setReceipt(o)}
                          className="w-7 h-7 rounded bg-[var(--surface)] hover:bg-[var(--cyan)]/20 hover:text-[var(--cyan)] flex items-center justify-center"
                          title="View receipt"
                        >
                          <Printer size={12} />
                        </button>
                      </div>
                    </div>
                  ))}
                  {sel.orders.length === 0 && <div className="text-xs text-[var(--muted)]">No orders yet</div>}
                </div>
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-[var(--border)] p-10 text-center text-[var(--muted)] text-sm">
              Pick a member to see their profile
            </div>
          )}
        </div>
      </div>

      {receipt && (
        <Receipt order={receipt} memberName={sel?.member?.name} onClose={() => setReceipt(null)} />
      )}
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="p-2 rounded-lg bg-[var(--surface-2)] border border-[var(--border)]">
      <div className="text-[9px] font-mono uppercase text-[var(--muted)]">{label}</div>
      <div className="font-display font-bold text-white">{value}</div>
    </div>
  );
}