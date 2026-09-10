import { Users as UsersIcon, Trash2, TrendingUp } from "lucide-react";
import { fmtHKD } from "@/lib/api";
import ResCountdown from "./ResCountdown";

const STATUS_COLORS = {
  available: "border-[var(--emerald)]/60 bg-[var(--emerald)]/5 text-[var(--emerald)]",
  occupied:  "border-[var(--rose)]/60    bg-[var(--rose)]/10    text-[var(--rose)]",
  reserved:  "border-[var(--purple)]/60  bg-[var(--purple)]/10  text-[var(--purple)]",
  dirty:     "border-[var(--amber)]/60   bg-[var(--amber)]/10   text-[var(--amber)]",
  out_of_service: "border-[var(--muted)]/60 bg-[var(--surface)] text-[var(--muted)]",
};

/**
 * Draggable + clickable table card with combo heat-map glow.
 * Extracted from Floorplan.jsx during the component-split sprint.
 */
export default function TableCard({ table: t, hint, editMode, onDown, openTable, delTable }) {
  return (
    <div
      key={t.id}
      data-testid={`table-${t.name}`}
      onMouseDown={(e) => onDown(e, t)}
      onClick={() => openTable(t)}
      className={`absolute border-2 ${STATUS_COLORS[t.status]} ${
        t.shape === "circle" ? "rounded-full" : "rounded-lg"
      } select-none flex flex-col items-center justify-center p-2 transition-transform hover:scale-105 ${
        editMode ? "cursor-move" : "cursor-pointer"
      } ${hint ? "ring-2 ring-[var(--cyan)] ring-offset-2 ring-offset-[var(--surface)]" : ""}`}
      style={{
        left: t.x, top: t.y, width: t.width, height: t.height,
        boxShadow: hint ? "0 0 24px rgba(0,242,254,0.55)" : undefined,
      }}
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
      {hint && (
        <div data-testid={`combo-hint-${t.name}`}
          className="absolute -top-2 left-1/2 -translate-x-1/2 whitespace-nowrap px-1.5 py-0.5 rounded-full bg-[var(--cyan)] text-black text-[9px] font-mono font-black flex items-center gap-0.5 shadow-lg">
          <TrendingUp size={9} /> +1 {hint.product_name?.split(" ")[0]} → -{hint.discount_type === "percent" ? `${hint.discount_value}%` : fmtHKD(hint.discount)}
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
  );
}
