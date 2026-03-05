import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_CAROP_API_URL ?? "http://localhost:38006",
  timeout: 10000
});

const LOCAL_DEMO_TOKEN =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZW1vLXVzZXIiLCJyb2xlcyI6WyJhZG1pbiIsIm9wZXJhdG9yIl19.8lZKxO7olP-q-Y4sx-2I4n2oTtHPiOkO1iWtcWKonF0";

function resolveToken(): string {
  const envToken = import.meta.env.VITE_CAROP_TOKEN ?? "";
  if (envToken) {
    return envToken;
  }

  if (typeof window !== "undefined" && window.location.hostname === "localhost") {
    return LOCAL_DEMO_TOKEN;
  }

  return "";
}

export async function fetchDashboardSummary() {
  const token = resolveToken();
  const response = await api.get("/api/v1/dashboard/summary", {
    headers: token ? { Authorization: `Bearer ${token}` } : {}
  });
  return response.data;
}

export async function fetchTpsMetrics() {
  const token = resolveToken();
  const response = await api.get("/metrics/tps", {
    headers: token ? { Authorization: `Bearer ${token}` } : {}
  });
  return response.data;
}
