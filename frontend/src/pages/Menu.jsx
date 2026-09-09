import { useEffect, useState } from "react";
import { api, fmtHKD } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Trash2, Clock } from "lucide-react";

export default function Menu() {
  const [cats, setCats] = useState([]);
  const [prods, setProds] = useState([]);
  const [hh, setHh] = useState([]);
  const [tab, setTab] = useState("products");

  const load = async () => {
    const [c, p, h] = await Promise.all([
      api.get("/categories"),
      api.get("/products"),
      api.get("/happy-hours"),
    ]);
    setCats(c.data); setProds(p.data); setHh(h.data);
  };
  useEffect(() => { load(); }, []);

  const addCat = async () => {
    const name = prompt("Category name?");
    if (!name) return;
    const kind = prompt("Kind (food/drink)?", "food");
    await api.post("/categories", { name, color: "#00F2FE" });
    load();
  };
  const delCat = async (id) => {
    if (!confirm("Delete category?")) return;
    await api.delete(`/categories/${id}`); load();
  };
  const addProd = async () => {
    if (!cats.length) return toast.error("Add a category first");
    const name = prompt("Product name?");
    if (!name) return;
    const price = parseFloat(prompt("Price (HKD)?", "100") || "0");
    const category_id = cats[0].id;
    await api.post("/products", {
      name, category_id, price, kind: "drink", course: "drink",
      variants: [], modifiers: [], happy_hour_eligible: false,
    });
    load();
  };
  const delProd = async (id) => {
    if (!confirm("Delete product?")) return;
    await api.delete(`/products/${id}`); load();
  };

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <h1 className="font-display text-2xl font-black">Menu Manager</h1>
        <div className="ml-auto flex gap-2">
          {["products", "categories", "happy_hour"].map((t) => (
            <button
              key={t}
              data-testid={`menu-tab-${t}`}
              onClick={() => setTab(t)}
              className={`px-4 py-2 rounded-lg font-mono text-xs uppercase tracking-widest border ${
                tab === t ? "bg-[var(--cyan)] text-black border-transparent" : "bg-[var(--surface)] text-white border-[var(--border)]"
              }`}
            >
              {t.replace("_", " ")}
            </button>
          ))}
        </div>
      </div>

      {tab === "products" && (
        <div>
          <button data-testid="btn-add-product" onClick={addProd} className="btn-neon px-4 py-2 rounded-lg text-xs uppercase flex items-center gap-2 mb-4">
            <Plus size={14} /> Add Product
          </button>
          <div className="grid grid-cols-4 gap-3">
            {prods.map((p) => {
              const cat = cats.find((c) => c.id === p.category_id);
              return (
                <div key={p.id} className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="font-display font-bold">{p.name}</div>
                      <div className="text-[10px] font-mono uppercase text-[var(--muted)]">{cat?.name} · {p.course}</div>
                    </div>
                    <button data-testid={`del-prod-${p.name}`} onClick={() => delProd(p.id)} className="text-[var(--rose)]">
                      <Trash2 size={14} />
                    </button>
                  </div>
                  <div className="mt-2 font-mono font-bold text-[var(--amber)]">{fmtHKD(p.price)}</div>
                  <div className="mt-2 text-[10px] font-mono text-[var(--muted)]">
                    {p.variants?.length || 0} variants · {p.modifiers?.length || 0} mods
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {tab === "categories" && (
        <div>
          <button data-testid="btn-add-category" onClick={addCat} className="btn-neon px-4 py-2 rounded-lg text-xs uppercase flex items-center gap-2 mb-4">
            <Plus size={14} /> Add Category
          </button>
          <div className="grid grid-cols-4 gap-3">
            {cats.map((c) => (
              <div key={c.id} className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{ background: c.color }} />
                  <div className="font-display font-bold">{c.name}</div>
                  <button data-testid={`del-cat-${c.name}`} onClick={() => delCat(c.id)} className="ml-auto text-[var(--rose)]">
                    <Trash2 size={14} />
                  </button>
                </div>
                <div className="text-[10px] font-mono uppercase text-[var(--muted)] mt-1">{c.kind}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === "happy_hour" && (
        <div>
          <div className="grid grid-cols-2 gap-3">
            {hh.map((h) => (
              <div key={h.id} className="p-5 rounded-xl border border-[var(--amber)]/40 bg-[var(--amber)]/5">
                <div className="flex items-center gap-2 mb-2">
                  <Clock size={16} className="text-[var(--amber)]" />
                  <div className="font-display font-black text-lg">{h.name}</div>
                </div>
                <div className="font-mono text-sm text-[var(--muted)]">
                  {h.start_time} — {h.end_time}
                </div>
                <div className="mt-2 text-3xl font-display font-black text-[var(--amber)]">-{h.percent_off}%</div>
                <div className="text-[10px] font-mono uppercase text-[var(--muted)] mt-1">
                  {h.category_ids.length} categor{h.category_ids.length === 1 ? "y" : "ies"} · {h.days.length}/7 days
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
