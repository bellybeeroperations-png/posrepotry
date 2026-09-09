import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Delete, LogIn, KeyRound } from "lucide-react";

export default function Login() {
  const [mode, setMode] = useState("email");
  const [email, setEmail] = useState("polymuze111@gmail.com");
  const [password, setPassword] = useState("admin123");
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false);
  const { login, pinLogin } = useAuth();
  const nav = useNavigate();

  const doLogin = async (e) => {
    e?.preventDefault();
    setBusy(true);
    try {
      await login(email, password);
      toast.success("Welcome back");
      nav("/floorplan");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Login failed");
    } finally {
      setBusy(false);
    }
  };

  const doPin = async (val) => {
    setBusy(true);
    try {
      await pinLogin(val);
      toast.success("Shift access granted");
      nav("/floorplan");
    } catch (err) {
      toast.error("Invalid PIN");
      setPin("");
    } finally {
      setBusy(false);
    }
  };

  const tapKey = (k) => {
    if (k === "back") return setPin((p) => p.slice(0, -1));
    if (k === "enter") return pin.length >= 4 && doPin(pin);
    setPin((p) => {
      const np = (p + k).slice(0, 6);
      if (np.length === 4) doPin(np);
      return np;
    });
  };

  return (
    <div className="h-screen w-full grid-bg noise flex items-center justify-center relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-[var(--cyan)]/5 via-transparent to-[var(--amber)]/5 pointer-events-none" />
      <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-[var(--cyan)] to-transparent opacity-60" />

      <div className="w-full max-w-md p-8 rounded-2xl glass relative">
        <div className="text-center mb-8">
          <div className="font-display text-4xl font-black tracking-tight">
            <span className="text-[var(--cyan)]">HK</span>
            <span className="text-white">·</span>
            <span className="text-[var(--amber)]">BAR</span>
          </div>
          <div className="font-mono text-xs text-[var(--muted)] tracking-[0.3em] uppercase mt-1">
            Advanced POS · Hong Kong
          </div>
        </div>

        <div className="flex gap-2 mb-6 p-1 bg-[var(--surface-2)] rounded-lg">
          <button
            data-testid="tab-email"
            className={`flex-1 py-2 rounded-md text-sm font-semibold transition ${
              mode === "email" ? "bg-[var(--cyan)] text-black" : "text-[var(--muted)]"
            }`}
            onClick={() => setMode("email")}
          >
            <LogIn size={14} className="inline mr-1.5" /> Email
          </button>
          <button
            data-testid="tab-pin"
            className={`flex-1 py-2 rounded-md text-sm font-semibold transition ${
              mode === "pin" ? "bg-[var(--amber)] text-black" : "text-[var(--muted)]"
            }`}
            onClick={() => setMode("pin")}
          >
            <KeyRound size={14} className="inline mr-1.5" /> Quick PIN
          </button>
        </div>

        {mode === "email" ? (
          <form onSubmit={doLogin} className="space-y-4">
            <div>
              <label className="text-xs font-mono uppercase tracking-wider text-[var(--muted)]">
                Email
              </label>
              <input
                data-testid="input-email"
                type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                className="mt-1 w-full bg-[var(--surface-2)] border border-[var(--border)] rounded-lg px-4 py-3 text-white focus:border-[var(--cyan)] focus:outline-none"
              />
            </div>
            <div>
              <label className="text-xs font-mono uppercase tracking-wider text-[var(--muted)]">
                Password
              </label>
              <input
                data-testid="input-password"
                type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                className="mt-1 w-full bg-[var(--surface-2)] border border-[var(--border)] rounded-lg px-4 py-3 text-white focus:border-[var(--cyan)] focus:outline-none"
              />
            </div>
            <button
              data-testid="btn-login-submit"
              disabled={busy}
              className="w-full btn-neon py-3 rounded-lg mt-2"
            >
              {busy ? "Signing in…" : "Sign In"}
            </button>
          </form>
        ) : (
          <div className="space-y-4">
            <div className="h-16 rounded-lg bg-[var(--surface-2)] border border-[var(--border)] flex items-center justify-center font-mono text-3xl tracking-[0.5em] text-[var(--amber)]" data-testid="pin-display">
              {pin.padEnd(4, "•")}
            </div>
            <div className="grid grid-cols-3 gap-2">
              {["1","2","3","4","5","6","7","8","9","back","0","enter"].map((k) => (
                <button
                  key={k}
                  data-testid={`pin-key-${k}`}
                  onClick={() => tapKey(k)}
                  disabled={busy}
                  className={`h-14 rounded-lg font-display text-xl font-bold transition-all border ${
                    k === "enter"
                      ? "btn-amber border-transparent"
                      : k === "back"
                      ? "bg-[var(--surface-2)] border-[var(--border)] text-[var(--rose)]"
                      : "bg-[var(--surface-2)] border-[var(--border)] text-white hover:border-[var(--cyan)]"
                  }`}
                >
                  {k === "back" ? <Delete size={20} className="mx-auto" /> : k === "enter" ? "GO" : k}
                </button>
              ))}
            </div>
            <p className="text-xs text-center text-[var(--muted)] font-mono">
              Try PIN 1111 · 2222 · 3333 · 4444
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
