import { Clock } from "lucide-react";

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const inp = "w-full bg-[var(--surface-2)] border border-[var(--border)] rounded-md px-3 py-2 text-sm text-white focus:border-[var(--cyan)] focus:outline-none";

/**
 * Deal-of-the-Night rotator sub-form.
 * Extracted from ComboEditor.jsx during the component-split sprint.
 */
export default function ComboScheduleFields({ days, setDays, startT, setStartT, endT, setEndT }) {
  const toggleDay = (d) => setDays(days.includes(d) ? days.filter((x) => x !== d) : [...days, d].sort());

  return (
    <div data-testid="combo-schedule" className="mb-4 p-3 rounded-lg border border-[var(--amber)]/30 bg-[var(--amber)]/5">
      <div className="text-[10px] font-mono uppercase text-[var(--amber)] mb-2 flex items-center gap-1">
        <Clock size={10} /> Deal-of-the-Night · window (HK time)
      </div>
      <div className="flex flex-wrap gap-1 mb-2">
        {DAY_NAMES.map((d, i) => (
          <button key={d} data-testid={`combo-day-${d}`} onClick={() => toggleDay(i)}
            className={`px-2 py-1 rounded text-[10px] font-mono uppercase border ${
              days.includes(i) ? "bg-[var(--amber)]/25 border-[var(--amber)] text-[var(--amber)]"
                               : "bg-[var(--surface-2)] border-[var(--border)] text-[var(--muted)]"
            }`}>{d}</button>
        ))}
        <span className="text-[10px] font-mono text-[var(--muted)] ml-2 self-center">
          {days.length === 0 ? "(any day)" : `${days.length} day(s)`}
        </span>
      </div>
      <div className="flex gap-2">
        <div className="flex-1">
          <div className="text-[10px] font-mono uppercase text-[var(--muted)] mb-1">Start</div>
          <input data-testid="combo-start" type="time" value={startT} onChange={(e) => setStartT(e.target.value)} className={inp} />
        </div>
        <div className="flex-1">
          <div className="text-[10px] font-mono uppercase text-[var(--muted)] mb-1">End</div>
          <input data-testid="combo-end" type="time" value={endT} onChange={(e) => setEndT(e.target.value)} className={inp} />
        </div>
      </div>
      <div className="text-[10px] font-mono text-[var(--muted)] mt-2">
        Cross-midnight windows supported (e.g. 22:00 → 03:00)
      </div>
    </div>
  );
}
