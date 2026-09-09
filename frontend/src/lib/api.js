import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API,
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

// Attach bearer token as fallback (cookies work but bearer helps in some hosted previews)
api.interceptors.request.use((config) => {
  const t = localStorage.getItem("hkbar_token");
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});

export const fmtHKD = (v) =>
  new Intl.NumberFormat("en-HK", {
    style: "currency",
    currency: "HKD",
    minimumFractionDigits: 0,
  }).format(v || 0);
