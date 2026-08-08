"use client";
/**
 * Visa Pathway Predictor
 * Route: /dashboard/pathway
 * POST /api/predict/pathway
 *
 * GBM model (model_a.joblib) — predicts best visa subclass (189/190/491)
 * given: occupation, state, points, english_level, age, experience
 */
import { useState, useRef, useEffect } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
} from "recharts";
import { C, Card } from "@/components/ui";
import { FormLabel, ScoreBadge, Skeleton, PredictorCard, Autocomplete, AutocompleteSuggestion } from "@/components/shared";

const API = "";

const VISA_COLORS: Record<string, string> = {
  "189": C.green,
  "190": C.blue,
  "491": C.purple,
};
const VISA_LABELS: Record<string, string> = {
  "189": "189 — Skilled Independent",
  "190": "190 — State Nominated",
  "491": "491 — Regional (Provisional)",
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
const STATES = ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"];

const sel: any = {
  background: C.bg,
  border: `1px solid ${C.border}`,
  borderRadius: 8,
  padding: "10px 14px",
  color: C.text,
  fontSize: 13,
  outline: "none",
  cursor: "pointer",
  width: "100%",
  transition: "all 0.2s",
};
const inp: any = {
  background: C.bg,
  border: `1px solid ${C.border}`,
  borderRadius: 8,
  padding: "10px 14px",
  color: C.text,
  fontSize: 13,
  outline: "none",
  width: "100%",
  transition: "all 0.2s",
};



export default function PathwayPredictor() {
  const [form, setForm] = useState({
    occupation: "",
    state: "NSW",
    points: 80,
  });
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"top" | "all" | "shap">("top");

  // Autocomplete state
  const [searchInputValue, setSearchInputValue] = useState("");
  const [suggestions, setSuggestions] = useState<AutocompleteSuggestion[]>([]);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const debounceTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    return () => {
      if (debounceTimeoutRef.current) clearTimeout(debounceTimeoutRef.current);
    };
  }, []);

  const handleSearchInput = (value: string) => {
    setSearchInputValue(value);
    setIsDropdownOpen(true);
    set("occupation", value); // Fallback: user can type raw code directly

    if (!value.trim()) {
      setSuggestions([]);
      return;
    }

    if (debounceTimeoutRef.current) clearTimeout(debounceTimeoutRef.current);

    debounceTimeoutRef.current = setTimeout(() => {
      setSuggestionsLoading(true);
      fetch(`${API}/api/data/shortage-forecast?limit=50&search=${encodeURIComponent(value)}`)
        .then((r) => r.json())
        .then((d) => {
          const uniqueMap = new Map<string, AutocompleteSuggestion>();
          (d.records || []).forEach((r: any) => {
            if (!uniqueMap.has(r.anzsco_code)) {
              uniqueMap.set(r.anzsco_code, { anzsco_code: r.anzsco_code, occupation: r.occupation });
            }
          });
          setSuggestions(Array.from(uniqueMap.values()).slice(0, 10));
          setSuggestionsLoading(false);
        }).catch(() => {
          setSuggestions([]);
          setSuggestionsLoading(false);
        });
    }, 300);
  };

  const handleSelectSuggestion = (s: AutocompleteSuggestion) => {
    setSearchInputValue(`${s.occupation} (${s.anzsco_code})`);
    set("occupation", s.anzsco_code);
    setIsDropdownOpen(false);
  };

  const set = (k: string, v: any) => setForm((f) => ({ ...f, [k]: v }));

  const run = async () => {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const r = await fetch(`${API}/api/predict/pathway`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          occupation: form.occupation,
          state: form.state,
          points: Number(form.points),
        }),
      });
      const d = await r.json();

      // Check for error in response
      if (d.error) {
        setError(d.error);
      } else if (d.detail) {
        // FastAPI HTTPException returns detail field
        setError(d.detail);
      } else if (!r.ok) {
        setError(`Server error: ${r.status} ${r.statusText}`);
      } else if (d && typeof d === "object" && d.class_probs && d.shap_values) {
        // Only set result if response has expected structure
        setResult(d);
      } else {
        setError("Invalid response format from server");
        console.error("Unexpected response format:", d);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  // ── Derived chart data ───────────────────────────────────
  const classProbs =
    result && result.class_probs
      ? Object.entries(result.class_probs).map(([name, val]: any) => {
          const visaNum = name.split("_")[0];
          const stateName =
            name.split("_")[1] === "National" ? "" : ` ${name.split("_")[1]}`;
          return {
            name: `${visaNum}${stateName}`,
            prob: Math.round(val * 100),
            color: VISA_COLORS[visaNum] || C.muted,
          };
        })
      : [];

  const shapData =
    result && result.shap_values
      ? Object.entries(result.shap_values).map(([feat, val]: any) => ({
          feature: feat,
          importance: Math.round(val * 100),
        }))
      : [];

  // Top 10 pathways for table
  const topPathways = result?.pathways?.slice(0, 12) ?? [];

  return (
    <div
      suppressHydrationWarning
      style={{
        padding: "24px 28px",
        maxWidth: 1400,
        background: C.bg,
        minHeight: "100vh",
      }}
    >
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
          Visa Pathway Predictor
        </h1>
        <p style={{ fontSize: 13, color: C.muted }}>
          GradientBoosting model (model_a) · Predicts best visa subclass (189 /
          190 / 491) from your profile
        </p>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))",
          gap: 20,
          alignItems: "start",
        }}
      >
        {/* ── INPUT FORM ────────────────────────────────── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <Card>
            <p
              style={{
                fontSize: 13,
                fontWeight: 700,
                color: C.text,
                marginBottom: 16,
              }}
            >
              Applicant Profile
            </p>

            {/* Occupation */}
            <div style={{ marginBottom: 14 }}>
              <FormLabel
                text="ANZSCO Occupation"
                sub="Search by name or 6-digit code e.g. 261313"
              />
              <div style={{ marginTop: 4 }}>
                <Autocomplete
                  inputValue={searchInputValue || form.occupation}
                  onInputChange={handleSearchInput}
                  suggestions={suggestions}
                  onSelectSuggestion={handleSelectSuggestion}
                  isLoading={suggestionsLoading}
                  isOpen={isDropdownOpen}
                  setIsOpen={setIsDropdownOpen}
                />
              </div>
            </div>

            {/* State */}
            <div style={{ marginBottom: 14 }}>
              <FormLabel
                text="Nominated State"
                sub="State you prefer or plan to apply to"
              />
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

            {/* Points */}
            <div style={{ marginBottom: 20 }}>
              <FormLabel
                text="Total Points Score"
                sub={`Include all factors (Age, English, Exp) in this score. Current: ${form.points} pts`}
              />
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <input
                  type="range"
                  min={60}
                  max={140}
                  value={form.points}
                  onChange={(e) => set("points", Number(e.target.value))}
                  style={{ flex: 1, accentColor: C.blue }}
                />
                <span
                  style={{
                    fontSize: 16,
                    fontWeight: 800,
                    color: C.blue,
                    minWidth: 42,
                    textAlign: "right",
                  }}
                >
                  {form.points}
                </span>
              </div>
              {/* Points threshold indicators */}
              <div style={{ display: "flex", gap: 4, marginTop: 8 }}>
                {[
                  { pts: 60, label: "491 min", color: C.purple },
                  { pts: 65, label: "190 min", color: C.blue },
                  { pts: 85, label: "Good", color: C.green },
                  { pts: 100, label: "Strong", color: C.amber },
                ].map((t) => (
                  <div
                    key={t.pts}
                    style={{
                      flex: 1,
                      textAlign: "center",
                      padding: "3px 0",
                      borderRadius: 4,
                      fontSize: 9,
                      fontWeight: 700,
                      background:
                        form.points >= t.pts ? `${t.color}20` : C.border,
                      color: form.points >= t.pts ? t.color : C.muted,
                      border: `1px solid ${form.points >= t.pts ? t.color + "40" : C.border}`,
                    }}
                  >
                    {t.pts}+ {t.label}
                  </div>
                ))}
              </div>
            </div>

            <button
              onClick={run}
              disabled={loading}
              style={{
                width: "100%",
                padding: "12px 0",
                borderRadius: 8,
                border: "none",
                cursor: loading ? "not-allowed" : "pointer",
                background: loading ? C.border : C.blue,
                color: "#fff",
                fontSize: 13,
                fontWeight: 700,
                letterSpacing: "0.03em",
              }}
            >
              {loading ? "Running model…" : "⚡  Predict Pathway"}
            </button>

            {error && (
              <div
                style={{
                  marginTop: 12,
                  padding: "10px 14px",
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
              ["Algorithm", "GradientBoostingClassifier"],
              ["Estimators", "200"],
              ["Classes", "17 Visa+State Combinations"],
              ["Features", "3 (occupation, state, points)"],
              ["File", "model_a.joblib"],
            ].map(([k, v]) => (
              <div
                key={k}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  padding: "5px 0",
                  borderBottom: `1px solid ${C.border}`,
                }}
              >
                <span style={{ fontSize: 11, color: C.muted }}>{k}</span>
                <span
                  style={{
                    fontSize: 11,
                    color: C.text,
                    textAlign: "right",
                    maxWidth: "60%",
                  }}
                >
                  {v}
                </span>
              </div>
            ))}
          </Card>
        </div>

        {/* ── RESULTS ───────────────────────────────────── */}
        {loading ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <Skeleton height={200} borderRadius={14} />
            <Skeleton height={40} borderRadius={8} />
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 14 }}>
              <Skeleton height={220} borderRadius={12} />
              <Skeleton height={220} borderRadius={12} />
            </div>
          </div>
        ) : !result ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              height: 400,
              background: C.surface,
              borderRadius: 14,
              border: `1px solid ${C.border}`,
            }}
          >
            <div style={{ textAlign: "center" }}>
              <p style={{ fontSize: 40, marginBottom: 12 }}>⚡</p>
              <p style={{ fontSize: 14, color: C.muted }}>
                Fill in the profile and click Predict Pathway
              </p>
              <p style={{ fontSize: 11, color: "#374151", marginTop: 6 }}>
                Model will rank all visa × state combinations
              </p>
            </div>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {/* Top recommendation */}
            <PredictorCard
              title="Top Recommended Pathway"
              subtitle={result.top_pathway.state !== "Any (National)" ? `→ ${result.top_pathway.state}` : "National"}
              value={result.top_pathway.visa_name}
              score={result.top_pathway.score}
              icon={result.top_pathway.visa === "189" ? "🛡️" : result.top_pathway.visa === "190" ? "🏅" : "🏜️"}
            />

            {/* Adjusted points callout */}
            <div
              style={{
                display: "flex",
                gap: 12,
                marginTop: 4,
                flexWrap: "wrap",
              }}
            >
              {[
                {
                  label: "User Points",
                  value: Number(result.points || 0),
                  color: C.blue,
                },
                {
                  label: "Adjusted Score (Impact)",
                  value: (Number(result.adjusted_points || 0) - Number(result.points || 0)).toFixed(2),
                  color: C.green,
                },
                {
                  label: "Final Propensity",
                  value: (Number(result.adjusted_points || 0) / 10).toFixed(2),
                  color: C.amber,
                },
              ].map((k) => (
                <div
                  key={k.label}
                  style={{
                    padding: "8px 16px",
                    background: `${k.color}12`,
                    border: `1px solid ${k.color}30`,
                    borderRadius: 8,
                  }}
                >
                  <p
                    style={{
                      fontSize: 9,
                      color: C.muted,
                      textTransform: "uppercase",
                      letterSpacing: "0.07em",
                    }}
                  >
                    {k.label}
                  </p>
                  <p
                    style={{ fontSize: 20, fontWeight: 800, color: k.color }}
                  >
                    {k.value}
                  </p>
                </div>
              ))}
            </div>

            {/* State Requirements Box */}
            {result.top_pathway.requirements && (
              <div
                style={{
                  padding: "16px",
                  background: `rgba(255,255,255,0.03)`,
                  border: `1px solid ${C.border}`,
                  borderRadius: 12,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: 10,
                  }}
                >
                  <p
                    style={{
                      fontSize: 13,
                      fontWeight: 700,
                      color: C.text,
                    }}
                  >
                    State Requirements ({result.top_pathway.state})
                  </p>
                  {result.top_pathway.service_fee && (
                    <span
                      style={{
                        fontSize: 11,
                        fontWeight: 600,
                        color: C.amber,
                        background: `${C.amber}15`,
                        padding: "2px 8px",
                        borderRadius: 4,
                        border: `1px solid ${C.amber}40`,
                      }}
                    >
                      Fee: {result.top_pathway.service_fee}
                    </span>
                  )}
                </div>
                <div
                  style={{
                    fontSize: 12,
                    color: C.muted,
                    lineHeight: 1.6,
                    maxHeight: 200,
                    overflowY: "auto",
                    paddingRight: 8,
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {result.top_pathway.requirements}
                </div>
              </div>
            )}
            
            {/* Tabs */}
            <div
              style={{
                display: "flex",
                gap: 2,
                background: C.surface,
                border: `1px solid ${C.border}`,
                borderRadius: 8,
                padding: 4,
              }}
            >
              {(
                [
                  ["top", "Top Pathways"],
                  ["shap", "Feature Importance"],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  onClick={() => setTab(id)}
                  style={{
                    flex: 1,
                    padding: "7px 0",
                    borderRadius: 6,
                    border: "none",
                    cursor: "pointer",
                    fontSize: 12,
                    fontWeight: 600,
                    background: tab === id ? C.blue : "transparent",
                    color: tab === id ? "#fff" : C.muted,
                  }}
                >
                  {label}
                </button>
              ))}
            </div>

            {/* Tab: Top Pathways */}
            {tab === "top" && (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
                  gap: 14,
                }}
              >
                {/* Class probability bars */}
                <Card>
                  <p
                    style={{
                      fontSize: 13,
                      fontWeight: 700,
                      color: C.text,
                      marginBottom: 14,
                    }}
                  >
                    Visa Class Probability
                  </p>
                  <ResponsiveContainer width="100%" height={160}>
                    <BarChart
                      data={classProbs}
                      margin={{ top: 4, right: 8, bottom: 0, left: -8 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                      <XAxis
                        dataKey="name"
                        tick={{ fill: C.muted, fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis
                        domain={[0, 100]}
                        tickFormatter={(v) => v + "%"}
                        tick={{ fill: C.muted, fontSize: 10 }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <Tooltip
                        formatter={(v: any) => [`${v}%`, "Probability"]}
                        contentStyle={{
                          background: C.surface,
                          border: `1px solid ${C.border}`,
                          borderRadius: 6,
                          fontSize: 11,
                        }}
                      />
                      <Bar dataKey="prob" radius={[4, 4, 0, 0]}>
                        {classProbs.map((d: any) => (
                          <Cell key={d.name} fill={d.color} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </Card>

                {/* Top 5 pathways list */}
                <Card>
                  <p
                    style={{
                      fontSize: 13,
                      fontWeight: 700,
                      color: C.text,
                      marginBottom: 14,
                    }}
                  >
                    Ranked Pathways
                  </p>
                  {topPathways.map((p: any, i: number) => {
                    const vc = VISA_COLORS[p.visa] || C.muted;
                    const sc = STATE_COLORS[p.state] || C.muted;
                    return (
                      <div
                        key={i}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 10,
                          padding: "8px 0",
                          borderBottom: `1px solid ${C.border}`,
                        }}
                      >
                        <span
                          style={{
                            fontSize: 13,
                            fontWeight: 800,
                            color: i === 0 ? C.amber : C.muted,
                            width: 20,
                          }}
                        >
                          #{i + 1}
                        </span>
                        <div style={{ flex: 1 }}>
                          <div
                            style={{
                              display: "flex",
                              gap: 6,
                              alignItems: "center",
                              marginBottom: 2,
                            }}
                          >
                            <span
                              style={{
                                fontSize: 11,
                                fontWeight: 700,
                                color: vc,
                                background: `${vc}18`,
                                padding: "1px 7px",
                                borderRadius: 4,
                                border: `1px solid ${vc}35`,
                              }}
                            >
                              {p.visa}
                            </span>
                            {p.state !== "Any (National)" && (
                              <span
                                style={{
                                  fontSize: 11,
                                  fontWeight: 700,
                                  color: sc,
                                }}
                              >
                                {p.state}
                              </span>
                            )}
                            {!p.eligible && (
                              <span style={{ fontSize: 10, color: "#ef4444" }}>
                                Not eligible
                              </span>
                            )}
                          </div>
                          <div
                            style={{
                              height: 3,
                              background: C.border,
                              borderRadius: 2,
                            }}
                          >
                            <div
                              style={{
                                width: `${p.score * 100}%`,
                                height: "100%",
                                background: vc,
                                borderRadius: 2,
                              }}
                            />
                          </div>
                        </div>
                        <span
                          style={{
                            fontSize: 12,
                            fontWeight: 700,
                            color: vc,
                            width: 40,
                            textAlign: "right",
                          }}
                        >
                          {(p.score * 100).toFixed(0)}%
                        </span>
                      </div>
                    );
                  })}
                </Card>
              </div>
            )}

            {/* Tab: SHAP / Feature Importance */}
            {tab === "shap" && (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
                  gap: 14,
                }}
              >
                <Card>
                  <p
                    style={{
                      fontSize: 13,
                      fontWeight: 700,
                      color: C.text,
                      marginBottom: 4,
                    }}
                  >
                    Feature Importance
                  </p>
                  <p style={{ fontSize: 11, color: C.muted, marginBottom: 14 }}>
                    GBM feature importances (proxy for SHAP) · Which input drove
                    this prediction most
                  </p>
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart
                      data={shapData}
                      layout="vertical"
                      margin={{ top: 0, right: 40, bottom: 0, left: 20 }}
                    >
                      <XAxis
                        type="number"
                        tickFormatter={(v) => `${v}%`}
                        tick={{ fill: C.muted, fontSize: 10 }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis
                        type="category"
                        dataKey="feature"
                        width={80}
                        tick={{ fill: C.muted, fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <Tooltip
                        formatter={(v: any) => [`${v}%`, "Importance"]}
                        contentStyle={{
                          background: C.surface,
                          border: `1px solid ${C.border}`,
                          borderRadius: 6,
                          fontSize: 11,
                        }}
                      />
                      <Bar dataKey="importance" radius={[0, 4, 4, 0]}>
                        {shapData.map((_: any, i: number) => (
                          <Cell
                            key={i}
                            fill={
                              [C.purple, C.blue, C.green, C.amber, C.cyan][
                                i % 5
                              ]
                            }
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </Card>

                <Card>
                  <p
                    style={{
                      fontSize: 13,
                      fontWeight: 700,
                      color: C.text,
                      marginBottom: 14,
                    }}
                  >
                    What drove this prediction?
                  </p>
                  {shapData.map((d: any, i: number) => {
                    const colors = [C.purple, C.blue, C.green, C.amber, C.cyan];
                    const col = colors[i % 5];
                    const insights: Record<string, string> = {
                      occupation: `Occupation (${form.occupation}): Core driver for eligibility and state-specific demand filters.`,
                      state: `Nominated State (${form.state}): Impacts matching bonuses and regional nomination quotas.`,
                      points: `Total Points (${form.points}): Primary threshold component (65+ for 189/190, 50+ for 491).`,
                    };
                    return (
                      <div
                        key={d.feature}
                        style={{
                          marginBottom: 10,
                          padding: "10px 14px",
                          background: `${col}08`,
                          borderRadius: 8,
                          borderLeft: `3px solid ${col}`,
                        }}
                      >
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
                              color: col,
                            }}
                          >
                            {d.feature}
                          </span>
                          <span
                            style={{
                              fontSize: 12,
                              fontWeight: 800,
                              color: col,
                            }}
                          >
                            {d.importance}%
                          </span>
                        </div>
                        <p style={{ fontSize: 11, color: C.muted }}>
                          {insights[d.feature] ||
                            `Importance: ${d.importance}% · This feature significantly influenced the prediction.`}
                        </p>
                      </div>
                    );
                  })}
                </Card>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
