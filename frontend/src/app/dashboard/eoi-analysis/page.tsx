"use client";
/**
 * EOI Analysis page
 * GET /api/data/summary          → KPI cards
 * GET /api/data/eoi/monthly      → pool + invitations trend
 * GET /api/data/eoi/occupations  → top occupations table (year, state, visa, limit)
 * GET /api/data/eoi/points       → points distribution (visa_type, state)
 */
import { useState, useEffect } from "react";
import Link from "next/link";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { useDataCache } from "@/lib/DataCacheContext";
import {
  C,
  Card,
  KPICard,
  ChartHeader,
  Badge,
  ChartTip,
  PageWrapper,
  Grid,
  Pagination,
} from "@/components/ui";

const API = "";
const fmt = (n: number) => n?.toLocaleString() ?? "—";
const STATES = ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"];

const selectStyle = {
  background: C.bg,
  border: `1px solid ${C.border}`,
  borderRadius: 6,
  padding: "7px 12px",
  color: C.muted,
  fontSize: 12,
  outline: "none",
  cursor: "pointer",
};

export default function EOIAnalysis() {
  // Filters
  const { get } = useDataCache();
  const [yearFilter, setYearFilter] = useState<number | null>(null);
  const [stateFilter, setStateFilter] = useState("");
  const [visaFilter, setVisaFilter] = useState("");
  const [page, setPage] = useState(1);
  const [searchOcc, setSearchOcc] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  // Debounce search: wait 500ms after user stops typing before triggering API call
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchOcc), 500);
    return () => clearTimeout(timer);
  }, [searchOcc]);

  // Data
  const [summary, setSummary] = useState<any>(null);
  const [monthly, setMonthly] = useState<any[]>([]);
  const [occupations, setOccupations] = useState<any[]>([]);
  const [points, setPoints] = useState<any[]>([]);

  // Loading states
  const [loadingSummary, setLoadingSummary] = useState(true);
  const [loadingOcc, setLoadingOcc] = useState(true);
  const [loadingPoints, setLoadingPoints] = useState(true);

  // Summary + monthly — once only
  useEffect(() => {
    get(`/api/data/summary`)
      .then(setSummary)
      .finally(() => setLoadingSummary(false));
    get(`/api/data/eoi/monthly`).then((d) => setMonthly(d.records || []));
  }, []);

  // Occupations — refetch when year, state, visa, search, or page changes
  const [occMeta, setOccMeta] = useState({ count: 0, page: 1, total_pages: 1 });

  // Reset page to 1 when debounced search changes
  useEffect(() => {
    setPage(1);
  }, [debouncedSearch]);

  useEffect(() => {
    setLoadingOcc(true);
    const p = new URLSearchParams({ page: String(page) });
    if (yearFilter) p.append("year", String(yearFilter));
    if (stateFilter) p.append("state", stateFilter);
    if (visaFilter) p.append("visa_type", visaFilter);
    if (debouncedSearch) p.append("search", debouncedSearch);
    get(`/api/data/eoi/occupations?${p}`)
      .then((d) => {
        setOccupations(d.records || []);
        setOccMeta({
          count: d.count,
          page: d.page,
          total_pages: d.total_pages,
        });
      })
      .finally(() => setLoadingOcc(false));
  }, [yearFilter, stateFilter, visaFilter, debouncedSearch, page, get]);

  // Points distribution — refetch when visa, state changes
  useEffect(() => {
    setLoadingPoints(true);
    const p = new URLSearchParams();
    if (visaFilter) p.append("visa_type", visaFilter);
    if (stateFilter) p.append("state", stateFilter);
    get(`/api/data/eoi/points?${p}`)
      .then((d) => setPoints(d.records || []))
      .finally(() => setLoadingPoints(false));
  }, [visaFilter, stateFilter]);

  // Pivot points → { points, SUBMITTED, INVITED }
  const pointsPivot = (() => {
    const map: Record<number, any> = {};
    for (const r of points) {
      if (!map[r.points])
        map[r.points] = { points: r.points, SUBMITTED: 0, INVITED: 0 };
      map[r.points][r.status] = r.total;
    }
    return Object.values(map).sort((a, b) => a.points - b.points);
  })();

  const monthlyLast12 = monthly.slice(-12);

  const hasFilter = yearFilter || stateFilter || visaFilter;

  return (
    <PageWrapper
      title="EOI Analysis"
      sub={`SkillSelect data · snapshot ${summary?.latest_snapshot || "..."} · ${summary?.eoi_pool ? fmt(summary.eoi_pool) : "—"} active pool`}
    >
      {/* ── KPI Cards ──────────────────────────────────────── */}
      <div style={Grid.four}>
        <KPICard
          label="Active EOI Pool"
          value={loadingSummary ? "..." : fmt(summary?.eoi_pool)}
          sub="Total submitted — latest snapshot"
          color={C.blue}
        />
        <KPICard
          label="Net Pool Growth"
          value={
            loadingSummary
              ? "..."
              : ((summary?.net_pool_change ?? 0) >= 0 ? "+" : "") +
                fmt(summary?.net_pool_change ?? 0)
          }
          sub="Month-on-month EOI change"
          color={(summary?.net_pool_change ?? 0) >= 0 ? C.green : C.red}
        />
        <KPICard
          label="Active Invitations"
          value={loadingSummary ? "..." : fmt(summary?.total_invitations)}
          sub="People holding 60-day invitations — latest snapshot"
          color={C.amber}
        />
        <KPICard
          label="Highest Points Invited"
          value={loadingSummary ? "..." : `${summary?.points_cutoff ?? 0} pts`}
          sub="Maximum points among invitees this snapshot"
          color={C.purple}
        />
      </div>

      {/* ── Charts ─────────────────────────────────────────── */}
      <div style={Grid.two}>
        {/* Monthly trend */}
        <Card>
          <ChartHeader color={C.blue}>
            Monthly Flow Trends — EOI Growth vs New Invitations
          </ChartHeader>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart
              data={monthlyLast12}
              margin={{ top: 4, right: 10, bottom: 0, left: -10 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
              <XAxis
                dataKey="month"
                tick={{ fill: C.muted, fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: C.muted, fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => v.toLocaleString()}
              />
              <Tooltip content={<ChartTip />} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Line
                type="monotone"
                dataKey="net_change"
                name="EOI Net Growth"
                stroke={C.blue}
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="invitations"
                name="New Invitations"
                stroke={C.green}
                strokeWidth={2}
                dot={{ r: 3, fill: C.green }}
              />
            </LineChart>
          </ResponsiveContainer>
        </Card>

        {/* Points distribution */}
        <Card>
          <ChartHeader color={C.amber}>
            Points Distribution — Submitted vs Invited
            {visaFilter && (
              <span style={{ fontSize: 10, color: C.muted, marginLeft: 8 }}>
                Visa {visaFilter}
              </span>
            )}
            {stateFilter && (
              <span style={{ fontSize: 10, color: C.muted, marginLeft: 4 }}>
                {stateFilter}
              </span>
            )}
          </ChartHeader>
          {loadingPoints ? (
            <div
              style={{
                height: 220,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: C.muted,
                fontSize: 12,
              }}
            >
              Loading...
            </div>
          ) : pointsPivot.length === 0 ? (
            <div
              style={{
                height: 220,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: C.muted,
                fontSize: 12,
              }}
            >
              No data — adjust filters
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart
                data={pointsPivot}
                margin={{ top: 4, right: 10, bottom: 0, left: -10 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                <XAxis
                  dataKey="points"
                  tick={{ fill: C.muted, fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: C.muted, fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v) => (v / 1000).toFixed(0) + "k"}
                />
                <Tooltip content={<ChartTip />} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar
                  dataKey="SUBMITTED"
                  name="Submitted"
                  fill={C.blue}
                  fillOpacity={0.5}
                  radius={[2, 2, 0, 0]}
                />
                <Bar
                  dataKey="INVITED"
                  name="Invited"
                  fill={C.green}
                  radius={[2, 2, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>

      {/* Filter removed and moved to Card Header */}

      {/* ── Occupations table ──────────────────────────────── */}
      <Card style={{ padding: 0, overflow: "hidden" }}>
        <div
          style={{
            padding: "16px 20px",
            borderBottom: `1px solid ${C.border}`,
            background: "rgba(255,255,255,0.01)",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 16,
            }}
          >
            <div>
              <p
                style={{
                  fontSize: 14,
                  fontWeight: 800,
                  color: C.text,
                }}
              >
                Occupations by EOI Activity
              </p>
              <p style={{ fontSize: 11, color: C.muted, marginTop: 2 }}>
                {loadingOcc ? "Loading..." : `${fmt(occMeta.count)} occupations found`}
                {yearFilter && ` · ${yearFilter}`}
                {stateFilter && ` · ${stateFilter}`}
              </p>
            </div>

            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              {/* Filter Group */}
              <div style={{ display: "flex", gap: 6, background: C.bg, padding: 3, borderRadius: 10, border: `1px solid ${C.border}` }}>
                <select
                  style={{ ...selectStyle, background: "transparent", border: "none", padding: "6px 10px" }}
                  value={yearFilter ?? ""}
                  onChange={(e) => setYearFilter(e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">All Years</option>
                  <option value="2024">2024</option>
                  <option value="2025">2025</option>
                  <option value="2026">2026</option>
                </select>
                <div style={{ width: 1, height: 16, background: C.border, alignSelf: "center" }} />
                <select
                  style={{ ...selectStyle, background: "transparent", border: "none", padding: "6px 10px" }}
                  value={stateFilter}
                  onChange={(e) => setStateFilter(e.target.value)}
                >
                  <option value="">All States</option>
                  {STATES.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
                <div style={{ width: 1, height: 16, background: C.border, alignSelf: "center" }} />
                <select
                  style={{ ...selectStyle, background: "transparent", border: "none", padding: "6px 10px" }}
                  value={visaFilter}
                  onChange={(e) => setVisaFilter(e.target.value)}
                >
                  <option value="">All Visas</option>
                  <option value="190">Visa 190</option>
                  <option value="491">Visa 491</option>
                  <option value="189">Visa 189</option>
                  <option value="188">Visa 188</option>
                </select>
              </div>

              {/* Search */}
              <div style={{ position: "relative" }}>
                <svg
                  width="13"
                  height="13"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke={C.muted}
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", pointerEvents: "none" }}
                >
                  <circle cx="11" cy="11" r="8" />
                  <path d="m21 21-4.35-4.35" />
                </svg>
                <input
                  value={searchOcc}
                  onChange={(e) => setSearchOcc(e.target.value)}
                  placeholder="Search occupation…"
                  style={{
                    background: C.bg,
                    border: `1px solid ${searchOcc ? C.blue : C.border}`,
                    borderRadius: 10,
                    padding: "7px 32px 7px 32px",
                    color: C.text,
                    fontSize: 12,
                    outline: "none",
                    width: 180,
                    transition: "all 0.2s",
                  }}
                  onFocus={(e) => e.currentTarget.style.borderColor = C.blue}
                  onBlur={(e) => e.currentTarget.style.borderColor = C.border}
                />
                {searchOcc && (
                  <button onClick={() => setSearchOcc("")} style={{ position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", color: C.muted, cursor: "pointer", fontSize: 12 }}>✕</button>
                )}
              </div>

              {hasFilter && (
                <button
                  onClick={() => {
                    setYearFilter(null);
                    setStateFilter("");
                    setVisaFilter("");
                  }}
                  style={{
                    background: `${C.red}15`,
                    border: `1px solid ${C.red}40`,
                    borderRadius: 10,
                    padding: "7px 12px",
                    color: C.red,
                    fontSize: 11,
                    cursor: "pointer",
                    fontWeight: 600,
                    transition: "all 0.2s",
                  }}
                >
                  ✕ Clear
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Header and Rows wrapped in overflowX auto */}
        <div style={{ overflowX: "auto" }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "2fr 0.7fr 0.7fr 0.9fr 1fr 1fr 1.1fr 0.8fr",
              gap: 8,
              padding: "7px 14px",
              marginBottom: 2,
              minWidth: 900,
            }}
          >
            {[
              "Occupation",
              "ANZSCO",
              "Visa",
              "EOI Pool",
              "Invitations",
              "Pipeline Total",
              "Inv. Rate",
              "Points Range",
            ].map((h) => (
              <span
                key={h}
                style={{
                  fontSize: 10,
                  color: C.muted,
                  fontWeight: 700,
                  textTransform: "uppercase",
                  letterSpacing: "0.07em",
                }}
              >
                {h}
              </span>
            ))}
          </div>

          {/* Rows */}
          <div style={{ maxHeight: 460, overflowY: "auto", minWidth: 900 }}>
            {loadingOcc ? (
              <div
                style={{
                  padding: "30px 0",
                  textAlign: "center",
                  color: C.muted,
                  fontSize: 12,
                }}
              >
                Loading occupations...
              </div>
            ) : occupations.length === 0 ? (
              <div
                style={{
                  padding: "30px 0",
                  textAlign: "center",
                  color: C.muted,
                  fontSize: 12,
                }}
              >
                No results — try adjusting filters
              </div>
            ) : (
              occupations.map((o, i) => {
                const rate = o.invitation_rate;
                const rateColor =
                  rate >= 0.5
                    ? C.green
                    : rate >= 0.2
                      ? C.blue
                      : rate > 0
                        ? C.amber
                        : C.muted;
                const newInv = o.new_invitations ?? 0;
                const pipelineTotal = o.pipeline_total ?? 0;
                return (
                  <Link
                    href={
                      o.anzsco_code ? `/dashboard/occupation/${o.anzsco_code}` : "#"
                    }
                    key={`${o.anzsco_code}-${i}`}
                    style={{
                      display: "grid",
                      gridTemplateColumns:
                        "2fr 0.7fr 0.7fr 0.9fr 1fr 1fr 1.1fr 0.8fr",
                      gap: 8,
                      padding: "9px 14px",
                      borderRadius: 6,
                      alignItems: "center",
                      background:
                        i % 2 === 0 ? "transparent" : "var(--surface-alt)",
                      textDecoration: "none",
                      cursor: o.anzsco_code ? "pointer" : "default",
                    }}
                    onMouseEnter={(e) => {
                      if (o.anzsco_code)
                        (e.currentTarget as HTMLElement).style.background = C.hover;
                    }}
                    onMouseLeave={(e) => {
                      if (o.anzsco_code)
                        (e.currentTarget as HTMLElement).style.background =
                          i % 2 === 0 ? "transparent" : "var(--surface-alt)";
                    }}
                  >
                    {/* Occupation Name */}
                    <span style={{ fontSize: 12, color: C.text, fontWeight: 500 }}>
                      {o.occupation_name || "—"}
                    </span>
                    {/* ANZSCO */}
                    <span
                      style={{
                        fontSize: 11,
                        color: C.text,
                        fontFamily: "monospace",
                      }}
                    >
                      {o.anzsco_code || "—"}
                    </span>
                    {/* Visa */}
                    <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                      {(o.visa_types?.length > 0 ? o.visa_types : []).map(
                        (v: string) => (
                          <Badge
                            key={v}
                            label={v}
                            color={
                              v === "190" ? C.blue : v === "491" ? C.purple : C.cyan
                            }
                          />
                        ),
                      )}
                    </div>
                    {/* EOI Pool */}
                    <div>
                      <span style={{ fontSize: 12, color: C.muted }}>
                        {fmt(o.pool)}
                      </span>
                      {o.net_growth !== 0 && (
                        <span
                          style={{
                            fontSize: 10,
                            color: o.net_growth > 0 ? C.green : C.red,
                            marginLeft: 4,
                          }}
                        >
                          {o.net_growth > 0
                            ? `+${fmt(o.net_growth)}`
                            : fmt(o.net_growth)}
                        </span>
                      )}
                    </div>
                    {/* Current Invitations (active INVITED count) */}
                    <span
                      style={{
                        fontSize: 12,
                        color: o.current_invitations > 0 ? C.green : C.muted,
                        fontWeight: o.current_invitations > 0 ? 700 : 400,
                      }}
                    >
                      {o.current_invitations > 0 ? fmt(o.current_invitations) : "—"}
                    </span>
                    {/* Pipeline Total */}
                    <span
                      style={{
                        fontSize: 12,
                        color: pipelineTotal > 0 ? C.blue : C.muted,
                      }}
                    >
                      {pipelineTotal > 0 ? fmt(pipelineTotal) : "—"}
                    </span>
                    {/* Inv. Rate bar */}
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <div
                        style={{
                          flex: 1,
                          height: 4,
                          background: C.border,
                          borderRadius: 2,
                        }}
                      >
                        <div
                          style={{
                            width: `${Math.min(rate * 100, 100)}%`,
                            height: "100%",
                            background: rateColor,
                            borderRadius: 2,
                          }}
                        />
                      </div>
                      <span
                        style={{
                          fontSize: 11,
                          color: rateColor,
                          width: 36,
                          textAlign: "right",
                        }}
                      >
                        {rate > 0 ? `${(rate * 100).toFixed(0)}%` : "0%"}
                      </span>
                    </div>
                    {/* Points Range */}
                    <span style={{ fontSize: 11, color: C.muted }}>
                      {o.min_invited_points > 0
                        ? `${o.min_invited_points}–${o.max_invited_points} pts`
                        : "—"}
                    </span>
                  </Link>
                );
              })
            )}
          </div>
        </div>
        <Pagination page={occMeta.page} totalPages={occMeta.total_pages} setPage={setPage} />
      </Card>
    </PageWrapper>
  );
}
