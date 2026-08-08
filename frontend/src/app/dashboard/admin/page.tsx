"use client";
/**
 * Admin panel — real DB table list from /api/data/admin/tables
 * User management + Model management: Sprint 7 (JWT auth required)
 */
import { useState, useEffect } from "react";
import { C, Card, PageWrapper, ChartHeader } from "@/components/ui";
import UsersTab from "./components/UsersTab";
import ActivityTab from "./components/ActivityTab";

const API = "";

// Real table row counts from the handover doc
const KNOWN_TABLES: Record<
  string,
  { rows: string; source: string; status: string }
> = {
  eoi_records: {
    rows: "8,303,408",
    source: "Dept of Home Affairs — SkillSelect",
    status: "loaded",
  },
  jsa_monthly_ads: {
    rows: "22,630",
    source: "Jobs and Skills Australia",
    status: "loaded",
  },
  jsa_quarterly_employment: {
    rows: "48,980",
    source: "Jobs and Skills Australia",
    status: "loaded",
  },
  jsa_demographics: {
    rows: "4,650",
    source: "Jobs and Skills Australia",
    status: "loaded",
  },
  jsa_education: {
    rows: "7,750",
    source: "Jobs and Skills Australia",
    status: "loaded",
  },
  jsa_shortage: {
    rows: "1,126",
    source: "Jobs and Skills Australia",
    status: "loaded",
  },
  jsa_projected: {
    rows: "620",
    source: "Jobs and Skills Australia",
    status: "loaded",
  },
  jsa_recruitment: {
    rows: "91",
    source: "Jobs and Skills Australia",
    status: "loaded",
  },
  jsa_top10: {
    rows: "6,200",
    source: "Jobs and Skills Australia",
    status: "loaded",
  },
  jsa_mobility: {
    rows: "19,321",
    source: "Jobs and Skills Australia",
    status: "loaded",
  },
  osl_shortage: {
    rows: "4,486",
    source: "DEWR — annual shortage list",
    status: "loaded",
  },
  national_migration_quotas: {
    rows: "48",
    source: "Dept of Home Affairs",
    status: "loaded",
  },
  state_nomination_quotas: {
    rows: "16",
    source: "Dept of Home Affairs",
    status: "loaded",
  },
  nero_regional: {
    rows: "89,460",
    source: "Jobs and Skills Australia — NERO",
    status: "loaded",
  },
  nero_northern: {
    rows: "44,730",
    source: "Jobs and Skills Australia — NERO",
    status: "loaded",
  },
  nero_sa4_lookup: {
    rows: "88",
    source: "Jobs and Skills Australia",
    status: "loaded",
  },
  nero_sa4: {
    rows: "3,936,240",
    source: "JSA — per state SA4 data",
    status: "loaded",
  },
};

