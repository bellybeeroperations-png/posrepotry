import { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { api, fmtHKD } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Trash2, Move, Edit3, Check, Users as UsersIcon, Sparkles, Clock, DollarSign, AlertCircle, Radio, Trophy, Target } from "lucide-react";
import { ReservationModal, TableActionModal } from "@/components/pos/Reservations";

const STATUS_LABELS = {
  available: "Available",
  occupied: "Occupied",
  bill_requested: "Bill Requested",
  dirty: "Needs Cleaning",
  reserved: "Reserved",
};
const STATUS_COLORS = {
  available: "table-available",
  occupied: "table-occupied",
  bill_requested: "table-bill",
  dirty: "table-dirty",
  reserved: "table-reserved",
};

export default function Floorplan() {
  const [areas, setAreas] = useState([]);
  const [activeArea, setActiveArea] = useState(null);
  const [tables, setTables] = useState([]);
  const [editMode, setEditMode] = useState(false);
  const [drag, setDrag] = useState(null);
  const [activeHH, setActiveHH] = useState([]);
  const [now, setNow] = useState(new Date());
  const [selTable, setSelTable] = useState(null);
  const [reserveTable, setReserveTable] = useState(null);
  const nav = useNavigate();

  const load = async () => {
    const a = (await api.get("/areas")).data;
    setAreas(a);
    if (!activeArea && a[0]) setActiveArea(a[0].id);
  };
  useEffect(() => { load(); }, []);
  useEffect(() => {
    api.get("/happy-hours/active").then((r) => setActiveHH(r.data.active || []));
    const hh = setInterval(() => api.get("/happy-hours/active").then((r) => setActiveHH(r.data.active || [])), 60000);
    const clk = setInterval(() => setNow(new Date()), 30000);
    return () => { clearInterval(hh); clearInterval(clk); };
  }, []);
  useEffect(() => {
    if (!activeArea) return;
    api.get("/tables", { params: { area_id: activeArea } }).then((r) => setTables(r.data));
    const t = setInterval(() => {
      api.get("/tables", { params: { area_id: activeArea } }).then((r) => setTables(r.data));
    }, 5000);
    return () => clearInterval(t);
  }, [activeArea]);

  // ---- business KPIs across ALL tables (fetch other areas silently) ----
  const [allTables, setAllTables] = useState([]);
  useEffect(() => {
    const fetchAll = () => api.get("/tables").then((r) => setAllTables(r.data));
    fetchAll();
    const t = setInterval(fetchAll, 10000);
    return () => clearInterval(t);
  }, []);

  const stats = useMemo(() => {
    const occupied = allTables.filter(t => t.status === "occupied");
    const covers = occupied.reduce((s, t) => s + (t.current_order?.guests || 0), 0);
    const due = occupied.reduce((s, t) => s + (t.current_order?.total || 0), 0);
    const free = allTables.filter(t => t.status === "available").length;
    const over30 = occupied.filter(t => {
      const op = t.current_order?.opened_at;
      if (!op) return false;
      const mins = (Date.now() - new Date(op).getTime()) / 60000;
      return mins > 30;
    }).length;
    // Day open: HK time between 11:00 and 06:00 next day
    const hkStr = new Date().toLocaleString("en-GB", { timeZone: "Asia/Hong_Kong", hour12: false, hour: "2-digit", minute: "2-digit" });
    const [hh] = hkStr.split(":").map(Number);
    const open = hh >= 11 || hh < 6;
    return { covers, due, free, over30, openTables: occupied.length, dayOpen: open };
  }, [allTables, now]);
  // ---- end KPIs ----

  const totals = tables.reduce((acc, t) => {
    acc[t.status] = (acc[t.status] || 0) + 1;
    return acc;
  }, {});

  const onDown = (e, t) => {
    if (!editMode) return;
    const rect = e.currentTarget.parentElement.getBoundingClientRect();
    setDrag({ id: t.id, startX: e.clientX, startY: e.clientY, x0: t.x, y0: t.y, rect });
  };
  const onMove = (e) => {
    if (!drag) return;
    const dx = e.clientX - drag.startX;
    const dy = e.clientY - drag.startY;
    setTables((ts) =>
      ts.map((t) => (t.id === drag.id ? { ...t, x: Math.max(0, drag.x0 + dx), y: Math.max(0, drag.y0 + dy) } : t))
    );
  };
  const onUp = async () => {
    if (!drag) return;
    const t = tables.find((x) => x.id === drag.id);
    setDrag(null);
    if (!t) return;
    try {
      await api.patch(`/tables/${t.id}`, { x: t.x, y: t.y });
    } catch {
      toast.error("Failed to save position");
    }
  };

  const addTable = async () => {
    const name = prompt("Table name / label?");
    if (!name) return;
    const seats = parseInt(prompt("Seats?", "4") || "4", 10);
    const doc = await api.post("/tables", {
      area_id: activeArea, name, seats, x: 40, y: 40, width: 90, height: 90, shape: "rect",
    });
    setTables((t) => [...t, doc.data]);
  };

  const delTable = async (id) => {
    if (!confirm("Delete this table?")) return;
    await api.delete(`/tables/${id}`);
    setTables((t) => t.filter((x) => x.id !== id));
  };

  const openTable = (t) => {
    if (editMode) return;
    setSelTable(t);
  };

  const goToOrder = (t) => {
    setSelTable(null);
    if (t.current_order_id) nav(`/register?order=${t.current_order_id}&table=${t.id}`);
    else nav(`/register?table=${t.id}&area=${activeArea}`);
  };

  const cancelReservation = async (t) => {
    if (!confirm(`Cancel reservation for ${t.reservation?.guest_name}?`)) return;
    try {
      await api.delete(`/reservations/${t.reservation.id}`);
      toast.success("Reservation cancelled");
      setSelTable(null);
      const r = await api.get("/tables", { params: { area_id: activeArea } });
      setTables(r.data);
    } catch { toast.error("Failed"); }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Business KPI bar */}
      <div className="mb-3 grid grid-cols-6 gap-2">
        <Kpi label="Covers" value={stats.covers} icon={UsersIcon} testid="kpi-covers" />
        <Kpi label="Open Tables" value={stats.openTables} icon={Radio} testid="kpi-open" color="#F59E0B" />
        <Kpi label="$ Due" value={fmtHKD(stats.due)} icon={DollarSign} testid="kpi-due" color="#FFB800" />
        <Kpi label="Free Tables" value={stats.free} icon={Check} testid="kpi-free" color="#10B981" />
        <Kpi label=">30m Sessions" value={stats.over30} icon={Clock} testid="kpi-over30" color="#F43F5E" />
        <div data-testid="kpi-day" className={`p-3 rounded-xl border flex items-center gap-2 ${stats.dayOpen ? "border-[var(--emerald)] bg-[var(--emerald)]/10" : "border-[var(--rose)] bg-[var(--rose)]/10"}`}>
          <span className={`w-2 h-2 rounded-full ${stats.dayOpen ? "bg-[var(--emerald)]" : "bg-[var(--rose)]"}`} style={{ boxShadow: stats.dayOpen ? "0 0 12px #10b981" : "0 0 12px #f43f5e" }} />
          <div>
            <div className="text-[10px] font-mono uppercase text-[var(--muted)]">Day</div>
            <div className={`font-display font-black ${stats.dayOpen ? "text-[var(--emerald)]" : "text-[var(--rose)]"}`}>
              {stats.dayOpen ? "OPEN" : "CLOSED"}
            </div>
          </div>
        </div>
      </div>

      {/* Sports ticker */}
      <SportsTicker />

      <div className="flex items-center gap-3 mb-4">
        <h1 className="font-display text-2xl font-black" data-testid="page-title">Floorplan</h1>
        <div className="ml-auto flex items-center gap-2">
          {areas.map((a) => (
            <button
              key={a.id}
              data-testid={`area-tab-${a.name}`}
              onClick={() => setActiveArea(a.id)}
              className={`px-4 py-2 rounded-lg font-mono text-xs uppercase tracking-widest border ${
                activeArea === a.id
                  ? "bg-[var(--cyan)] text-black border-transparent"
                  : "bg-[var(--surface)] text-white border-[var(--border)] hover:border-[var(--cyan)]"
              }`}
            >
              {a.name}
            </button>
          ))}
          <button
            data-testid="btn-edit-mode"
            onClick={() => setEditMode((m) => !m)}
            className={`px-4 py-2 rounded-lg font-mono text-xs uppercase tracking-widest border flex items-center gap-2 ${
              editMode
                ? "bg-[var(--amber)] text-black border-transparent"
                : "bg-[var(--surface)] text-white border-[var(--border)]"
            }`}
          >
            {editMode ? <Check size={14} /> : <Edit3 size={14} />}
            {editMode ? "Done" : "Edit"}
          </button>
          {editMode && (
            <button data-testid="btn-add-table" onClick={addTable} className="btn-neon px-4 py-2 rounded-lg text-xs uppercase flex items-center gap-2">
              <Plus size={14} /> Add Table
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-5 gap-3 mb-4">
        {["available","occupied","bill_requested","dirty","reserved"].map((s) => (
          <div key={s} className={`rounded-lg border p-3 ${STATUS_COLORS[s]}`}>
            <div className="text-[10px] font-mono uppercase tracking-widest opacity-80">{STATUS_LABELS[s]}</div>
            <div className="text-3xl font-display font-black">{totals[s] || 0}</div>
          </div>
        ))}
      </div>

      <div className="flex-1 flex gap-3 min-h-0">
        <div
          className="flex-1 relative rounded-xl border border-[var(--border)] bg-[var(--surface)] grid-bg overflow-auto"
          onMouseMove={onMove}
          onMouseUp={onUp}
          onMouseLeave={onUp}
          data-testid="floorplan-canvas"
        >
          {tables.map((t) => (
            <div
              key={t.id}
              data-testid={`table-${t.name}`}
              onMouseDown={(e) => onDown(e, t)}
              onClick={() => openTable(t)}
              className={`absolute border-2 ${STATUS_COLORS[t.status]} ${
                t.shape === "circle" ? "rounded-full" : "rounded-lg"
              } select-none flex flex-col items-center justify-center p-2 transition-transform hover:scale-105 ${
                editMode ? "cursor-move" : "cursor-pointer"
              }`}
              style={{ left: t.x, top: t.y, width: t.width, height: t.height }}
            >
              <div className="font-display font-black text-lg">{t.name}</div>
              <div className="flex items-center gap-1 text-[10px] font-mono opacity-80">
                <UsersIcon size={10} /> {t.seats}
              </div>
              {t.current_order && (
                <div className="font-mono text-[11px] font-bold mt-0.5">
                  {fmtHKD(t.current_order.total)}
                </div>
              )}
              {t.reservation && t.status === "reserved" && (
                <div className="text-[9px] font-mono opacity-80 leading-tight text-center px-1">
                  <div className="truncate max-w-[80px]">{t.reservation.guest_name}</div>
                  <ResCountdown iso={t.reservation.reserved_for} />
                </div>
              )}
              {editMode && (
                <button
                  data-testid={`btn-del-${t.name}`}
                  onClick={(e) => { e.stopPropagation(); delTable(t.id); }}
                  className="absolute -top-2 -right-2 w-6 h-6 bg-[var(--rose)] text-white rounded-full flex items-center justify-center"
                >
                  <Trash2 size={12} />
                </button>
              )}
            </div>
          ))}
          {editMode && (
            <div className="absolute bottom-4 left-4 bg-black/70 px-3 py-2 rounded-lg text-xs font-mono flex items-center gap-2">
              <Move size={14} /> Drag tables to reposition
            </div>
          )}
        </div>

        {/* Right sidebar */}
        <aside className="w-72 shrink-0 flex flex-col gap-3 overflow-y-auto">
          <SidebarCard title="Active Promotions" icon={Sparkles} color="#FFB800" testid="sidebar-promos">
            {activeHH.length === 0 ? (
              <div className="text-[var(--muted)] text-xs">No live happy hours right now</div>
            ) : (
              activeHH.map(h => (
                <div key={h.id} className="text-xs">
                  <div className="flex items-center gap-1">
                    <span className="pulse-dot" style={{ background: "#FFB800", boxShadow: "0 0 8px #FFB800" }} />
                    <span className="font-semibold">{h.name}</span>
                    <span className="ml-auto font-mono text-[var(--amber)] font-bold">-{h.percent_off}%</span>
                  </div>
                  <div className="text-[10px] font-mono text-[var(--muted)] mt-0.5">
                    ends {h.end_time} · {h.category_ids?.length || 0} categor{h.category_ids?.length === 1 ? "y" : "ies"}
                  </div>
                </div>
              ))
            )}
          </SidebarCard>
          <SidebarCard title="Items to Push" icon={Trophy} color="#00F2FE" testid="sidebar-push">
            <PushList />
          </SidebarCard>
          <SidebarCard title="Announcements" icon={AlertCircle} color="#A855F7" testid="sidebar-announce">
            <div className="text-xs space-y-1.5">
              <div className="flex items-start gap-1.5"><span className="text-[var(--purple)]">·</span><span>Trivia Night tonight 21:00 — reserve BACKROOM</span></div>
              <div className="flex items-start gap-1.5"><span className="text-[var(--purple)]">·</span><span>New craft IPA on tap · promote to VIPs</span></div>
              <div className="flex items-start gap-1.5"><span className="text-[var(--purple)]">·</span><span>Darts league semifinals Saturday</span></div>
            </div>
          </SidebarCard>
        </aside>
      </div>

      {selTable && (
        <TableActionModal
          table={selTable}
          onClose={() => setSelTable(null)}
          onOpen={() => goToOrder(selTable)}
          onReserve={() => { setReserveTable(selTable); setSelTable(null); }}
          onCancel={() => cancelReservation(selTable)}
        />
      )}
      {reserveTable && (
        <ReservationModal
          table={reserveTable}
          onClose={() => setReserveTable(null)}
          onSaved={async () => {
            setReserveTable(null);
            const r = await api.get("/tables", { params: { area_id: activeArea } });
            setTables(r.data);
          }}
        />
      )}
    </div>
  );
}

function ResCountdown({ iso }) {
  const [, setTick] = useState(0);
  useEffect(() => { const t = setInterval(() => setTick(x => x + 1), 30000); return () => clearInterval(t); }, []);
  const ms = new Date(iso).getTime() - Date.now();
  const mins = Math.round(ms / 60000);
  if (mins > 0) return <div className="font-mono">in {mins > 60 ? `${Math.floor(mins / 60)}h ${mins % 60}m` : `${mins}m`}</div>;
  return <div className="font-mono text-[var(--rose)]">now · {Math.abs(mins)}m late</div>;
}

function Kpi({ label, value, icon: Icon, testid, color = "#00F2FE" }) {
  return (
    <div data-testid={testid} className="p-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] flex items-center gap-3">
      <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: `${color}18` }}>
        <Icon size={16} style={{ color }} />
      </div>
      <div>
        <div className="text-[10px] font-mono uppercase text-[var(--muted)]">{label}</div>
        <div className="font-display font-black text-lg text-white leading-tight">{value}</div>
      </div>
    </div>
  );
}

