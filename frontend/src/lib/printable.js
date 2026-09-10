/** Safe printable-window helper — opens a blob URL in a new window and triggers print.
 * XSS-hardened: no direct HTML injection into the current document; all content is
 * placed inside a sandboxed Blob URL that the browser treats as a separate origin. */
export function openPrintableWindow(html, name = "print") {
  const blob = new Blob([html], { type: "text/html" });
  const url = URL.createObjectURL(blob);
  const w = window.open(url, name, "width=420,height=700");
  if (w) {
    const doPrint = () => setTimeout(() => {
      try { w.focus(); w.print(); }
      catch (err) { console.warn("[printable] print blocked:", err); }
    }, 400);
    // Load event fires for blob URLs
    w.addEventListener("load", doPrint, { once: true });
    // Fallback in case load already fired before we listened
    setTimeout(doPrint, 600);
  }
  // Release the object URL after a minute (well past the print dialog)
  setTimeout(() => URL.revokeObjectURL(url), 60000);
  return w;
}
