import { useEffect, useState } from "react";
import { api, fmtHKD } from "@/lib/api";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, PieChart, Pie, Cell } from "recharts";
import { TrendingUp, Users, Receipt, Wallet, Truck } from "lucide-react";

const COLORS = ["#00F2FE", "#FFB800", "#A855F7", "#10B981", "#F43F5E", "#06B6D4"];
const PLATFORM_TINT = { foodpanda: "#F43F5E", deliveroo: "#10B981", keeta: "#FFB800" };

export default function Reports() {
  const [data, setData] = useState(null);
  useEffect(() => { api.get("/reports/summary").then((r) => setData(r.data)); }, []);
  if (!data) return <div className="text-[var(--muted)]">Loading…</div>;

  return (
    <div>
      <h1 className="font-display text-2xl font-black mb-4">Reports & Insights</h1>
      <div className="grid grid-cols-5 gap-3 mb-4">
        <Kpi label="Gross Revenue" value={fmtHKD(data.total_revenue)} icon={Wallet} color="#00F2FE" testid="kpi-revenue" />
        <Kpi label="Net Revenue" value={fmtHKD(data.net_revenue)} icon={Wallet} color="#10B981" testid="kpi-net-revenue"
          sub={data.delivery_fees > 0 ? `− ${fmtHKD(data.delivery_fees)} platform fees` : "no platform fees"} />
        <Kpi label="Orders" value={data.total_orders} icon={Receipt} color="#FFB800" testid="kpi-orders" />
        <Kpi label="Avg Ticket" value={fmtHKD(data.avg_ticket)} icon={TrendingUp} color="#A855F7" testid="kpi-avg" />
        <Kpi label="Top Staff" value={data.by_staff[0]?.name || "—"} icon={Users} color="#10B981" testid="kpi-staff" />
      </div>
      {data.by_delivery_platform?.length > 0 && (
        <Card title="Delivery — Fee Split" data-testid="card-delivery-split">
          <div className="grid grid-cols-3 gap-3">
            {data.by_delivery_platform.map((p) => (
              <div key={p.platform} data-testid={`delivery-split-${p.platform}`}
                className="p-3 rounded-lg border" style={{ borderColor: (PLATFORM_TINT[p.platform] || "#26334D") + "66" }}>
                <div className="flex items-center gap-2">
                  <Truck size={14} style={{ color: PLATFORM_TINT[p.platform] || "#94A3B8" }} />
                  <div className="font-mono text-xs uppercase font-bold" style={{ color: PLATFORM_TINT[p.platform] || "#94A3B8" }}>
                    {p.platform}
                  </div>
                  <div className="ml-auto text-[10px] font-mono text-[var(--muted)]">{p.orders} orders</div>
                </div>
                <div className="mt-2 grid grid-cols-3 gap-1 text-[10px] font-mono">
                  <div><div className="text-[var(--muted)]">Gross</div><div className="text-white font-bold">{fmtHKD(p.gross)}</div></div>
                  <div><div className="text-[var(--muted)]">Fee</div><div className="text-[var(--rose)] font-bold">-{fmtHKD(p.fee)}</div></div>
                  <div><div className="text-[var(--muted)]">Net</div><div className="text-[var(--emerald)] font-bold">{fmtHKD(p.net)}</div></div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
      <div className="grid grid-cols-2 gap-4 mt-4">
        <Card title="Revenue by Hour (HK)">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data.by_hour}>
              <XAxis dataKey="hour" stroke="#94A3B8" fontSize={11} />
              <YAxis stroke="#94A3B8" fontSize={11} />
              <Tooltip contentStyle={{ background: "#121824", border: "1px solid #26334D" }} />
              <Bar dataKey="revenue" fill="#00F2FE" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Sales by Category">
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={data.by_category} dataKey="revenue" nameKey="name" cx="50%" cy="50%" innerRadius={40} outerRadius={80} paddingAngle={2}>
                {data.by_category.map((c, i) => <Cell key={c.name} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ background: "#121824", border: "1px solid #26334D" }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="mt-2 grid grid-cols-2 gap-1 text-xs">
            {data.by_category.slice(0, 6).map((c, i) => (
              <div key={c.name} className="flex items-center gap-1">
                <div className="w-2 h-2 rounded" style={{ background: COLORS[i % COLORS.length] }} />
                <span className="text-[var(--muted)]">{c.name}</span>
                <span className="ml-auto font-mono">{fmtHKD(c.revenue)}</span>
              </div>
            ))}
          </div>
        </Card>
        <Card title="Payment Mix">
          {data.by_payment.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={data.by_payment} layout="vertical">
                <XAxis type="number" stroke="#94A3B8" fontSize={11} />
                <YAxis type="category" dataKey="name" stroke="#94A3B8" fontSize={11} width={80} />
                <Tooltip contentStyle={{ background: "#121824", border: "1px solid #26334D" }} />
                <Bar dataKey="revenue" fill="#FFB800" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </Card>
        <Card title="Top Staff Revenue">
          {data.by_staff.length ? (
            <div className="space-y-2">
              {data.by_staff.slice(0, 6).map((s, i) => (
                <div key={s.name} className="flex items-center gap-3">
                  <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold" style={{ background: COLORS[i % COLORS.length], color: "#000" }}>
                    {s.name?.[0]}
                  </div>
                  <div className="flex-1 text-sm">{s.name}</div>
                  <div className="font-mono font-bold text-[var(--amber)]">{fmtHKD(s.revenue)}</div>
                </div>
              ))}
            </div>
          ) : <Empty />}
        </Card>
      </div>
    </div>
  );
}

const Kpi = ({ label, value, icon: Icon, color, testid, sub }) => (
  <div data-testid={testid} className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
    <div className="flex items-center justify-between">
      <div className="text-[10px] font-mono uppercase text-[var(--muted)]">{label}</div>
      <Icon size={16} style={{ color }} />
    </div>
    <div className="font-display font-black text-2xl mt-1">{value}</div>
    {sub && <div className="text-[9px] font-mono uppercase text-[var(--muted)] mt-0.5">{sub}</div>}
  </div>
);
const Card = ({ title, children, ...rest }) => (
  <div {...rest} className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
    <div className="text-xs font-mono uppercase text-[var(--muted)] mb-3">{title}</div>
    {children}
  </div>
);
const Empty = () => <div className="text-[var(--muted)] text-sm py-8 text-center">No data yet — take orders first.</div>;
