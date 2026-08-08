/**
 * api/client.js
 * Axios wrapper for all backend API calls.
 * Base URL proxied via next.config.js rewrites → FastAPI on Railway.
 */
import axios from "axios";

const client = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
  timeout: 30000,
});

// ── /api/data/* ────────────────────────────────────────────
export const dataAPI = {
  /** GET /api/data/summary — dashboard KPIs, Redis cached */
  getSummary: () => client.get("/data/summary"),

  /** GET /api/data/migration-trends */
  getMigrationTrends: () => client.get("/data/migration-trends"),

  /** GET /api/data/visa-analytics */
  getVisaAnalytics: () => client.get("/data/visa-analytics"),

  /** GET /api/data/shortage-heatmap */
  getShortageHeatmap: (year) => client.get("/data/shortage-heatmap", { params: { year } }),

  /** GET /api/data/employment-projections */
  getEmploymentProjections: () => client.get("/data/employment-projections"),

  /** GET /api/data/eoi */
  getEOI: () => client.get("/data/eoi"),

  /** GET /api/data/report?type=X&from=Y&to=Z */
  getReport: (type, from, to) => client.get("/data/report", { params: { type, from, to } }),

  /** GET /api/data/admin/* — JWT protected */
  getAdmin: (path) => client.get(`/data/admin/${path}`),
};

// ── /api/predict/* ─────────────────────────────────────────
export const predictAPI = {
  /**
   * POST /api/predict/{model_name}
   * Returns: { prediction, confidence, shap_values }
   * model_name: "pathway" | "shortage" | "volume" | "approval"
   */
  run: (modelName, features) => client.post(`/predict/${modelName}`, features),
};

// ── /api/llm/* ─────────────────────────────────────────────
export const llmAPI = {
  /**
   * POST /api/llm/chat — returns SSE stream
   * Use useSSE hook instead of this for streaming
   */
  chatUrl: "/api/llm/chat",
};

export default client;
