"use client";
/**
 * Migration Volume Forecaster
 * Route: /dashboard/predictors
 * Model: Prophet (Meta) — 60 monthly predictions Jan 2026 – Dec 2030
 */
import { useState, useEffect, useMemo } from "react";
import {
  ComposedChart,
  BarChart,
  Area,
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Cell,
} from "recharts";
import { useDataCache } from "@/lib/DataCacheContext";
import { C, Card, PageWrapper } from "@/components/ui";

const API = "";
const fmt = (n: number) => Math.round(n ?? 0).toLocaleString();
const fmtK = (n: number) =>
  n >= 1000 ? `${(n / 1000).toFixed(0)}k` : String(Math.round(n));

const MONTHS = [
  "",
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];
const YEAR_COLORS: Record<number, string> = {
  2026: "#2a8bff",
  2027: "#10b981",
  2028: "#f59e0b",
  2029: "#8b5cf6",
  2030: "#ef4444",
};

function KpiCard({ label, value, sub, color }: any) {
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
      <p style={{ fontSize: 24, fontWeight: 800, color, lineHeight: 1 }}>
        {value}
      </p>
      {sub && (
        <p style={{ fontSize: 10, color: C.muted, marginTop: 4 }}>{sub}</p>
      )}
    </div>
  );
}

function Pill({ label, active, color, onClick }: any) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: "5px 14px",
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

function ForecastTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  return (
    <div
      style={{
        background: "var(--surface)",
        border: `1px solid ${C.border}`,
        borderRadius: 8,
        padding: "10px 14px",
        fontSize: 11,
      }}
    >
      <p style={{ fontWeight: 700, color: C.text, marginBottom: 6 }}>
        {MONTHS[d.month_no]} {d.year}
      </p>
      <p style={{ color: C.purple, marginBottom: 2 }}>
        Forecast: <strong>{fmt(d.yhat)}</strong>
      </p>
      <p style={{ color: `${C.green}cc`, marginBottom: 2 }}>
        80% CI: {fmt(d.yhat_lower_80)} – {fmt(d.yhat_upper_80)}
      </p>
      <p style={{ color: `${C.amber}aa` }}>
        95% CI: {fmt(d.yhat_lower_95)} – {fmt(d.yhat_upper_95)}
      </p>
    </div>
  );
}

