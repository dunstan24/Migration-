"use client";
/**
 * Visa Approval Probability Scorer
 * Route:  /dashboard/approval
 * Model:  XGBoost (model_xgboost.json) — 13 features, binary:logistic
 *
 * Inputs: Visa Type (190/491), Occupation, English Level, State
 * NO Points — model tidak menggunakan Points secara langsung
 * Count EOIs — fetched live from MySQL per occupation+state+visa
 */
import { useState, useEffect, useRef, useCallback } from "react";
import {
  RadialBarChart,
  RadialBar,
  PolarAngleAxis,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
} from "recharts";
import { C, Card } from "@/components/ui";
import { FormLabel, ScoreBadge, Skeleton } from "@/components/shared";

const API = "";

const STATES = ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"];
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

// Model hanya support 189, 190 dan 491
const VISA_OPTIONS = [
  { value: "189", label: "189 — Points-Tested Stream" },
  { value: "190", label: "190 — State Nominated (Skilled)" },
  { value: "491", label: "491 — Skilled Work Regional (Provisional)" },
];

const ENGLISH_OPTIONS = [
  {
    value: "superior",
    label: "Superior",
    sub: "IELTS 8+",
    bonus: 20,
    color: "#8B5CF6",
  },
  {
    value: "proficient",
    label: "Proficient",
    sub: "IELTS 7",
    bonus: 10,
    color: "#0891B2",
  },
  {
    value: "competent",
    label: "Competent",
    sub: "around IELTS 6",
    bonus: 0,
    color: "#059669",
  },
];

const BACKEND_URL = "";
const normalizeProb = (p: number) => (p > 1 ? p / 100 : p);
const probColor = (p: number) => {
  const n = normalizeProb(p);
  return n > 0.5 ? C.blue : C.orange;
};

const fmtEoi = (n: any) => {
  const v = Number(n);
  if (isNaN(v)) return String(n ?? "—");
  return v <= 10 ? "<20" : String(v);
};

const sel: any = {
  background: C.bg,
  border: `1px solid ${C.border}`,
  borderRadius: 6,
  padding: "9px 12px",
  color: C.text,
  fontSize: 13,
  outline: "none",
  cursor: "pointer",
  width: "100%",
};
const inp: any = {
  background: C.bg,
  border: `1px solid ${C.border}`,
  borderRadius: 6,
  padding: "9px 12px",
  color: C.text,
  fontSize: 13,
  outline: "none",
  width: "100%",
};

// ── Highlight matching text ───────────────────────────────────
function Highlight({ text, query }: { text: string; query: string }) {
  if (!query.trim()) return <span>{text}</span>;
  const idx = text.toLowerCase().indexOf(query.toLowerCase());
  if (idx === -1) return <span>{text}</span>;
  return (
    <span>
      {text.slice(0, idx)}
      <span
        style={{
          background: `${C.blue}35`,
          color: C.blue,
          borderRadius: 3,
          padding: "0 2px",
        }}
      >
        {text.slice(idx, idx + query.length)}
      </span>
      {text.slice(idx + query.length)}
    </span>
  );
}

