import { useEffect, useState } from "react";
import { api, fmtHKD } from "@/lib/api";
import { Trophy, Zap, TrendingUp, X, Check } from "lucide-react";

const ICON = {
  shown: <Zap size={12} className="text-[var(--muted)]" />,
  accepted: <Check size={12} className="text-[var(--emerald)]" />,
  dismissed: <X size={12} className="text-[var(--rose)]" />,
};

export default function UpsellLog() {
  const [feed, setFeed] = useState([]);
  const [board, setBoard] = useState([]);

  const load = () => {
    api.get("/upsell/feed", { params: { limit: 40 } }).then((r) => setFeed(r.data));
    api.get("/upsell/leaderboard").then((r) => setBoard(r.data));
  };
  useEffect(() => {
    load();
    const t = setInterval(load, 12000);
    return () => clearInterval(t);
  }, []);

  const totalShown = board.reduce((s, r) => s + r.shown, 0);
  const totalAccepted = board.reduce((s, r) => s + r.accepted, 0);
  const totalLift = board.reduce((s, r) => s + r.revenue_lifted, 0);

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <h1 className="font-display text-3xl font-black flex items-center gap-2">
          <Trophy className="text-[var(--amber)]" /> Upsell Nudges
        </h1>
        <span className="text-xs font-mono uppercase text-[var(--muted)]">
          Live combo heat-map · coachable leaderboard
        </span>
      </div>

      <div className="grid grid-cols-4 gap-3 mb-4">
        <Kpi label="Nudges Shown"   value={totalShown}          color="#94A3B8" testid="kpi-upsell-shown" />
        <Kpi label="Accepted"       value={totalAccepted}       color="#10B981" testid="kpi-upsell-accepted" />
        <Kpi label="Conversion %"   value={`${totalShown ? Math.round(100 * totalAccepted / totalShown) : 0}%`}
             color="#00F2FE" testid="kpi-upsell-conversion" />
        <Kpi label="Revenue Lifted" value={fmtHKD(totalLift)}   color="#FFB800" testid="kpi-upsell-lift" />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Card title="Server Leaderboard (7-day)">
          {board.length === 0 && <Empty />}
          <div className="space-y-2">
            {board.map((r, i) => (
              <div key={r.server_id} data-testid={`board-row-${i}`}
                className="flex items-center gap-3 p-2 rounded-lg bg-[var(--surface-2)] border border-[var(--border)]">
                <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-black font-mono"
                  style={{ background: i === 0 ? "#FFB800" : "#26334D", color: i === 0 ? "#000" : "#FFF" }}>
                  {i + 1}
                </div>
                <div className="flex-1 text-sm font-semibold">{r.server_name}</div>
                <div className="text-[10px] font-mono text-[var(--muted)]">
                  {r.accepted}/{r.shown} · {r.conversion}%
                </div>
                <div className="w-24 text-right font-mono font-bold text-[var(--amber)]">
                  {fmtHKD(r.revenue_lifted)}
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Live Feed">
          {feed.length === 0 && <Empty />}
          <div className="space-y-1.5 max-h-[420px] overflow-y-auto">
            {feed.map((f) => (
              <div key={f.id} data-testid={`feed-${f.id}`}
                className="flex items-center gap-2 text-xs px-2 py-1.5 rounded border border-[var(--border)] bg-[var(--surface-2)]">
                {ICON[f.status]}
                <span className="font-mono text-[var(--muted)] w-24 truncate">{f.server_name}</span>
                <TrendingUp size={11} className="text-[var(--cyan)]" />
                <span className="truncate">+1 <span className="text-white font-semibold">{f.product_name}</span></span>
                <span className="text-[var(--muted)]">·</span>
                <span className="text-[var(--cyan)] font-mono">{f.combo_name}</span>
                <span className="ml-auto font-mono text-[var(--amber)]">{fmtHKD(f.potential_discount)}</span>
                <span className="text-[9px] font-mono text-[var(--muted)] w-16 text-right">{tsFmt(f.ts)}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

function tsFmt(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString("en-HK", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Hong_Kong" });
  } catch { return "—"; }
}

const Kpi = ({ label, value, color, testid }) => (
  <div data-testid={testid} className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
    <div className="flex items-center justify-between">
      <div className="text-[10px] font-mono uppercase text-[var(--muted)]">{label}</div>
      <div className="w-2 h-2 rounded-full" style={{ background: color, boxShadow: `0 0 8px ${color}` }} />
    </div>
    <div className="font-display font-black text-2xl mt-1">{value}</div>
  </div>
);
const Card = ({ title, children }) => (
  <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
    <div className="text-xs font-mono uppercase text-[var(--muted)] mb-3">{title}</div>
    {children}
  </div>
);
const Empty = () => <div className="text-[var(--muted)] text-sm py-8 text-center">Nothing yet — nudges will stream in as the heat-map fires.</div>;
