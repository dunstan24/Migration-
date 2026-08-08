"use client";
/**
 * Occupation Detail Page
 * Route: /dashboard/occupation/[anzsco]
 *
 * APIs (all real data):
 *   GET /api/data/occupation/{anzsco}          → EOI, JSA, OSL, workforce, demos
 *   GET /api/data/quota                        → state quota lookup
 *   GET /api/data/nero/{anzsco4}               → regional NERO trend
 *   GET /api/data/nero-sa4/{anzsco4}           → SA4 employment breakdown
 *   GET /api/data/shortage-forecast/{anzsco}   → ML 5yr shortage forecast per state
 */
import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  PieChart,
  Pie,
  Legend,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
} from "recharts";
import { useDataCache } from "@/lib/DataCacheContext";
import { C, Card, ChartTip } from "@/components/ui";

const API = "";
const fmt = (n: number) => n?.toLocaleString() ?? "—";
const fmtK = (n: number) =>
  n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n ?? 0);
const pct = (n: number) => `${((n ?? 0) * 100).toFixed(1)}%`;

const VISA_COLORS: Record<string, string> = {
  "190": C.blue,
  "491": C.purple,
  "189": C.green,
  "188": C.amber,
};
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
const STATE_ORDER = ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"];
const PALETTE = [
  C.blue,
  C.purple,
  C.green,
  C.amber,
  C.cyan,
  "#ef4444",
  "#ec4899",
  "#14b8a6",
];

const SHORTAGE_LABEL: Record<string, { label: string; color: string }> = {
  S: { label: "Shortage", color: "#ef4444" },
  NS: { label: "No Shortage", color: C.green },
  MR: { label: "Met & Rising", color: C.amber },
};

// ── Sub-components ────────────────────────────────────────────

function StatBox({ label, value, sub, color }: any) {
  return (
    <div
      style={{
        background: "var(--surface-alt)",
        border: `1px solid ${C.border}`,
        borderRadius: 10,
        padding: "14px 16px",
        borderTop: `2px solid ${color}40`,
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
      <p
        style={{
          fontSize: 20,
          fontWeight: 800,
          color,
          lineHeight: 1,
          marginBottom: 4,
        }}
      >
        {value}
      </p>
      {sub && <p style={{ fontSize: 11, color: C.muted }}>{sub}</p>}
    </div>
  );
}

function SH({
  title,
  color = C.blue,
  sub,
}: {
  title: string;
  color?: string;
  sub?: string;
}) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: sub ? 2 : 0,
        }}
      >
        <div
          style={{ width: 3, height: 16, background: color, borderRadius: 2 }}
        />
        <p style={{ fontSize: 13, fontWeight: 700, color: C.text }}>{title}</p>
      </div>
      {sub && (
        <p style={{ fontSize: 10, color: C.muted, paddingLeft: 11 }}>{sub}</p>
      )}
    </div>
  );
}

function NoData({ msg }: { msg: string }) {
  return (
    <div style={{ padding: "28px 0", textAlign: "center" }}>
      <p style={{ fontSize: 12, color: C.muted }}>{msg}</p>
    </div>
  );
}

function MlBadge({ prob }: { prob: number }) {
  const p = prob ?? 0;
  const col = p >= 0.65 ? "#ef4444" : p >= 0.4 ? C.amber : C.green;
  const lbl = p >= 0.65 ? "High Risk" : p >= 0.4 ? "Medium" : "Low Risk";
  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 700,
        color: col,
        background: `${col}18`,
        padding: "2px 8px",
        borderRadius: 4,
        border: `1px solid ${col}40`,
      }}
    >
      {lbl} {(p * 100).toFixed(0)}%
    </span>
  );
}

// ── Main ──────────────────────────────────────────────────────

