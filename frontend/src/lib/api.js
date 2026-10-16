import axios from "axios";
import { clearWorkContext, workContextToken } from "./workContext";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL?.trim();

if (!BACKEND_URL) {
  throw new Error(
    "REACT_APP_BACKEND_URL is required. Set it to the backend origin without trailing /api."
  );
}

const NORMALIZED_BACKEND_URL = BACKEND_URL.replace(/\/+$/, "");

if (NORMALIZED_BACKEND_URL.endsWith("/api")) {
  throw new Error(
    "REACT_APP_BACKEND_URL must be the backend origin without trailing /api."
  );
}

export const API = `${NORMALIZED_BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API,
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("caos_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  const workToken = workContextToken();
  if (workToken) config.headers["X-CAOS-Work-Context"] = workToken;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    const workCode = err?.response?.data?.detail?.code;
    if (workCode === "unknown_department" || workCode === "expired_context" || workCode === "invalid_token") {
      clearWorkContext();
    }
    if (err?.response?.status === 401) {
      // stay silent; caller can redirect
      if (err?.config?.headers?.["X-CAOS-Work-Context"]) clearWorkContext();
    }
    return Promise.reject(err);
  }
);
