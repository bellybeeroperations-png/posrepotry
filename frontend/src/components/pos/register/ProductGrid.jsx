import { fmtHKD } from "@/lib/api";
import { Ban } from "lucide-react";

/** Product grid with category filter, HH pricing, 86'd overlay + secret-menu gating. */
export default function ProductGrid({ products, categories, activeCat, setActiveCat, onPick, hhFor, hhPrice, user, memberTier }) {
  const isManager = user?.role === "admin" || user?.role === "manager";
  const TIER_RANK = { Bronze: 1, Silver: 2, Gold: 3, Platinum: 4 };
  const memberRank = TIER_RANK[memberTier] || 0;
  const filtered = products
    .filter((p) => !activeCat || p.category_id === activeCat)
    // Hide products whose min_tier exceeds the attached member's tier (staff always see all)
    .filter((p) => {
      if (!p.min_tier) return true;
      if (isManager) return true;
      return memberRank >= (TIER_RANK[p.min_tier] || 99);
    });

  return (
    <>
      <div className="col-span-2 flex flex-col gap-2 overflow-y-auto">
        <div className="text-xs font-mono uppercase tracking-widest text-[var(--muted)] mb-1">Categories</div>
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

      <div className="col-span-6 grid grid-cols-3 auto-rows-min gap-3 overflow-y-auto pr-1 content-start">
        {filtered.map((p) => {
          const pct = hhFor(p);
          const dp = hhPrice(p);
          const eight = p.eightysix;
          return (
            <button
              key={p.id}
              data-testid={`prod-${p.name}`}
              onClick={() => onPick(p)}
              className={`relative p-4 rounded-xl border text-left transition group min-w-0 ${
                eight
                  ? "border-[var(--rose)]/40 bg-[var(--surface)] hover:border-[var(--rose)]"
                  : pct
                  ? "border-[var(--amber)]/60 bg-[var(--amber)]/5 hover:bg-[var(--amber)]/10"
                  : "border-[var(--border)] bg-[var(--surface)] hover:border-[var(--cyan)] hover:bg-[var(--surface-2)]"
              }`}
            >
              <div className="font-display font-bold text-white leading-tight truncate">{p.name}</div>
              <div className="text-xs font-mono text-[var(--muted)] mt-1 uppercase">{p.course}</div>
              {pct ? (
                <div className="mt-2 flex items-baseline gap-2 flex-wrap">
                  <span className="font-mono font-bold text-[var(--amber)]">{fmtHKD(dp)}</span>
                  <span className="text-[10px] font-mono text-[var(--muted)] line-through">{fmtHKD(p.price)}</span>
                  <span className="text-[9px] font-mono uppercase bg-[var(--amber)] text-black px-1 rounded font-black">-{pct}%</span>
                </div>
              ) : (
                <div className="mt-2 font-mono font-bold text-[var(--amber)]">{fmtHKD(p.price)}</div>
              )}
              {eight && (
                <div className="absolute inset-0 rounded-xl flex items-center justify-center bg-[var(--rose)]/25 backdrop-blur-[1px]">
                  <div className="flex items-center gap-1.5 bg-[var(--rose)] text-white px-2 py-1 rounded font-mono text-xs font-black tracking-widest">
                    <Ban size={12} /> 86'd
                  </div>
                </div>
              )}
              {p.happy_hour_eligible && !pct && !eight && (
                <div className="mt-1 inline-block text-[9px] font-mono uppercase bg-[var(--amber)]/15 text-[var(--amber)] px-1.5 py-0.5 rounded">
                  Happy Hr
                </div>
              )}
              {p.min_tier && (
                <div data-testid={`ribbon-${p.name}`}
                  className="absolute top-2 right-2 px-1.5 py-0.5 rounded-full bg-[var(--purple)]/25 border border-[var(--purple)] text-[9px] font-mono uppercase font-black text-[var(--purple)] flex items-center gap-0.5">
                  ★ {p.min_tier}
                </div>
              )}
            </button>
          );
        })}
        {filtered.length === 0 && (
          <div className="col-span-3 text-[var(--muted)] text-sm">No products in this category.</div>
        )}
      </div>
    </>
  );
}
