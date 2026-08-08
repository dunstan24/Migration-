"use client";
/**
 * Shortage Analysis Page — fully redesigned
 * Route: /dashboard/shortage
 * All data REAL — OSL 2021–2025 + ML forecast 2026–2030
 */
import { useState, useEffect, useMemo, useRef } from "react";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  Legend,
  ReferenceLine,
} from "recharts";
import { useDataCache } from "@/lib/DataCacheContext";
import { C, Card, ChartTip, PageWrapper, Pagination } from "@/components/ui";
import { Autocomplete, AutocompleteSuggestion } from "@/components/shared";

const API =
  typeof window !== "undefined"
    ? ""
    : process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const pct = (n: number) => `${(n * 100).toFixed(0)}%`;
const fmt = (n: number) => n?.toLocaleString() ?? "—";

const STATES = ["NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT", "ACT"];
const YEARS = ["2026", "2027", "2028", "2029", "2030"];
const SKILL_COLORS = ["#2a8bff", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];
const STATE_COLORS: Record<string, string> = {
  NSW: "#2a8bff",
  VIC: "#8b5cf6",
  QLD: "#f59e0b",
  SA: "#ef4444",
  WA: "#10b981",
  TAS: "#06b6d4",
  NT: "#f97316",
  ACT: "#ec4899",
};

function probColor(p: number) {
  return p >= 0.65 ? "#ef4444" : p >= 0.4 ? "#f59e0b" : "#10b981";
}

// ── Shared UI ────────────────────────────────────────────────────

function KpiCard({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string | number;
  sub?: string;
  color: string;
}) {
  return (
    <div
      style={{
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: 10,
        padding: "16px 20px",
        borderTop: `3px solid ${color}`,
      }}
    >
      <p
        style={{
          fontSize: 10,
          color: C.muted,
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          fontWeight: 700,
          marginBottom: 6,
        }}
      >
        {label}
      </p>
      <p style={{ fontSize: 26, fontWeight: 800, color, lineHeight: 1 }}>
        {value}
      </p>
      {sub && (
        <p style={{ fontSize: 10, color: C.muted, marginTop: 4 }}>{sub}</p>
      )}
    </div>
  );
}

function Pill({
  label,
  active,
  color,
  onClick,
}: {
  label: string;
  active: boolean;
  color: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: "5px 13px",
        borderRadius: 20,
        fontSize: 11,
        cursor: "pointer",
        fontWeight: active ? 700 : 400,
        border: `1px solid ${active ? color : C.border}`,
        background: active ? `${color}20` : "transparent",
        color: active ? color : C.muted,
      }}
    >
      {label}
    </button>
  );
}

