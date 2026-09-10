import { NavLink, useNavigate } from "react-router-dom";
import {
  LayoutGrid, Utensils, Users, Shield, LineChart, PartyPopper, LogOut, Sparkles, Flame, Clock, ClipboardList, Beer, Zap,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useEffect, useState } from "react";

const NAV = [
  { to: "/floorplan", label: "Floor", icon: LayoutGrid, testid: "nav-floorplan" },
  { to: "/register", label: "Register", icon: Sparkles, testid: "nav-register" },
  { to: "/bar", label: "Bar", icon: Zap, testid: "nav-quickbar" },
  { to: "/kds", label: "KDS", icon: Flame, testid: "nav-kds" },
  { to: "/kegs", label: "Kegs", icon: Beer, testid: "nav-kegs" },
  { to: "/waitlist", label: "Wait", icon: ClipboardList, testid: "nav-waitlist" },
  { to: "/menu", label: "Menu", icon: Utensils, testid: "nav-menu" },
  { to: "/crm", label: "Members", icon: Users, testid: "nav-crm" },
  { to: "/shift", label: "Shift", icon: Clock, testid: "nav-shift" },
  { to: "/staff", label: "Staff", icon: Shield, testid: "nav-staff" },
  { to: "/reports", label: "Reports", icon: LineChart, testid: "nav-reports" },
];

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const hkTime = now.toLocaleTimeString("en-HK", {
    timeZone: "Asia/Hong_Kong", hour12: false,
  });

  return (
    <div className="flex h-screen w-full bg-[var(--bg)] text-[var(--text)] noise">
      {/* Left rail */}
      <aside className="w-[88px] shrink-0 border-r border-[var(--border)] bg-[var(--surface)] flex flex-col items-center py-4 gap-2">
        <div className="mb-2 flex flex-col items-center">
          <div className="font-display text-[var(--cyan)] font-black text-xl">HK</div>
          <div className="font-mono text-[10px] text-[var(--muted)] tracking-widest">BAR·POS</div>
        </div>
        <nav className="flex flex-col gap-1.5 w-full px-2 mt-2 flex-1">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              data-testid={n.testid}
              className={({ isActive }) =>
                `group flex flex-col items-center justify-center gap-1 py-3 rounded-lg transition-all ${
                  isActive
                    ? "bg-[var(--cyan)]/12 text-[var(--cyan)] neon-cyan"
                    : "text-[var(--muted)] hover:bg-[var(--surface-2)] hover:text-white"
                }`
              }
            >
              <n.icon size={20} strokeWidth={1.75} />
              <span className="text-[10px] font-mono uppercase tracking-wider">{n.label}</span>
            </NavLink>
          ))}
        </nav>
        <button
          data-testid="btn-logout"
          onClick={async () => {
            await logout();
            nav("/login");
          }}
          className="w-full mx-2 py-3 rounded-lg text-[var(--rose)] hover:bg-[var(--rose)]/10 flex flex-col items-center gap-1"
          title="Logout"
        >
          <LogOut size={20} strokeWidth={1.75} />
          <span className="text-[10px] font-mono uppercase tracking-wider">Out</span>
        </button>
      </aside>

      {/* Top bar + content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-14 border-b border-[var(--border)] bg-[var(--surface)]/80 backdrop-blur flex items-center px-5 gap-4">
          <div className="flex items-center gap-2">
            <span className="pulse-dot" />
            <span className="font-mono text-xs text-[var(--muted)] tracking-widest uppercase">
              LIVE · HK
            </span>
            <span className="font-mono text-lg text-white" data-testid="topbar-clock">
              {hkTime}
            </span>
          </div>
          <div className="ml-auto flex items-center gap-4">
            <div className="text-right">
              <div className="text-sm font-semibold text-white" data-testid="topbar-user-name">
                {user?.name}
              </div>
              <div className="text-[10px] font-mono uppercase tracking-widest text-[var(--cyan)]">
                {user?.role}
              </div>
            </div>
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-[var(--cyan)] to-[var(--purple)] flex items-center justify-center font-bold text-black">
              {user?.name?.[0] || "?"}
            </div>
          </div>
        </header>
        <main className="flex-1 overflow-auto p-6 fade-in">{children}</main>
      </div>
    </div>
  );
}
