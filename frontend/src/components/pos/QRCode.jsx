import { X, Printer, Copy } from "lucide-react";
import { toast } from "sonner";
import { openPrintableWindow } from "@/lib/printable";

/** Generates a QR image via api.qrserver.com — no npm dep needed. */
export function QRCode({ table, url, onClose }) {
  const menuUrl = url || `${window.location.origin}/m/${table.id}`;
  const qr = `https://api.qrserver.com/v1/create-qr-code/?size=280x280&margin=8&data=${encodeURIComponent(menuUrl)}`;

  const copy = async () => {
    await navigator.clipboard.writeText(menuUrl);
    toast.success("Link copied");
  };
  const printQR = () => {
    const html = `<!doctype html><html><head><title>Table ${table.name} · Menu QR</title>
<style>body{font-family:'JetBrains Mono',monospace;text-align:center;padding:20px;color:#000;background:#fff}
h1{font-size:28px;margin:0;letter-spacing:.15em}
h2{font-size:12px;letter-spacing:.3em;margin:2px 0 20px;color:#666}
.t{font-size:56px;font-weight:900;margin:10px 0 4px}
.s{font-size:11px;color:#666}
img{margin:16px 0;border:6px solid #000}
.url{font-size:10px;word-break:break-all;color:#666;margin-top:8px}
@page{size:auto;margin:8mm}
</style></head><body>
<h1>HK · BAR</h1><h2>SCAN TO VIEW OUR MENU</h2>
<div class="s">Your table</div><div class="t">${table.name}</div>
<img src="${qr}" alt="qr" width="280" height="280"/>
<div class="s">Order at the bar or ask your server</div>
<div class="url">${menuUrl}</div>
</body></html>`;
    openPrintableWindow(html, "qr");
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl w-full max-w-sm p-6 text-center" onClick={e => e.stopPropagation()}>
        <button onClick={onClose} className="absolute top-3 right-3 text-[var(--muted)]"><X size={18} /></button>
        <div className="text-[10px] font-mono uppercase tracking-widest text-[var(--muted)]">Menu QR</div>
        <div className="font-display font-black text-4xl text-[var(--cyan)] mb-4">{table.name}</div>
        <div className="p-4 bg-white rounded-xl inline-block">
          <img data-testid="qr-image" src={qr} alt={`QR ${table.name}`} width="220" height="220" />
        </div>
        <div className="text-xs font-mono text-[var(--muted)] mt-3 break-all" data-testid="qr-url">{menuUrl}</div>
        <div className="flex gap-2 mt-4">
          <button data-testid="qr-copy" onClick={copy} className="flex-1 py-2.5 rounded-lg bg-[var(--surface-2)] border border-[var(--border)] flex items-center justify-center gap-1.5 text-sm">
            <Copy size={14} /> Copy Link
          </button>
          <button data-testid="qr-print" onClick={printQR} className="flex-1 btn-neon py-2.5 rounded-lg flex items-center justify-center gap-1.5 text-sm">
            <Printer size={14} /> Print
          </button>
        </div>
      </div>
    </div>
  );
}
