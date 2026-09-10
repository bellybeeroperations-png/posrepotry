import { useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Shield, X, Delete } from "lucide-react";

/**
 * Manager PIN gate.
 * <ManagerPin action="void this item" onSuccess={fn} onClose={fn} requiredRoles={["manager","admin"]} />
 */
export default function ManagerPin({ action = "authorize", onSuccess, onClose, requiredRoles = ["manager", "admin"] }) {
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (val) => {
    setBusy(true);
    try {
      const r = await api.post("/auth/pin-verify", { pin: val, required_roles: requiredRoles });
      toast.success(`Approved by ${r.data.name}`);
      onSuccess(r.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "PIN rejected");
      setPin("");
    } finally { setBusy(false); }
  };

  const tap = (k) => {
    if (k === "back") return setPin(p => p.slice(0, -1));
    if (k === "enter") return pin.length >= 4 && submit(pin);
    setPin(p => {
      const np = (p + k).slice(0, 6);
      if (np.length === 4) submit(np);
      return np;
    });
  };

  return (
    <div className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-[var(--surface)] border border-[var(--rose)]/40 rounded-xl w-full max-w-sm p-6">
        <button onClick={onClose} data-testid="mgr-pin-close" className="absolute top-3 right-3 text-[var(--muted)]"><X size={18} /></button>
        <div className="flex items-center gap-2 mb-2">
          <Shield size={16} className="text-[var(--rose)]" />
          <div className="font-mono text-xs uppercase tracking-widest text-[var(--rose)] font-bold">Manager Override</div>
        </div>
        <div className="font-display font-black text-xl mb-1">Enter manager PIN</div>
        <div className="text-xs text-[var(--muted)] mb-4">To {action}</div>

        <div className="h-14 rounded-lg bg-[var(--surface-2)] border border-[var(--border)] flex items-center justify-center font-mono text-2xl tracking-[0.5em] text-[var(--amber)] mb-3" data-testid="mgr-pin-display">
          {pin.padEnd(4, "•")}
        </div>
        <div className="grid grid-cols-3 gap-2">
          {["1","2","3","4","5","6","7","8","9","back","0","enter"].map(k => (
            <button
              key={k}
              data-testid={`mgr-pin-${k}`}
              onClick={() => tap(k)}
              disabled={busy}
              className={`h-12 rounded-lg font-display text-lg font-bold border ${
                k === "enter"
                  ? "btn-amber border-transparent"
                  : k === "back"
                  ? "bg-[var(--surface-2)] border-[var(--border)] text-[var(--rose)]"
                  : "bg-[var(--surface-2)] border-[var(--border)] text-white hover:border-[var(--cyan)]"
              }`}
            >
              {k === "back" ? <Delete size={16} className="mx-auto" /> : k === "enter" ? "OK" : k}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
