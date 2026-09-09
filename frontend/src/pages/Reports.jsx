import { useEffect, useState } from "react";
import { api, fmtHKD } from "@/lib/api";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, PieChart, Pie, Cell } from "recharts";
import { TrendingUp, Users, Receipt, Wallet } from "lucide-react";

const COLORS = ["#00F2FE", "#FFB800", "#A855F7", "#10B981", "#F43F5E", "#06B6D4"];

export default function Reports() {
  const [data, setData] = useState(null);
  useEffect(() => { api.get("/reports/summary").then((r) => setData(r.data)); }, []);
  if (!data) return <div className="text-[var(--muted)]">Loading…</div>;

  return (
    <div>
      <h1 className="font-display text-2xl font-black mb-4">Reports & Insights</h1>
      <div className="grid grid-cols-4 gap-3 mb-4">
        <Kpi label="Revenue" value={fmtHKD(data.total_revenue)} icon={Wallet} color="#00F2FE" testid="kpi-revenue" />
        <Kpi label="Orders" value={data.total_orders} icon={Receipt} color="#FFB800" testid="kpi-orders" />
        <Kpi label="Avg Ticket" value={fmtHKD(data.avg_ticket)} icon={TrendingUp} color="#A855F7" testid="kpi-avg" />
        <Kpi label="Top Staff" value={data.by_staff[0]?.name || "—"} icon={Users} color="#10B981" testid="kpi-staff" />
      </div>
      <div className="grid grid-cols-2 gap-4">
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
                {data.by_category.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
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

const Kpi = ({ label, value, icon: Icon, color, testid }) => (
  <div data-testid={testid} className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
    <div className="flex items-center justify-between">
      <div className="text-[10px] font-mono uppercase text-[var(--muted)]">{label}</div>
      <Icon size={16} style={{ color }} />
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
const Empty = () => <div className="text-[var(--muted)] text-sm py-8 text-center">No data yet — take orders first.</div>;
