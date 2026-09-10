import { useState, useEffect } from "react";
import { fmtHKD } from "@/lib/api";
import {
  CreditCard, Banknote, Wallet, Coins, QrCode, Radio,
  Plus, Trash2, Check,
} from "lucide-react";

/**
 * Hong Kong payment modal.
 * Methods: cash, card, octopus, fps_qr, alipayhk, wechatpay_hk, payme, unionpay, split.
 * Octopus: simulated "tap" animation. FPS: QR display with amount.
 */
const METHODS = [
  ["cash", Banknote, "Cash", "#10B981"],
  ["card", CreditCard, "Visa/Master", "#00F2FE"],
  ["octopus", Radio, "Octopus", "#FFB800"],
  ["fps_qr", QrCode, "FPS QR", "#A855F7"],
  ["alipayhk", Wallet, "AlipayHK", "#06B6D4"],
  ["wechatpay_hk", Wallet, "WeChat Pay", "#10B981"],
  ["payme", Wallet, "PayMe", "#F43F5E"],
  ["unionpay", Coins, "UnionPay", "#EC4899"],
];

export default function PaymentModal({ total, guests, onClose, onPay }) {
  const [mode, setMode] = useState("single");
  const [method, setMethod] = useState("cash");
  const [amount, setAmount] = useState(total);
  const [tip, setTip] = useState(0);
  const [splits, setSplits] = useState([{ method: "cash", amount: total }]);
  const [splitMode, setSplitMode] = useState("equal");

  const splitTotal = splits.reduce((s, x) => s + (parseFloat(x.amount) || 0), 0);
  const splitDiff = +(splitTotal - total).toFixed(2);
  const change = method === "cash" ? Math.max(0, amount - total) : 0;

  const applySplitMode = (m) => {
    setSplitMode(m);
    if (m === "equal") {
      const n = splits.length || 2;
      const per = +(total / n).toFixed(2);
      const arr = Array.from({ length: n }, (_, i) => ({ method: splits[i]?.method || "card", amount: per }));
      arr[arr.length - 1].amount = +(per + (total - per * n)).toFixed(2);
      setSplits(arr);
    } else if (m === "by_seat") {
      const per = +(total / guests).toFixed(2);
      const arr = Array.from({ length: guests }, (_, i) => ({ method: "card", amount: per, label: `Seat ${i + 1}` }));
      if (arr.length) arr[arr.length - 1].amount = +(per + (total - per * guests)).toFixed(2);
      setSplits(arr);
    }
  };

  const submit = () => {
    if (mode === "split") return onPay({ method: "split", amount: splitTotal, tip, splits });
    onPay({ method, amount, tip, splits: [] });
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl w-full max-w-lg p-6">
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="font-display font-black text-2xl">Payment</div>
            <div className="text-xs font-mono uppercase text-[var(--muted)]">Order total</div>
          </div>
          <div className="text-3xl font-display font-black text-[var(--cyan)]">{fmtHKD(total)}</div>
        </div>

        <div className="flex gap-1 mb-4 p-1 bg-[var(--surface-2)] rounded-lg">
          <button data-testid="pay-mode-single" onClick={() => setMode("single")}
            className={`flex-1 py-2 rounded-md text-sm font-semibold ${mode === "single" ? "bg-[var(--cyan)] text-black" : "text-[var(--muted)]"}`}>
            Single Payment
          </button>
          <button data-testid="pay-mode-split" onClick={() => { setMode("split"); applySplitMode(splitMode); }}
            className={`flex-1 py-2 rounded-md text-sm font-semibold ${mode === "split" ? "bg-[var(--amber)] text-black" : "text-[var(--muted)]"}`}>
            Split Bill
          </button>
        </div>

        {mode === "single" ? (
          <SingleMode
            method={method} setMethod={setMethod}
            amount={amount} setAmount={setAmount}
            tip={tip} setTip={setTip}
            total={total} change={change}
          />
        ) : (
          <SplitMode
            guests={guests} splits={splits} setSplits={setSplits}
            splitMode={splitMode} applySplitMode={applySplitMode}
            splitTotal={splitTotal} splitDiff={splitDiff} total={total}
          />
        )}

        <div className="flex gap-2 mt-4">
          <button onClick={onClose} className="flex-1 py-2.5 rounded-lg bg-[var(--surface-2)]">Cancel</button>
          <button data-testid="pay-confirm" onClick={submit}
            disabled={mode === "split" && splitDiff < -0.01}
            className="flex-1 btn-neon py-2.5 rounded-lg disabled:opacity-40">
            Confirm
          </button>
        </div>
      </div>
    </div>
  );
}