export default function OccupationDetail() {
  const { anzsco } = useParams<{ anzsco: string }>();
  const router = useRouter();

  const { get } = useDataCache();
  const [data, setData] = useState<any>(null);
  const [quota, setQuota] = useState<any>(null);
  const [nero, setNero] = useState<any>(null);
  const [neroSa4, setNeroSa4] = useState<any>(null);
  const [mlFcast, setMlFcast] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState("eoi");

  useEffect(() => {
    if (!anzsco) return;
    setLoading(true);
    const a4 = anzsco.slice(0, 4);
    Promise.allSettled([
      get(`/api/data/occupation/${anzsco}`),
      get(`/api/data/quota`),
      get(`/api/data/nero/${a4}`),
      get(`/api/data/nero-sa4/${a4}`),
      get(`/api/data/shortage-forecast/${a4}`),
    ])
      .then(([occ, q, n, ns, fc]) => {
        if (occ.status === "fulfilled") {
          if (occ.value.error) setError(occ.value.error);
          else setData(occ.value);
        }
        if (q.status === "fulfilled") {
          const lookup: Record<string, Record<string, number>> = {};
          for (const s of q.value.state_allocation || [])
            lookup[s.state] = { "190": s.visa_190, "491": s.visa_491 };
          setQuota(lookup);
        }
        if (n.status === "fulfilled" && !n.value.error) setNero(n.value);
        if (ns.status === "fulfilled" && !ns.value.error) setNeroSa4(ns.value);
        if (
          fc.status === "fulfilled" &&
          !fc.value.error &&
          fc.value.records?.length
        )
          setMlFcast(fc.value);
      })
      .finally(() => setLoading(false));
  }, [anzsco]);

  if (loading)
    return (
      <div
        style={{
          padding: 40,
          textAlign: "center",
          color: C.muted,
          fontSize: 14,
        }}
      >
        Loading occupation data…
      </div>
    );
  if (error || !data)
    return (
      <div style={{ padding: 40, textAlign: "center" }}>
        <p style={{ color: "#ef4444", marginBottom: 12 }}>
          Occupation not found: {anzsco}
        </p>
        <button
          onClick={() => router.push("/dashboard")}
          style={{
            background: C.blue,
            color: "#fff",
            border: "none",
            borderRadius: 6,
            padding: "8px 18px",
            cursor: "pointer",
            fontSize: 12,
          }}
        >
          ← Back
        </button>
      </div>
    );

  // ── Derived values ─────────────────────────────────────────
  const invRate = (data.invitation_rate || 0) * 100;
  const rateColor =
    invRate >= 50
      ? C.green
      : invRate >= 20
        ? C.blue
        : invRate >= 5
          ? C.amber
          : "#ef4444";
  const eoisub = data.eoi_summary || {};
  const uniqueStates = Array.from(
    new Map(
      (data.state_breakdown || []).map((s: any) => [s.state, s]),
    ).values(),
  );
  const openStates = uniqueStates.filter((s: any) => s.is_open);
  const shortage = data.shortage_data?.[0];
  const ssStyle = shortage
    ? SHORTAGE_LABEL[shortage.rating] || {
        label: shortage.rating,
        color: C.muted,
      }
    : null;
  const latestEmp = data.workforce?.[data.workforce.length - 1]?.employment;
  const proj2030 = data.employment_projection?.find(
    (p: any) => p.year === 2030,
  )?.change;
  const ageData = (data.demographics || []).filter(
    (d: any) => d.category === "Age group",
  );
  const genderData = (data.demographics || []).filter(
    (d: any) =>
      d.category?.toLowerCase().includes("sex") ||
      d.category?.toLowerCase().includes("gender"),
  );

  // ML forecast: build chart data — states as series, years as X
  const mlYears = ["2026", "2027", "2028", "2029", "2030"];
  const mlChartData = mlYears.map((yr) => {
    const row: any = { year: yr };
    for (const r of mlFcast?.records || []) row[r.state] = r[`prob_${yr}`];
    return row;
  });
  const mlStates = (mlFcast?.records || []).map((r: any) => r.state);

  const TABS = [
    { id: "eoi", label: "SkillSelect" },
    { id: "states", label: "States & Visa" },
    { id: "points", label: "Points" },
    { id: "workforce", label: "Workforce" },
    { id: "market", label: "Job Market" },
    { id: "demographics", label: "Demographics" },
    { id: "projection", label: "Projection" },
    { id: "ml", label: "ML Forecast" },
    { id: "nero", label: "Regional NERO" },
  ];

  return (
    <div
      suppressHydrationWarning
      style={{
        padding: "16px 14px",
        maxWidth: 1360,
        background: C.bg,
        minHeight: "100vh",
      }}
    >
      {/* Back */}
      <button
        onClick={() => router.back()}
        style={{
          background: "transparent",
          border: `1px solid ${C.border}`,
          borderRadius: 6,
          padding: "6px 14px",
          color: C.muted,
          fontSize: 12,
          cursor: "pointer",
          marginBottom: 18,
        }}
      >
        ← Back
      </button>

      {/* ── Header ────────────────────────────────────────── */}
      <div
        style={{
          background: C.surface,
          border: `1px solid ${C.border}`,
          borderRadius: 14,
          padding: "22px 24px",
          marginBottom: 20,
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            flexWrap: "wrap",
            gap: 12,
          }}
        >
          <div style={{ flex: 1 }}>
            {/* Badges */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                marginBottom: 8,
                flexWrap: "wrap",
              }}
            >
              <span
                style={{
                  fontFamily: "monospace",
                  fontSize: 11,
                  color: C.muted,
                  background: "var(--surface-alt)",
                  padding: "3px 8px",
                  borderRadius: 5,
                  border: `1px solid ${C.border}`,
                }}
              >
                ANZSCO {anzsco}
              </span>
              {data.visa_types?.map((v: string) => (
                <span
                  key={v}
                  style={{
                    background: `${VISA_COLORS[v] || C.muted}18`,
                    color: VISA_COLORS[v] || C.muted,
                    fontSize: 10,
                    fontWeight: 700,
                    padding: "3px 10px",
                    borderRadius: 5,
                    border: `1px solid ${VISA_COLORS[v] || C.muted}35`,
                  }}
                >
                  Visa {v}
                </span>
              ))}
              {ssStyle && (
                <span
                  style={{
                    background: `${ssStyle.color}18`,
                    color: ssStyle.color,
                    fontSize: 10,
                    fontWeight: 700,
                    padding: "3px 10px",
                    borderRadius: 5,
                    border: `1px solid ${ssStyle.color}40`,
                  }}
                >
                  ⚡ {ssStyle.label}
                </span>
              )}
              {mlFcast?.records?.[0] && (
                <MlBadge prob={mlFcast.records[0].prob_2026} />
              )}
              {data.osl_history?.length > 0 && (
                <span
                  style={{
                    fontSize: 10,
                    color: C.amber,
                    background: `${C.amber}15`,
                    padding: "3px 8px",
                    borderRadius: 5,
                    border: `1px solid ${C.amber}35`,
                  }}
                >
                  OSL {data.osl_history[0].skill_level_desc}
                </span>
              )}
            </div>
            <h1
              style={{
                fontSize: 22,
                fontWeight: 800,
                color: "var(--text)",
                letterSpacing: "-0.3px",
                marginBottom: 6,
              }}
            >
              {data.occupation_name}
            </h1>
            <p style={{ fontSize: 12, color: C.muted }}>
              {openStates.length} state{openStates.length !== 1 ? "s" : ""} open
              {latestEmp ? ` · ${fmt(latestEmp)} employed` : ""}
              {proj2030 ? ` · ${proj2030} growth to 2030` : ""}
              {data.osl_history?.length > 0 &&
                ` · OSL 2025: ${data.osl_history[data.osl_history.length - 1]?.national === 1 ? "National shortage" : "No national shortage"}`}
            </p>
          </div>

          {/* Invitation rate gauge */}
          <div style={{ textAlign: "center", minWidth: 90 }}>
            <div
              style={{
                position: "relative",
                width: 76,
                height: 76,
                margin: "0 auto 6px",
              }}
            >
              <svg width="76" height="76" viewBox="0 0 76 76">
                <circle
                  cx="38"
                  cy="38"
                  r="30"
                  fill="none"
                  stroke={C.border}
                  strokeWidth="6"
                />
                <circle
                  cx="38"
                  cy="38"
                  r="30"
                  fill="none"
                  stroke={rateColor}
                  strokeWidth="6"
                  strokeDasharray={`${Math.min(invRate, 100) * 1.885} 188.5`}
                  strokeDashoffset="47"
                  strokeLinecap="round"
                />
              </svg>
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <span
                  style={{ fontSize: 13, fontWeight: 800, color: rateColor }}
                >
                  {invRate.toFixed(0)}%
                </span>
              </div>
            </div>
            <p
              style={{
                fontSize: 10,
                color: C.muted,
                textTransform: "uppercase",
                letterSpacing: "0.07em",
              }}
            >
              Inv. Rate
            </p>
          </div>
        </div>
      </div>

      {/* ── KPI Row ───────────────────────────────────────── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 180px), 1fr))",
          gap: 10,
          marginBottom: 20,
        }}
      >
        <StatBox
          label="EOI Pool"
          value={fmt(data.pool_total)}
          sub="Last 12 months"
          color={C.blue}
        />
        <StatBox
          label="Invitations"
          value={fmt(data.invitations_total)}
          sub="Last 12 months"
          color={C.green}
        />
        <StatBox
          label="Open States"
          value={openStates.length}
          sub="Currently open"
          color={C.purple}
        />
        <StatBox
          label="Employed"
          value={latestEmp ? fmtK(latestEmp) : "—"}
          sub="Latest quarter"
          color={C.cyan}
        />
        <StatBox
          label="Growth 2030"
          value={proj2030 || "—"}
          sub="JSA projection"
          color={C.amber}
        />
        <StatBox
          label="JSA Shortage"
          value={ssStyle?.label || "—"}
          sub={shortage?.driver || "JSA assessment"}
          color={ssStyle?.color || C.muted}
        />
      </div>

      {/* ── Tabs ──────────────────────────────────────────── */}
      <div
        style={{
          marginBottom: 16,
          background: C.surface,
          border: `1px solid ${C.border}`,
          borderRadius: 8,
          padding: 4,
          overflowX: "auto",
          WebkitOverflowScrolling: "touch",
        }}
      >
        <div style={{ display: "flex", gap: 4, minWidth: "max-content", paddingRight: 20 }}>
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              style={{
                flexShrink: 0,
                padding: "8px 16px",
                borderRadius: 6,
                border: "none",
                cursor: "pointer",
                fontSize: 12,
                fontWeight: 600,
                transition: "all 0.15s",
                background: activeTab === t.id ? C.blue : "transparent",
                color: activeTab === t.id ? "#fff" : C.muted,
              }}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* ══ TAB: SkillSelect ══════════════════════════════════ */}
      {activeTab === "eoi" && (
        <div
          style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 400px), 1fr))", gap: 16 }}
        >
          {/* EOI Status breakdown */}
          <Card>
            <SH
              title="EOI Status Breakdown"
              color={C.blue}
              sub="Source: SkillSelect EOI snapshots · eoi_records"
            />
            {Object.keys(eoisub).length === 0 ? (
              <NoData msg="No EOI status data" />
            ) : (
              Object.entries(eoisub).map(([status, d]: any) => {
                const col =
                  status === "INVITED"
                    ? C.green
                    : status === "SUBMITTED"
                      ? C.blue
                      : status === "HOLD"
                        ? C.amber
                        : C.muted;
                return (
                  <div
                    key={status}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      padding: "10px 0",
                      borderBottom: `1px solid ${C.border}22`,
                    }}
                  >
                    <div
                      style={{ display: "flex", alignItems: "center", gap: 8 }}
                    >
                      <div
                        style={{
                          width: 8,
                          height: 8,
                          borderRadius: "50%",
                          background: col,
                        }}
                      />
                      <span
                        style={{ fontSize: 12, color: C.text, fontWeight: 500 }}
                      >
                        {status}
                      </span>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <p style={{ fontSize: 13, fontWeight: 700, color: col }}>
                        {fmt(d.total)}
                      </p>
                      <p style={{ fontSize: 10, color: C.muted }}>
                        {d.min_pts}–{d.max_pts} pts · avg {d.avg_pts}
                      </p>
                    </div>
                  </div>
                );
              })
            )}
          </Card>

          {/* Invitation rate by points */}
          <Card>
            <SH
              title="Invitation Rate by Points Score"
              color={C.green}
              sub="Invited ÷ Submitted per points band"
            />
            {data.points_distribution?.length === 0 ? (
              <NoData msg="No points data" />
            ) : (
              [65, 70, 75, 80, 85, 90, 95, 100, 105, 110].map((pts) => {
                const s =
                  data.points_distribution?.find((p: any) => p.points === pts)
                    ?.SUBMITTED || 0;
                const i =
                  data.points_distribution?.find((p: any) => p.points === pts)
                    ?.INVITED || 0;
                const r = s > 0 ? Math.min((i / s) * 100, 100) : 0;
                const col =
                  r >= 50
                    ? C.green
                    : r >= 20
                      ? C.blue
                      : r >= 5
                        ? C.amber
                        : C.border;
                if (s === 0 && i === 0) return null;
                return (
                  <div
                    key={pts}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      marginBottom: 7,
                    }}
                  >
                    <span
                      style={{
                        fontSize: 11,
                        color: C.muted,
                        width: 38,
                        textAlign: "right",
                      }}
                    >
                      {pts}pts
                    </span>
                    <div
                      style={{
                        flex: 1,
                        height: 5,
                        background: C.border,
                        borderRadius: 3,
                      }}
                    >
                      <div
                        style={{
                          width: `${r}%`,
                          height: "100%",
                          background: col,
                          borderRadius: 3,
                        }}
                      />
                    </div>
                    <span
                      style={{
                        fontSize: 11,
                        color: col,
                        width: 34,
                        textAlign: "right",
                        fontWeight: 600,
                      }}
                    >
                      {r > 0 ? `${r.toFixed(0)}%` : "—"}
                    </span>
                    <span style={{ fontSize: 10, color: C.muted, width: 52 }}>
                      {fmt(i)} inv
                    </span>
                  </div>
                );
              })
            )}
          </Card>

          {/* Monthly EOI trend */}
          <Card style={{ gridColumn: "1 / -1" }}>
            <SH
              title="Monthly EOI Pool & Invitations — All Time"
              color={C.cyan}
              sub="Source: eoi_records · All available snapshot months"
            />
            {data.monthly_trend?.length === 0 ? (
              <NoData msg="No monthly trend data" />
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart
                  data={data.monthly_trend?.slice(-18) || []}
                  margin={{ top: 4, right: 8, bottom: 0, left: -10 }}
                >
                  <defs>
                    <linearGradient id="gP" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={C.blue} stopOpacity={0.25} />
                      <stop offset="95%" stopColor={C.blue} stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="gI" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={C.green} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={C.green} stopOpacity={0} />
                    </linearGradient>
                  </defs>
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
                    tickFormatter={fmtK}
                  />
                  <Tooltip content={<ChartTip />} />
                  <Legend wrapperStyle={{ fontSize: 10 }} />
                  <Area
                    type="monotone"
                    dataKey="pool"
                    name="Pool"
                    stroke={C.blue}
                    fill="url(#gP)"
                    strokeWidth={2}
                    dot={false}
                  />
                  <Area
                    type="monotone"
                    dataKey="invitations"
                    name="Invited"
                    stroke={C.green}
                    fill="url(#gI)"
                    strokeWidth={2}
                    dot={{ r: 3, fill: C.green }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </Card>
        </div>
      )}

      {/* ══ TAB: States & Visa ════════════════════════════════ */}
      {activeTab === "states" && (
        <div>
          <Card style={{ marginBottom: 14 }}>
            <SH
              title="State & Visa Availability"
              color={C.purple}
              sub="Source: eoi_records — last 12 snapshot months"
            />
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 200px), 1fr))",
                gap: 10,
                marginBottom: 20,
              }}
            >
              {STATE_ORDER.map((state) => {
                const sd = (data.state_breakdown || []).filter(
                  (s: any) => s.state === state,
                );
                const isOpen = sd.some((s: any) => s.is_open);
                return (
                  <div
                    key={state}
                    style={{
                      background: isOpen ? `${C.green}10` : "var(--surface-alt)",
                      border: `1px solid ${isOpen ? C.green + "40" : C.border}`,
                      borderRadius: 10,
                      padding: "14px 16px",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginBottom: 8,
                      }}
                    >
                      <span
                        style={{
                          fontSize: 14,
                          fontWeight: 800,
                          color: isOpen ? C.green : C.muted,
                        }}
                      >
                        {state}
                      </span>
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          color: isOpen ? C.green : C.muted,
                          background: isOpen ? `${C.green}20` : `${C.muted}15`,
                          padding: "2px 7px",
                          borderRadius: 4,
                        }}
                      >
                        {isOpen ? "OPEN" : "CLOSED"}
                      </span>
                    </div>
                    {sd.map((s: any) => (
                      <div key={s.visa_type} style={{ marginBottom: 6 }}>
                        <span
                          style={{
                            fontSize: 10,
                            color: VISA_COLORS[s.visa_type] || C.muted,
                            fontWeight: 700,
                          }}
                        >
                          Visa {s.visa_type}
                        </span>
                        {s.is_open && (
                          <p style={{ fontSize: 10, color: C.amber }}>
                            {s.min_invited_points}–{s.max_invited_points} pts
                          </p>
                        )}
                        <p style={{ fontSize: 10, color: C.muted }}>
                          Pool {fmt(s.pool)} · Inv {fmt(s.invitations)}
                        </p>
                        {quota?.[state]?.[s.visa_type] && (
                          <p style={{ fontSize: 10, color: C.cyan }}>
                            Quota: {fmt(quota[state][s.visa_type])} slots
                          </p>
                        )}
                      </div>
                    ))}
                    {sd.length === 0 && (
                      <p style={{ fontSize: 11, color: C.muted }}>
                        No EOI data
                      </p>
                    )}
                  </div>
                );
              })}
            </div>

            {/* State pool bar chart */}
            {data.state_breakdown?.length > 0 &&
              (() => {
                const byState: Record<string, { pool: number; inv: number }> =
                  {};
                for (const s of data.state_breakdown) {
                  if (!byState[s.state]) byState[s.state] = { pool: 0, inv: 0 };
                  byState[s.state].pool += s.pool;
                  byState[s.state].inv += s.invitations;
                }
                const chartD = Object.entries(byState).map(([state, v]) => ({
                  state,
                  ...v,
                }));
                return (
                  <>
                    <SH
                      title="EOI Pool vs Invitations by State"
                      color={C.blue}
                    />
                    <ResponsiveContainer width="100%" height={180}>
                      <BarChart
                        data={chartD}
                        margin={{ top: 4, right: 8, bottom: 0, left: -10 }}
                      >
                        <CartesianGrid
                          strokeDasharray="3 3"
                          stroke={C.border}
                        />
                        <XAxis
                          dataKey="state"
                          tick={{ fill: C.muted, fontSize: 10 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          tick={{ fill: C.muted, fontSize: 9 }}
                          axisLine={false}
                          tickLine={false}
                          tickFormatter={fmtK}
                        />
                        <Tooltip content={<ChartTip />} />
                        <Legend wrapperStyle={{ fontSize: 10 }} />
                        <Bar
                          dataKey="pool"
                          name="Pool"
                          fill={`${C.blue}80`}
                          radius={[3, 3, 0, 0]}
                        />
                        <Bar
                          dataKey="inv"
                          name="Invitations"
                          fill={C.green}
                          radius={[3, 3, 0, 0]}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </>
                );
              })()}
          </Card>

          {/* Top regions */}
          {data.top_regions?.length > 0 && (
            <Card>
              <SH
                title="Top SA4 Regions by Employment"
                color={C.cyan}
                sub="Source: jsa_top10 · Employment category"
              />
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 400px), 1fr))",
                  gap: 8,
                }}
              >
                {data.top_regions.map((r: any) => (
                  <div
                    key={`${r.rank}-${r.region}`}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      padding: "8px 12px",
                      background: "var(--surface-alt)",
                      borderRadius: 8,
                    }}
                  >
                    <span
                      style={{
                        fontSize: 11,
                        fontWeight: 800,
                        color: r.rank <= 3 ? C.amber : C.muted,
                        width: 22,
                      }}
                    >
                      #{r.rank}
                    </span>
                    <div style={{ flex: 1 }}>
                      <div
                        style={{
                          height: 3,
                          background: C.border,
                          borderRadius: 2,
                          marginBottom: 3,
                        }}
                      >
                        <div
                          style={{
                            width: `${(r.value / (data.top_regions[0]?.value || 1)) * 100}%`,
                            height: "100%",
                            background: C.green,
                            borderRadius: 2,
                          }}
                        />
                      </div>
                      <span style={{ fontSize: 11, color: C.text }}>
                        {r.region}
                      </span>
                    </div>
                    <span
                      style={{ fontSize: 12, fontWeight: 700, color: C.green }}
                    >
                      {fmt(r.value)}
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}

      {/* ══ TAB: Points ════════════════════════════════════════ */}
      {activeTab === "points" && (
        <Card>
          <SH
            title="Points Distribution — Submitted vs Invited"
            color={C.purple}
            sub="Source: eoi_records · Latest year · All states"
          />
          {data.points_distribution?.length > 0 ? (
            <ResponsiveContainer width="100%" height={340}>
              <BarChart
                data={data.points_distribution}
                margin={{ top: 4, right: 8, bottom: 0, left: -10 }}
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
                  tickFormatter={fmtK}
                />
                <Tooltip content={<ChartTip />} />
                <Legend wrapperStyle={{ fontSize: 10 }} />
                <Bar
                  dataKey="SUBMITTED"
                  name="Submitted"
                  fill={`${C.blue}70`}
                  radius={[3, 3, 0, 0]}
                />
                <Bar
                  dataKey="INVITED"
                  name="Invited"
                  fill={C.green}
                  radius={[3, 3, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <NoData msg="No points distribution data" />
          )}
        </Card>
      )}

      {/* ══ TAB: Workforce ════════════════════════════════════ */}
      {activeTab === "workforce" && (
        <div
          style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 400px), 1fr))", gap: 16 }}
        >
          {/* Employment trend */}
          <Card style={{ gridColumn: "1 / -1" }}>
            <SH
              title="Employment Trend (Quarterly)"
              color={C.cyan}
              sub="Source: jsa_quarterly_employment"
            />
            {data.workforce?.length > 0 ? (
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart
                  data={data.workforce}
                  margin={{ top: 4, right: 8, bottom: 0, left: -10 }}
                >
                  <defs>
                    <linearGradient id="gE" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={C.cyan} stopOpacity={0.25} />
                      <stop offset="95%" stopColor={C.cyan} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                  <XAxis
                    dataKey="quarter"
                    tick={{ fill: C.muted, fontSize: 9 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fill: C.muted, fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={fmtK}
                  />
                  <Tooltip content={<ChartTip />} />
                  <Area
                    type="monotone"
                    dataKey="employment"
                    name="Employed"
                    stroke={C.cyan}
                    fill="url(#gE)"
                    strokeWidth={2}
                    dot={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <NoData msg="No employment data — run jsa_ingestor.py" />
            )}
          </Card>

          {/* Recruitment */}
          <Card>
            <SH
              title="Recruitment Insights"
              color="#ef4444"
              sub="Source: jsa_recruitment"
            />
            {data.recruitment ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {[
                  {
                    label: "Vacancies Filled",
                    value: pct(data.recruitment.filled_vacancies || 0),
                    color:
                      data.recruitment.filled_vacancies > 0.7
                        ? C.green
                        : C.amber,
                  },
                  {
                    label: "Avg Applicants/Vacancy",
                    value: (data.recruitment.avg_applicants || 0).toFixed(1),
                    color: C.blue,
                  },
                  {
                    label: "Avg Qualified",
                    value: (data.recruitment.avg_qualified || 0).toFixed(1),
                    color: C.purple,
                  },
                  {
                    label: "Avg Suitable",
                    value: (data.recruitment.avg_suitable || 0).toFixed(1),
                    color: C.cyan,
                  },
                  {
                    label: "Avg Experience Req'd",
                    value: `${(data.recruitment.avg_experience || 0).toFixed(1)} yrs`,
                    color: C.amber,
                  },
                  {
                    label: "Require Experience",
                    value: pct(data.recruitment.pct_require_exp || 0),
                    color: "#ef4444",
                  },
                ].map((item) => (
                  <div
                    key={item.label}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      padding: "8px 0",
                      borderBottom: `1px solid ${C.border}22`,
                    }}
                  >
                    <span style={{ fontSize: 12, color: C.muted }}>
                      {item.label}
                    </span>
                    <span
                      style={{
                        fontSize: 14,
                        fontWeight: 700,
                        color: item.color,
                      }}
                    >
                      {item.value}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <NoData msg="No recruitment data available for this occupation in JSA source" />
            )}
          </Card>

          {/* Education */}
          <Card>
            <SH
              title="Main Education Fields"
              color={C.purple}
              sub="Source: jsa_education"
            />
            {data.education?.length > 0 ? (
              data.education.slice(0, 8).map((e: any, i: number) => (
                <div key={i} style={{ marginBottom: 10 }}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      marginBottom: 3,
                    }}
                  >
                    <span
                      style={{ fontSize: 11, color: C.text, maxWidth: "75%" }}
                    >
                      {e.field}
                    </span>
                    <span style={{ fontSize: 11, color: C.muted }}>
                      {pct(e.share)}
                    </span>
                  </div>
                  <div
                    style={{ height: 4, background: C.border, borderRadius: 2 }}
                  >
                    <div
                      style={{
                        width: pct(e.share),
                        height: "100%",
                        background: PALETTE[i % PALETTE.length],
                        borderRadius: 2,
                      }}
                    />
                  </div>
                  <p style={{ fontSize: 9, color: C.muted, marginTop: 2 }}>
                    {e.level}
                  </p>
                </div>
              ))
            ) : (
              <NoData msg="No education data — run jsa_ingestor.py" />
            )}
          </Card>
        </div>
      )}

      {/* ══ TAB: Job Market ════════════════════════════════════ */}
      {activeTab === "market" && (
        <div
          style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 400px), 1fr))", gap: 16 }}
        >
          {/* Job ads */}
          <Card style={{ gridColumn: "1 / -1" }}>
            <SH
              title="Job Advertisements (Monthly, Last 24 Months)"
              color={C.blue}
              sub="Source: jsa_monthly_ads"
            />
            {data.job_vacancies?.length > 0 ? (
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart
                  data={data.job_vacancies}
                  margin={{ top: 4, right: 8, bottom: 0, left: -10 }}
                >
                  <defs>
                    <linearGradient id="gJ" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={C.blue} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={C.blue} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: C.muted, fontSize: 9 }}
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
                    dataKey="job_ads"
                    name="Job Ads"
                    stroke={C.blue}
                    fill="url(#gJ)"
                    strokeWidth={2}
                    dot={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <NoData msg="No job ads data — run jsa_ingestor.py" />
            )}
          </Card>

          {/* Shortage status */}
          <Card>
            <SH
              title="JSA Shortage Assessment"
              color="#ef4444"
              sub="Source: jsa_shortage"
            />
            {data.shortage_data?.length > 0 ? (
              data.shortage_data.map((s: any) => {
                const ss = SHORTAGE_LABEL[s.rating] || {
                  label: s.rating,
                  color: C.muted,
                };
                return (
                  <div
                    key={s.anzsco_code}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "flex-start",
                      padding: "10px 0",
                      borderBottom: `1px solid ${C.border}22`,
                    }}
                  >
                    <div>
                      <p style={{ fontSize: 12, color: C.text }}>{s.name}</p>
                      <p style={{ fontSize: 10, color: C.muted }}>
                        {s.anzsco_code} · {s.driver || "—"}
                      </p>
                    </div>
                    <span
                      style={{
                        fontSize: 11,
                        fontWeight: 700,
                        color: ss.color,
                        background: `${ss.color}18`,
                        padding: "3px 10px",
                        borderRadius: 5,
                        border: `1px solid ${ss.color}35`,
                        whiteSpace: "nowrap",
                      }}
                    >
                      {ss.label}
                    </span>
                  </div>
                );
              })
            ) : (
              <NoData msg="No shortage data — run jsa_ingestor.py" />
            )}
          </Card>

          {/* Top hiring regions */}
          <Card>
            <SH
              title="Top Hiring Regions (SA4)"
              color={C.green}
              sub="Source: jsa_top10 · Employment category"
            />
            {data.top_regions?.length > 0 ? (
              data.top_regions.map((r: any) => (
                <div
                  key={r.rank}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "8px 0",
                    borderBottom: `1px solid ${C.border}22`,
                  }}
                >
                  <span
                    style={{
                      fontSize: 12,
                      fontWeight: 800,
                      color: r.rank <= 3 ? C.amber : C.muted,
                      width: 24,
                    }}
                  >
                    #{r.rank}
                  </span>
                  <div style={{ flex: 1 }}>
                    <div
                      style={{
                        height: 3,
                        background: C.border,
                        borderRadius: 2,
                        marginBottom: 3,
                      }}
                    >
                      <div
                        style={{
                          width: `${(r.value / (data.top_regions[0]?.value || 1)) * 100}%`,
                          height: "100%",
                          background: C.green,
                          borderRadius: 2,
                        }}
                      />
                    </div>
                    <span style={{ fontSize: 12, color: C.text }}>
                      {r.region}
                    </span>
                  </div>
                  <span
                    style={{ fontSize: 12, fontWeight: 700, color: C.green }}
                  >
                    {fmt(r.value)}
                  </span>
                </div>
              ))
            ) : (
              <NoData msg="No regional data — run jsa_ingestor.py" />
            )}
          </Card>
        </div>
      )}

      {/* ══ TAB: Demographics ══════════════════════════════════ */}
      {activeTab === "demographics" && (
        <div
          style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 400px), 1fr))", gap: 16 }}
        >
          {/* Age */}
          <Card>
            <SH
              title="Age Group Distribution"
              color={C.purple}
              sub="Source: jsa_demographics"
            />
            {ageData.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart
                  data={ageData}
                  layout="vertical"
                  margin={{ top: 0, right: 50, bottom: 0, left: 10 }}
                >
                  <XAxis
                    type="number"
                    domain={[0, 0.5]}
                    tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                    tick={{ fill: C.muted, fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    type="category"
                    dataKey="segment"
                    width={60}
                    tick={{ fill: C.muted, fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    formatter={(v: any) => `${(+v * 100).toFixed(1)}%`}
                    contentStyle={{
                      background: C.surface,
                      border: `1px solid ${C.border}`,
                      borderRadius: 6,
                      fontSize: 11,
                    }}
                  />
                  <Bar dataKey="share" name="Share" radius={[0, 4, 4, 0]}>
                    {ageData.map((_: any, i: number) => (
                      <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <NoData msg="No age data — run jsa_ingestor.py" />
            )}
          </Card>

          {/* Gender */}
          <Card>
            <SH
              title="Gender Distribution"
              color={C.cyan}
              sub="Source: jsa_demographics"
            />
            {genderData.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie
                    data={genderData}
                    dataKey="share"
                    nameKey="segment"
                    cx="50%"
                    cy="50%"
                    outerRadius={100}
                    label={({ name, value }: any) =>
                      `${name} ${(value * 100).toFixed(0)}%`
                    }
                  >
                    {genderData.map((_: any, i: number) => (
                      <Cell key={i} fill={PALETTE[i]} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(v: any) => `${(+v * 100).toFixed(1)}%`}
                    contentStyle={{
                      background: C.surface,
                      border: `1px solid ${C.border}`,
                      borderRadius: 6,
                      fontSize: 11,
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : data.demographics?.length > 0 ? (
              <div>
                {(data.demographics || [])
                  .slice(0, 12)
                  .map((d: any, i: number) => (
                    <div
                      key={i}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        padding: "6px 0",
                        borderBottom: `1px solid ${C.border}22`,
                      }}
                    >
                      <span style={{ fontSize: 11, color: C.muted }}>
                        {d.category} · {d.segment}
                      </span>
                      <span
                        style={{
                          fontSize: 11,
                          fontWeight: 700,
                          color: PALETTE[i % PALETTE.length],
                        }}
                      >
                        {pct(d.share)}
                      </span>
                    </div>
                  ))}
              </div>
            ) : (
              <NoData msg="No gender data — run jsa_ingestor.py" />
            )}
          </Card>

          {/* Education full grid */}
          {data.education?.length > 0 && (
            <Card style={{ gridColumn: "1 / -1" }}>
              <SH
                title="Education Fields & Levels"
                color={C.amber}
                sub="Source: jsa_education"
              />
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 300px), 1fr))",
                  gap: 8,
                }}
              >
                {data.education.map((e: any, i: number) => (
                  <div
                    key={i}
                    style={{
                      padding: "10px 14px",
                      background: "var(--surface-alt)",
                      borderRadius: 8,
                      borderLeft: `3px solid ${PALETTE[i % PALETTE.length]}`,
                    }}
                  >
                    <p
                      style={{
                        fontSize: 12,
                        color: C.text,
                        fontWeight: 600,
                        marginBottom: 3,
                      }}
                    >
                      {e.field}
                    </p>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                      }}
                    >
                      <span style={{ fontSize: 10, color: C.muted }}>
                        {e.level}
                      </span>
                      <span
                        style={{
                          fontSize: 11,
                          fontWeight: 700,
                          color: PALETTE[i % PALETTE.length],
                        }}
                      >
                        {pct(e.share)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}

      {/* ══ TAB: Projection ════════════════════════════════════ */}
      {activeTab === "projection" && (
        <div
          style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 400px), 1fr))", gap: 16 }}
        >
          {/* Employment projection */}
          <Card>
            <SH
              title="Employment Growth Projection (JSA)"
              color={C.green}
              sub="Source: jsa_projected"
            />
            {data.employment_projection?.length > 0 ? (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 14,
                  marginTop: 8,
                }}
              >
                {data.employment_projection.map((p: any) => {
                  const val = parseFloat(p.change?.replace("%", "") || "0");
                  const col =
                    val >= 15
                      ? C.green
                      : val >= 5
                        ? C.blue
                        : val < 0
                          ? "#ef4444"
                          : C.amber;
                  return (
                    <div
                      key={`${p.year}-${p.group}`}
                      style={{
                        background: "var(--surface-alt)",
                        border: `1px solid ${C.border}`,
                        borderRadius: 12,
                        padding: "18px 22px",
                      }}
                    >
                      <p
                        style={{
                          fontSize: 10,
                          color: C.muted,
                          marginBottom: 4,
                        }}
                      >
                        By {p.year}
                      </p>
                      <p
                        style={{
                          fontSize: 38,
                          fontWeight: 900,
                          color: col,
                          lineHeight: 1,
                        }}
                      >
                        {p.change}
                      </p>
                      <p style={{ fontSize: 10, color: C.muted, marginTop: 5 }}>
                        Projected change · {p.group}
                      </p>
                      <div
                        style={{
                          marginTop: 8,
                          height: 5,
                          background: C.border,
                          borderRadius: 3,
                        }}
                      >
                        <div
                          style={{
                            width: `${Math.min(Math.abs(val) * 2, 100)}%`,
                            height: "100%",
                            background: col,
                            borderRadius: 3,
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <NoData msg="No projection data — run jsa_ingestor.py" />
            )}
          </Card>

          {/* JSA shortage detail */}
          <Card>
            <SH
              title="JSA Shortage Assessment Detail"
              color="#ef4444"
              sub="Source: jsa_shortage"
            />
            {data.shortage_data?.length > 0 ? (
              data.shortage_data.map((s: any) => {
                const ss = SHORTAGE_LABEL[s.rating] || {
                  label: s.rating,
                  color: C.muted,
                };
                return (
                  <div
                    key={s.anzsco_code}
                    style={{
                      background: "var(--surface-alt)",
                      border: `1px solid ${ss.color}30`,
                      borderRadius: 10,
                      padding: 16,
                      marginBottom: 10,
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        marginBottom: 8,
                      }}
                    >
                      <div>
                        <p
                          style={{
                            fontSize: 12,
                            color: C.text,
                            fontWeight: 600,
                          }}
                        >
                          {s.name}
                        </p>
                        <p style={{ fontSize: 10, color: C.muted }}>
                          ANZSCO {s.anzsco_code}
                        </p>
                      </div>
                      <span
                        style={{
                          fontSize: 13,
                          fontWeight: 800,
                          color: ss.color,
                        }}
                      >
                        {ss.label}
                      </span>
                    </div>
                    {s.driver && (
                      <div
                        style={{
                          background: `${ss.color}10`,
                          borderRadius: 6,
                          padding: "6px 10px",
                        }}
                      >
                        <p style={{ fontSize: 11, color: ss.color }}>
                          Driver: {s.driver}
                        </p>
                      </div>
                    )}
                  </div>
                );
              })
            ) : (
              <NoData msg="No shortage data — run jsa_ingestor.py" />
            )}
          </Card>

          {/* OSL history table — full width */}
          {data.osl_history?.length > 0 && (
            <Card style={{ gridColumn: "1 / -1" }}>
              <SH
                title="DEWR Occupation Shortage List (OSL) — 2021 to 2025"
                color={C.amber}
                sub={`Source: osl_shortage · Skill Level ${data.osl_history[0]?.skill_level} — ${data.osl_history[0]?.skill_level_desc}`}
              />
              <div style={{ overflowX: "auto" }}>
                <table
                  style={{
                    width: "100%",
                    borderCollapse: "collapse",
                    fontSize: 11,
                  }}
                >
                  <thead>
                    <tr>
                      {[
                        "Year",
                        "National",
                        "NSW",
                        "VIC",
                        "QLD",
                        "SA",
                        "WA",
                        "TAS",
                        "NT",
                        "ACT",
                        "States in Shortage",
                      ].map((h) => (
                        <th
                          key={h}
                          style={{
                            padding: "6px 10px",
                            textAlign: "center",
                            color: C.muted,
                            fontWeight: 700,
                            textTransform: "uppercase",
                            letterSpacing: "0.06em",
                            fontSize: 9,
                            borderBottom: `1px solid ${C.border}`,
                          }}
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.osl_history.map((row: any, i: number) => {
                      const natCol = row.national === 1 ? "#ef4444" : C.green;
                      return (
                        <tr
                          key={row.year}
                          style={{
                            background: i % 2 === 0 ? "transparent" : "var(--surface-alt)",
                          }}
                        >
                          <td
                            style={{
                              padding: "8px 10px",
                              textAlign: "center",
                              fontWeight: 700,
                              color: C.text,
                            }}
                          >
                            {row.year}
                          </td>
                          <td
                            style={{ padding: "8px 10px", textAlign: "center" }}
                          >
                            <span
                              style={{
                                fontSize: 14,
                                color: natCol,
                                fontWeight: 800,
                              }}
                            >
                              {row.national === 1 ? "●" : "○"}
                            </span>
                          </td>
                          {[
                            "NSW",
                            "VIC",
                            "QLD",
                            "SA",
                            "WA",
                            "TAS",
                            "NT",
                            "ACT",
                          ].map((s) => {
                            const val = row[s];
                            const col =
                              val === 1
                                ? "#ef4444"
                                : val === 0
                                  ? C.muted
                                  : C.muted;
                            return (
                              <td
                                key={s}
                                style={{
                                  padding: "8px 10px",
                                  textAlign: "center",
                                }}
                              >
                                <span
                                  style={{
                                    fontSize: 13,
                                    color: col,
                                    fontWeight: val === 1 ? 700 : 400,
                                    opacity: val === 0 ? 0.3 : 1,
                                  }}
                                >
                                  {val === 1 ? "●" : "○"}
                                </span>
                              </td>
                            );
                          })}
                          <td
                            style={{ padding: "8px 10px", textAlign: "center" }}
                          >
                            <span
                              style={{
                                fontSize: 12,
                                fontWeight: 700,
                                color:
                                  (row.shortage_state_count || 0) >= 6
                                    ? "#ef4444"
                                    : (row.shortage_state_count || 0) >= 3
                                      ? C.amber
                                      : C.muted,
                              }}
                            >
                              {row.shortage_state_count || 0}/8
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </div>
      )}

      {/* ══ TAB: ML Forecast ═══════════════════════════════════ */}
      {activeTab === "ml" && (
        <div
          style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 400px), 1fr))", gap: 16 }}
        >
          {!mlFcast ? (
            <Card style={{ gridColumn: "1 / -1" }}>
              <NoData
                msg={`No ML forecast data for ANZSCO4 ${anzsco?.slice(0, 4)} — run shortage_forecast_ingestor.py`}
              />
            </Card>
          ) : (
            <>
              {/* State forecast line chart */}
              <Card style={{ gridColumn: "1 / -1" }}>
                <SH
                  title="ML Shortage Probability by State — 2026 to 2030"
                  color={C.purple}
                  sub="Source: shortage_forecast · RandomForest model · Values = probability of shortage"
                />
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart
                    data={mlChartData}
                    margin={{ top: 4, right: 16, bottom: 0, left: -10 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                    <XAxis
                      dataKey="year"
                      tick={{ fill: C.muted, fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      domain={[0, 1]}
                      tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                      tick={{ fill: C.muted, fontSize: 10 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      formatter={(v: any, name: any) => [
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
                    <Legend wrapperStyle={{ fontSize: 10 }} />
                    {mlStates.map((state: string) => (
                      <Line
                        key={state}
                        type="monotone"
                        dataKey={state}
                        name={state}
                        stroke={STATE_COLORS[state] || C.muted}
                        strokeWidth={2}
                        dot={{
                          r: 4,
                          fill: STATE_COLORS[state] || C.muted,
                          stroke: "none",
                        }}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </Card>

              {/* 2026 snapshot bars */}
              <Card>
                <SH
                  title="2026 Shortage Risk by State"
                  color={C.purple}
                  sub="Probability of shortage in 2026 · Source: shortage_forecast"
                />
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 8,
                    marginTop: 4,
                  }}
                >
                  {mlFcast.records
                    .slice()
                    .sort((a: any, b: any) => b.prob_2026 - a.prob_2026)
                    .map((r: any) => {
                      const p = r.prob_2026;
                      const col =
                        p >= 0.65 ? "#ef4444" : p >= 0.4 ? C.amber : C.green;
                      return (
                        <div key={r.state}>
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              marginBottom: 3,
                            }}
                          >
                            <span
                              style={{
                                fontSize: 12,
                                fontWeight: 700,
                                color: STATE_COLORS[r.state] || C.muted,
                              }}
                            >
                              {r.state}
                            </span>
                            <div
                              style={{
                                display: "flex",
                                alignItems: "center",
                                gap: 8,
                              }}
                            >
                              <MlBadge prob={p} />
                              <span
                                style={{
                                  fontSize: 12,
                                  fontWeight: 800,
                                  color: col,
                                }}
                              >
                                {(p * 100).toFixed(1)}%
                              </span>
                            </div>
                          </div>
                          <div
                            style={{
                              height: 5,
                              background: C.border,
                              borderRadius: 3,
                            }}
                          >
                            <div
                              style={{
                                width: `${p * 100}%`,
                                height: "100%",
                                background: col,
                                borderRadius: 3,
                              }}
                            />
                          </div>
                        </div>
                      );
                    })}
                </div>
              </Card>

              {/* 5-year trend table */}
              <Card>
                <SH
                  title="5-Year Forecast Table"
                  color={C.blue}
                  sub="Shortage probability per state per year"
                />
                <div style={{ overflowX: "auto", width: "100%", WebkitOverflowScrolling: "touch" }}>
                  <table
                    style={{
                      width: "100%",
                      minWidth: "600px",
                      borderCollapse: "collapse",
                      fontSize: 11,
                    }}
                  >
                    <thead>
                      <tr>
                        {[
                          "Occupation",
                          "State",
                          "2026",
                          "2027",
                          "2028",
                          "2029",
                          "2030",
                          "Trend",
                        ].map((h) => (
                          <th
                            key={h}
                            style={{
                              padding: "10px 12px",
                              textAlign: h === "State" ? "left" : "center",
                              color: C.muted,
                              fontWeight: 700,
                              textTransform: "uppercase",
                              letterSpacing: "0.06em",
                              fontSize: 9,
                              borderBottom: `1px solid ${C.border}`,
                              whiteSpace: "nowrap",
                            }}
                          >
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {mlFcast.records.map((r: any, i: number) => {
                        const delta = r.prob_2030 - r.prob_2026;
                        const trendCol =
                          delta > 0.05
                            ? "#ef4444"
                            : delta < -0.05
                              ? C.green
                              : C.muted;
                        const trendArrow =
                          delta > 0.05 ? "↑" : delta < -0.05 ? "↓" : "→";
                        return (
                          <tr
                            key={r.state}
                            style={{
                              background: i % 2 === 0 ? "transparent" : "var(--surface-alt)",
                            }}
                          >
                            <td
                              style={{
                                padding: "10px 12px",
                                fontWeight: 700,
                                color: C.text,
                                whiteSpace: "nowrap",
                              }}
                            >
                              {r.occupation || "—"}
                            </td>
                            <td
                              style={{
                                padding: "10px 12px",
                                fontWeight: 700,
                                color: STATE_COLORS[r.state] || C.muted,
                                whiteSpace: "nowrap",
                              }}
                            >
                              {r.state}
                            </td>
                            {["2026", "2027", "2028", "2029", "2030"].map(
                              (yr) => {
                                const val = r[`prob_${yr}`];
                                const col =
                                  val >= 0.65
                                    ? "#ef4444"
                                    : val >= 0.4
                                      ? C.amber
                                      : C.green;
                                return (
                                  <td
                                    key={yr}
                                    style={{
                                      padding: "10px 12px",
                                      textAlign: "center",
                                      whiteSpace: "nowrap",
                                    }}
                                  >
                                    <span
                                      style={{
                                        fontSize: 11,
                                        fontWeight: 700,
                                        color: col,
                                      }}
                                    >
                                      {(val * 100).toFixed(0)}%
                                    </span>
                                  </td>
                                );
                              },
                            )}
                            <td
                              style={{
                                padding: "10px 12px",
                                textAlign: "center",
                                fontSize: 14,
                                fontWeight: 800,
                                color: trendCol,
                                whiteSpace: "nowrap",
                              }}
                            >
                              {trendArrow}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </Card>
            </>
          )}
        </div>
      )}

      {/* ══ TAB: Regional NERO ════════════════════════════════ */}
      {activeTab === "nero" && (
        <div>
          {!nero ? (
            <Card>
              <NoData
                msg={`No NERO data for ANZSCO4 ${anzsco?.slice(0, 4)} — run nero_ingestor.py`}
              />
            </Card>
          ) : (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 400px), 1fr))",
                gap: 16,
              }}
            >
              {/* NERO summary stats + trend */}
              <Card style={{ gridColumn: "1 / -1" }}>
                <SH
                  title={`NERO — Regional vs Major City (${nero.latest_date || "latest"})`}
                  color={C.blue}
                  sub="Source: nero_regional — employment estimates by remoteness"
                />
                <div
                  style={{
                    display: "flex",
                    gap: 14,
                    marginBottom: 16,
                    flexWrap: "wrap",
                  }}
                >
                  {[
                    {
                      label: "Regional (latest)",
                      value: nero.latest_regional?.["Regional"],
                      yoy: nero.yoy_regional,
                      color: C.green,
                    },
                    {
                      label: "Major City (latest)",
                      value: nero.latest_regional?.["Major City"],
                      yoy: nero.yoy_major_city,
                      color: C.blue,
                    },
                    {
                      label: "Northern AU (latest)",
                      value: nero.latest_northern?.nero_estimate,
                      yoy: null,
                      color: C.amber,
                    },
                  ].map((k) => (
                    <div
                      key={k.label}
                      style={{
                        padding: "10px 16px",
                        background: `${k.color}10`,
                        border: `1px solid ${k.color}30`,
                        borderRadius: 8,
                        minWidth: 160,
                      }}
                    >
                      <p
                        style={{
                          fontSize: 10,
                          color: C.muted,
                          marginBottom: 4,
                        }}
                      >
                        {k.label}
                      </p>
                      <p
                        style={{
                          fontSize: 20,
                          fontWeight: 800,
                          color: k.color,
                        }}
                      >
                        {k.value ? fmt(k.value) : "—"}
                      </p>
                      {k.yoy != null && (
                        <p
                          style={{
                            fontSize: 10,
                            color: k.yoy >= 0 ? C.green : "#ef4444",
                            marginTop: 3,
                          }}
                        >
                          {k.yoy >= 0 ? "▲" : "▼"} {Math.abs(k.yoy)}% YoY
                        </p>
                      )}
                    </div>
                  ))}
                </div>
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart
                    data={nero.regional_trend || []}
                    margin={{ top: 4, right: 8, bottom: 0, left: -10 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                    <XAxis
                      dataKey="date"
                      tick={{ fill: C.muted, fontSize: 9 }}
                      axisLine={false}
                      tickLine={false}
                      tickFormatter={(v: string) => v?.slice(0, 7)}
                      interval={5}
                    />
                    <YAxis
                      tick={{ fill: C.muted, fontSize: 9 }}
                      axisLine={false}
                      tickLine={false}
                      tickFormatter={(v: number) =>
                        v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v)
                      }
                    />
                    <Tooltip content={<ChartTip />} />
                    <Legend wrapperStyle={{ fontSize: 10 }} />
                    <Line
                      type="monotone"
                      dataKey="Regional"
                      name="Regional"
                      stroke={C.green}
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="Major City"
                      name="Major City"
                      stroke={C.blue}
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </Card>

              {/* Northern AU */}
              <Card>
                <SH
                  title="Northern Australia NERO Trend"
                  color={C.amber}
                  sub="Source: nero_northern"
                />
                <ResponsiveContainer width="100%" height={200}>
                  <AreaChart
                    data={nero.northern_trend || []}
                    margin={{ top: 4, right: 8, bottom: 0, left: -10 }}
                  >
                    <defs>
                      <linearGradient id="gNorth" x1="0" y1="0" x2="0" y2="1">
                        <stop
                          offset="5%"
                          stopColor={C.amber}
                          stopOpacity={0.3}
                        />
                        <stop
                          offset="95%"
                          stopColor={C.amber}
                          stopOpacity={0}
                        />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                    <XAxis
                      dataKey="date"
                      tick={{ fill: C.muted, fontSize: 9 }}
                      axisLine={false}
                      tickLine={false}
                      tickFormatter={(v: string) => v?.slice(0, 7)}
                      interval={5}
                    />
                    <YAxis
                      tick={{ fill: C.muted, fontSize: 9 }}
                      axisLine={false}
                      tickLine={false}
                      tickFormatter={(v: number) =>
                        v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v)
                      }
                    />
                    <Tooltip content={<ChartTip />} />
                    <Area
                      type="monotone"
                      dataKey="nero_estimate"
                      name="Northern AU"
                      stroke={C.amber}
                      fill="url(#gNorth)"
                      strokeWidth={2}
                      dot={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </Card>

              {/* SA4 by state */}
              <Card>
                <SH
                  title="Employment by State (SA4 Level)"
                  color={C.purple}
                  sub={`Source: nero_sa4 · ${neroSa4?.latest_date || ""} · Total: ${fmt(neroSa4?.total_employment || 0)}`}
                />
                {neroSa4?.by_state?.length > 0 ? (
                  <div
                    style={{ display: "flex", flexDirection: "column", gap: 6 }}
                  >
                    {neroSa4.by_state.map((s: any) => {
                      const sp =
                        neroSa4.total_employment > 0
                          ? (s.nsc_emp / neroSa4.total_employment) * 100
                          : 0;
                      const col = STATE_COLORS[s.state] || C.muted;
                      return (
                        <div key={s.state}>
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              marginBottom: 3,
                            }}
                          >
                            <span
                              style={{
                                fontSize: 11,
                                color: col,
                                fontWeight: 700,
                              }}
                            >
                              {s.state}
                            </span>
                            <span style={{ fontSize: 11, color: C.text }}>
                              {fmt(s.nsc_emp)}{" "}
                              <span style={{ color: C.muted }}>
                                ({sp.toFixed(1)}%)
                              </span>
                            </span>
                          </div>
                          <div
                            style={{
                              height: 4,
                              background: C.border,
                              borderRadius: 2,
                              marginBottom: 4,
                            }}
                          >
                            <div
                              style={{
                                width: `${sp}%`,
                                height: "100%",
                                background: col,
                                borderRadius: 2,
                              }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <NoData msg="No SA4 data — run nero_sa4_ingestor.py" />
                )}
              </Card>

              {/* Top SA4 regions */}
              {neroSa4?.by_sa4?.length > 0 && (
                <Card style={{ gridColumn: "1 / -1" }}>
                  <SH
                    title={`Top SA4 Regions — ${neroSa4.latest_date}`}
                    color={C.cyan}
                    sub="Source: nero_sa4 · Top 12 regions by employment"
                  />
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 200px), 1fr))",
                      gap: 8,
                    }}
                  >
                    {neroSa4.by_sa4.slice(0, 12).map((r: any, i: number) => {
                      const col = STATE_COLORS[r.state] || C.muted;
                      const rp =
                        neroSa4.total_employment > 0
                          ? (r.nsc_emp / neroSa4.total_employment) * 100
                          : 0;
                      return (
                        <div
                          key={`${r.sa4_code}-${i}`}
                          style={{
                            padding: "10px 12px",
                            background: `${col}08`,
                            border: `1px solid ${col}25`,
                            borderRadius: 8,
                            borderLeft: `3px solid ${col}`,
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              marginBottom: 2,
                            }}
                          >
                            <span
                              style={{
                                fontSize: 10,
                                color: col,
                                fontWeight: 700,
                              }}
                            >
                              {r.state}
                            </span>
                            <span style={{ fontSize: 10, color: C.muted }}>
                              #{i + 1}
                            </span>
                          </div>
                          <p
                            style={{
                              fontSize: 11,
                              color: C.text,
                              fontWeight: 600,
                              marginBottom: 2,
                            }}
                          >
                            {r.sa4_name}
                          </p>
                          <p
                            style={{
                              fontSize: 12,
                              color: col,
                              fontWeight: 800,
                            }}
                          >
                            {fmt(r.nsc_emp)}
                          </p>
                          <p style={{ fontSize: 10, color: C.muted }}>
                            {rp.toFixed(1)}% of national
                          </p>
                        </div>
                      );
                    })}
                  </div>
                </Card>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
