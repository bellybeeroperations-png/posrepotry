import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, fmtHKD } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Trash2, Move, Edit3, Check, Users as UsersIcon } from "lucide-react";

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
  const nav = useNavigate();

  const load = async () => {
    const a = (await api.get("/areas")).data;
    setAreas(a);
    if (!activeArea && a[0]) setActiveArea(a[0].id);
  };
  useEffect(() => { load(); }, []);
  useEffect(() => {
    if (!activeArea) return;
    api.get("/tables", { params: { area_id: activeArea } }).then((r) => setTables(r.data));
    const t = setInterval(() => {
      api.get("/tables", { params: { area_id: activeArea } }).then((r) => setTables(r.data));
    }, 5000);
    return () => clearInterval(t);
  }, [activeArea]);

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
    if (t.current_order_id) nav(`/register?order=${t.current_order_id}&table=${t.id}`);
    else nav(`/register?table=${t.id}&area=${activeArea}`);
  };

  return (
    <div className="h-full flex flex-col">
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
    </div>
  );
}
