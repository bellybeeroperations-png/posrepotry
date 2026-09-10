/** Extract a printable string from any Axios / FastAPI error. */
export function errMsg(e, fallback = "Request failed") {
  const d = e?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x?.msg || JSON.stringify(x)).join(", ");
  if (d && typeof d === "object") return d.msg || JSON.stringify(d);
  return e?.message || fallback;
}