// ---- Single mode ----
function SingleMode({ method, setMethod, amount, setAmount, tip, setTip, total, change }) {
  return (
    <>
      <div className="grid grid-cols-4 gap-2 mb-4">
        {METHODS.map(([v, Icon, label, color]) => (
          <button key={v} data-testid={`pay-method-${v}`} onClick={() => { setMethod(v); setAmount(total); }}
            className={`p-3 rounded-lg border flex flex-col items-center gap-1 transition ${
              method === v ? "bg-[var(--surface-2)]" : "bg-[var(--surface-2)]/50"
            }`}
            style={method === v ? { borderColor: color, boxShadow: `0 0 12px ${color}55` } : { borderColor: "var(--border)" }}
          >
            <Icon size={18} style={{ color }} />
            <span className="text-[9px] font-mono uppercase leading-tight text-center">{label}</span>
          </button>
        ))}
      </div>

      {method === "octopus" && <OctopusTap amount={total} />}
      {method === "fps_qr" && <FPSQR amount={total} />}

      {method === "cash" && (
        <>
          <label className="text-xs font-mono uppercase text-[var(--muted)]">Amount received</label>
          <input data-testid="pay-amount" type="number" value={amount}
            onChange={(e) => setAmount(parseFloat(e.target.value) || 0)}
            className="w-full mt-1 mb-3 bg-[var(--surface-2)] border border-[var(--border)] rounded-md px-3 py-2 font-mono text-lg" />
          <div className="text-sm font-mono">Change: <span className="text-[var(--amber)] font-bold">{fmtHKD(change)}</span></div>
        </>
      )}

      {["card", "alipayhk", "wechatpay_hk", "payme", "unionpay"].includes(method) && (
        <div className="mt-2 p-3 rounded-lg bg-[var(--surface-2)] border border-[var(--border)] text-xs font-mono text-[var(--muted)]">
          Present card / QR to terminal · MOCKED processing
        </div>
      )}

      <label className="text-xs font-mono uppercase text-[var(--muted)] mt-3 block">Tip</label>
      <input data-testid="pay-tip" type="number" value={tip}
        onChange={(e) => setTip(parseFloat(e.target.value) || 0)}
        className="w-full mt-1 bg-[var(--surface-2)] border border-[var(--border)] rounded-md px-3 py-2 font-mono" />
    </>
  );
}

// ---- Octopus tap simulation ----
function OctopusTap({ amount }) {
  const [step, setStep] = useState("ready"); // ready | tapping | done
  useEffect(() => {
    if (step !== "tapping") return;
    const t = setTimeout(() => setStep("done"), 1800);
    return () => clearTimeout(t);
  }, [step]);
  return (
    <div data-testid="octopus-panel" className="p-4 rounded-lg border border-[var(--amber)]/50 bg-[var(--amber)]/5 text-center mb-3">
      <div className="text-[10px] font-mono uppercase tracking-widest text-[var(--amber)] font-bold mb-2">Octopus Reader</div>
      {step === "ready" && (
        <button data-testid="octopus-tap" onClick={() => setStep("tapping")}
          className="w-full py-6 rounded-lg bg-[var(--amber)] text-black font-display font-black text-xl">
          Tap Octopus to Pay {fmtHKD(amount)}
        </button>
      )}
      {step === "tapping" && (
        <div className="py-6">
          <div className="animate-pulse font-display font-black text-lg text-[var(--amber)]">Reading card…</div>
          <div className="mt-2 h-1 bg-[var(--surface-2)] rounded overflow-hidden">
            <div className="h-full bg-[var(--amber)] animate-[ticker_1.8s_linear]" style={{ width: "100%" }} />
          </div>
        </div>
      )}
      {step === "done" && (
        <div data-testid="octopus-done" className="py-6 text-[var(--emerald)] font-display font-black text-lg flex items-center justify-center gap-2">
          <Check size={20} /> Tap accepted · confirm to complete
        </div>
      )}
    </div>
  );
}