export default function Admin() {
  const [tables, setTables] = useState<string[]>([]);
  const [health, setHealth] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"database" | "users" | "activity">("database");

  useEffect(() => {
    Promise.all([
      fetch(`${API}/api/data/admin/tables`).then((r) => r.json()),
      fetch(`${API}/health`).then((r) => r.json()),
    ])
      .then(([t, h]) => {
        setTables(t.tables || []);
        setHealth(h);
      })
      .finally(() => setLoading(false));
  }, []);

  const loadedTables = tables.filter(
    (t) => (KNOWN_TABLES[t]?.status || "loaded") === "loaded",
  );
  const emptyTables = Object.keys(KNOWN_TABLES).filter(
    (t) => KNOWN_TABLES[t].status === "empty",
  );
  const totalRows = "12.5M+";

  return (
    <PageWrapper
      title="Admin Panel"
      sub="Database overview and administrative management panel"
    >
      {/* ── KPIs ────────────────────────────────────────────── */}

      {/* ── KPIs ────────────────────────────────────────────── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: 12,
          marginBottom: 20,
        }}
      >
        {[
          {
            label: "DB Status",
            value:
              health?.database === "connected"
                ? "Connected"
                : loading
                  ? "..."
                  : "Error",
            color: health?.database === "connected" ? C.green : C.red,
          },
          {
            label: "Tables in DB",
            value: loading ? "..." : String(tables.length),
            color: C.blue,
          },
          { label: "Total Rows", value: totalRows, color: C.cyan },
          {
            label: "Empty Tables",
            value: String(emptyTables.length),
            color: C.amber,
          },
        ].map((k) => (
          <div
            key={k.label}
            style={{
              background: C.surface,
              border: `1px solid ${C.border}`,
              borderRadius: 10,
              padding: "16px",
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
              {k.label}
            </p>
            <p style={{ fontSize: 22, fontWeight: 800, color: k.color }}>
              {k.value}
            </p>
          </div>
        ))}
      </div>

      {/* ── Tabs ─────────────────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          gap: 4,
          marginBottom: 16,
          borderBottom: `1px solid ${C.border}`,
          paddingBottom: 0,
        }}
      >
        {(["database", "users", "activity"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              background: "none",
              border: "none",
              borderBottom:
                tab === t ? `2px solid ${C.blue}` : "2px solid transparent",
              padding: "8px 18px",
              cursor: "pointer",
              fontSize: 13,
              fontWeight: tab === t ? 600 : 400,
              color: tab === t ? C.blue : C.muted,
              textTransform: "capitalize",
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {/* ── Database tab ─────────────────────────────────────── */}
      {tab === "database" && (
        <Card>
          <ChartHeader color={C.blue}>
            Main Database — migration_db (MySQL)
          </ChartHeader>

          <div style={{ overflowX: "auto" }}>
            {/* Header row */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "2fr 1fr 2fr 0.8fr",
                gap: 8,
                padding: "7px 14px",
                marginBottom: 4,
                minWidth: 600,
              }}
            >
              {["Table Name", "Rows", "Data Source", "Status"].map((h) => (
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

            {loading ? (
              <div
                style={{
                  padding: "30px 0",
                  textAlign: "center",
                  color: C.muted,
                  fontSize: 12,
                }}
              >
                Loading tables...
              </div>
            ) : (
              <div style={{ minWidth: 600 }}>
                {Object.entries(KNOWN_TABLES).map(([tname, info], i) => {
                  const exists = tables.includes(tname);
                  const statusColor =
                    info.status === "empty" ? C.amber : !exists ? C.red : C.green;
                  const statusLabel =
                    info.status === "empty"
                      ? "Empty"
                      : !exists
                        ? "Missing"
                        : "Loaded";
                  return (
                    <div
                      key={tname}
                      style={{
                        display: "grid",
                        gridTemplateColumns: "2fr 1fr 2fr 0.8fr",
                        gap: 8,
                        padding: "9px 14px",
                        alignItems: "center",
                        background:
                          i % 2 === 0 ? "transparent" : "var(--surface-alt)",
                        borderBottom: `1px solid ${C.border}11`,
                      }}
                    >
                      <span
                        style={{
                          fontSize: 11,
                          color: C.text,
                          fontFamily: "monospace",
                        }}
                      >
                        {tname}
                      </span>
                      <span
                        style={{
                          fontSize: 12,
                          color: info.status === "empty" ? C.muted : C.text,
                          fontWeight: info.status !== "empty" ? 600 : 400,
                        }}
                      >
                        {info.rows}
                      </span>
                      <span style={{ fontSize: 11, color: C.muted }}>
                        {info.source}
                      </span>
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          color: statusColor,
                          background: `${statusColor}15`,
                          padding: "2px 8px",
                          borderRadius: 4,
                          border: `1px solid ${statusColor}35`,
                          width: "fit-content",
                        }}
                      >
                        {statusLabel}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {emptyTables.length > 0 && (
            <div
              style={{
                marginTop: 16,
                padding: "12px 16px",
                background: `${C.amber}10`,
                border: `1px solid ${C.amber}30`,
                borderRadius: 8,
              }}
            >
              <p
                style={{
                  fontSize: 12,
                  color: C.amber,
                  fontWeight: 600,
                  marginBottom: 4,
                }}
              >
                {emptyTables.length} tables have no data yet
              </p>
              <p style={{ fontSize: 11, color: C.muted }}>
                Check backend logs for synchronization issues or incomplete data
                ingestion for the tables listed above.
              </p>
            </div>
          )}
        </Card>
      )}

      {/* ── Users Tab ─────────────────────────────────────── */}
      {tab === "users" && <UsersTab />}

      {/* ── Activity Tab ──────────────────────────────────── */}
      {tab === "activity" && <ActivityTab />}
    </PageWrapper>
  );
}
