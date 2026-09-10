import { fmtHKD } from "@/lib/api";
import { X, Printer, Mail } from "lucide-react";
import { toast } from "sonner";
import { openPrintableWindow } from "@/lib/printable";

export default function Receipt({ order, memberName, onClose }) {
  const html = () => receiptHtml(order, memberName);
  const doPrint = () => openPrintableWindow(html(), "receipt");
  const doEmail = () => {
    // MOCKED: pretend we sent it
    toast.success(memberName ? `Receipt emailed to ${memberName}` : "Receipt queued for email");
  };

  const tsLocal = (iso) =>
    iso ? new Date(iso).toLocaleString("en-HK", { timeZone: "Asia/Hong_Kong", hour12: false }) : "—";

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white text-black rounded-xl w-full max-w-sm max-h-[92vh] overflow-y-auto shadow-2xl relative">
        <button onClick={onClose} data-testid="receipt-close" className="absolute top-2 right-2 text-neutral-400 hover:text-black z-10">
          <X size={20} />
        </button>
        <div className="p-6 font-mono text-[13px] leading-relaxed" data-testid="receipt-body">
          <div className="text-center">
            <div className="font-black text-xl tracking-widest">HK · BAR</div>
            <div className="text-[10px] uppercase tracking-[0.25em] text-neutral-500">Advanced POS · Hong Kong</div>
          </div>
          <div className="border-t border-dashed border-neutral-400 my-3" />
          <div className="text-[11px] text-neutral-600">
            Receipt #{order?.id?.slice(-6).toUpperCase()}
          </div>
          <div className="text-[11px] text-neutral-600">{tsLocal(order?.closed_at || order?.opened_at)}</div>
          <div className="text-[11px] text-neutral-600">
            Type: {order?.order_type} · Guests: {order?.guests}
          </div>
          {memberName && (
            <div className="text-[11px] text-neutral-600">Member: {memberName}</div>
          )}
          <div className="border-t border-dashed border-neutral-400 my-3" />
          {(order?.lines || []).map((l, i) => (
            <div key={`${l.product_id || "x"}-${l.variant || ""}-${i}`} className="flex justify-between text-[12px]">
              <div className="flex-1">
                {l.qty}× {l.name}
                {l.modifiers?.length > 0 && (
                  <div className="text-[10px] text-neutral-500 pl-3">+ {l.modifiers.join(", ")}</div>
                )}
              </div>
              <div className="tabular-nums">{fmtHKD(l.price * l.qty)}</div>
            </div>
          ))}
          <div className="border-t border-dashed border-neutral-400 my-3" />
          <Row label="Subtotal" value={fmtHKD(order?.subtotal || 0)} />
          {order?.discount > 0 && <Row label="Discount" value={`- ${fmtHKD(order.discount)}`} />}
          <Row label={`Service (${order?.service_charge_pct || 10}%)`} value={fmtHKD(order?.service_charge || 0)} />
          <div className="border-t border-neutral-800 my-2" />
          <div className="flex justify-between font-black text-lg">
            <span>TOTAL</span>
            <span>{fmtHKD(order?.total || 0)}</span>
          </div>
          {order?.payment && (
            <>
              <div className="border-t border-dashed border-neutral-400 my-3" />
              <Row label={`Paid (${order.payment.method})`} value={fmtHKD(order.payment.amount || 0)} />
              {order.payment.method === "split" && (order.payment.splits || []).map((s, i) => (
                <Row key={`${s.method}-${s.amount}-${i}`} label={`  · ${s.method}`} value={fmtHKD(s.amount)} sub />
              ))}
              {order.payment.tip > 0 && <Row label="Tip" value={fmtHKD(order.payment.tip)} />}
              {order.payment.change > 0 && <Row label="Change" value={fmtHKD(order.payment.change)} />}
            </>
          )}
          <div className="border-t border-dashed border-neutral-400 my-3" />
          <div className="text-center text-[10px] text-neutral-500">
            THANK YOU · SEE YOU AGAIN
            <br />
            {tsLocal(order?.closed_at || new Date().toISOString())}
          </div>
        </div>
        <div className="flex gap-2 p-4 bg-neutral-100 border-t border-neutral-200">
          <button data-testid="receipt-email" onClick={doEmail}
            className="flex-1 py-2.5 rounded-lg border border-neutral-300 bg-white text-sm font-semibold flex items-center justify-center gap-2">
            <Mail size={14} /> Email
          </button>
          <button data-testid="receipt-print" onClick={doPrint}
            className="flex-1 py-2.5 rounded-lg bg-black text-white text-sm font-semibold flex items-center justify-center gap-2">
            <Printer size={14} /> Print
          </button>
        </div>
      </div>
    </div>
  );
}