function SidebarCard({ title, icon: Icon, color, testid, children }) {
  return (
    <div data-testid={testid} className="rounded-xl border border-[var(--border)] bg-[var(--surface)] overflow-hidden">
      <div className="px-3 py-2 border-b border-[var(--border)] flex items-center gap-2">
        <Icon size={14} style={{ color }} />
        <div className="text-xs font-mono uppercase tracking-widest">{title}</div>
      </div>
      <div className="p-3 space-y-2">{children}</div>
    </div>
  );
}

function PushList() {
  const [items, setItems] = useState([]);
  useEffect(() => {
    api.get("/products").then(r => {
      const picks = r.data.filter(p => p.happy_hour_eligible).slice(0, 5);
      setItems(picks);
    });
  }, []);
  if (!items.length) return <div className="text-[var(--muted)] text-xs">Nothing flagged to push</div>;
  return items.map(p => (
    <div key={p.id} className="text-xs flex items-center gap-2">
      <Target size={10} className="text-[var(--cyan)]" />
      <span className="flex-1 truncate">{p.name}</span>
      <span className="font-mono text-[var(--amber)]">{fmtHKD(p.price)}</span>
    </div>
  ));
}

function SportsTicker() {
  const games = [
    { league: "EPL", match: "Man Utd vs Arsenal", time: "TV1 · 20:00", live: true },
    { league: "NBA", match: "Lakers vs Warriors", time: "TV2 · 22:30", live: true },
    { league: "F1", match: "Bahrain Grand Prix", time: "TV3 · Tomorrow 21:00", live: false },
    { league: "UFC", match: "Fight Night 251", time: "TV4 · Sat 09:00", live: false },
    { league: "AFL", match: "Melbourne vs Sydney", time: "TV5 · Sun 12:00", live: false },
    { league: "MLB", match: "Yankees vs Red Sox", time: "TV6 · Late", live: false },
  ];
  return (
    <div className="mb-3 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--surface)]">
      <div className="flex items-stretch">
        <div className="px-3 py-2 bg-[var(--rose)]/20 border-r border-[var(--rose)]/40 flex items-center gap-2 shrink-0">
          <span className="pulse-dot" style={{ background: "#F43F5E", boxShadow: "0 0 12px #F43F5E" }} />
          <span className="text-[10px] font-mono uppercase tracking-widest text-[var(--rose)] font-bold">Live · Sports</span>
        </div>
        <div className="flex-1 overflow-hidden relative">
          <div className="flex gap-6 py-2 px-3 whitespace-nowrap animate-[ticker_45s_linear_infinite]">
            {[...games, ...games].map((g, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                {g.live && <span className="w-1.5 h-1.5 rounded-full bg-[var(--rose)]" />}
                <span className="font-mono uppercase text-[var(--cyan)] font-bold">{g.league}</span>
                <span className="text-white">{g.match}</span>
                <span className="font-mono text-[var(--muted)]">{g.time}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
