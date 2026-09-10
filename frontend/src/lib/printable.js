/** Safe printable-window helper — replaces document.write (XSS-hardened). */
export function openPrintableWindow(html, name = "print") {
  const blob = new Blob([html], { type: "text/html" });
  const url = URL.createObjectURL(blob);
  const w = window.open(url, name, "width=420,height=700");
  if (w) {
    const doPrint = () => setTimeout(() => { try { w.focus(); w.print(); } catch {} }, 400);
    // Load fires for blob URLs
    w.addEventListener("load", doPrint, { once: true });
    // Fallback in case load already fired
    setTimeout(doPrint, 600);
  }
  // Release the object URL after a minute (well past the print dialog)
  setTimeout(() => URL.revokeObjectURL(url), 60000);
  return w;
}