const Row = ({ label, value, sub }) => (
  <div className={`flex justify-between text-[12px] ${sub ? "text-neutral-500" : ""}`}>
    <span>{label}</span>
    <span className="tabular-nums">{value}</span>
  </div>
);

function receiptHtml(order, memberName) {
  const ts = (iso) => iso ? new Date(iso).toLocaleString("en-HK", { timeZone: "Asia/Hong_Kong" }) : "";
  const rows = (order.lines || []).map(l => `
    <tr><td>${l.qty}× ${escapeHtml(l.name)}${l.modifiers?.length ? `<br><span class="s">+ ${escapeHtml(l.modifiers.join(", "))}</span>` : ""}</td>
    <td class="r">HK$ ${(l.price * l.qty).toFixed(2)}</td></tr>`).join("");
  const splits = order.payment?.method === "split" && order.payment.splits
    ? order.payment.splits.map(s => `<tr><td class="s">&nbsp;· ${s.method}</td><td class="r s">HK$ ${(s.amount || 0).toFixed(2)}</td></tr>`).join("") : "";
  return `<!doctype html><html><head><meta charset="utf-8"/><title>Receipt</title>
<style>body{font-family:'JetBrains Mono',monospace;font-size:12px;width:280px;margin:0;padding:12px;color:#000}
h1{font-size:20px;text-align:center;margin:0;letter-spacing:.15em}
h2{font-size:10px;text-align:center;margin:0 0 10px;letter-spacing:.25em;color:#666}
hr{border:0;border-top:1px dashed #000;margin:6px 0}
.r{text-align:right}
.s{color:#666;font-size:10px}
.big{font-size:15px;font-weight:900}
table{width:100%;border-collapse:collapse}
td{padding:2px 0;vertical-align:top}
.center{text-align:center}
@page{size:auto;margin:4mm}
</style></head><body>
<h1>HK · BAR</h1><h2>ADVANCED POS · HONG KONG</h2>
<div class="s">Receipt #${(order.id || "").slice(-6).toUpperCase()}</div>
<div class="s">${ts(order.closed_at || order.opened_at)}</div>
<div class="s">Type: ${order.order_type} · Guests: ${order.guests}</div>
${memberName ? `<div class="s">Member: ${escapeHtml(memberName)}</div>` : ""}
<hr/>
<table>${rows}</table>
<hr/>
<table>
<tr><td>Subtotal</td><td class="r">HK$ ${(order.subtotal || 0).toFixed(2)}</td></tr>
${order.discount > 0 ? `<tr><td>Discount</td><td class="r">- HK$ ${order.discount.toFixed(2)}</td></tr>` : ""}
<tr><td>Service (${order.service_charge_pct || 10}%)</td><td class="r">HK$ ${(order.service_charge || 0).toFixed(2)}</td></tr>
</table>
<hr/>
<table><tr><td class="big">TOTAL</td><td class="big r">HK$ ${(order.total || 0).toFixed(2)}</td></tr></table>
${order.payment ? `<hr/><table>
<tr><td>Paid (${order.payment.method})</td><td class="r">HK$ ${(order.payment.amount || 0).toFixed(2)}</td></tr>
${splits}
${order.payment.tip > 0 ? `<tr><td>Tip</td><td class="r">HK$ ${order.payment.tip.toFixed(2)}</td></tr>` : ""}
${order.payment.change > 0 ? `<tr><td>Change</td><td class="r">HK$ ${order.payment.change.toFixed(2)}</td></tr>` : ""}
</table>` : ""}
<hr/>
<div class="center s">THANK YOU · SEE YOU AGAIN</div>
</body></html>`;
}
function escapeHtml(s) { return (s || "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
