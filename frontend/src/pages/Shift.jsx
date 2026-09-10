import { useEffect, useState } from "react";
import { api, fmtHKD } from "@/lib/api";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { LogIn, LogOut, Printer, Wallet, Users as UsersIcon, Receipt as ReceiptIcon } from "lucide-react";
import { openPrintableWindow } from "@/lib/printable";

export default function Shift() {
  const { user } = useAuth();
  const [current, setCurrent] = useState({ open: false });
  const [history, setHistory] = useState([]);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const c = await api.get("/shifts/current"); setCurrent(c.data);
    const h = await api.get("/shifts"); setHistory(h.data);
  };
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, []);

  const clockIn = async () => {
    setBusy(true);
    try { await api.post("/shifts/clock-in"); toast.success("Clocked in"); await load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };
  const clockOut = async () => {
    if (!confirm("Clock out and close shift?")) return;
    setBusy(true);
    try { await api.post("/shifts/clock-out"); toast.success("Clocked out — Z report ready"); await load(); }
    catch (e) { toast.error("Failed"); }
    finally { setBusy(false); }
  };

  const printReport = (report, type) => {
    openPrintableWindow(reportHtml(report, type, user?.name), "shift");
  };

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <h1 className="font-display text-2xl font-black">Shift Reports</h1>
        <div className="ml-auto">
          {current.open ? (
            <button data-testid="btn-clock-out" onClick={clockOut} disabled={busy}
              className="px-5 py-2.5 rounded-lg bg-[var(--rose)] text-white font-bold flex items-center gap-2">
              <LogOut size={16} /> Clock Out · Z Report
            </button>
          ) : (
            <button data-testid="btn-clock-in" onClick={clockIn} disabled={busy}
              className="px-5 py-2.5 rounded-lg btn-neon flex items-center gap-2">
              <LogIn size={16} /> Clock In
            </button>
          )}
        </div>
      </div>

      {current.open && (
        <div className="mb-6 rounded-xl border border-[var(--emerald)]/40 bg-[var(--emerald)]/5 p-5">
          <div className="flex items-center gap-2 mb-3">
            <span className="pulse-dot" />
            <div className="font-mono text-xs uppercase tracking-widest text-[var(--emerald)] font-bold">
              Live Shift · {user?.name}
            </div>
            <div className="ml-auto text-xs font-mono text-[var(--muted)]">
              Since {new Date(current.shift?.clock_in).toLocaleTimeString("en-HK", { timeZone: "Asia/Hong_Kong", hour12: false })}
            </div>
          </div>
          <div className="grid grid-cols-5 gap-3">
            <Kpi label="Revenue" value={fmtHKD(current.revenue)} icon={Wallet} testid="shift-revenue" />
            <Kpi label="Orders" value={current.orders} icon={ReceiptIcon} testid="shift-orders" color="#00F2FE" />
            <Kpi label="Covers" value={current.covers} icon={UsersIcon} testid="shift-covers" color="#A855F7" />
            <Kpi label="Tips" value={fmtHKD(current.tips)} icon={Wallet} testid="shift-tips" color="#10B981" />
            <Kpi label="Avg Ticket" value={fmtHKD(current.avg_ticket)} icon={ReceiptIcon} testid="shift-avg" color="#F43F5E" />
          </div>
          <div className="mt-4 flex gap-2">
            <button data-testid="btn-x-report" onClick={() => printReport(current, "X")}
              className="px-4 py-2 rounded-lg bg-[var(--surface-2)] border border-[var(--border)] text-sm flex items-center gap-2">
              <Printer size={14} /> Print X Report (mid-shift)
            </button>
          </div>
          {current.by_payment?.length > 0 && (
            <div className="mt-4 grid grid-cols-4 gap-2">
              {current.by_payment.map(p => (
                <div key={p.method} className="p-2 rounded bg-[var(--surface-2)] border border-[var(--border)]">
                  <div className="text-[10px] font-mono uppercase text-[var(--muted)]">{p.method}</div>
                  <div className="font-mono font-bold">{fmtHKD(p.amount)}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="mb-2 text-xs font-mono uppercase tracking-widest text-[var(--muted)]">Recent Shifts</div>
      <div className="space-y-2">
        {history.filter(h => !current.open || h.shift.id !== current.shift?.id).slice(0, 20).map(h => (
          <div key={h.shift.id} data-testid={`shift-row-${h.shift.id}`}
               className="p-4 rounded-lg border border-[var(--border)] bg-[var(--surface)] flex items-center gap-4">
            <div className="w-9 h-9 rounded-full bg-[var(--surface-2)] flex items-center justify-center font-bold">
              {h.shift.user_name?.[0]}
            </div>
            <div>
              <div className="font-semibold">{h.shift.user_name} <span className="text-[10px] text-[var(--muted)] font-mono uppercase">{h.shift.role}</span></div>
              <div className="text-[10px] font-mono text-[var(--muted)]">
                {new Date(h.shift.clock_in).toLocaleString("en-HK", { timeZone: "Asia/Hong_Kong" })}
                {h.shift.clock_out ? ` → ${new Date(h.shift.clock_out).toLocaleTimeString("en-HK", { timeZone: "Asia/Hong_Kong", hour12: false })}` : " (open)"}
              </div>
            </div>
            <div className="ml-auto flex items-center gap-6 text-sm font-mono">
              <div><span className="text-[var(--muted)]">Rev </span><span className="font-bold text-[var(--amber)]">{fmtHKD(h.revenue)}</span></div>
              <div><span className="text-[var(--muted)]">Orders </span><span className="font-bold">{h.orders}</span></div>
              <div><span className="text-[var(--muted)]">Tips </span><span className="font-bold">{fmtHKD(h.tips)}</span></div>
            </div>
            <button data-testid={`btn-z-${h.shift.id}`} onClick={() => printReport(h, h.shift.clock_out ? "Z" : "X")}
              className="px-3 py-2 rounded-lg bg-[var(--surface-2)] border border-[var(--border)] text-xs flex items-center gap-1.5">
              <Printer size={12} /> Print {h.shift.clock_out ? "Z" : "X"}
            </button>
          </div>
        ))}
        {history.length === 0 && !current.open && (
          <div className="text-[var(--muted)] text-sm">No shifts yet — clock in to start tracking.</div>
        )}
      </div>
    </div>
  );
}

function Kpi({ label, value, icon: Icon, color = "#FFB800", testid }) {
  return (
    <div data-testid={testid} className="p-3 rounded-lg border border-[var(--border)] bg-[var(--surface)]">
      <div className="flex items-center justify-between">
        <div className="text-[10px] font-mono uppercase text-[var(--muted)]">{label}</div>
        <Icon size={14} style={{ color }} />
      </div>
      <div className="font-display font-black text-xl mt-1">{value}</div>
    </div>
  );
}

function reportHtml(r, type, whoami) {
  const s = r.shift;
  const esc = (v) => (v == null ? "" : String(v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])));
  const rows = (r.by_payment || []).map(p => `<tr><td>${esc(p.method).toUpperCase()}</td><td class="r">HK$ ${p.amount.toFixed(2)}</td></tr>`).join("");
  return `<!doctype html><html><head><meta charset="utf-8"/><title>${type} Report</title>
<style>
body{font-family:'JetBrains Mono',monospace;font-size:12px;color:#000;background:#fff;padding:12px;width:320px}
h1{font-size:18px;text-align:center;margin:0}
h2{font-size:14px;text-align:center;margin:2px 0 12px;letter-spacing:.15em}
hr{border:0;border-top:1px dashed #000;margin:8px 0}
table{width:100%;border-collapse:collapse;margin:6px 0}
td{padding:2px 0}
.r{text-align:right}
.big{font-size:16px;font-weight:900}
.center{text-align:center}
.sub{color:#666}
@page{size:auto;margin:6mm}
</style></head><body>
<h1>HK · BAR</h1>
<h2>${type} REPORT · ${type === "X" ? "MID-SHIFT" : "END-OF-SHIFT"}</h2>
<div class="sub center">${new Date().toLocaleString("en-HK",{timeZone:"Asia/Hong_Kong"})}</div>
<hr/>
<div>Staff: <b>${esc(s.user_name)}</b> <span class="sub">(${esc(s.role)})</span></div>
<div>In:  ${new Date(s.clock_in).toLocaleString("en-HK",{timeZone:"Asia/Hong_Kong"})}</div>
<div>Out: ${s.clock_out ? new Date(s.clock_out).toLocaleString("en-HK",{timeZone:"Asia/Hong_Kong"}) : "— live —"}</div>
<div class="sub">Printed by: ${esc(whoami || "")}</div>
<hr/>
<table>
<tr><td>Orders</td><td class="r"><b>${r.orders}</b></td></tr>
<tr><td>Covers</td><td class="r"><b>${r.covers}</b></td></tr>
<tr><td>Avg Ticket</td><td class="r">HK$ ${r.avg_ticket.toFixed(2)}</td></tr>
<tr><td>Tips</td><td class="r">HK$ ${r.tips.toFixed(2)}</td></tr>
</table>
<hr/>
<div class="sub">PAYMENT MIX</div>
<table>${rows || '<tr><td class="sub">— none —</td><td></td></tr>'}</table>
<hr/>
<div class="big">TOTAL REVENUE</div>
<div class="big r">HK$ ${r.revenue.toFixed(2)}</div>
<hr/>
<div class="center sub">— thank you —</div>
</body></html>`;
}
