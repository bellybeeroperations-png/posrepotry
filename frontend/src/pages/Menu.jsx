import { useEffect, useState } from "react";
import { api, fmtHKD } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Trash2, Clock, Edit3, Sparkles, Package, Ban } from "lucide-react";
import { ProductEditor, CategoryEditor, HappyHourEditor } from "@/components/pos/editors";
import { ComboEditor } from "@/components/pos/ComboEditor";
import { errMsg } from "@/lib/errors";

const DAY_NAMES = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];

export default function Menu() {
  const [cats, setCats] = useState([]);
  const [prods, setProds] = useState([]);
  const [hh, setHh] = useState([]);
  const [combos, setCombos] = useState([]);
  const [tab, setTab] = useState("products");
  const [filterCat, setFilterCat] = useState("all");
  const [editingProd, setEditingProd] = useState(null);
  const [editingCat, setEditingCat] = useState(null);
  const [editingHh, setEditingHh] = useState(null);
  const [editingCombo, setEditingCombo] = useState(null);

  const load = async () => {
    const [c, p, h, cb] = await Promise.all([
      api.get("/categories"), api.get("/products"), api.get("/happy-hours"), api.get("/combos"),
    ]);
    setCats(c.data); setProds(p.data); setHh(h.data); setCombos(cb.data);
  };
  useEffect(() => { load(); }, []);

  const saveProd = async (data) => {
    try {
      if (editingProd?.id) await api.patch(`/products/${editingProd.id}`, data);
      else await api.post("/products", data);
      toast.success("Product saved"); setEditingProd(null); load();
    } catch (e) { toast.error(errMsg(e, "Failed")); }
  };
  const saveCat = async (data) => {
    try {
      if (editingCat?.id) await api.patch(`/categories/${editingCat.id}`, data);
      else await api.post("/categories", data);
      toast.success("Category saved"); setEditingCat(null); load();
    } catch (e) { toast.error(errMsg(e, "Failed")); }
  };
  const saveHh = async (data) => {
    try {
      if (editingHh?.id) await api.patch(`/happy-hours/${editingHh.id}`, data);
      else await api.post("/happy-hours", data);
      toast.success("Happy hour saved"); setEditingHh(null); load();
    } catch (e) { toast.error(errMsg(e, "Failed")); }
  };
  const saveCombo = async (data) => {
    try {
      if (editingCombo?.id) await api.patch(`/combos/${editingCombo.id}`, data);
      else await api.post("/combos", data);
      toast.success("Combo saved"); setEditingCombo(null); load();
    } catch (e) { toast.error(errMsg(e, "Failed")); }
  };
  const del = async (path, name, cb) => {
    if (!confirm(`Delete ${name}?`)) return;
    await api.delete(path); toast.success("Deleted"); cb();
  };

  const shownProds = filterCat === "all" ? prods : prods.filter(p => p.category_id === filterCat);

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <h1 className="font-display text-2xl font-black">Menu Manager</h1>
        <div className="ml-auto flex gap-2">
          {["products","categories","happy_hour","combos"].map(t => (
            <button key={t} data-testid={`menu-tab-${t}`} onClick={() => setTab(t)}
              className={`px-4 py-2 rounded-lg font-mono text-xs uppercase tracking-widest border ${
                tab === t ? "bg-[var(--cyan)] text-black border-transparent" : "bg-[var(--surface)] text-white border-[var(--border)]"
              }`}>
              {t.replace("_"," ")}
            </button>
          ))}
        </div>
      </div>

      {tab === "products" && (
        <div>
          <div className="flex items-center gap-2 mb-4 flex-wrap">
            <button data-testid="btn-add-product" onClick={() => setEditingProd({})}
              className="btn-neon px-4 py-2 rounded-lg text-xs uppercase flex items-center gap-2">
              <Plus size={14} /> New Product
            </button>
            <div className="flex flex-wrap gap-1 ml-2">
              <button onClick={() => setFilterCat("all")}
                className={`px-3 py-1 rounded-md text-xs font-mono uppercase border ${filterCat === "all" ? "bg-[var(--cyan)] text-black border-transparent" : "bg-[var(--surface)] text-[var(--muted)] border-[var(--border)]"}`}>All</button>
              {cats.map(c => (
                <button key={c.id} onClick={() => setFilterCat(c.id)}
                  className={`px-3 py-1 rounded-md text-xs font-mono uppercase border ${filterCat === c.id ? "text-black border-transparent" : "bg-[var(--surface)] text-[var(--muted)] border-[var(--border)]"}`}
                  style={filterCat === c.id ? { background: c.color } : {}}>
                  {c.name}
                </button>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-4 gap-3">
            {shownProds.map(p => {
              const cat = cats.find(c => c.id === p.category_id);
              return (
                <div key={p.id} className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] hover:border-[var(--cyan)] transition group">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="font-display font-bold">{p.name}</div>
                      <div className="text-[10px] font-mono uppercase text-[var(--muted)]">
                        {cat?.name} · {p.course}
                      </div>
                    </div>
                    <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition">
                      <button data-testid={`toggle-86-${p.name}`}
                        onClick={async () => {
                          try {
                            await api.post(`/products/${p.id}/eightysix`, null, { params: { on: !p.eightysix } });
                            toast.success(p.eightysix ? "Back in stock" : "86'd — hidden from menu");
                            load();
                          } catch { toast.error("Failed"); }
                        }}
                        className={p.eightysix ? "text-[var(--emerald)]" : "text-[var(--amber)]"}
                        title={p.eightysix ? "Bring back" : "86 this item"}
                      >
                        <Ban size={14} />
                      </button>
                      <button data-testid={`edit-prod-${p.name}`} onClick={() => setEditingProd(p)} className="text-[var(--cyan)]"><Edit3 size={14} /></button>
                      <button data-testid={`del-prod-${p.name}`} onClick={() => del(`/products/${p.id}`, p.name, load)} className="text-[var(--rose)]"><Trash2 size={14} /></button>
                    </div>
                  </div>
                  <div className="mt-2 font-mono font-bold text-[var(--amber)]">{fmtHKD(p.price)}</div>
                  <div className="mt-2 flex items-center gap-2 text-[10px] font-mono text-[var(--muted)]">
                    <span>{p.variants?.length || 0}v</span>
                    <span>·</span>
                    <span>{p.modifiers?.length || 0}m</span>
                    {p.happy_hour_eligible && (
                      <span className="ml-auto flex items-center gap-1 text-[var(--amber)]"><Sparkles size={10} /> HH</span>
                    )}
                    {p.eightysix && (
                      <span data-testid={`badge-86-${p.name}`} className="ml-auto flex items-center gap-1 px-1.5 py-0.5 rounded bg-[var(--rose)] text-white font-black">
                        <Ban size={10} /> 86
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {tab === "categories" && (
        <div>
          <button data-testid="btn-add-category" onClick={() => setEditingCat({})}
            className="btn-neon px-4 py-2 rounded-lg text-xs uppercase flex items-center gap-2 mb-4">
            <Plus size={14} /> New Category
          </button>
          <div className="grid grid-cols-4 gap-3">
            {cats.map(c => (
              <div key={c.id} className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] group hover:border-[var(--cyan)]">
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded" style={{ background: c.color }} />
                  <div className="font-display font-bold">{c.name}</div>
                  <div className="ml-auto flex gap-1 opacity-0 group-hover:opacity-100 transition">
                    <button data-testid={`edit-cat-${c.name}`} onClick={() => setEditingCat(c)} className="text-[var(--cyan)]"><Edit3 size={14} /></button>
                    <button data-testid={`del-cat-${c.name}`} onClick={() => del(`/categories/${c.id}`, c.name, load)} className="text-[var(--rose)]"><Trash2 size={14} /></button>
                  </div>
                </div>
                <div className="text-[10px] font-mono uppercase text-[var(--muted)] mt-1">
                  {c.kind} · {prods.filter(p => p.category_id === c.id).length} products
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === "happy_hour" && (
        <div>
          <button data-testid="btn-add-hh" onClick={() => setEditingHh({})}
            className="btn-amber px-4 py-2 rounded-lg text-xs uppercase flex items-center gap-2 mb-4">
            <Plus size={14} /> New Happy Hour
          </button>
          <div className="grid grid-cols-2 gap-3">
            {hh.map(h => (
              <div key={h.id} className="p-5 rounded-xl border border-[var(--amber)]/40 bg-[var(--amber)]/5 group">
                <div className="flex items-center gap-2 mb-2">
                  <Clock size={16} className="text-[var(--amber)]" />
                  <div className="font-display font-black text-lg">{h.name}</div>
                  <div className="ml-auto flex gap-1 opacity-0 group-hover:opacity-100 transition">
                    <button data-testid={`edit-hh-${h.name}`} onClick={() => setEditingHh(h)} className="text-[var(--cyan)]"><Edit3 size={14} /></button>
                    <button data-testid={`del-hh-${h.name}`} onClick={() => del(`/happy-hours/${h.id}`, h.name, load)} className="text-[var(--rose)]"><Trash2 size={14} /></button>
                  </div>
                </div>
                <div className="font-mono text-sm text-[var(--muted)]">{h.start_time} — {h.end_time}</div>
                <div className="mt-2 text-3xl font-display font-black text-[var(--amber)]">-{h.percent_off}%</div>
                <div className="text-[10px] font-mono uppercase text-[var(--muted)] mt-1 flex gap-1 flex-wrap">
                  {DAY_NAMES.map((d, i) => (
                    <span key={d} className={`px-1.5 py-0.5 rounded ${h.days.includes(i) ? "bg-[var(--amber)]/20 text-[var(--amber)]" : "opacity-40"}`}>{d}</span>
                  ))}
                </div>
                <div className="text-[10px] font-mono text-[var(--muted)] mt-2">
                  {h.category_ids.length} categor{h.category_ids.length === 1 ? "y" : "ies"} eligible
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === "combos" && (
        <div>
          <button data-testid="btn-add-combo" onClick={() => setEditingCombo({})}
            className="btn-neon px-4 py-2 rounded-lg text-xs uppercase flex items-center gap-2 mb-4">
            <Plus size={14} /> New Combo Deal
          </button>
          {combos.length === 0 && (
            <div className="p-10 rounded-xl border border-dashed border-[var(--border)] text-center text-[var(--muted)]">
              No combo deals yet. Bundle 2+ products with an automatic discount when they're on the same ticket.
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            {combos.map(c => {
              const names = prods.filter(p => c.product_ids.includes(p.id)).map(p => p.name);
              return (
                <div key={c.id} className="p-5 rounded-xl border border-[var(--cyan)]/40 bg-[var(--cyan)]/5 group">
                  <div className="flex items-center gap-2 mb-2">
                    <Package size={16} className="text-[var(--cyan)]" />
                    <div className="font-display font-black text-lg">{c.name}</div>
                    <div className={`ml-auto text-[9px] font-mono uppercase px-2 py-0.5 rounded ${c.active ? "bg-[var(--emerald)]/20 text-[var(--emerald)]" : "bg-[var(--surface-2)] text-[var(--muted)]"}`}>
                      {c.active ? "Active" : "Paused"}
                    </div>
                    <button data-testid={`edit-combo-${c.name}`} onClick={() => setEditingCombo(c)} className="text-[var(--cyan)] opacity-0 group-hover:opacity-100"><Edit3 size={14} /></button>
                    <button data-testid={`del-combo-${c.name}`} onClick={() => del(`/combos/${c.id}`, c.name, load)} className="text-[var(--rose)] opacity-0 group-hover:opacity-100"><Trash2 size={14} /></button>
                  </div>
                  <div className="text-3xl font-display font-black text-[var(--cyan)]">
                    {c.discount_type === "percent" ? `-${c.discount_value}%` : `-${fmtHKD(c.discount_value)}`}
                  </div>
                  <div className="text-[10px] font-mono uppercase text-[var(--muted)] mt-1">When ticket contains:</div>
                  <div className="text-xs flex flex-wrap gap-1 mt-1">
                    {names.map((n) => <span key={n} className="px-1.5 py-0.5 rounded bg-[var(--surface-2)] border border-[var(--border)]">{n}</span>)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {editingProd && (
        <ProductEditor
          product={editingProd?.id ? editingProd : null}
          categories={cats}
          onClose={() => setEditingProd(null)}
          onSave={saveProd}
        />
      )}
      {editingCat && (
        <CategoryEditor category={editingCat?.id ? editingCat : null} onClose={() => setEditingCat(null)} onSave={saveCat} />
      )}
      {editingHh && (
        <HappyHourEditor hh={editingHh?.id ? editingHh : null} categories={cats} onClose={() => setEditingHh(null)} onSave={saveHh} />
      )}
      {editingCombo && (
        <ComboEditor combo={editingCombo?.id ? editingCombo : null} products={prods} onClose={() => setEditingCombo(null)} onSave={saveCombo} />
      )}
    </div>
  );
}