function SectionTitle({ title, sub }: { title: string; sub?: string }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <p
        style={{
          fontSize: 13,
          fontWeight: 700,
          color: C.text,
          marginBottom: 2,
        }}
      >
        {title}
      </p>
      {sub && <p style={{ fontSize: 10, color: C.muted }}>{sub}</p>}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
// TAB A — ML FORECAST 2026–2030
// ══════════════════════════════════════════════════════════════════

function ForecastTab({ isMobile }: any) {
  const { get } = useDataCache();
  const [state, setState] = useState("NSW");
  const [sortYr, setSortYr] = useState("2026");
  const [searchInputValue, setSearchInputValue] = useState("");
  const [data, setData] = useState<any>(null);
  const [searchData, setSearchData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<AutocompleteSuggestion[]>([]);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [selectedSearch, setSelectedSearch] =
    useState<AutocompleteSuggestion | null>(null);
  const debounceTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const [page, setPage] = useState(1);
  const limit = 20;

  useEffect(() => {
    setPage(1);
  }, [state, sortYr, selectedSearch]);

  // Fetch by state (default view)
  useEffect(() => {
    setLoading(true);
    setError("");
    get(
      `/api/data/shortage-forecast?state=${state}&limit=200&sort_year=${sortYr}`,
    )
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch((e) => {
        setError(e.message);
        setLoading(false);
      });
  }, [state, sortYr, get]);

  // Cleanup debounce timeout on unmount
  useEffect(() => {
    return () => {
      if (debounceTimeoutRef.current) {
        clearTimeout(debounceTimeoutRef.current);
      }
    };
  }, []);

  // Handle search input changes - fetch suggestions from API as user types
  const handleSearchInput = (value: string) => {
    setSearchInputValue(value);
    setIsDropdownOpen(true);

    if (!value.trim()) {
      setSuggestions([]);
      setSelectedSearch(null);
      return;
    }

    // Clear existing debounce timeout
    if (debounceTimeoutRef.current) {
      clearTimeout(debounceTimeoutRef.current);
    }

    // Set new debounce timeout (300ms)
    debounceTimeoutRef.current = setTimeout(() => {
      setSuggestionsLoading(true);
      get(
        `/api/data/shortage-forecast?limit=500&search=${encodeURIComponent(value)}`,
      )
        .then((d) => {
          // Extract unique occupations from results
          const uniqueMap = new Map<string, AutocompleteSuggestion>();
          (d.records || []).forEach((r: any) => {
            if (!uniqueMap.has(r.anzsco_code)) {
              uniqueMap.set(r.anzsco_code, {
                anzsco_code: r.anzsco_code,
                occupation: r.occupation,
              });
            }
          });
          const uniqueSuggestions = Array.from(uniqueMap.values()).slice(0, 10);
          setSuggestions(uniqueSuggestions);
          setSuggestionsLoading(false);
        })
        .catch(() => {
          setSuggestions([]);
          setSuggestionsLoading(false);
        });
    }, 300);
  };

  // Handle selection from autocomplete
  const handleSelectSuggestion = (suggestion: AutocompleteSuggestion) => {
    setSearchInputValue("");
    setSelectedSearch(suggestion);
    setSuggestions([]);

    // Fetch search results for the selected occupation
    setSearching(true);
    get(
      `/api/data/shortage-forecast?limit=500&sort_year=${sortYr}&search=${encodeURIComponent(suggestion.occupation)}`,
    )
      .then((d) => {
        setSearchData(d);
        setSearching(false);
      })
      .catch(() => setSearching(false));
  };

  // Which records to show
  const records: any[] = useMemo(() => {
    if (selectedSearch && searchData) return searchData.records || [];
    return data?.records || [];
  }, [data, searchData, selectedSearch]);

  const isSearchMode = !!selectedSearch;

  const totalPages = Math.ceil(records.length / limit);
  const paginatedRecords = records.slice((page - 1) * limit, page * limit);

  const trendData = YEARS.map((y) => ({
    year: y,
    avg: records.length
      ? +(
          records.reduce((s: number, r: any) => s + (r[`prob_${y}`] ?? 0), 0) /
          records.length
        ).toFixed(3)
      : 0,
    high: records.filter((r: any) => (r[`prob_${y}`] ?? 0) >= 0.65).length,
  }));

  const top10 = records.slice(0, 10);

  if (error)
    return (
      <Card>
        <p style={{ color: "#ef4444", fontSize: 12 }}>
          Could not load forecast. Run:{" "}
          <code style={{ fontFamily: "monospace" }}>
            python pipelines/ingestors/shortage_forecast_ingestor.py
          </code>
        </p>
      </Card>
    );

  return (
    <>
      {/* ── Controls ─────────────────────────────────────────── */}
      <div
        style={{
          background: "rgba(255,255,255,0.01)",
          border: `1px solid ${C.border}`,
          borderRadius: 12,
          padding: "16px 20px",
          marginBottom: 16,
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {/* Search Row */}
          <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
            <div style={{ flex: 1, minWidth: 280 }}>
              <Autocomplete
                inputValue={searchInputValue}
                onInputChange={handleSearchInput}
                suggestions={suggestions}
                onSelectSuggestion={handleSelectSuggestion}
                isLoading={suggestionsLoading}
                isOpen={isDropdownOpen}
                setIsOpen={setIsDropdownOpen}
              />
            </div>
            
            {/* Year Selector in a group */}
            <div style={{ display: "flex", gap: 6, background: C.bg, padding: 3, borderRadius: 10, border: `1px solid ${C.border}` }}>
              {YEARS.map((y) => (
                <button
                  key={y}
                  onClick={() => setSortYr(y)}
                  style={{
                    padding: "6px 12px",
                    borderRadius: 7,
                    fontSize: 11,
                    fontWeight: sortYr === y ? 800 : 500,
                    border: "none",
                    background: sortYr === y ? C.blue : "transparent",
                    color: sortYr === y ? "#fff" : C.muted,
                    cursor: "pointer",
                    transition: "all 0.2s"
                  }}
                >
                  {y}
                </button>
              ))}
            </div>
          </div>

          {selectedSearch && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "8px 12px",
                background: `${C.blue}10`,
                borderRadius: 8,
                border: `1px solid ${C.blue}30`,
              }}
            >
              <span style={{ fontSize: 10, color: C.blue, fontWeight: 700 }}>🎯 SELECTED OCCUPATION:</span>
              <span style={{ fontSize: 12, color: C.text, fontWeight: 600 }}>
                {selectedSearch.occupation}
              </span>
              <span style={{ fontSize: 10, color: C.muted, fontFamily: "monospace" }}>
                ({selectedSearch.anzsco_code})
              </span>
              <button
                onClick={() => {
                  setSelectedSearch(null);
                  setSearchData(null);
                  setSearchInputValue("");
                }}
                style={{
                  marginLeft: "auto",
                  background: "rgba(255,255,255,0.05)",
                  border: "none",
                  color: C.text,
                  cursor: "pointer",
                  fontSize: 12,
                  width: 20,
                  height: 20,
                  borderRadius: 10,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center"
                }}
              >
                ×
              </button>
            </div>
          )}

          {/* State Selector Row */}
          <div
            style={{
              display: "flex",
              gap: 12,
              alignItems: "center",
              opacity: isSearchMode ? 0.4 : 1,
              pointerEvents: isSearchMode ? "none" : "auto",
              paddingTop: 4,
              borderTop: `1px solid ${C.border}30`
            }}
          >
            <span style={{ fontSize: 10, color: C.muted, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em" }}>Filter State:</span>
            <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
              {STATES.map((s) => (
                <button
                  key={s}
                  onClick={() => setState(s)}
                  style={{
                    padding: "4px 10px",
                    borderRadius: 6,
                    fontSize: 10,
                    fontWeight: state === s ? 800 : 500,
                    border: `1px solid ${state === s ? STATE_COLORS[s] : C.border}`,
                    background: state === s ? `${STATE_COLORS[s]}15` : "transparent",
                    color: state === s ? STATE_COLORS[s] : C.muted,
                    cursor: "pointer",
                    transition: "all 0.2s"
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
            {isSearchMode && (
              <span style={{ fontSize: 10, color: C.amber, marginLeft: "auto" }}>
                ⚠️ State filter disabled during search
              </span>
            )}
          </div>
        </div>
      </div>

      {loading && !isSearchMode ? (
        <div
          style={{
            textAlign: "center",
            padding: 60,
            color: C.muted,
            fontSize: 12,
          }}
        >
          Loading forecast data…
        </div>
      ) : (
        <>
          {/* Charts row — hide when searching a specific occupation */}
          {!isSearchMode && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
                gap: 16,
                marginBottom: 16,
              }}
            >
              <Card>
                <SectionTitle
                  title={`Top 10 Highest Risk — ${state}, ${sortYr}`}
                  sub="Probability of being on shortage list · hover for exact value"
                />
                <ResponsiveContainer width="100%" height={248}>
                  <BarChart
                    data={top10}
                    layout="vertical"
                    margin={{ left: 0, right: 52, top: 0, bottom: 0 }}
                  >
                    <XAxis
                      type="number"
                      domain={[0, 1]}
                      tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                      tick={{ fontSize: 9, fill: C.muted }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      type="category"
                      dataKey="occupation"
                      width={180}
                      tick={{ fontSize: 8, fill: C.text }}
                      axisLine={false}
                      tickLine={false}
                      tickFormatter={(v: string) =>
                        v.length > 26 ? v.slice(0, 24) + "…" : v
                      }
                    />
                    <Tooltip
                      formatter={(v: any) => [
                        `${(+v * 100).toFixed(1)}%`,
                        "Shortage Probability",
                      ]}
                      contentStyle={{
                        background: C.surface,
                        border: `1px solid ${C.border}`,
                        borderRadius: 6,
                        fontSize: 11,
                      }}
                    />
                    <ReferenceLine
                      x={0.65}
                      stroke="#ef444450"
                      strokeDasharray="4 3"
                    />
                    <ReferenceLine
                      x={0.4}
                      stroke="#f59e0b50"
                      strokeDasharray="4 3"
                    />
                    <Bar dataKey={`prob_${sortYr}`} radius={[0, 4, 4, 0]}>
                      {top10.map((r: any, i: number) => (
                        <Cell
                          key={i}
                          fill={probColor(r[`prob_${sortYr}`] ?? 0)}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </Card>

              <Card>
                <SectionTitle
                  title={`Shortage Trajectory — ${state}`}
                  sub="Average probability and high-risk count 2026–2030"
                />
                <ResponsiveContainer width="100%" height={248}>
                  <AreaChart
                    data={trendData}
                    margin={{ top: 4, right: 8, bottom: 0, left: -10 }}
                  >
                    <defs>
                      <linearGradient id="pGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop
                          offset="5%"
                          stopColor={C.purple}
                          stopOpacity={0.3}
                        />
                        <stop
                          offset="95%"
                          stopColor={C.purple}
                          stopOpacity={0}
                        />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                    <XAxis
                      dataKey="year"
                      tick={{ fontSize: 10, fill: C.muted }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      yAxisId="l"
                      domain={[0, 0.6]}
                      tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                      tick={{ fontSize: 9, fill: C.muted }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      yAxisId="r"
                      orientation="right"
                      tick={{ fontSize: 9, fill: C.muted }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      formatter={(v: any, name: string) => [
                        name === "avg"
                          ? `${(+v * 100).toFixed(1)}%`
                          : String(v),
                        name === "avg" ? "Avg Probability" : "High Risk Count",
                      ]}
                      contentStyle={{
                        background: C.surface,
                        border: `1px solid ${C.border}`,
                        borderRadius: 6,
                        fontSize: 11,
                      }}
                    />
                    <Area
                      yAxisId="l"
                      type="monotone"
                      dataKey="avg"
                      stroke={C.purple}
                      fill="url(#pGrad)"
                      strokeWidth={2}
                      dot={{ r: 4, fill: C.purple }}
                      name="avg"
                    />
                    <Bar
                      yAxisId="r"
                      dataKey="high"
                      fill={`${C.red}35`}
                      radius={[2, 2, 0, 0]}
                      name="high"
                    />
                    <Legend wrapperStyle={{ fontSize: 10, color: C.muted }} />
                  </AreaChart>
                </ResponsiveContainer>
              </Card>
            </div>
          )}

          {/* Search result: occupation across all states as line chart */}
          {isSearchMode && records.length > 0 && (
            <Card style={{ marginBottom: 16 }}>
              <SectionTitle
                title={`"${records[0]?.occupation}" — All States, 2026–2030`}
                sub={`ANZSCO ${records[0]?.anzsco_code} · Shortage probability per state · Source: ML model (RandomForest)`}
              />
              <ResponsiveContainer width="100%" height={240}>
                <LineChart
                  margin={{ top: 4, right: 16, bottom: 0, left: -10 }}
                  data={YEARS.map((y) => {
                    const point: any = { year: y };
                    records.forEach((r: any) => {
                      point[r.state] = r[`prob_${y}`] ?? 0;
                    });
                    return point;
                  })}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                  <XAxis
                    dataKey="year"
                    tick={{ fontSize: 10, fill: C.muted }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    domain={[0, 1]}
                    tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                    tick={{ fontSize: 9, fill: C.muted }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    formatter={(v: any, name: string) => [
                      `${(+v * 100).toFixed(1)}%`,
                      name,
                    ]}
                    contentStyle={{
                      background: C.surface,
                      border: `1px solid ${C.border}`,
                      borderRadius: 6,
                      fontSize: 11,
                    }}
                  />
                  <ReferenceLine
                    y={0.65}
                    stroke="#ef444450"
                    strokeDasharray="4 3"
                    label={{ value: "High risk", fill: "#ef4444", fontSize: 9 }}
                  />
                  <ReferenceLine
                    y={0.4}
                    stroke="#f59e0b50"
                    strokeDasharray="4 3"
                    label={{ value: "Med risk", fill: "#f59e0b", fontSize: 9 }}
                  />
                  {records.map((r: any, i: number) => (
                    <Line
                      key={`${r.state}-${i}`}
                      type="monotone"
                      dataKey={r.state}
                      stroke={STATE_COLORS[r.state] || C.muted}
                      strokeWidth={2}
                      dot={{ r: 4, fill: STATE_COLORS[r.state] || C.muted }}
                    />
                  ))}
                  <Legend wrapperStyle={{ fontSize: 10 }} />
                </LineChart>
              </ResponsiveContainer>
            </Card>
          )}

          {/* Full table */}
          <Card>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: 12,
              }}
            >
              <SectionTitle
                title={
                  isSearchMode
                    ? `Search results for "${selectedSearch?.occupation}"`
                    : "All Occupations — 5-Year Forecast"
                }
                sub={
                  isSearchMode
                    ? `${records.length} result(s) across all states · sorted by ${sortYr}`
                    : `${records.length} occupations · ${state} · sorted by ${sortYr}`
                }
              />
              <div style={{ display: "flex", gap: 14 }}>
                {[
                  ["High ≥65%", "#ef4444"],
                  ["Med 40–65%", "#f59e0b"],
                  ["Low <40%", "#10b981"],
                ].map(([l, c]) => (
                  <div
                    key={l}
                    style={{ display: "flex", alignItems: "center", gap: 5 }}
                  >
                    <div
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: 2,
                        background: c,
                      }}
                    />
                    <span style={{ fontSize: 10, color: C.muted }}>{l}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Header and Rows wrapped in overflowX auto */}
            {/* Header and Rows wrapped in overflowX auto */}
            {isMobile ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 12, padding: "8px 0" }}>
                {searching ? (
                  <p style={{ textAlign: "center", color: C.muted, padding: 24, fontSize: 12 }}>Searching…</p>
                ) : paginatedRecords.length === 0 ? (
                  <p style={{ textAlign: "center", color: C.muted, padding: 24, fontSize: 12 }}>
                    {isSearchMode ? `No results for "${selectedSearch?.occupation}"` : "No data"}
                  </p>
                ) : (
                  paginatedRecords.map((r: any, i: number) => {
                    const probs = YEARS.map((y) => r[`prob_${y}`] ?? 0);
                    const sp = r[`prob_${sortYr}`] ?? 0;
                    const delta = probs[4] - probs[0];
                    const arrow = delta > 0.05 ? "↑" : delta < -0.05 ? "↓" : "→";
                    const arrowC = delta > 0.05 ? "#ef4444" : delta < -0.05 ? "#10b981" : C.muted;
                    
                    return (
                      <div
                        key={`${r.anzsco_code}-${r.state}-${i}`}
                        style={{
                          padding: 14,
                          borderRadius: 8,
                          background: C.surfaceAlt,
                          border: `1px solid ${C.border}`,
                          borderLeft: sp >= 0.65 ? "4px solid #ef4444" : sp >= 0.4 ? "4px solid #f59e0b" : `1px solid ${C.border}`,
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                          <span style={{ fontSize: 13, fontWeight: 600, color: C.text }}>{r.occupation}</span>
                          <span style={{ fontSize: 14, fontWeight: 800, color: arrowC }}>{arrow}</span>
                        </div>
                        <div style={{ fontSize: 10, color: C.muted, fontFamily: "monospace", marginBottom: 12 }}>
                          {r.anzsco_code} {isSearchMode && `· ${r.state}`}
                        </div>
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 4 }}>
                          {probs.map((p, yi) => {
                            const isSortCol = YEARS[yi] === sortYr;
                            return (
                              <div key={yi} style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
                                <span style={{ fontSize: 9, color: isSortCol ? C.cyan : C.muted, fontWeight: isSortCol ? 700 : 400, marginBottom: 2 }}>{YEARS[yi]}</span>
                                <span style={{
                                  fontSize: 11,
                                  fontWeight: isSortCol ? 800 : 500,
                                  color: probColor(p),
                                  background: isSortCol ? `${probColor(p)}18` : "transparent",
                                  padding: "2px 6px",
                                  borderRadius: 4,
                                }}>{pct(p)}</span>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: isSearchMode
                      ? "68px 1fr 44px 52px 52px 52px 52px 52px 60px"
                      : "68px 1fr 52px 52px 52px 52px 52px 60px",
                    gap: 6,
                    padding: "6px 12px",
                    borderBottom: `1px solid ${C.border}`,
                    marginBottom: 2,
                    minWidth: 800,
                  }}
                >
                  {[
                    "Code",
                    "Occupation",
                    ...(isSearchMode ? ["State"] : []),
                    ...YEARS,
                    "Trend",
                  ].map((h) => (
                    <span
                      key={h}
                      style={{
                        fontSize: 9,
                        fontWeight: 700,
                        textTransform: "uppercase" as const,
                        letterSpacing: "0.06em",
                        color: h === sortYr ? C.cyan : C.muted,
                      }}
                    >
                      {h}
                      {h === sortYr ? " ▼" : ""}
                    </span>
                  ))}
                </div>

                {/* Rows */}
                <div style={{ maxHeight: 460, overflowY: "auto", minWidth: 800 }}>
                  {searching ? (
                    <p
                      style={{
                        textAlign: "center",
                        color: C.muted,
                        padding: 24,
                        fontSize: 12,
                      }}
                    >
                      Searching…
                    </p>
                  ) : paginatedRecords.length === 0 ? (
                    <p
                      style={{
                        textAlign: "center",
                        color: C.muted,
                        padding: 24,
                        fontSize: 12,
                      }}
                    >
                      {isSearchMode
                        ? `No results for "${selectedSearch?.occupation}"`
                        : "No data"}
                    </p>
                  ) : (
                    paginatedRecords.map((r: any, i: number) => {
                      const probs = YEARS.map((y) => r[`prob_${y}`] ?? 0);
                      const sp = r[`prob_${sortYr}`] ?? 0;
                      const delta = probs[4] - probs[0];
                      const arrow = delta > 0.05 ? "↑" : delta < -0.05 ? "↓" : "→";
                      const arrowC =
                        delta > 0.05
                          ? "#ef4444"
                          : delta < -0.05
                            ? "#10b981"
                            : C.muted;
                      const cols = isSearchMode
                        ? "68px 1fr 44px 52px 52px 52px 52px 52px 60px"
                        : "68px 1fr 52px 52px 52px 52px 52px 60px";
                      return (
                        <div
                          key={`${r.anzsco_code}-${r.state}-${i}`}
                          style={{
                            display: "grid",
                            gridTemplateColumns: cols,
                            gap: 6,
                            padding: "6px 12px",
                            borderRadius: 5,
                            alignItems: "center",
                            background:
                              i % 2 === 0 ? "transparent" : "var(--surface-alt)",
                            borderLeft:
                              sp >= 0.65
                                ? "2px solid #ef4444"
                                : sp >= 0.4
                                  ? "2px solid #f59e0b"
                                  : "2px solid transparent",
                            cursor: "pointer",
                          }}
                          onMouseEnter={(e) =>
                            (e.currentTarget.style.background = C.hover)
                          }
                          onMouseLeave={(e) =>
                            (e.currentTarget.style.background =
                              i % 2 === 0 ? "transparent" : "var(--surface-alt)")
                          }
                        >
                          <span
                            style={{
                              fontSize: 10,
                              color: C.muted,
                              fontFamily: "monospace",
                            }}
                          >
                            {r.anzsco_code}
                          </span>
                          <span
                            style={{ fontSize: 11, color: C.text, lineHeight: 1.3 }}
                          >
                            {r.occupation}
                          </span>
                          {isSearchMode && (
                            <span
                              style={{
                                fontSize: 10,
                                fontWeight: 700,
                                color: STATE_COLORS[r.state] || C.muted,
                              }}
                            >
                              {r.state}
                            </span>
                          )}
                          {probs.map((p, yi) => {
                            const isSortCol = YEARS[yi] === sortYr;
                            return (
                              <span
                                key={yi}
                                style={{
                                  fontSize: 11,
                                  fontWeight: isSortCol ? 800 : 400,
                                  color: probColor(p),
                                  background: isSortCol
                                    ? `${probColor(p)}18`
                                    : "transparent",
                                  borderRadius: 4,
                                  padding: isSortCol ? "1px 4px" : 0,
                                  textAlign: "center" as const,
                                }}
                              >
                                {pct(p)}
                              </span>
                            );
                          })}
                          <span
                            style={{
                              fontSize: 14,
                              fontWeight: 700,
                              color: arrowC,
                              textAlign: "center" as const,
                            }}
                          >
                            {arrow}
                          </span>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            )}
          <Pagination page={page} totalPages={totalPages} setPage={setPage} />
        </Card>
      </>
    )}
  </>
);
}

// ══════════════════════════════════════════════════════════════════
// TAB B — HISTORICAL OSL 2021–2025
// ══════════════════════════════════════════════════════════════════

function HistoricalTab({ trend, heatmap, year, setYear, isMobile }: any) {
  const [search, setSearch] = useState("");
  const [skillF, setSkillF] = useState<number | null>(null);

  const [suggestions, setSuggestions] = useState<AutocompleteSuggestion[]>([]);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [selectedSearch, setSelectedSearch] = useState<AutocompleteSuggestion | null>(null);

  const handleSearchInput = (value: string) => {
    setSearch(value);
    setIsDropdownOpen(true);
    if (!value.trim()) {
      setSuggestions([]);
      setSelectedSearch(null);
      return;
    }

    const q = value.toLowerCase();
    const uniqueMap = new Map<string, AutocompleteSuggestion>();
    (heatmap?.records || []).forEach((r: any) => {
      if (
        r.occupation_name.toLowerCase().includes(q) ||
        r.anzsco_code.includes(q)
      ) {
        if (!uniqueMap.has(r.anzsco_code)) {
          uniqueMap.set(r.anzsco_code, {
            anzsco_code: r.anzsco_code,
            occupation: r.occupation_name,
          });
        }
      }
    });

    setSuggestions(Array.from(uniqueMap.values()).slice(0, 10));
  };

  const handleSelectSuggestion = (suggestion: AutocompleteSuggestion) => {
    setSearch("");
    setSelectedSearch(suggestion);
    setSuggestions([]);
  };

  const records = useMemo(() => {
    return (heatmap?.records || []).filter((r: any) => {
      if (selectedSearch) {
        return (
          r.anzsco_code === selectedSearch.anzsco_code &&
          (!skillF || r.skill_level === skillF)
        );
      }
      const q = search.toLowerCase();
      return (
        (!search ||
          r.occupation_name.toLowerCase().includes(q) ||
          r.anzsco_code.includes(q)) &&
        (!skillF || r.skill_level === skillF)
      );
    });
  }, [heatmap, search, skillF, selectedSearch]);

  const shortage = records.filter((r: any) => r.national === 1).length;
  const noList = records.filter((r: any) => r.national === 0).length;

  const [page, setPage] = useState(1);
  const limit = 20;

  useEffect(() => {
    setPage(1);
  }, [search, skillF, selectedSearch, year]);

  const totalPages = Math.ceil(records.length / limit);
  const paginatedRecords = records.slice((page - 1) * limit, page * limit);

  return (
    <>
      {/* Charts */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: isMobile ? "1fr" : "repeat(auto-fit, minmax(320px, 1fr))",
          gap: 16,
          marginBottom: 20,
        }}
      >
        <Card>
          <SectionTitle
            title="National Shortage Count 2021–2025"
            sub="Occupations on the national shortage list"
          />
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart
              data={trend?.yearly_trend || []}
              margin={{ top: 4, right: 8, bottom: 0, left: -10 }}
            >
              <defs>
                <linearGradient id="rGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
              <XAxis
                dataKey="year"
                tick={{ fill: C.muted, fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: C.muted, fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<ChartTip />} />
              <Area
                type="monotone"
                dataKey="national"
                name="National Shortage"
                stroke="#ef4444"
                fill="url(#rGrad)"
                strokeWidth={2}
                dot={{ r: 4, fill: "#ef4444" }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </Card>

        <Card>
          <SectionTitle
            title={`Shortage by State — ${year}`}
            sub="Number of shortage occupations per state"
          />
          <ResponsiveContainer width="100%" height={200}>
            <BarChart
              data={STATES.map((s) => ({
                state: s,
                count: heatmap?.state_shortage_counts?.[s] || 0,
              }))}
              margin={{ top: 4, right: 8, bottom: 0, left: -10 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
              <XAxis
                dataKey="state"
                tick={{ fill: C.muted, fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: C.muted, fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<ChartTip />} />
              <Bar dataKey="count" name="Shortage Count" radius={[4, 4, 0, 0]}>
                {STATES.map((s) => (
                  <Cell key={s} fill={STATE_COLORS[s]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card>
          <SectionTitle
            title="Shortage by Skill Level — 2025"
            sub="Proportion of each skill level on shortage list"
          />
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 12,
              marginTop: 8,
            }}
          >
            {(trend?.skill_breakdown || []).map((s: any, i: number) => (
              <div key={s.skill_level}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginBottom: 4,
                  }}
                >
                  <div>
                    <span
                      style={{
                        fontSize: 12,
                        fontWeight: 700,
                        color: SKILL_COLORS[i],
                      }}
                    >
                      Level {s.skill_level}
                    </span>
                    <span
                      style={{ fontSize: 10, color: C.muted, marginLeft: 8 }}
                    >
                      {s.desc}
                    </span>
                  </div>
                  <span
                    style={{
                      fontSize: 12,
                      fontWeight: 700,
                      color: SKILL_COLORS[i],
                    }}
                  >
                    {s.shortage}/{s.total} · {s.pct}%
                  </span>
                </div>
                <div
                  style={{ height: 6, background: C.border, borderRadius: 3 }}
                >
                  <div
                    style={{
                      width: `${s.pct}%`,
                      height: "100%",
                      background: SKILL_COLORS[i],
                      borderRadius: 3,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <SectionTitle
            title="State Shortage Trend 2021–2025"
            sub="NSW · VIC · QLD · WA"
          />
          <ResponsiveContainer width="100%" height={200}>
            <LineChart
              data={trend?.yearly_trend || []}
              margin={{ top: 4, right: 8, bottom: 0, left: -10 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
              <XAxis
                dataKey="year"
                tick={{ fill: C.muted, fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: C.muted, fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<ChartTip />} />
              {["NSW", "VIC", "QLD", "WA"].map((s) => (
                <Line
                  key={s}
                  type="monotone"
                  dataKey={s}
                  name={s}
                  stroke={STATE_COLORS[s]}
                  strokeWidth={2}
                  dot={false}
                />
              ))}
              <Legend wrapperStyle={{ fontSize: 10, color: C.muted }} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* Filters (Matching ForecastTab layout) */}
      <div
        style={{
          background: "rgba(255,255,255,0.01)",
          border: `1px solid ${C.border}`,
          borderRadius: 12,
          padding: "16px 20px",
          marginBottom: 16,
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
            <div style={{ flex: 1, minWidth: 280 }}>
              <Autocomplete
                inputValue={search}
                onInputChange={handleSearchInput}
                suggestions={suggestions}
                onSelectSuggestion={handleSelectSuggestion}
                isLoading={false}
                isOpen={isDropdownOpen}
                setIsOpen={setIsDropdownOpen}
              />
            </div>

            {/* Year Selector in a group */}
            <div style={{ display: "flex", gap: 6, background: C.bg, padding: 3, borderRadius: 10, border: `1px solid ${C.border}` }}>
              {[2021, 2022, 2023, 2024, 2025].map((y) => (
                <button
                  key={y}
                  onClick={() => setYear(y)}
                  style={{
                    padding: "6px 12px",
                    borderRadius: 7,
                    fontSize: 11,
                    fontWeight: year === y ? 800 : 500,
                    border: "none",
                    background: year === y ? C.blue : "transparent",
                    color: year === y ? "#fff" : C.muted,
                    cursor: "pointer",
                    transition: "all 0.2s"
                  }}
                >
                  {y}
                </button>
              ))}
            </div>
          </div>

          {selectedSearch && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "8px 12px",
                background: `${C.blue}10`,
                borderRadius: 8,
                border: `1px solid ${C.blue}30`,
              }}
            >
              <span style={{ fontSize: 10, color: C.blue, fontWeight: 700 }}>🎯 SELECTED OCCUPATION:</span>
              <span style={{ fontSize: 12, color: C.text, fontWeight: 600 }}>
                {selectedSearch.occupation}
              </span>
              <span style={{ fontSize: 10, color: C.muted, fontFamily: "monospace" }}>
                ({selectedSearch.anzsco_code})
              </span>
              <button
                onClick={() => setSelectedSearch(null)}
                style={{
                  marginLeft: "auto",
                  background: "rgba(255,255,255,0.05)",
                  border: "none",
                  color: C.text,
                  cursor: "pointer",
                  fontSize: 12,
                  width: 20,
                  height: 20,
                  borderRadius: 10,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center"
                }}
              >
                ×
              </button>
            </div>
          )}

          <div
            style={{
              display: "flex",
              gap: 12,
              alignItems: "center",
              opacity: selectedSearch ? 0.4 : 1,
              paddingTop: 4,
              borderTop: `1px solid ${C.border}30`
            }}
          >
            <span style={{ fontSize: 10, color: C.muted, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em" }}>Skill Levels:</span>
            <div style={{ display: "flex", gap: 5 }}>
              <button
                onClick={() => setSkillF(null)}
                style={{
                  padding: "4px 10px",
                  borderRadius: 6,
                  fontSize: 10,
                  fontWeight: !skillF ? 800 : 500,
                  border: `1px solid ${!skillF ? C.purple : C.border}`,
                  background: !skillF ? `${C.purple}15` : "transparent",
                  color: !skillF ? C.purple : C.muted,
                  cursor: "pointer"
                }}
              >
                All Skills
              </button>
              {[1, 2, 3, 4, 5].map((l) => (
                <button
                  key={l}
                  onClick={() => setSkillF(skillF === l ? null : l)}
                  style={{
                    padding: "4px 10px",
                    borderRadius: 6,
                    fontSize: 10,
                    fontWeight: skillF === l ? 800 : 500,
                    border: `1px solid ${skillF === l ? SKILL_COLORS[l - 1] : C.border}`,
                    background: skillF === l ? `${SKILL_COLORS[l - 1]}15` : "transparent",
                    color: skillF === l ? SKILL_COLORS[l - 1] : C.muted,
                    cursor: "pointer"
                  }}
                >
                  L{l}
                </button>
              ))}
            </div>
            <span style={{ fontSize: 11, color: C.muted, marginLeft: "auto" }}>
              <strong style={{ color: C.red }}>{shortage}</strong> shortage · <strong style={{ color: C.text }}>{noList}</strong> not on list
            </span>
          </div>
        </div>
      </div>

      {/* OSL Table */}
      <Card>
        {/* Header and Rows wrapped in overflowX auto */}
        {isMobile ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 8, padding: "8px 0" }}>
            {paginatedRecords.length === 0 ? (
              <p style={{ textAlign: "center", color: C.muted, padding: 20, fontSize: 12 }}>No results</p>
            ) : (
              paginatedRecords.map((r: any, i: number) => (
                <div
                  key={`${r.anzsco_code}-${i}`}
                  style={{
                    padding: 12,
                    borderRadius: 8,
                    background: C.surfaceAlt,
                    border: `1px solid ${C.border}`,
                    borderLeft: r.national === 1 ? "4px solid #ef4444" : `1px solid ${C.border}`,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: C.text }}>
                      {r.occupation_name}
                    </span>
                    <span style={{ fontSize: 11, fontWeight: 700, color: SKILL_COLORS[r.skill_level - 1] }}>
                      L{r.skill_level}
                    </span>
                  </div>
                  <div style={{ fontSize: 10, color: C.muted, fontFamily: "monospace", marginBottom: 12 }}>
                    {r.anzsco_code}
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {STATES.map((s) => (
                      <div
                        key={s}
                        style={{
                          padding: "2px 6px",
                          borderRadius: 4,
                          fontSize: 10,
                          fontWeight: 700,
                          background: r[s.toLowerCase()] === 1 ? `${STATE_COLORS[s]}15` : "transparent",
                          color: r[s.toLowerCase()] === 1 ? STATE_COLORS[s] : C.muted,
                          border: `1px solid ${r[s.toLowerCase()] === 1 ? STATE_COLORS[s] : C.border}`,
                        }}
                      >
                        {s}
                      </div>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <div
              style={{
                display: "grid",
                gridTemplateColumns:
                  "96px 1fr 50px 42px 42px 42px 42px 42px 42px 42px 42px 50px",
                gap: 4,
                padding: "6px 10px",
                borderBottom: `1px solid ${C.border}`,
                marginBottom: 2,
                minWidth: 800,
              }}
            >
              {["ANZSCO", "Occupation", "Skill", "NAT", ...STATES].map((h) => (
                <span
                  key={h}
                  style={{
                    fontSize: 9,
                    color: C.muted,
                    fontWeight: 700,
                    textTransform: "uppercase" as const,
                    letterSpacing: "0.06em",
                  }}
                >
                  {h}
                </span>
              ))}
            </div>
            <div style={{ maxHeight: 500, overflowY: "auto", minWidth: 800 }}>
              {paginatedRecords.length === 0 ? (
                <p
                  style={{
                    textAlign: "center",
                    color: C.muted,
                    padding: 20,
                    fontSize: 12,
                  }}
                >
                  No results
                </p>
              ) : (
                paginatedRecords.map((r: any, i: number) => (
                  <div
                    key={`${r.anzsco_code}-${i}`}
                    style={{
                      display: "grid",
                      gridTemplateColumns:
                        "96px 1fr 50px 42px 42px 42px 42px 42px 42px 42px 42px 50px",
                      gap: 4,
                      padding: "6px 10px",
                      borderRadius: 5,
                      alignItems: "center",
                      background:
                        i % 2 === 0 ? "transparent" : "var(--surface-alt)",
                      borderLeft:
                        r.national === 1
                          ? "2px solid #ef444460"
                          : "2px solid transparent",
                    }}
                  >
                    <span
                      style={{
                        fontSize: 10,
                        color: C.muted,
                        fontFamily: "monospace",
                      }}
                    >
                      {r.anzsco_code}
                    </span>
                    <span style={{ fontSize: 11, color: C.text }}>
                      {r.occupation_name}
                    </span>
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 700,
                        color: SKILL_COLORS[r.skill_level - 1] || C.muted,
                      }}
                    >
                      L{r.skill_level}
                    </span>
                    <span
                      style={{
                        fontSize: 12,
                        fontWeight: 800,
                        textAlign: "center" as const,
                        color: r.national === 1 ? "#ef4444" : "#1f2937",
                      }}
                    >
                      {r.national === 1 ? "●" : "○"}
                    </span>
                    {STATES.map((s) => (
                      <span
                        key={s}
                        style={{
                          fontSize: 12,
                          textAlign: "center" as const,
                          color:
                            r[s.toLowerCase()] === 1 ? STATE_COLORS[s] : "#1f2937",
                        }}
                      >
                        {r[s.toLowerCase()] === 1 ? "●" : "○"}
                      </span>
                    ))}
                  </div>
                ))
              )}
            </div>
          </div>
        )}
        <Pagination page={page} totalPages={totalPages} setPage={setPage} />
      </Card>
    </>
  );
}

// ══════════════════════════════════════════════════════════════════
// MAIN PAGE
// ══════════════════════════════════════════════════════════════════

export default function ShortageAnalysis() {
  const { get } = useDataCache();
  const [tab, setTab] = useState<"forecast" | "historical">("forecast");
  const [trend, setTrend] = useState<any>(null);
  const [heatmap, setHeatmap] = useState<any>(null);
  const [year, setYear] = useState(2025);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth <= 768);
    handleResize(); // initial check
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    Promise.all([
      get(`/api/data/osl-trend`),
      get(`/api/data/shortage-heatmap?year=2025`),
    ]).then(([t, h]) => {
      setTrend(t);
      setHeatmap(h);
    });
  }, []);

  useEffect(() => {
    get(`/api/data/shortage-heatmap?year=${year}`).then((h) => setHeatmap(h));
  }, [year]);

  return (
    <PageWrapper>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h1
          style={{
            fontSize: 22,
            fontWeight: 800,
            color: "var(--text)",
            marginBottom: 4,
          }}
        >
          Occupation Shortage Analysis
        </h1>
        <p style={{ fontSize: 13, color: C.muted }}>
          Historical OSL 2021–2025 (DESE) &nbsp;·&nbsp; ML forecast 2026–2030
          (RandomForest, 916 occupations)
        </p>
      </div>

      {/* KPIs */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: isMobile ? "1fr" : "repeat(auto-fit, minmax(200px, 1fr))",
          gap: 12,
          marginBottom: 28,
        }}
      >
        <KpiCard
          label="Total Occupations"
          value={fmt(heatmap?.total_occupations)}
          sub="In OSL 2025"
          color="#2a8bff"
        />
        <KpiCard
          label="National Shortage"
          value={fmt(heatmap?.national_shortage_count)}
          sub="On shortage list"
          color="#ef4444"
        />
        <KpiCard
          label="Shortage Rate"
          value={`${heatmap?.national_shortage_pct ?? 0}%`}
          sub="Of all occupations"
          color="#f59e0b"
        />
        <KpiCard
          label="Forecast Occupations"
          value="916"
          sub="With 2026–2030 ML forecast"
          color="#8b5cf6"
        />
      </div>

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          borderBottom: `1px solid ${C.border}`,
          marginBottom: 20,
        }}
      >
        {(
          [
            {
              key: "forecast",
              label: "ML Forecast 2026–2030",
              color: C.purple,
            },
            {
              key: "historical",
              label: "Historical OSL 2021–2025",
              color: C.blue,
            },
          ] as const
        ).map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            style={{
              padding: "10px 24px",
              fontSize: 12,
              fontWeight: tab === t.key ? 700 : 500,
              cursor: "pointer",
              border: "none",
              borderRadius: "8px 8px 0 0",
              background: tab === t.key ? C.surface : "transparent",
              color: tab === t.key ? t.color : C.muted,
              borderBottom:
                tab === t.key
                  ? `2px solid ${t.color}`
                  : "2px solid transparent",
              marginBottom: -1,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "forecast" && <ForecastTab isMobile={isMobile} />}
      {tab === "historical" && (
        <HistoricalTab
          trend={trend}
          heatmap={heatmap}
          year={year}
          setYear={setYear}
          isMobile={isMobile}
        />
      )}
    </PageWrapper>
  );
}
