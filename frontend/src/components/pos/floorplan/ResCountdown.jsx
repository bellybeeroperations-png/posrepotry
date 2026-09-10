import { useEffect, useState } from "react";

/** Tiny live countdown badge for a reservation's `reserved_for` ISO stamp. */
export default function ResCountdown({ iso }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 30000);
    return () => clearInterval(t);
  }, []);
  const target = new Date(iso).getTime();
  const diff = target - now;
  if (Number.isNaN(target)) return null;
  const mins = Math.round(diff / 60000);
  if (Math.abs(mins) < 60) return <span>{mins > 0 ? `in ${mins}m` : `${-mins}m late`}</span>;
  const hrs = Math.round(mins / 60);
  return <span>in {hrs}h</span>;
}
