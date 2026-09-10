import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import "@/App.css";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import Layout from "@/components/Layout";
import Login from "@/pages/Login";
import Floorplan from "@/pages/Floorplan";
import Register from "@/pages/Register";
import Menu from "@/pages/Menu";
import CRM from "@/pages/CRM";
import Staff from "@/pages/Staff";
import Reports from "@/pages/Reports";
import Events from "@/pages/Events";
import KDS from "@/pages/KDS";
import Shift from "@/pages/Shift";
import MobileMenu from "@/pages/MobileMenu";
import Waitlist from "@/pages/Waitlist";

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="h-screen flex items-center justify-center text-[var(--muted)] font-mono text-xs uppercase tracking-widest">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return <Layout>{children}</Layout>;
}

function GuestOnly({ children }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to="/floorplan" replace />;
  return children;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster position="top-right" theme="dark" richColors />
        <Routes>
          <Route path="/login" element={<GuestOnly><Login /></GuestOnly>} />
          <Route path="/m/:tableId" element={<MobileMenu />} />
          <Route path="/" element={<Navigate to="/floorplan" replace />} />
          <Route path="/floorplan" element={<Protected><Floorplan /></Protected>} />
          <Route path="/register" element={<Protected><Register /></Protected>} />
          <Route path="/menu" element={<Protected><Menu /></Protected>} />
          <Route path="/crm" element={<Protected><CRM /></Protected>} />
          <Route path="/staff" element={<Protected><Staff /></Protected>} />
          <Route path="/reports" element={<Protected><Reports /></Protected>} />
          <Route path="/events" element={<Protected><Events /></Protected>} />
          <Route path="/kds" element={<Protected><KDS /></Protected>} />
          <Route path="/shift" element={<Protected><Shift /></Protected>} />
          <Route path="/waitlist" element={<Protected><Waitlist /></Protected>} />
          <Route path="*" element={<Navigate to="/floorplan" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
