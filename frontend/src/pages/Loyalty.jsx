import { useEffect, useState } from "react";
import { api, fmtHKD } from "@/lib/api";
import { toast } from "sonner";
import { Trophy, Search, Sparkles, Gift, Ticket, Zap, Star, Award, Crown } from "lucide-react";

const TIER_ICONS = { Bronze: Award, Silver: Award, Gold: Star, Platinum: Crown };
const TIER_COLORS = { Bronze: "#C97D2E", Silver: "#94A3B8", Gold: "#FFB800", Platinum: "#A855F7" };

export default function Loyalty() {
  const [q, setQ] = useState("");
  const [members, setMembers] = useState([]);
  const [selId, setSelId] = useState(null);
  const [sum, setSum] = useState(null);
  const [spinning, setSpinning] = useState(false);
  const [spinResult, setSpinResult] = useState(null);

  useEffect(() => {
    if (q.length < 2) { setMembers([]); return; }
    api.get("/members", { params: { q } }).then((r) => setMembers(r.data.slice(0, 8)));
  }, [q]);

  const load = (mid) => api.get(`/loyalty/summary/${mid}`).then((r) => setSum(r.data));
  useEffect(() => { if (selId) load(selId); }, [selId]);

  const spin = async () => {
    if (!sum?.can_spin) return toast.error("Come back tomorrow — one spin per day");
    setSpinning(true);
    setTimeout(async () => {
      try {
        const r = await api.post(`/loyalty/spin/${selId}`);
        setSpinResult(r.data.prize);
        toast.success(`🎉 ${r.data.prize.title}`);
        load(selId);
      } catch (e) { toast.error(e?.response?.data?.detail || "Spin failed"); }
      finally { setSpinning(false); }
    }, 2500);
  };

  const scratch = async () => {
    if (!sum?.pending_scratch) return;
    try {
      const r = await api.post(`/loyalty/scratch/${sum.pending_scratch.id}/claim`);
      toast.success(`🎊 ${r.data.prize.title}`);
      load(selId);
    } catch (e) { toast.error(e?.response?.data?.detail || "Claim failed"); }
  };

  if (!selId) {
    return (
      <div>
        <h1 className="font-display text-3xl font-black flex items-center gap-2 mb-4">
          <Trophy className="text-[var(--amber)]" /> Loyalty & Rewards
        </h1>
        <div className="relative max-w-lg mb-4">
          <Search size={16} className="absolute left-3 top-3 text-[var(--muted)]" />
          <input data-testid="loyalty-search" value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="Search member by name or phone…"
            className="w-full pl-10 pr-3 py-2 rounded-lg bg-[var(--surface)] border border-[var(--border)] text-sm" />
        </div>
        <div className="grid grid-cols-3 gap-2">
          {members.map((m) => (
            <button key={m.id} data-testid={`loyalty-pick-${m.id}`} onClick={() => setSelId(m.id)}
              className="p-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] text-left hover:border-[var(--cyan)]">
              <div className="font-display font-bold">{m.name}</div>
              <div className="text-[10px] font-mono text-[var(--muted)]">{m.phone} · {m.points || 0} pts</div>
            </button>
          ))}
        </div>
      </div>
    );
  }

  if (!sum) return <div className="text-[var(--muted)]">Loading…</div>;
  const Tier = TIER_ICONS[sum.tier.name];
  const tierColor = TIER_COLORS[sum.tier.name];
  const stampPct = Math.round((sum.stamps / sum.stamp_goal) * 100);
  // Progress toward the NEXT tier, relative to the size of the current tier band.
  const currentMin = sum.tier.min_spend;
  const nextMin = sum.next_tier?.min_spend;
  const spendNow = sum.member.lifetime_spend || 0;
  const nextPct = sum.next_tier
    ? Math.max(0, Math.min(100, Math.round(((spendNow - currentMin) / (nextMin - currentMin)) * 100)))
    : 100;

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <button onClick={() => { setSelId(null); setSum(null); }} className="text-xs font-mono uppercase text-[var(--muted)]">← back</button>
        <h1 className="font-display text-2xl font-black">{sum.member.name}</h1>
        <span data-testid="tier-badge"
          className="px-2 py-0.5 rounded-full text-[10px] font-mono uppercase font-black flex items-center gap-1 border"
          style={{ borderColor: tierColor, background: `${tierColor}22`, color: tierColor }}>
          <Tier size={11} /> {sum.tier.name}
        </span>
      </div>

      <div className="grid grid-cols-4 gap-3 mb-4">
        <Kpi label="Points" value={sum.points} testid="kpi-points" />
        <Kpi label="Stamps" value={`${sum.stamps} / ${sum.stamp_goal}`} testid="kpi-stamps" />
        <Kpi label="Visits" value={sum.member.visits || 0} testid="kpi-visits" />
        <Kpi label="Lifetime" value={fmtHKD(sum.member.lifetime_spend || 0)} testid="kpi-lifetime" />
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* Tier ladder + progress */}
        <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
          <div className="text-xs font-mono uppercase text-[var(--muted)] mb-2">Tier Ladder</div>
          <div className="flex items-center gap-2 mb-3">
            <span className="font-display font-black text-2xl" style={{ color: tierColor }}>{sum.tier.name}</span>
            {sum.next_tier && (
              <span className="text-xs text-[var(--muted)] font-mono">
                → {sum.next_tier.name} in {fmtHKD(sum.spend_to_next)}
              </span>
            )}
          </div>
          <div className="h-2 rounded bg-[var(--surface-2)] overflow-hidden mb-3">
            <div data-testid="tier-progress" className="h-full" style={{ width: `${nextPct}%`, background: tierColor }} />
          </div>
          <div className="space-y-1">
            {sum.tier.perks.map((p) => (
              <div key={p} className="text-xs flex items-center gap-1.5"><Sparkles size={10} className="text-[var(--amber)]" />{p}</div>
            ))}
          </div>
        </div>

        {/* Stamp card */}
        <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
          <div className="text-xs font-mono uppercase text-[var(--muted)] mb-2 flex items-center gap-1">
            <Ticket size={12} /> Stamp Card · {sum.stamps}/{sum.stamp_goal}
          </div>
          <div className="grid grid-cols-5 gap-2 mb-3">
            {Array.from({ length: sum.stamp_goal }, (_, i) => (
              <div key={i} data-testid={`stamp-${i}`}
                className={`aspect-square rounded-full flex items-center justify-center border-2 ${
                  i < sum.stamps ? "bg-[var(--amber)] border-[var(--amber)] text-black" : "border-[var(--border)] text-[var(--muted)]"
                }`}>
                {i < sum.stamps ? <Star size={16} /> : <span className="text-[10px] font-mono">{i + 1}</span>}
              </div>
            ))}
          </div>
          <div className="text-[10px] font-mono text-[var(--muted)]">10 visits → free house cocktail voucher</div>
        </div>

        {/* Spin wheel */}
        <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
          <div className="text-xs font-mono uppercase text-[var(--muted)] mb-3 flex items-center gap-1">
            <Zap size={12} /> Daily Spin
          </div>
          <div className="flex items-center gap-4">
            <div data-testid="spin-wheel"
              className={`w-32 h-32 rounded-full border-4 border-[var(--amber)] bg-gradient-to-br from-[var(--amber)] via-[var(--cyan)] to-[var(--purple)] flex items-center justify-center shadow-lg ${spinning ? "animate-spin" : ""}`}
              style={{ animationDuration: spinning ? "0.3s" : undefined }}>
              <Gift className="text-white" size={40} />
            </div>
            <div className="flex-1">
              {sum.can_spin ? (
                <button data-testid="btn-spin" onClick={spin} disabled={spinning}
                  className="btn-neon w-full py-3 rounded-lg font-mono uppercase text-sm">
                  {spinning ? "Spinning…" : "SPIN THE WHEEL"}
                </button>
              ) : (
                <div className="text-xs text-[var(--muted)]">Come back tomorrow for your next free spin.</div>
              )}
              {spinResult && !spinning && (
                <div data-testid="spin-result" className="mt-2 p-2 rounded bg-[var(--amber)]/15 border border-[var(--amber)] text-xs font-mono text-[var(--amber)]">
                  You won: <b>{spinResult.title}</b>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Scratch ticket */}
        <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
          <div className="text-xs font-mono uppercase text-[var(--muted)] mb-3 flex items-center gap-1">
            <Ticket size={12} /> Scratch Ticket
          </div>
          {sum.pending_scratch ? (
            <button data-testid="btn-scratch" onClick={scratch}
              className="w-full h-24 rounded-lg bg-gradient-to-br from-[var(--purple)] to-[var(--rose)] font-display font-black text-lg text-white uppercase hover:scale-[1.02] active:scale-[0.98] transition shadow-lg">
              🎟 SCRATCH TO REVEAL
            </button>
          ) : (
            <div className="text-xs text-[var(--muted)] py-6 text-center">
              No pending ticket. Your next payment might drop one (~20% chance).
            </div>
          )}
        </div>

        {/* Voucher wallet */}
        <div className="col-span-2 p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
          <div className="text-xs font-mono uppercase text-[var(--muted)] mb-3 flex items-center gap-1">
            <Gift size={12} /> Wallet · {sum.vouchers.length} voucher(s)
          </div>
          {sum.vouchers.length === 0 && (
            <div className="text-xs text-[var(--muted)] py-4 text-center">No active vouchers yet — spin, scratch, or hit 10 stamps to earn some.</div>
          )}
          <div className="grid grid-cols-3 gap-2">
            {sum.vouchers.map((v) => (
              <div key={v.id} data-testid={`voucher-${v.code}`}
                className="p-3 rounded-lg border border-dashed border-[var(--amber)] bg-[var(--amber)]/5">
                <div className="text-[10px] font-mono uppercase text-[var(--amber)]">{v.source.replace("_", " ")}</div>
                <div className="font-display font-bold text-sm text-white mt-1">{v.title}</div>
                <div className="text-[10px] font-mono text-[var(--muted)] mt-1">
                  Code {v.code} · {v.discount_type === "percent" ? `${v.discount_value}% off` : `HK$${v.discount_value} off`}
                </div>
                <div className="text-[9px] font-mono text-[var(--muted)] mt-0.5">Expires {new Date(v.expires_at).toLocaleDateString("en-HK")}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

const Kpi = ({ label, value, testid }) => (
  <div data-testid={testid} className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
    <div className="text-[10px] font-mono uppercase text-[var(--muted)]">{label}</div>
    <div className="font-display font-black text-2xl mt-1">{value}</div>
  </div>
);