// ---- FPS QR display ----
function FPSQR({ amount }) {
  const ref = `HKBAR-${Date.now().toString().slice(-6)}`;
  // Simulated FPS payload — real integration would build EMVCo QR string
  const payload = `HK.FPS://pay?to=HKBAR&amt=${amount.toFixed(2)}&ref=${ref}`;
  const qr = `https://api.qrserver.com/v1/create-qr-code/?size=180x180&margin=6&data=${encodeURIComponent(payload)}`;
  return (
    <div data-testid="fps-panel" className="p-4 rounded-lg border border-[var(--purple)]/50 bg-[var(--purple)]/5 text-center mb-3">
      <div className="text-[10px] font-mono uppercase tracking-widest text-[var(--purple)] font-bold mb-2">FPS Faster Payment</div>
      <div className="p-3 bg-white rounded-lg inline-block">
        <img data-testid="fps-qr-image" src={qr} alt="FPS QR" width="160" height="160" />
      </div>
      <div className="mt-2 font-mono text-xs text-[var(--muted)]">Ref: <span className="text-white">{ref}</span></div>
      <div className="mt-1 font-mono text-lg font-black text-[var(--purple)]">{fmtHKD(amount)}</div>
      <div className="mt-1 text-[10px] font-mono text-[var(--muted)]">Guest scans with any HK bank app · MOCKED</div>
    </div>
  );
}

// ---- Split mode ----
function SplitMode({ guests, splits, setSplits, splitMode, applySplitMode, splitTotal, splitDiff, total }) {
  const setSplit = (i, k, v) =>
    setSplits(splits.map((s, idx) => (idx === i ? { ...s, [k]: k === "amount" ? parseFloat(v) || 0 : v } : s)));
  const addSplit = () => setSplits([...splits, { method: "card", amount: 0 }]);
  const delSplit = (i) => setSplits(splits.filter((_, idx) => idx !== i));

  return (
    <>
      <div className="flex gap-1 mb-3 text-[10px] font-mono uppercase">
        {[["equal", "Equal Parts"], ["by_seat", `By Seat (${guests})`], ["custom", "Custom"]].map(([v, l]) => (
          <button key={v} data-testid={`split-mode-${v}`} onClick={() => applySplitMode(v)}
            className={`flex-1 py-2 rounded-md border ${splitMode === v ? "bg-[var(--amber)] text-black border-transparent" : "bg-[var(--surface-2)] text-[var(--muted)] border-[var(--border)]"}`}>
            {l}
          </button>
        ))}
      </div>
      <div className="space-y-2 max-h-64 overflow-y-auto">
        {splits.map((s, i) => (
          <div key={i} className="grid grid-cols-[80px_1fr_100px_36px] gap-2 items-center">
            <span className="text-xs font-mono text-[var(--muted)]">{s.label || `Split ${i + 1}`}</span>
            <select data-testid={`split-method-${i}`} value={s.method} onChange={(e) => setSplit(i, "method", e.target.value)}
              className="bg-[var(--surface-2)] border border-[var(--border)] rounded-md px-2 py-1.5 text-sm">
              {METHODS.filter(m => m[0] !== "split").map(([v, , l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            <input data-testid={`split-amount-${i}`} type="number" step="0.01" value={s.amount}
              onChange={(e) => setSplit(i, "amount", e.target.value)}
              disabled={splitMode !== "custom"}
              className="bg-[var(--surface-2)] border border-[var(--border)] rounded-md px-2 py-1.5 text-sm font-mono text-right disabled:opacity-70" />
            {splitMode === "custom" && splits.length > 1 && (
              <button onClick={() => delSplit(i)} className="text-[var(--rose)]"><Trash2 size={14} /></button>
            )}
          </div>
        ))}
      </div>
      {splitMode === "custom" && (
        <button data-testid="split-add" onClick={addSplit} className="mt-2 text-xs text-[var(--cyan)] flex items-center gap-1">
          <Plus size={12} /> Add split
        </button>
      )}
      <div className="mt-3 p-2 rounded-md bg-[var(--surface-2)] border border-[var(--border)] flex items-center justify-between text-xs font-mono">
        <span>Splits sum</span>
        <span className={splitDiff < -0.01 ? "text-[var(--rose)] font-bold" : "text-[var(--amber)] font-bold"} data-testid="split-sum">
          {fmtHKD(splitTotal)} {splitDiff !== 0 && `(${splitDiff > 0 ? "+" : ""}${fmtHKD(splitDiff)})`}
        </span>
      </div>
    </>
  );
}
