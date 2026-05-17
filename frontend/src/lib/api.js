import axios from "axios";

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
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401) {
      // stay silent; caller can redirect
    }
    return Promise.reject(err);
  }
);
