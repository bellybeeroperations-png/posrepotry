import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Trash2, ShieldCheck } from "lucide-react";

const ROLE_COLOR = {
  admin: "#F43F5E", manager: "#FFB800", bartender: "#00F2FE",
  server: "#10B981", cashier: "#A855F7",
};

export default function Staff() {
  const [staff, setStaff] = useState([]);
  const load = async () => setStaff((await api.get("/staff")).data);
  useEffect(() => { load(); }, []);

  const addStaff = async () => {
    const name = prompt("Name?"); if (!name) return;
    const email = prompt("Email?"); if (!email) return;
    const password = prompt("Password?"); if (!password) return;
    const role = prompt("Role (manager/bartender/server/cashier)?", "server");
    const pin = prompt("4-digit PIN?", "5555");
    try {
      await api.post("/staff", { name, email, password, role, pin });
      toast.success("Staff added"); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  const del = async (id) => {
    if (!confirm("Remove staff?")) return;
    try { await api.delete(`/staff/${id}`); load(); } catch { toast.error("Failed"); }
  };

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <h1 className="font-display text-2xl font-black">Staff & Roles</h1>
        <button data-testid="btn-add-staff" onClick={addStaff} className="ml-auto btn-neon px-4 py-2 rounded-lg text-xs uppercase flex items-center gap-2">
          <Plus size={14} /> Add Staff
        </button>
      </div>
      <div className="grid grid-cols-3 gap-3">
        {staff.map((u) => (
          <div key={u.id} className="p-5 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-full flex items-center justify-center font-black text-black text-lg"
                style={{ background: ROLE_COLOR[u.role] || "#94A3B8" }}>
                {u.name?.[0]}
              </div>
              <div className="flex-1">
                <div className="font-display font-bold">{u.name}</div>
                <div className="text-xs text-[var(--muted)]">{u.email}</div>
              </div>
              {u.role !== "admin" && (
                <button data-testid={`del-staff-${u.name}`} onClick={() => del(u.id)} className="text-[var(--rose)]">
                  <Trash2 size={14} />
                </button>
              )}
            </div>
            <div className="mt-3 flex items-center gap-2 text-[10px] font-mono uppercase">
              <span className="px-2 py-0.5 rounded" style={{ background: `${ROLE_COLOR[u.role]}22`, color: ROLE_COLOR[u.role] }}>
                <ShieldCheck size={10} className="inline mr-1" />
                {u.role}
              </span>
              <span className="text-[var(--muted)]">PIN {u.pin}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
