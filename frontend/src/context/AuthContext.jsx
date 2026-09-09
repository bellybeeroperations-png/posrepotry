import { createContext, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const t = localStorage.getItem("hkbar_token");
        if (!t) return setLoading(false);
        const { data } = await api.get("/auth/me");
        setUser(data);
      } catch {
        localStorage.removeItem("hkbar_token");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    localStorage.setItem("hkbar_token", data.token);
    setUser(data.user);
    return data.user;
  };

  const pinLogin = async (pin) => {
    const { data } = await api.post("/auth/pin-login", { pin });
    localStorage.setItem("hkbar_token", data.token);
    setUser(data.user);
    return data.user;
  };

  const logout = async () => {
    try {
      await api.post("/auth/logout");
    } catch {}
    localStorage.removeItem("hkbar_token");
    setUser(null);
  };

  return (
    <AuthCtx.Provider value={{ user, loading, login, pinLogin, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