export default function Predictors() {
  const { get } = useDataCache();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [ci, setCi] = useState<"80" | "95" | "both">("80");
  const [yearFilter, setYearFilter] = useState<number | null>(null);

  useEffect(() => {
    get(`/api/data/volume-forecast`)
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const records: any[] = useMemo(() => {
    const all = data?.records || [];
    return yearFilter ? all.filter((r: any) => r.year === yearFilter) : all;
  }, [data, yearFilter]);

  const chartData = records.map((r: any) => ({
    ...r,
    label: `${MONTHS[r.month_no]}'${String(r.year).slice(2)}`,
  }));

  const yearly: any[] = data?.yearly_totals || [];
  const allY = records.map((r: any) => r.yhat);
  const total = (data?.records || []).reduce(
    (s: number, r: any) => s + r.yhat,
    0,
  );

  const seasonality = Array.from({ length: 12 }, (_, i) => {
    const mo = i + 1;
    const vals = (data?.records || [])
      .filter((r: any) => r.month_no === mo)
      .map((r: any) => r.yhat);
    return {
      month: MONTHS[mo],
      avg: vals.length
        ? Math.round(
            vals.reduce((a: number, b: number) => a + b, 0) / vals.length,
          )
        : 0,
    };
  });

  if (loading)
    return (
      <PageWrapper>
        <div style={{ textAlign: "center", padding: 80, color: C.muted }}>
          Loading forecast…
        </div>
      </PageWrapper>
    );

  if (!data?.records?.length)
    return (
      <PageWrapper>
        <div
          style={{
            background: `${C.red}10`,
            border: `1px solid ${C.red}40`,
            borderRadius: 10,
            padding: "24px",
          }}
        >
          <p
            style={{
              color: C.red,
              fontWeight: 700,
              fontSize: 14,
              marginBottom: 8,
            }}
          >
            Forecast data not loaded
          </p>
          <p style={{ color: C.muted, fontSize: 12, marginBottom: 4 }}>
            {data?.error || "Table is empty or missing."}
          </p>
          <p style={{ color: C.muted, fontSize: 12 }}>
            1. Place{" "}
            <code style={{ color: C.text }}>
              final_migration_forecast_2030.csv
            </code>{" "}
            in{" "}
            <code style={{ color: C.text }}>
              backend/data/raw/volume_forecast/
            </code>
          </p>
          <p style={{ color: C.muted, fontSize: 12, marginTop: 4 }}>
            2. Run:{" "}
            <code style={{ color: C.text }}>
              python pipelines/ingestors/volume_forecast_ingestor.py
            </code>
          </p>
        </div>
      </PageWrapper>
    );

  return (
    <PageWrapper>
      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <h1
          style={{
            fontSize: 22,
            fontWeight: 800,
            color: "var(--text)",
            marginBottom: 4,
          }}
        >
          Migration Volume Forecaster
        </h1>
        <p style={{ fontSize: 13, color: C.muted }}>
          Prophet (Meta) · Monthly migration volume Jan 2026 – Dec 2030 · 80%
          and 95% confidence intervals
        </p>
      </div>

      {/* Model info */}
      <div
        style={{
          background: `${C.purple}10`,
          border: `1px solid ${C.purple}30`,
          borderRadius: 8,
          padding: "10px 18px",
          marginBottom: 20,
          display: "flex",
          gap: 32,
          flexWrap: "wrap",
        }}
      >
        {[
          ["Model", "Prophet (Meta)"],
          ["Horizon", "60 months"],
          ["Intervals", "80% + 95% CI"],
          ["Source", "migration_volume_forecast"],
        ].map(([k, v]) => (
          <div key={k}>
            <p
              style={{
                fontSize: 9,
                color: C.muted,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                fontWeight: 700,
              }}
            >
              {k}
            </p>
            <p
              style={{
                fontSize: 12,
                color: C.purple,
                fontWeight: 600,
                marginTop: 2,
              }}
            >
              {v}
            </p>
          </div>
        ))}
      </div>

      {/* KPIs */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: 12,
          marginBottom: 22,
        }}
      >
        <KpiCard
          label="Total 2026–2030"
          value={(total / 1000000).toFixed(2) + "M"}
          sub="Cumulative forecast"
          color={C.purple}
        />
        <KpiCard
          label="Peak Month"
          value={fmt(Math.max(...allY))}
          sub="Highest monthly forecast"
          color="#ef4444"
        />
        <KpiCard
          label="Trough Month"
          value={fmt(Math.min(...allY))}
          sub="Lowest monthly forecast"
          color="#f59e0b"
        />
        <KpiCard
          label="Monthly Average"
          value={fmt(
            allY.reduce((a: number, b: number) => a + b, 0) / allY.length,
          )}
          sub="60-month mean"
          color={C.blue}
        />
        <KpiCard
          label="2026 Annual"
          value={fmt(yearly[0]?.total)}
          sub="Full year forecast total"
          color={C.green}
        />
      </div>

      {/* Controls */}
      <div
        style={{
          display: "flex",
          gap: 6,
          alignItems: "center",
          marginBottom: 14,
          flexWrap: "wrap",
        }}
      >
        <Pill
          label="All"
          active={!yearFilter}
          color={C.purple}
          onClick={() => setYearFilter(null)}
        />
        {[2026, 2027, 2028, 2029, 2030].map((y) => (
          <Pill
            key={y}
            label={String(y)}
            active={yearFilter === y}
            color={YEAR_COLORS[y]}
            onClick={() => setYearFilter(yearFilter === y ? null : y)}
          />
        ))}
        <div
          style={{
            width: 1,
            height: 18,
            background: C.border,
            margin: "0 6px",
          }}
        />
        <Pill
          label="CI 80%"
          active={ci === "80"}
          color={C.green}
          onClick={() => setCi("80")}
        />
        <Pill
          label="CI 95%"
          active={ci === "95"}
          color={C.amber}
          onClick={() => setCi("95")}
        />
        <Pill
          label="Both"
          active={ci === "both"}
          color={C.blue}
          onClick={() => setCi("both")}
        />
      </div>

      {/* Main chart */}
      <Card style={{ marginBottom: 14 }}>
        <div style={{ marginBottom: 14 }}>
          <p style={{ fontSize: 13, fontWeight: 700, color: C.text }}>
            {yearFilter
              ? `Monthly Forecast — ${yearFilter}`
              : "Monthly Migration Volume Forecast 2026–2030"}
          </p>
          <p style={{ fontSize: 10, color: C.muted, marginTop: 2 }}>
            Point forecast (line) with confidence intervals (shaded) · Source:
            Prophet model
          </p>
        </div>
        <ResponsiveContainer width="100%" height={310}>
          <ComposedChart
            data={chartData}
            margin={{ top: 8, right: 16, bottom: 0, left: -4 }}
          >
            <defs>
              <linearGradient id="ci95g" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={C.amber} stopOpacity={0.32} />
                <stop offset="95%" stopColor={C.amber} stopOpacity={0.12} />
              </linearGradient>
              <linearGradient id="ci80g" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={C.green} stopOpacity={0.45} />
                <stop offset="95%" stopColor={C.green} stopOpacity={0.18} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
            <XAxis
              dataKey="label"
              tick={{ fill: C.muted, fontSize: 9 }}
              axisLine={false}
              tickLine={false}
              interval={yearFilter ? 0 : "preserveStartEnd"}
              minTickGap={20}
              angle={-45}
              textAnchor="end"
              height={40}
            />
            <YAxis
              domain={["auto", "auto"]}
              tick={{ fill: C.muted, fontSize: 9 }}
              axisLine={false}
              tickLine={false}
              tickFormatter={fmtK}
            />
            <Tooltip content={<ForecastTooltip />} />

            {(ci === "95" || ci === "both") && (
              <Line
                type="monotone"
                dataKey="yhat_upper_95"
                name="95% Upper Bound"
                stroke={C.amber}
                strokeWidth={2}
                strokeDasharray="4 4"
                dot={false}
                activeDot={false}
              />
            )}
            {(ci === "95" || ci === "both") && (
              <Line
                type="monotone"
                dataKey="yhat_lower_95"
                name="95% Lower Bound"
                stroke={C.amber}
                strokeWidth={2}
                strokeDasharray="4 4"
                dot={false}
                activeDot={false}
                legendType="none"
              />
            )}
            {(ci === "80" || ci === "both") && (
              <Line
                type="monotone"
                dataKey="yhat_upper_80"
                name="80% Upper Bound"
                stroke={C.green}
                strokeWidth={2}
                strokeDasharray="4 4"
                dot={false}
                activeDot={false}
              />
            )}
            {(ci === "80" || ci === "both") && (
              <Line
                type="monotone"
                dataKey="yhat_lower_80"
                name="80% Lower Bound"
                stroke={C.green}
                strokeWidth={2}
                strokeDasharray="4 4"
                dot={false}
                activeDot={false}
                legendType="none"
              />
            )}
            <Line
              type="monotone"
              dataKey="yhat"
              name="Forecast"
              stroke={C.purple}
              strokeWidth={2.5}
              dot={{ r: 2, fill: C.purple, stroke: "none" }}
              activeDot={{ r: 5, fill: C.purple }}
            />
            <Legend wrapperStyle={{ fontSize: 10 }} />
          </ComposedChart>
        </ResponsiveContainer>
      </Card>

      {/* Yearly totals + Seasonality */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
          gap: 14,
          marginBottom: 14,
        }}
      >
        <Card>
          <div style={{ marginBottom: 12 }}>
            <p style={{ fontSize: 13, fontWeight: 700, color: C.text }}>
              Annual Forecast Totals 2026–2030
            </p>
            <p style={{ fontSize: 10, color: C.muted, marginTop: 2 }}>
              Sum of monthly forecasts per year · Note: values are similar by
              design (stable migration policy)
            </p>
          </div>
          {/* Summary stat cards per year */}
          <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
            {yearly.map((r: any) => (
              <div
                key={r.year}
                style={{
                  flex: 1,
                  textAlign: "center",
                  padding: "10px 6px",
                  background: `${YEAR_COLORS[r.year] || C.purple}12`,
                  border: `1px solid ${YEAR_COLORS[r.year] || C.purple}30`,
                  borderRadius: 8,
                }}
              >
                <p style={{ fontSize: 9, color: C.muted }}>{r.year}</p>
                <p
                  style={{
                    fontSize: 14,
                    fontWeight: 800,
                    color: YEAR_COLORS[r.year] || C.purple,
                    marginTop: 3,
                  }}
                >
                  {(r.total / 1000000).toFixed(3)}M
                </p>
                <p style={{ fontSize: 9, color: C.muted, marginTop: 2 }}>
                  {r.months} months
                </p>
              </div>
            ))}
          </div>
          {/* Bar chart with zoomed Y-axis to show differences */}
          <ResponsiveContainer width="100%" height={160}>
            <BarChart
              data={yearly}
              margin={{ top: 4, right: 8, bottom: 0, left: -8 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
              <XAxis
                dataKey="year"
                tick={{ fill: C.muted, fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                domain={[
                  (dataMin: number) =>
                    Math.floor((dataMin * 0.9995) / 1000) * 1000,
                  (dataMax: number) =>
                    Math.ceil((dataMax * 1.0005) / 1000) * 1000,
                ]}
                tick={{ fill: C.muted, fontSize: 9 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => (v / 1000000).toFixed(3) + "M"}
              />
              <Tooltip
                formatter={(v: any) => [
                  `${(+v / 1000000).toFixed(4)}M (${fmt(+v)})`,
                  "Annual Total",
                ]}
                contentStyle={{
                  background: C.surface,
                  border: `1px solid ${C.border}`,
                  borderRadius: 6,
                  fontSize: 11,
                }}
              />
              <Bar dataKey="total" radius={[4, 4, 0, 0]}>
                {yearly.map((r: any) => (
                  <Cell key={r.year} fill={YEAR_COLORS[r.year] || C.purple} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <p style={{ fontSize: 10, color: C.muted, marginTop: 8 }}>
            ⓘ Y-axis zoomed in — absolute difference between years is ~
            {fmt(
              yearly.length >= 2
                ? Math.round(
                    Math.max(...yearly.map((r: any) => r.total)) -
                      Math.min(...yearly.map((r: any) => r.total)),
                  )
                : 0,
            )}{" "}
            migrants/year
          </p>
        </Card>

        <Card>
          <div style={{ marginBottom: 12 }}>
            <p style={{ fontSize: 13, fontWeight: 700, color: C.text }}>
              Average Monthly Seasonality
            </p>
            <p style={{ fontSize: 10, color: C.muted, marginTop: 2 }}>
              Mean forecast per calendar month across 2026–2030 · Shows which
              months typically have higher migration
            </p>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <ComposedChart
              data={seasonality}
              margin={{ top: 4, right: 8, bottom: 0, left: -8 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
              <XAxis
                dataKey="month"
                tick={{ fill: C.muted, fontSize: 9 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                domain={["auto", "auto"]}
                tick={{ fill: C.muted, fontSize: 9 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={fmtK}
              />
              <Tooltip
                formatter={(v: any) => [fmt(+v), "Avg Volume"]}
                contentStyle={{
                  background: C.surface,
                  border: `1px solid ${C.border}`,
                  borderRadius: 6,
                  fontSize: 11,
                }}
              />
              <Bar dataKey="avg" fill={`${C.cyan}50`} radius={[3, 3, 0, 0]} />
              <Line
                type="monotone"
                dataKey="avg"
                stroke={C.cyan}
                strokeWidth={2}
                dot={{ r: 3, fill: C.cyan, stroke: "none" }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* Full table */}
      <Card>
        <div style={{ marginBottom: 12 }}>
          <p style={{ fontSize: 13, fontWeight: 700, color: C.text }}>
            Full Monthly Forecast Table
          </p>
          <p style={{ fontSize: 10, color: C.muted, marginTop: 2 }}>
            {records.length} months · point forecast + 80% and 95% confidence
            intervals
          </p>
        </div>

        <div style={{ overflowX: "auto" }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "110px 60px 110px 110px 110px 110px 110px",
              gap: 6,
              padding: "6px 12px",
              borderBottom: `1px solid ${C.border}`,
              marginBottom: 2,
              minWidth: 700,
            }}
          >
            {[
              "Month",
              "Year",
              "Forecast",
              "Lower 80%",
              "Upper 80%",
              "Lower 95%",
              "Upper 95%",
            ].map((h) => (
              <span
                key={h}
                style={{
                  fontSize: 9,
                  fontWeight: 700,
                  textTransform: "uppercase" as const,
                  letterSpacing: "0.06em",
                  color: C.muted,
                }}
              >
                {h}
              </span>
            ))}
          </div>

          <div style={{ maxHeight: 400, overflowY: "auto", minWidth: 700 }}>
            {chartData.map((r: any, i: number) => (
              <div
                key={r.month}
                style={{
                  display: "grid",
                  gridTemplateColumns:
                    "110px 60px 110px 110px 110px 110px 110px",
                  gap: 6,
                  padding: "6px 12px",
                  borderRadius: 4,
                  alignItems: "center",
                  background:
                    i % 2 === 0 ? "transparent" : "var(--surface-alt)",
                  borderLeft: `2px solid ${YEAR_COLORS[r.year] || C.purple}40`,
                }}
              >
                <span style={{ fontSize: 11, fontWeight: 600, color: C.text }}>
                  {MONTHS[r.month_no]} {r.year}
                </span>
                <span style={{ fontSize: 10, color: C.muted }}>{r.year}</span>
                <span
                  style={{ fontSize: 12, fontWeight: 800, color: C.purple }}
                >
                  {fmt(r.yhat)}
                </span>
                <span style={{ fontSize: 10, color: `${C.green}cc` }}>
                  {fmt(r.yhat_lower_80)}
                </span>
                <span style={{ fontSize: 10, color: `${C.green}cc` }}>
                  {fmt(r.yhat_upper_80)}
                </span>
                <span style={{ fontSize: 10, color: `${C.amber}99` }}>
                  {fmt(r.yhat_lower_95)}
                </span>
                <span style={{ fontSize: 10, color: `${C.amber}99` }}>
                  {fmt(r.yhat_upper_95)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </Card>
    </PageWrapper>
  );
}