// ── Occupation autocomplete with keyboard nav ─────────────────
function OccupationSearch({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  const [query, setQuery] = useState(value);
  const [results, setResults] = useState<string[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(value);
  const [activeIdx, setActiveIdx] = useState(-1);
  const timer = useRef<any>(null);
  const ref = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node))
        setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  useEffect(() => {
    setActiveIdx(-1);
  }, [results]);

  useEffect(() => {
    if (activeIdx >= 0 && listRef.current) {
      const items = listRef.current.querySelectorAll("[data-item]");
      items[activeIdx]?.scrollIntoView({ block: "nearest" });
    }
  }, [activeIdx]);

  const handleInput = (q: string) => {
    setQuery(q);
    onChange(q);
    setSelected("");
    clearTimeout(timer.current);
    if (!q.trim()) {
      setResults([]);
      setOpen(false);
      return;
    }
    timer.current = setTimeout(async () => {
      setLoading(true);
      try {
        const r = await fetch(
          `${API}/api/predict/approval/occupations?q=${encodeURIComponent(q)}`,
        );
        const d = await r.json();
        setResults(d.occupations || []);
        setOpen((d.occupations || []).length > 0);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 250);
  };

  const pick = useCallback(
    (occ: string) => {
      setQuery(occ);
      setSelected(occ);
      onChange(occ);
      setOpen(false);
      setResults([]);
    },
    [onChange],
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open || results.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIdx((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIdx((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (activeIdx >= 0 && results[activeIdx]) pick(results[activeIdx]);
    } else if (e.key === "Escape") {
      setOpen(false);
      setActiveIdx(-1);
    }
  };

  const anzscoCode = selected ? selected.split(" ")[0] : "";
  const occName = selected ? selected.split(" ").slice(1).join(" ") : "";
  // Only highlight non-numeric queries (if user types a name, not a code)
  const queryForHL = /^\d+$/.test(query.trim()) ? "" : query;

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <div style={{ position: "relative" }}>
        <input
          style={{ ...inp, paddingRight: 36 }}
          value={query}
          onChange={(e) => handleInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => query && results.length > 0 && setOpen(true)}
          placeholder="Ketik nama atau kode ANZSCO — contoh: nurse, chef, 261313…"
          autoComplete="off"
        />
        <span
          style={{
            position: "absolute",
            right: 10,
            top: "50%",
            transform: "translateY(-50%)",
            fontSize: 13,
            userSelect: "none",
          }}
        >
          {loading ? (
            <span
              style={{
                color: C.blue,
                display: "inline-block",
                animation: "spin 0.8s linear infinite",
              }}
            >
              ⟳
            </span>
          ) : selected ? (
            <span style={{ color: C.green }}>✓</span>
          ) : query ? (
            <span style={{ color: C.muted, fontSize: 10 }}>↵</span>
          ) : null}
        </span>
      </div>

      {/* Dropdown */}
      {open && results.length > 0 && (
        <div
          ref={listRef}
          style={{
            position: "absolute",
            top: "calc(100% + 4px)",
            left: 0,
            right: 0,
            zIndex: 200,
            background: "var(--surface)",
            border: `1px solid ${C.border}`,
            borderRadius: 10,
            maxHeight: 280,
            overflowY: "auto",
            boxShadow: "0 12px 32px rgba(0,0,0,0.6)",
          }}
        >
          <div
            style={{
              padding: "6px 12px",
              borderBottom: `1px solid ${C.border}`,
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              position: "sticky",
              top: 0,
              background: "var(--surface)",
            }}
          >
            <span style={{ fontSize: 10, color: C.muted }}>
              {results.length} hasil · ↑↓ navigasi · Enter pilih
            </span>
            <button
              onClick={() => setOpen(false)}
              style={{
                background: "none",
                border: "none",
                color: C.muted,
                cursor: "pointer",
                fontSize: 13,
              }}
            >
              ✕
            </button>
          </div>
          {results.map((occ, idx) => {
            const code = occ.split(" ")[0];
            const name = occ.split(" ").slice(1).join(" ");
            const isSelected = occ === selected;
            const isActive = idx === activeIdx;
            return (
              <div
                key={occ}
                data-item
                onClick={() => pick(occ)}
                onMouseEnter={() => setActiveIdx(idx)}
                style={{
                  padding: "9px 12px",
                  cursor: "pointer",
                  borderBottom: `1px solid ${C.border}18`,
                  background: isActive
                    ? `${C.blue}18`
                    : isSelected
                      ? `${C.blue}10`
                      : "transparent",
                  display: "flex",
                  alignItems: "center",
                  gap: 9,
                  transition: "background 0.1s",
                }}
              >
                <span
                  style={{
                    padding: "2px 6px",
                    borderRadius: 4,
                    fontSize: 10,
                    fontWeight: 800,
                    background: isSelected ? `${C.blue}30` : `${C.border}50`,
                    color: isSelected ? C.blue : C.muted,
                    fontFamily: "monospace",
                    whiteSpace: "nowrap",
                    flexShrink: 0,
                  }}
                >
                  {code}
                </span>
                <span
                  style={{
                    fontSize: 12,
                    color: C.text,
                    flex: 1,
                    lineHeight: 1.3,
                  }}
                >
                  <Highlight text={name} query={queryForHL} />
                </span>
                {isSelected && (
                  <span style={{ color: C.green, fontSize: 12 }}>✓</span>
                )}
                {isActive && !isSelected && (
                  <span style={{ color: C.muted, fontSize: 10 }}>↵</span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* No results */}
      {open && !loading && results.length === 0 && query.length > 1 && (
        <div
          style={{
            position: "absolute",
            top: "calc(100% + 4px)",
            left: 0,
            right: 0,
            zIndex: 200,
            background: "var(--surface)",
            border: `1px solid ${C.border}`,
            borderRadius: 10,
            padding: "16px 14px",
            textAlign: "center",
            boxShadow: "0 8px 24px rgba(0,0,0,0.5)",
          }}
        >
          <p style={{ fontSize: 12, color: C.muted }}>
            Tidak ada hasil untuk "{query}"
          </p>
          <p style={{ fontSize: 10, color: "#374151", marginTop: 4 }}>
            Coba kode ANZSCO 6 digit atau nama singkat
          </p>
        </div>
      )}

      {/* Confirmed selection */}
      {selected && (
        <div
          style={{
            marginTop: 8,
            padding: "8px 12px",
            borderRadius: 8,
            background: `${C.green}10`,
            border: `1px solid ${C.green}30`,
            display: "flex",
            alignItems: "center",
            gap: 10,
          }}
        >
          <div
            style={{
              padding: "3px 9px",
              borderRadius: 5,
              fontSize: 12,
              fontWeight: 800,
              background: `${C.green}25`,
              color: C.green,
              fontFamily: "monospace",
              flexShrink: 0,
            }}
          >
            {anzscoCode}
          </div>
          <div style={{ flex: 1 }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: C.text }}>
              {occName}
            </p>
            <p style={{ fontSize: 10, color: C.muted }}>ANZSCO confirmed ✓</p>
          </div>
          <button
            onClick={() => {
              setSelected("");
              setQuery("");
              onChange("");
            }}
            style={{
              background: "none",
              border: "none",
              color: C.muted,
              cursor: "pointer",
              fontSize: 12,
            }}
          >
            ✕
          </button>
        </div>
      )}

      <style
        dangerouslySetInnerHTML={{
          __html: `@keyframes spin { to { transform: rotate(360deg); } }`,
        }}
      />
    </div>
  );
}

// ── Radial gauge ──────────────────────────────────────────────
function ProbGauge({ prob }: { prob: number }) {
  const n = normalizeProb(prob);
  const pct = Math.round(n * 100);
  const col = probColor(n);
  return (
    <div
      style={{
        position: "relative",
        width: 200,
        height: 200,
        margin: "0 auto",
      }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <RadialBarChart
          cx="50%"
          cy="50%"
          innerRadius="72%"
          outerRadius="100%"
          barSize={14}
          data={[{ value: pct, fill: col }]}
          startAngle={225}
          endAngle={-45}
        >
          <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
          <RadialBar
            dataKey="value"
            cornerRadius={6}
            background={{ fill: C.border }}
          />
        </RadialBarChart>
      </ResponsiveContainer>
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <p style={{ fontSize: 34, fontWeight: 900, color: col, lineHeight: 1 }}>
          ≈ {(n * 100).toFixed(2)}%
        </p>
        <p style={{ fontSize: 10, color: C.muted, marginTop: 4 }}>
          {"PROBABILITY"}
        </p>
      </div>
    </div>
  );
}

// ── Feature importance bar ────────────────────────────────────
function ImpBar({
  name,
  value,
  max,
}: {
  name: string;
  value: number;
  max: number;
}) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  const short = name
    .replace("Visa Type_190SAS Skilled Australian Sponsored", "Visa: 190")
    .replace(
      "Visa Type_491SNR State or Territory Nominated - Regional",
      "Visa: 491",
    )
    .replace(/^State_/, "State: ")
    .replace("occupation_enc", "Occupation")
    .replace("English Test Score", "English Score")
    .slice(0, 30);
  return (
    <div style={{ marginBottom: 6 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginBottom: 2,
        }}
      >
        <span style={{ fontSize: 10, color: C.muted }}>{short}</span>
        <span style={{ fontSize: 10, color: C.text }}>
          ≈ {(value * 100).toFixed(1)}%
        </span>
      </div>
      <div style={{ height: 5, borderRadius: 3, background: C.border }}>
        <div
          style={{
            height: "100%",
            borderRadius: 3,
            width: `${pct}%`,
            background: C.blue,
            transition: "width 0.4s",
          }}
        />
      </div>
    </div>
  );
}

// ── EOI source badge ──────────────────────────────────────────
function EoiSourceBadge({ source }: { source?: string }) {
  const map: Record<string, { label: string; color: string }> = {
    warehouse_db: { label: "from MySQL DB", color: C.green },
    fallback_default: { label: "estimasi", color: C.amber },
    csv_4_vars: { label: "dari CSV (Exact)", color: C.green },
    csv_3_vars_no_state: { label: "dari CSV (Estimasi State)", color: C.blue },
    csv_3_vars_no_english: {
      label: "dari CSV (Estimasi English)",
      color: C.blue,
    },
    csv_2_vars_occ_visa: {
      label: "dari CSV (Estimasi State & English)",
      color: C.amber,
    },
    csv_1_var_occ: { label: "dari CSV (Estimasi Occupation)", color: C.amber },
    fallback_default_no_match: { label: "estimasi (No Match)", color: C.muted },
    manual_input: { label: "Manual Input", color: C.purple },
  };
  const s = source ? map[source] : null;
  if (!s) return null;
  return (
    <span
      style={{
        fontSize: 9,
        padding: "1px 5px",
        borderRadius: 4,
        marginLeft: 4,
        background: `${s.color}20`,
        color: s.color,
      }}
    >
      {s.label}
    </span>
  );
}

// ── Main page ─────────────────────────────────────────────────
export default function ApprovalScorer() {
  const [form, setForm] = useState({
    visa_type: "491",
    occupation: "",
    state: "NSW",
    english_level: "proficient",
    count_eois: 50,
    eoi_mode: "auto",
  });

  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [whatIfData, setWhatIfData] = useState<any[]>([]);
  const [whatIfLoad, setWhatIfLoad] = useState(false);
  const [eoiSource, setEoiSource] = useState<string>("");

  const set = (k: string, v: any) => setForm((f) => ({ ...f, [k]: v }));

  useEffect(() => {
    if (!form.occupation.trim()) return;
    if (form.eoi_mode !== "auto") return;

    const fetchEoiCount = async () => {
      try {
        const engObj = ENGLISH_OPTIONS.find(
          (o) => o.value === form.english_level,
        );
        const engScore = engObj ? engObj.bonus : 10;
        const res = await fetch(
          `${API}/api/predict/approval/eoi_count?occupation=${encodeURIComponent(
            form.occupation,
          )}&visa_type=${encodeURIComponent(form.visa_type)}&english_score=${engScore}&state=${encodeURIComponent(form.state)}`,
        );
        const data = await res.json();
        if (data && data.count !== undefined) {
          set("count_eois", data.count);
          setEoiSource(data.source);
        }
      } catch (err) {
        console.error("Auto-fetch EOI failed", err);
      }
    };

    // add small debounce so it doesn't query on every keystroke too quickly
    const BACKEND_URL = "";
    const timer = setTimeout(() => {
      fetchEoiCount();
    }, 500);
    return () => clearTimeout(timer);
  }, [
    form.occupation,
    form.visa_type,
    form.english_level,
    form.state,
    form.eoi_mode,
  ]);

  const currentEnglish = ENGLISH_OPTIONS.find(
    (o) => o.value === form.english_level,
  );

  const run = async (overrideState?: string, skipWhatIf = false) => {
    if (!form.occupation.trim()) {
      setError("Pilih occupation terlebih dahulu");
      return;
    }
    setLoading(true);
    if (!skipWhatIf) setWhatIfData([]); // Clear previous What-If data
    setError("");
    setResult(null);
    const targetState = overrideState || form.state;
    if (overrideState) set("state", overrideState);

    try {
      const r = await fetch(`${API}/api/predict/approval`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          visa_type: form.visa_type,
          occupation: form.occupation,
          state: targetState,
          english_level: form.english_level,
          count_eois: form.count_eois,
          eoi_mode: form.eoi_mode,
        }),
      });
      const d = await r.json();
      if (d.error) setError(d.error);
      else {
        setResult(d);
        if (!skipWhatIf) runWhatIf();
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const runWhatIf = async () => {
    if (!form.occupation.trim()) {
      setError("Pilih occupation terlebih dahulu");
      return;
    }
    setWhatIfLoad(true);
    const out: any[] = [];
    await Promise.allSettled(
      STATES.map(async (st) => {
        try {
          const r = await fetch(`${API}/api/predict/approval`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              ...form,
              state: st,
              count_eois: form.count_eois,
              eoi_mode: form.eoi_mode,
            }),
          });
          const d = await r.json();
          if (d.probability !== undefined)
            out.push({
              state: st,
              prob: normalizeProb(d.probability),
              eoi: d.inputs?.count_eois,
            });
        } catch {}
      }),
    );
    out.sort((a, b) => b.prob - a.prob);
    setWhatIfData(out);
    setWhatIfLoad(false);
  };

  const topImp = result?.top_feature_importance ?? {};
  const impMax = Math.max(...Object.values(topImp).map(Number), 0.001);
  const prob = result ? normalizeProb(result.probability) : 0;

  return (
    <div
      suppressHydrationWarning
      style={{
        padding: "24px 28px",
        width: "100%",
        maxWidth: "100%",
        background: C.bg,
        minHeight: "100vh",
      }}
    >
      {/* Header */}
      <div style={{ marginBottom: 22 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            marginBottom: 4,
          }}
        >
          <h1 style={{ fontSize: 22, fontWeight: 800, color: "var(--text)" }}>
            Visa Approval Probability Scorer
          </h1>
          <span
            style={{
              padding: "3px 10px",
              borderRadius: 20,
              fontSize: 11,
              fontWeight: 700,
              background: `${C.green}20`,
              color: C.green,
              border: `1px solid ${C.green}40`,
            }}
          >
            XGBoost
          </span>
          <span
            style={{
              padding: "3px 10px",
              borderRadius: 20,
              fontSize: 11,
              fontWeight: 700,
              background: `${C.cyan}15`,
              color: C.cyan,
              border: `1px solid ${C.cyan}30`,
            }}
          >
            13 features
          </span>
        </div>
        <p style={{ fontSize: 13, color: C.muted }}>
          Predicts EOI lodgement probability · Masukkan jumlah EOI secara manual
        </p>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
          gap: 20,
          alignItems: "start",
        }}
      >
        {/* ── FORM ─────────────────────────────────────── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <Card>
            <p
              style={{
                fontSize: 13,
                fontWeight: 700,
                color: C.text,
                marginBottom: 14,
              }}
            >
              EOI Profile
            </p>

            {/* Visa Type */}
            <div style={{ marginBottom: 13 }}>
              <FormLabel
                text="Visa Type"
                sub="Model support: 190,491 and 189 only"
              />
              <select
                style={sel}
                value={form.visa_type}
                onChange={(e) => set("visa_type", e.target.value)}
              >
                {VISA_OPTIONS.map((v) => (
                  <option key={v.value} value={v.value}>
                    {v.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Occupation autocomplete */}
            <div style={{ marginBottom: 13 }}>
              <FormLabel
                text="Occupation"
                sub="Ketik nama atau kode ANZSCO — 483 occupations"
              />
              <OccupationSearch
                value={form.occupation}
                onChange={(v) => set("occupation", v)}
              />
            </div>

            {/* English Level */}
            <div style={{ marginBottom: 13 }}>
              <FormLabel
                text="English Proficiency"
                sub="Menentukan English Test Score dalam model"
              />
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
                  gap: 6,
                }}
              >
                {ENGLISH_OPTIONS.map((o) => {
                  const active = form.english_level === o.value;
                  return (
                    <button
                      key={o.value}
                      onClick={() => set("english_level", o.value)}
                      style={{
                        padding: "10px 12px",
                        borderRadius: 8,
                        cursor: "pointer",
                        textAlign: "left",
                        border: `1px solid ${active ? o.color : C.border}`,
                        background: active ? `${o.color}18` : "transparent",
                      }}
                    >
                      <p
                        style={{
                          fontSize: 12,
                          fontWeight: 700,
                          color: active ? o.color : C.text,
                        }}
                      >
                        {o.label}
                      </p>
                      <p
                        style={{
                          fontSize: 10,
                          color: active ? o.color : C.muted,
                        }}
                      >
                        {o.sub}
                        {o.bonus > 0 && (
                          <span style={{ marginLeft: 4, fontWeight: 700 }}>
                            · score {o.bonus}
                          </span>
                        )}
                      </p>
                    </button>
                  );
                })}
              </div>
              {currentEnglish && (
                <div
                  style={{
                    marginTop: 8,
                    padding: "6px 10px",
                    background: `${currentEnglish.color}10`,
                    border: `1px solid ${currentEnglish.color}30`,
                    borderRadius: 6,
                  }}
                >
                  <p style={{ fontSize: 11, color: currentEnglish.color }}>
                    English Test Score model:{" "}
                    <strong>{currentEnglish.bonus}</strong>
                    {currentEnglish.bonus === 0 && " (no bonus)"}
                  </p>
                </div>
              )}
            </div>

            {/* Count EOIs — slider */}
            <div style={{ marginBottom: 14 }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-end",
                  marginBottom: 12,
                }}
              >
                <FormLabel
                  text="Count EOIs"
                  sub={
                    form.eoi_mode === "auto"
                      ? "Estimasi berdasarkan state"
                      : "Jumlah EOI dalam pool (kombinasi ini)"
                  }
                />
                <div
                  style={{
                    display: "flex",
                    background: `${C.border}40`,
                    borderRadius: 6,
                    padding: 2,
                  }}
                >
                  <button
                    onClick={() => set("eoi_mode", "auto")}
                    style={{
                      padding: "4px 8px",
                      fontSize: 11,
                      fontWeight: form.eoi_mode === "auto" ? 600 : 400,
                      background:
                        form.eoi_mode === "auto" ? C.bg : "transparent",
                      color: form.eoi_mode === "auto" ? C.blue : C.muted,
                      border: "none",
                      borderRadius: 4,
                      cursor: "pointer",
                      boxShadow:
                        form.eoi_mode === "auto"
                          ? "0 1px 3px rgba(0,0,0,0.1)"
                          : "none",
                    }}
                  >
                    🪄 Auto
                  </button>
                  <button
                    onClick={() => set("eoi_mode", "manual")}
                    style={{
                      padding: "4px 8px",
                      fontSize: 11,
                      fontWeight: form.eoi_mode === "manual" ? 600 : 400,
                      background:
                        form.eoi_mode === "manual" ? C.bg : "transparent",
                      color: form.eoi_mode === "manual" ? C.purple : C.muted,
                      border: "none",
                      borderRadius: 4,
                      cursor: "pointer",
                      boxShadow:
                        form.eoi_mode === "manual"
                          ? "0 1px 3px rgba(0,0,0,0.1)"
                          : "none",
                    }}
                  >
                    ✍️ Manual
                  </button>
                </div>
              </div>
              {(() => {
                // Discrete stops: index 0 = 10 ("<20"), then 20,30,...100,150,200,300,500
                const EOI_STOPS = [
                  10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 150, 200, 300, 500,
                ];
                const currentIdx =
                  EOI_STOPS.indexOf(form.count_eois) !== -1
                    ? EOI_STOPS.indexOf(form.count_eois)
                    : 0;
                const displayValue = fmtEoi(form.count_eois);

                return (
                  <>
                    {/* Value display */}
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginBottom: 10,
                      }}
                    >
                      <span
                        style={{
                          fontSize: 22,
                          fontWeight: 800,
                          color: C.blue,
                          fontFamily: "monospace",
                          letterSpacing: "-0.02em",
                        }}
                      >
                        {displayValue}
                      </span>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 6,
                        }}
                      >
                        <span
                          style={{
                            fontSize: 10,
                            color: C.muted,
                            padding: "2px 8px",
                            borderRadius: 4,
                            background: `${C.border}80`,
                          }}
                        >
                          EOIs in pool
                        </span>
                        <EoiSourceBadge source={eoiSource} />
                      </div>
                    </div>

                    {/* Slider */}
                    <div
                      style={{
                        position: "relative",
                        padding: "4px 0",
                        opacity: form.eoi_mode === "auto" ? 0.5 : 1,
                        pointerEvents:
                          form.eoi_mode === "auto" ? "none" : "auto",
                      }}
                    >
                      <input
                        type="range"
                        min={0}
                        max={EOI_STOPS.length - 1}
                        step={1}
                        value={currentIdx}
                        onChange={(e) => {
                          const idx = parseInt(e.target.value);
                          set("count_eois", EOI_STOPS[idx]);
                          set("eoi_mode", "manual");
                          setEoiSource("manual_input");
                        }}
                        style={{
                          width: "100%",
                          height: 6,
                          appearance: "none",
                          WebkitAppearance: "none",
                          background: `linear-gradient(to right, ${C.blue} ${(currentIdx / (EOI_STOPS.length - 1)) * 100}%, ${C.border} ${(currentIdx / (EOI_STOPS.length - 1)) * 100}%)`,
                          borderRadius: 4,
                          outline: "none",
                          cursor:
                            form.eoi_mode === "auto"
                              ? "not-allowed"
                              : "pointer",
                        }}
                        disabled={form.eoi_mode === "auto"}
                      />
                    </div>

                    {/* Tick labels */}
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        marginTop: 6,
                        padding: "0 2px",
                        opacity: form.eoi_mode === "auto" ? 0.5 : 1,
                      }}
                    >
                      {["<20", "50", "100", "200", "500"].map((label) => (
                        <span
                          key={label}
                          style={{ fontSize: 9, color: C.muted }}
                        >
                          {label}
                        </span>
                      ))}
                    </div>

                    <p style={{ fontSize: 10, color: C.muted, marginTop: 6 }}>
                      ⚠ Geser slider untuk estimasi jumlah EOI aktif.
                      {form.count_eois <= 10 && (
                        <span style={{ color: C.amber, marginLeft: 4 }}>
                          {"<20 = sedikit kompetisi"}
                        </span>
                      )}
                    </p>

                    {/* Slider thumb styling */}
                    <style
                      dangerouslySetInnerHTML={{
                        __html: `
                      input[type="range"]::-webkit-slider-thumb {
                        -webkit-appearance: none;
                        appearance: none;
                        width: 18px;
                        height: 18px;
                        border-radius: 50%;
                        background: ${C.blue};
                        border: 3px solid ${C.surface};
                        box-shadow: 0 0 8px ${C.blue}60, 0 2px 6px rgba(0,0,0,0.4);
                        cursor: grab;
                        transition: box-shadow 0.2s, transform 0.15s;
                      }
                      input[type="range"]::-webkit-slider-thumb:hover {
                        box-shadow: 0 0 14px ${C.blue}90, 0 2px 8px rgba(0,0,0,0.5);
                        transform: scale(1.15);
                      }
                      input[type="range"]::-webkit-slider-thumb:active {
                        cursor: grabbing;
                        transform: scale(1.1);
                      }
                      input[type="range"]::-moz-range-thumb {
                        width: 18px;
                        height: 18px;
                        border-radius: 50%;
                        background: ${C.blue};
                        border: 3px solid ${C.surface};
                        box-shadow: 0 0 8px ${C.blue}60, 0 2px 6px rgba(0,0,0,0.4);
                        cursor: grab;
                      }
                      input[type="range"]::-moz-range-track {
                        height: 6px;
                        border-radius: 4px;
                        background: transparent;
                      }
                    `,
                      }}
                    />
                  </>
                );
              })()}
            </div>

            {/* State */}
            <div style={{ marginBottom: 18 }}>
              <FormLabel text="Nominated State" />
              <select
                style={sel}
                value={form.state}
                onChange={(e) => set("state", e.target.value)}
              >
                {STATES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>

            <button
              onClick={() => run()}
              disabled={loading}
              style={{
                width: "100%",
                padding: "11px 0",
                borderRadius: 8,
                border: "none",
                cursor: loading ? "not-allowed" : "pointer",
                background: loading ? C.border : C.blue,
                color: "#fff",
                fontSize: 13,
                fontWeight: 700,
                marginBottom: 8,
              }}
            >
              {loading ? "Running XGBoost…" : "⚡  Score Approval"}
            </button>

            {error && (
              <div
                style={{
                  marginTop: 10,
                  padding: "10px 12px",
                  background: `${C.red}12`,
                  border: `1px solid ${C.red}40`,
                  borderRadius: 8,
                }}
              >
                <p style={{ fontSize: 11, color: "#ef4444" }}>{error}</p>
              </div>
            )}
          </Card>

          {/* Model info */}
          <Card>
            <p
              style={{
                fontSize: 11,
                fontWeight: 700,
                color: C.muted,
                textTransform: "uppercase",
                letterSpacing: "0.07em",
                marginBottom: 10,
              }}
            >
              Model Info
            </p>
            {[
              ["Algorithm", "XGBoost (binary:logistic)"],
              ["Features", "5 features"],
              ["Visa Support", "190, 491 and 189 only"],
              ["Target", "LODGED · NOT LODGED"],
              ["Occupations", "483 classes"],
            ].map(([k, v]) => (
              <div
                key={k}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  padding: "4px 0",
                  borderBottom: `1px solid ${C.border}22`,
                }}
              >
                <span style={{ fontSize: 11, color: C.muted }}>{k}</span>
                <span style={{ fontSize: 11, color: C.text }}>{v}</span>
              </div>
            ))}
          </Card>
        </div>

        {/* ── RESULTS ──────────────────────────────────── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {loading ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <Skeleton height={260} borderRadius={14} />
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 12,
                }}
              >
                <Skeleton height={120} borderRadius={10} />
                <Skeleton height={120} borderRadius={10} />
              </div>
              <Skeleton height={200} borderRadius={12} />
            </div>
          ) : (
            <>
              {/* Placeholder */}
              {!result && whatIfData.length === 0 && (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    height: 380,
                    background: C.surface,
                    borderRadius: 14,
                    border: `1px solid ${C.border}`,
                  }}
                >
                  <div style={{ textAlign: "center" }}>
                    <p style={{ fontSize: 36, marginBottom: 10 }}>🎯</p>
                    <p style={{ fontSize: 14, color: C.muted }}>
                      Isi profil dan klik Score Approval
                    </p>
                    <p style={{ fontSize: 11, color: "#374151", marginTop: 4 }}>
                      XGBoost · 13 features · Manual Count EOIs
                    </p>
                  </div>
                </div>
              )}

              {/* Main result */}
              {result && (
                <>
                  {/* Hero card */}
                  <div
                    style={{
                      background: `${probColor(prob)}10`,
                      border: `1px solid ${probColor(prob)}40`,
                      borderRadius: 14,
                      padding: "22px 26px",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: 20,
                        flexWrap: "wrap",
                      }}
                    >
                      <div>
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
                          XGBoost Prediction
                        </p>
                        <p
                          style={{
                            fontSize: 26,
                            fontWeight: 900,
                            color: probColor(prob),
                            marginBottom: 6,
                          }}
                        >
                          {result.label}
                        </p>
                        <p
                          style={{
                            fontSize: 12,
                            color: C.muted,
                            marginBottom: 14,
                          }}
                        >
                          {result.interpretation}
                        </p>

                        {/* Input chips */}
                        <div
                          style={{
                            display: "flex",
                            gap: 8,
                            flexWrap: "wrap",
                            marginBottom: 12,
                          }}
                        >
                          {[
                            { l: "Visa", v: result.inputs?.visa_type ?? "—" },
                            {
                              l: "English Score",
                              v: result.inputs?.english_score ?? "—",
                              highlight: true,
                              hcolor: C.purple,
                            },
                            { l: "English", v: form.english_level },
                            { l: "State", v: result.inputs?.state ?? "—" },
                            {
                              l: "EOI Count",
                              v:
                                result.inputs?.count_eois === 10
                                  ? "<20"
                                  : (result.inputs?.count_eois ?? "—"),
                              source: result.inputs?.count_eois_source,
                            },
                          ].map((k: any) => (
                            <div
                              key={k.l}
                              style={{
                                padding: "5px 12px",
                                background: k.highlight
                                  ? `${k.hcolor}20`
                                  : `${C.border}40`,
                                borderRadius: 8,
                                border: k.highlight
                                  ? `1px solid ${k.hcolor}40`
                                  : "none",
                              }}
                            >
                              <p
                                style={{
                                  fontSize: 9,
                                  color: k.highlight ? k.hcolor : C.muted,
                                }}
                              >
                                {k.l}
                              </p>
                              <p
                                style={{
                                  fontSize: 13,
                                  fontWeight: 800,
                                  color: k.highlight ? k.hcolor : C.text,
                                  display: "flex",
                                  alignItems: "center",
                                }}
                              >
                                {k.v}
                                {k.source && (
                                  <EoiSourceBadge source={k.source} />
                                )}
                              </p>
                            </div>
                          ))}
                        </div>

                        {/* Occupation */}
                        <div
                          style={{
                            padding: "8px 12px",
                            background: result.occupation_known
                              ? `${C.green}10`
                              : `${C.amber}10`,
                            border: `1px solid ${result.occupation_known ? C.green + "40" : C.amber + "40"}`,
                            borderRadius: 8,
                          }}
                        >
                          <p
                            style={{
                              fontSize: 10,
                              fontWeight: 700,
                              color: result.occupation_known
                                ? C.green
                                : C.amber,
                            }}
                          >
                            {result.occupation_known
                              ? "✓ Occupation recognised"
                              : "⚠ Occupation estimated"}
                          </p>
                          <p
                            style={{
                              fontSize: 12,
                              color: C.text,
                              marginTop: 2,
                            }}
                          >
                            {result.inputs?.occupation}
                          </p>
                        </div>
                      </div>

                      {/* Gauge */}
                      <div style={{ textAlign: "center" }}>
                        <ProbGauge prob={prob} />
                        <p
                          style={{
                            textAlign: "center",
                            fontSize: 10,
                            color: C.muted,
                            marginTop: 6,
                          }}
                        >
                          {result.prediction_label === "LODGED"
                            ? "✅ Predicted: LODGED"
                            : "❌ Predicted: NOT LODGED"}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Feature importance */}
                  {/* What-If: All States */}
                  {whatIfData.length > 0 && (
                    <Card>
                      <p
                        style={{
                          fontSize: 13,
                          fontWeight: 700,
                          color: C.text,
                          marginBottom: 4,
                        }}
                      >
                        What-If: Approval Probability Across All States
                      </p>
                      <p
                        style={{
                          fontSize: 11,
                          color: C.muted,
                          marginBottom: 14,
                        }}
                      >
                        {form.occupation} · Visa {form.visa_type} · English:{" "}
                        {form.english_level} · Count: {form.count_eois}
                      </p>
                      <ResponsiveContainer width="100%" height={190}>
                        <BarChart
                          data={whatIfData}
                          margin={{ top: 4, right: 8, bottom: 0, left: -8 }}
                        >
                          <CartesianGrid
                            strokeDasharray="3 3"
                            stroke={C.border}
                          />
                          <XAxis
                            dataKey="state"
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
                            formatter={(v: any) => [
                              `≈ ${(+v * 100).toFixed(2)}%`,
                              "Approval",
                            ]}
                            contentStyle={{
                              background: C.surface,
                              border: `1px solid ${C.border}`,
                              borderRadius: 6,
                              fontSize: 11,
                            }}
                          />
                          <Bar
                            dataKey="prob"
                            radius={[4, 4, 0, 0]}
                            onClick={(data) => {
                              if (data && data.state) run(data.state, true);
                            }}
                            style={{ cursor: "pointer" }}
                          >
                            {whatIfData.map((d: any) => (
                              <Cell
                                key={d.state}
                                fill={STATE_COLORS[d.state] || C.muted}
                                opacity={d.state === form.state ? 1 : 0.65}
                              />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>

                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
                          gap: 8,
                          marginTop: 12,
                        }}
                      >
                        {whatIfData.map((d: any, i: number) => (
                          <div
                            key={d.state}
                            style={{
                              padding: "8px 10px",
                              borderRadius: 8,
                              cursor: "pointer",
                              background:
                                d.state === form.state
                                  ? `${STATE_COLORS[d.state] || C.muted}18`
                                  : "transparent",
                              border: `1px solid ${
                                d.state === form.state
                                  ? (STATE_COLORS[d.state] || C.muted) + "50"
                                  : C.border
                              }`,
                            }}
                            onClick={() => run(d.state, true)}
                          >
                            <div
                              style={{
                                display: "flex",
                                justifyContent: "space-between",
                              }}
                            >
                              <span
                                style={{
                                  fontSize: 12,
                                  fontWeight: 700,
                                  color: STATE_COLORS[d.state] || C.muted,
                                }}
                              >
                                {d.state}
                              </span>
                              <span style={{ fontSize: 9, color: C.muted }}>
                                #{i + 1}
                              </span>
                            </div>
                            <p
                              style={{
                                fontSize: 17,
                                fontWeight: 800,
                                color: probColor(d.prob),
                              }}
                            >
                              ≈ {(d.prob * 100).toFixed(2)}%
                            </p>
                            {d.eoi !== undefined && (
                              <p
                                style={{
                                  fontSize: 10,
                                  color: C.muted,
                                  marginTop: 1,
                                }}
                              >
                                EOI:{" "}
                                <strong style={{ color: C.text }}>
                                  {d.eoi === 10 ? "<20" : d.eoi}
                                </strong>
                              </p>
                            )}
                            {d.state === form.state && (
                              <p
                                style={{
                                  fontSize: 9,
                                  color: C.green,
                                  marginTop: 2,
                                }}
                              >
                                ★ Selected
                              </p>
                            )}
                          </div>
                        ))}
                      </div>

                      {whatIfData[0] && (
                        <div
                          style={{
                            marginTop: 12,
                            padding: "10px 14px",
                            background: `${C.green}10`,
                            border: `1px solid ${C.green}30`,
                            borderRadius: 10,
                          }}
                        >
                          <p
                            style={{
                              fontSize: 12,
                              color: C.green,
                              fontWeight: 700,
                            }}
                          >
                            🏆 Best state: {whatIfData[0].state} — ≈{" "}
                            {(whatIfData[0].prob * 100).toFixed(2)}% approval
                            probability
                          </p>
                          {whatIfData[0].state !== form.state && (
                            <p
                              style={{
                                fontSize: 11,
                                color: C.muted,
                                marginTop: 2,
                              }}
                            >
                              State kamu ({form.state}): ≈{" "}
                              {(
                                (whatIfData.find(
                                  (d: any) => d.state === form.state,
                                )?.prob || 0) * 100
                              ).toFixed(2)}
                              %
                            </p>
                          )}
                        </div>
                      )}
                    </Card>
                  )}

                  {/* Feature importance */}
                  {Object.keys(topImp).length > 0 && (
                    <Card>
                      <p
                        style={{
                          fontSize: 13,
                          fontWeight: 700,
                          color: C.text,
                          marginBottom: 14,
                        }}
                      >
                        Top Feature Importances
                      </p>
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "1fr 1fr",
                          gap: "0 28px",
                        }}
                      >
                        {Object.entries(topImp).map(([name, val]) => (
                          <ImpBar
                            key={name}
                            name={name}
                            value={Number(val)}
                            max={impMax}
                          />
                        ))}
                      </div>
                    </Card>
                  )}
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
