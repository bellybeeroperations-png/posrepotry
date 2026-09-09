import { Trophy, Tv, Target } from "lucide-react";

export default function Events() {
  return (
    <div>
      <h1 className="font-display text-2xl font-black mb-4">Events · Sports · Darts</h1>
      <div className="grid grid-cols-3 gap-4">
        <Card icon={Tv} title="Live Sports" color="#00F2FE">
          <Row label="Man Utd vs Arsenal" sub="TV1 · 20:00" tag="LIVE" />
          <Row label="Lakers vs Warriors" sub="TV2 · 22:30" tag="LIVE" />
          <Row label="F1 Bahrain GP" sub="TV3 · Tomorrow 21:00" tag="UPCOMING" />
        </Card>
        <Card icon={Target} title="Darts Queue" color="#FFB800">
          <Row label="Board A — Team Neon" sub="501 · Match 3/5" tag="PLAYING" />
          <Row label="Board B — Free" sub="No queue" tag="IDLE" />
          <Row label="Waiting: Priya's Crew" sub="ETA 15m" tag="QUEUED" />
        </Card>
        <Card icon={Trophy} title="Trivia Night" color="#A855F7">
          <Row label="Thursday Trivia" sub="8 teams · 32 players" tag="TONIGHT" />
          <Row label="Sunday Music Quiz" sub="Registration open" tag="OPEN" />
          <Row label="Karaoke Battle Royale" sub="Next Sat" tag="SCHEDULED" />
        </Card>
      </div>
      <div className="mt-6 p-4 rounded-xl border border-dashed border-[var(--border)] text-sm text-[var(--muted)]">
        Full event, darts scoring, and trivia registration modules coming in the next build — this is the live overview board for now.
      </div>
    </div>
  );
}

const Card = ({ icon: Icon, title, color, children }) => (
  <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] overflow-hidden">
    <div className="px-4 py-3 border-b border-[var(--border)] flex items-center gap-2">
      <Icon size={16} style={{ color }} />
      <div className="font-display font-black text-lg">{title}</div>
    </div>
    <div className="divide-y divide-[var(--border)]">{children}</div>
  </div>
);
const Row = ({ label, sub, tag }) => (
  <div className="px-4 py-3 flex items-center gap-3">
    <div className="flex-1">
      <div className="font-semibold text-sm">{label}</div>
      <div className="text-xs text-[var(--muted)]">{sub}</div>
    </div>
    <span className="text-[10px] font-mono uppercase px-2 py-1 rounded bg-[var(--surface-2)] border border-[var(--border)]">
      {tag}
    </span>
  </div>
);
