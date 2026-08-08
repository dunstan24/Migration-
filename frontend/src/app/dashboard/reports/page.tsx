"use client";
/**
 * Reports Page
 * Route: /dashboard/reports
 * Generates a PDF client report via GET /api/reports/generate
 * Uses same input logic as pathway and approval pages
 */
import { useState, useEffect, useRef } from "react";
import { C, Card } from "@/components/ui";
import {
  FormLabel,
  Autocomplete,
  AutocompleteSuggestion,
} from "@/components/shared";

const API = "";

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

const REPORT_SECTIONS = [
  {
    id: "eoi",
    icon: "📈",
    title: "EOI Trends",
    desc: "Monthly EOI activity, lodge rates, and top occupations by volume",
    color: "#0891B2",
  },
  {
    id: "shortage",
    icon: "⚠️",
    title: "Shortage Forecast",
    desc: "National & state shortage ratings from DESE OSL 2025",
    color: "#D97706",
  },
  {
    id: "pathway",
    icon: "🗺️",
    title: "Pathway Recommendations",
    desc: "GBM model visa + state combinations ranked by match score",
    color: "#8B5CF6",
  },
  {
    id: "approval",
    icon: "✅",
    title: "Approval Probability",
    desc: "XGBoost What-If analysis across all 8 Australian states",
    color: "#059669",
  },
];

const VISA_OPTIONS = [
  { value: "491", label: "491 — Skilled Work Regional" },
  { value: "190", label: "190 — State Nominated" },
  { value: "189", label: "189 — Skilled Independent" },
];

const ENGLISH_OPTIONS = [
  { value: "superior", label: "Superior (+20 pts)" },
  { value: "proficient", label: "Proficient (+10 pts)" },
  { value: "competent", label: "Competent (around IELTS 6)" },
];

const MONTH_LABELS: Record<number, string> = {
  3: "3 months",
  6: "6 months",
  12: "12 months",
  18: "18 months",
  24: "24 months",
  0: "all data",
};

const STATE_OPTIONS = ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"];

function SectionDivider({
  title,
  color = C.blue,
}: {
  title: string;
  color?: string;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        margin: "16px 0 12px",
      }}
    >
      <div
        style={{ width: 3, height: 14, background: color, borderRadius: 2 }}
      />
      <p
        style={{
          fontSize: 11,
          fontWeight: 700,
          color: C.muted,
          textTransform: "uppercase",
          letterSpacing: "0.07em",
        }}
      >
        {title}
      </p>
    </div>
  );
}

export default function ReportsPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [stepIdx, setStepIdx] = useState(0);

  const [profile, setProfile] = useState({
    // Basic
    occupation: "",
    visa_type: "491",
    state: "NSW",
    points: 80,
    months: 6,
    // Pathway inputs
    english_level: "proficient",
    age: 30,
    experience: 5,
    // Approval inputs
    count_eois: 100,
  });

  // Autocomplete state
  const [searchInputValue, setSearchInputValue] = useState(profile.occupation);
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
    setP("occupation", value); // Fallback: user can type raw code directly

    if (!value.trim()) {
      setSuggestions([]);
      return;
    }

    if (debounceTimeoutRef.current) clearTimeout(debounceTimeoutRef.current);

    debounceTimeoutRef.current = setTimeout(() => {
      setSuggestionsLoading(true);
      fetch(
        `${API}/api/data/shortage-forecast?limit=50&search=${encodeURIComponent(value)}`,
      )
        .then((r) => r.json())
        .then((d) => {
          const uniqueMap = new Map<string, AutocompleteSuggestion>();
          (d.records || []).forEach((r: any) => {
            if (!uniqueMap.has(r.anzsco_code)) {
              uniqueMap.set(r.anzsco_code, {
                anzsco_code: r.anzsco_code,
                occupation: r.occupation,
              });
            }
          });
          setSuggestions(Array.from(uniqueMap.values()).slice(0, 10));
          setSuggestionsLoading(false);
        })
        .catch(() => {
          setSuggestions([]);
          setSuggestionsLoading(false);
        });
    }, 300);
  };

  const handleSelectSuggestion = (s: AutocompleteSuggestion) => {
    setSearchInputValue(`${s.occupation} (${s.anzsco_code})`);
    setP("occupation", s.anzsco_code);
    setIsDropdownOpen(false);
  };

  const setP = (k: string, v: any) => setProfile((f) => ({ ...f, [k]: v }));

  const generate = async () => {
    setLoading(true);
    setError("");
    setSuccess(false);
    setStepIdx(0);

    let i = 0;
    const interval = setInterval(() => {
      i = Math.min(i + 1, progressSteps.length - 1);
      setStepIdx(i);
    }, 1600);

    try {
      const params = new URLSearchParams({
        visa_type: profile.visa_type,
        occupation: profile.occupation,
        state: profile.state,
        points: String(profile.points),
        months: String(profile.months),
        // Pathway
        english_level: profile.english_level,
        age: String(profile.age),
        experience: String(profile.experience),
        // Approval
        count_eois: String(profile.count_eois),
      });

      // Use AbortController with 180s timeout for PDF generation
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 180000); // 3 minutes

      try {
        const res = await fetch(`${API}/api/reports/generate?${params}`, {
          signal: controller.signal,
        });
        clearInterval(interval);
        clearTimeout(timeoutId);

        if (!res.ok) {
          let errMsg = "Unknown error";
          try {
            const bodyText = await res.text();
            try {
              const err = JSON.parse(bodyText);
              errMsg = err.detail || err.message || JSON.stringify(err);
            } catch {
              errMsg = bodyText || `HTTP ${res.status}`;
            }
          } catch {
            errMsg = `HTTP ${res.status}`;
          }
          console.error("❌ PDF Generation Failed:", errMsg);
          throw new Error(errMsg);
        }

        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "Inter_Migration_Intelligence_Report.pdf";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        setSuccess(true);
      } catch (fetchErr: any) {
        clearTimeout(timeoutId);
        throw fetchErr;
      }
    } catch (e: any) {
      clearInterval(interval);
      setError(e.message);
    } finally {
      setLoading(false);
      setStepIdx(0);
    }
  };

  const progressSteps = [
    `Fetching EOI data (${MONTH_LABELS[profile.months] ?? profile.months + " months"})…`,
    "Running shortage analysis…",
    "Computing pathway recommendations…",
    "Building approval analysis…",
    "Generating PDF…",
  ];
  const progressPct = loading
    ? ([10, 30, 50, 70, 90][stepIdx] ?? 10)
    : success
      ? 100
      : 0;
  // Adjusted points preview
  const englishBonus =
    profile.english_level === "superior"
      ? 20
      : profile.english_level === "proficient"
        ? 10
        : 0;
  const adjPoints = profile.points + englishBonus;

  return (
    <div
      suppressHydrationWarning
      style={{
        padding: "24px 28px",
        maxWidth: 1200,
        background: C.bg,
        minHeight: "100vh",
      }}
    >
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            marginBottom: 6,
          }}
        >
          <h1 style={{ fontSize: 22, fontWeight: 800, color: "var(--text)" }}>
            Client Report Generator
          </h1>
          <span
            style={{
              padding: "3px 10px",
              borderRadius: 20,
              fontSize: 11,
              fontWeight: 700,
              background: `${C.purple}20`,
              color: C.purple,
              border: `1px solid ${C.purple}40`,
            }}
          >
            PDF
          </span>
        </div>
        <p style={{ fontSize: 13, color: C.muted }}>
          Generate a professional PDF report — EOI trends, shortage analysis,
          pathway recommendations, and approval probability.
        </p>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(380px, 1fr))",
          gap: 20,
          alignItems: "start",
        }}
      >
        {/* ── LEFT ─────────────────────────────────────────────── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Report contents */}
          <Card>
            <p
              style={{
                fontSize: 13,
                fontWeight: 700,
                color: C.text,
                marginBottom: 16,
              }}
            >
              What&apos;s in the Report
            </p>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
                gap: 10,
              }}
            >
              {REPORT_SECTIONS.map((s) => (
                <div
                  key={s.id}
                  style={{
                    padding: "14px 16px",
                    background: `${s.color}0d`,
                    border: `1px solid ${s.color}30`,
                    borderRadius: 10,
                    display: "flex",
                    gap: 12,
                    alignItems: "flex-start",
                  }}
                >
                  <span style={{ fontSize: 22, flexShrink: 0, marginTop: 1 }}>
                    {s.icon}
                  </span>
                  <div>
                    <p
                      style={{
                        fontSize: 13,
                        fontWeight: 700,
                        color: C.text,
                        marginBottom: 3,
                      }}
                    >
                      {s.title}
                    </p>
                    <p
                      style={{ fontSize: 11, color: C.muted, lineHeight: 1.5 }}
                    >
                      {s.desc}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Slide structure */}
          <Card>
            <p
              style={{
                fontSize: 13,
                fontWeight: 700,
                color: C.text,
                marginBottom: 14,
              }}
            >
              Report Structure · 6 Pages
            </p>
            <div
              style={{
                display: "flex",
                gap: 8,
                overflowX: "auto",
                paddingBottom: 4,
              }}
            >
              {[
                { n: 1, title: "Cover", bg: "#1E2761", tc: "#CADCFC" },
                { n: 2, title: "EOI Trends", bg: "#F8FAFC", tc: "#1E2761" },
                { n: 3, title: "Shortage", bg: "#F8FAFC", tc: "#1E2761" },
                { n: 4, title: "Pathway", bg: "#F8FAFC", tc: "#1E2761" },
                { n: 5, title: "Approval", bg: "#F8FAFC", tc: "#1E2761" },
                { n: 6, title: "Summary", bg: "#1E2761", tc: "#CADCFC" },
              ].map((s) => (
                <div
                  key={s.n}
                  style={{
                    flexShrink: 0,
                    width: 130,
                    height: 74,
                    background: s.bg,
                    border: `1px solid ${C.border}`,
                    borderRadius: 6,
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 4,
                  }}
                >
                  <span
                    style={{
                      fontSize: 9,
                      color: s.n === 1 || s.n === 6 ? "#CADCFC80" : C.muted,
                    }}
                  >
                    Page {s.n}
                  </span>
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      color: s.tc,
                      textAlign: "center",
                      padding: "0 6px",
                    }}
                  >
                    {s.title}
                  </span>
                  <div
                    style={{
                      width: 24,
                      height: 2,
                      borderRadius: 1,
                      background: "#0891B2",
                      marginTop: 2,
                    }}
                  />
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* ── RIGHT: Config + generate ──────────────────────────── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <Card>
            <p
              style={{
                fontSize: 13,
                fontWeight: 700,
                color: C.text,
                marginBottom: 4,
              }}
            >
              Report Profile
            </p>
            <p
              style={{
                fontSize: 11,
                color: C.muted,
                marginBottom: 4,
                lineHeight: 1.5,
              }}
            >
              Fill in all details for accurate pathway and approval predictions.
            </p>

            {/* ── BASIC INFO ── */}
            <SectionDivider title="Basic Info" color={C.blue} />

            <div style={{ marginBottom: 14 }}>
              <FormLabel
                text="Occupation"
                sub="Search by name or ANZSCO code"
              />
              <div style={{ marginTop: 4 }}>
                <Autocomplete
                  inputValue={searchInputValue || profile.occupation}
                  onInputChange={handleSearchInput}
                  suggestions={suggestions}
                  onSelectSuggestion={handleSelectSuggestion}
                  isLoading={suggestionsLoading}
                  isOpen={isDropdownOpen}
                  setIsOpen={setIsDropdownOpen}
                />
              </div>
            </div>

            <div style={{ marginBottom: 12 }}>
              <FormLabel text="Visa Type" />
              <select
                style={sel}
                value={profile.visa_type}
                onChange={(e) => setP("visa_type", e.target.value)}
              >
                {VISA_OPTIONS.map((v) => (
                  <option key={v.value} value={v.value}>
                    {v.label}
                  </option>
                ))}
              </select>
            </div>

            <div style={{ marginBottom: 12 }}>
              <FormLabel text="Preferred State" />
              <select
                style={sel}
                value={profile.state}
                onChange={(e) => setP("state", e.target.value)}
              >
                {STATE_OPTIONS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>

            <div style={{ marginBottom: 12 }}>
              <FormLabel
                text="Points Score"
                sub={`${profile.points} pts base`}
              />
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <input
                  type="range"
                  min={65}
                  max={130}
                  step={5}
                  value={profile.points}
                  onChange={(e) => setP("points", Number(e.target.value))}
                  style={{ flex: 1, accentColor: C.blue }}
                />
                <span
                  style={{
                    fontSize: 16,
                    fontWeight: 800,
                    color: C.blue,
                    minWidth: 36,
                    textAlign: "right",
                  }}
                >
                  {profile.points}
                </span>
              </div>
            </div>

            {/* ── PATHWAY MODEL INPUTS ── */}
            <SectionDivider title="Pathway Model Inputs" color="#8B5CF6" />

            <div style={{ marginBottom: 12 }}>
              <FormLabel
                text="English Level"
                sub="Professional English proficiency"
              />
              <select
                style={sel}
                value={profile.english_level}
                onChange={(e) => setP("english_level", e.target.value)}
              >
                {ENGLISH_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Adjusted points preview */}
            <div
              style={{
                padding: "8px 12px",
                background: `${C.purple}10`,
                border: `1px solid ${C.purple}30`,
                borderRadius: 8,
                marginBottom: 14,
              }}
            >
              <p style={{ fontSize: 11, color: C.purple }}>
                Adjusted points for pathway: <strong>{adjPoints} pts</strong>
                {englishBonus > 0 && (
                  <span style={{ color: C.muted }}>
                    {" "}
                    ({profile.points} + {englishBonus} English bonus)
                  </span>
                )}
              </p>
            </div>

            {/* ── APPROVAL MODEL INPUTS ── */}
            <SectionDivider title="Approval Model Inputs" color={C.green} />

            <div style={{ marginBottom: 14 }}>
              <FormLabel
                text="EOI Count in Cohort"
                sub="Estimated EOIs in your occupation/state/visa group"
              />
              {(() => {
                const eoi_values = [
                  10,
                  ...Array.from({ length: 49 }, (_, i) => 20 + i * 10),
                ];
                const current_idx = eoi_values.indexOf(profile.count_eois);
                return (
                  <>
                    <div
                      style={{ display: "flex", alignItems: "center", gap: 10 }}
                    >
                      <input
                        type="range"
                        min={0}
                        max={eoi_values.length - 1}
                        step={1}
                        value={current_idx >= 0 ? current_idx : 0}
                        onChange={(e) =>
                          setP("count_eois", eoi_values[Number(e.target.value)])
                        }
                        style={{ flex: 1, accentColor: C.green }}
                      />
                      <span
                        style={{
                          fontSize: 16,
                          fontWeight: 800,
                          color: C.green,
                          minWidth: 40,
                          textAlign: "right",
                        }}
                      >
                        {profile.count_eois === 10 ? "<20" : profile.count_eois}
                      </span>
                    </div>
                    <p style={{ fontSize: 10, color: C.muted, marginTop: 4 }}>
                      {profile.count_eois <= 20
                        ? "↓ Small queue — higher approval probability"
                        : profile.count_eois >= 100
                          ? "↑ Large queue — more competition"
                          : "Medium queue size"}
                    </p>
                  </>
                );
              })()}
            </div>

            {/* Generate button */}
            <button
              onClick={generate}
              disabled={loading}
              style={{
                width: "100%",
                padding: "13px 0",
                borderRadius: 8,
                border: "none",
                cursor: loading ? "not-allowed" : "pointer",
                background: loading ? C.border : C.blue,
                color: "#fff",
                fontSize: 14,
                fontWeight: 700,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 8,
              }}
            >
              {loading ? (
                <>
                  <span>⏳</span> Generating…
                </>
              ) : (
                <>
                  <span>📄</span> Generate PDF Report
                </>
              )}
            </button>

            {/* Progress */}
            {loading && (
              <div style={{ marginTop: 12 }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginBottom: 6,
                  }}
                >
                  <p style={{ fontSize: 11, color: C.blue }}>
                    {progressSteps[stepIdx]}
                  </p>
                  <p style={{ fontSize: 11, color: C.muted }}>{progressPct}%</p>
                </div>
                <div
                  style={{
                    height: 4,
                    borderRadius: 2,
                    background: C.border,
                  }}
                >
                  <div
                    style={{
                      height: "100%",
                      borderRadius: 2,
                      background: C.blue,
                      width: `${progressPct}%`,
                      transition: "width 0.8s ease",
                    }}
                  />
                </div>
              </div>
            )}

            {/* Success */}
            {success && !loading && (
              <div
                style={{
                  marginTop: 12,
                  padding: "12px 14px",
                  background: `${C.green}10`,
                  border: `1px solid ${C.green}30`,
                  borderRadius: 8,
                }}
              >
                <p style={{ fontSize: 12, color: C.green, fontWeight: 700 }}>
                  ✅ Report downloaded successfully
                </p>
                <p style={{ fontSize: 11, color: C.muted, marginTop: 4 }}>
                  Check your downloads folder.
                </p>
              </div>
            )}

            {/* Error */}
            {error && (
              <div
                style={{
                  marginTop: 12,
                  padding: "10px 14px",
                  background: `${C.red}10`,
                  border: `1px solid ${C.red}30`,
                  borderRadius: 8,
                }}
              >
                <p
                  style={{
                    fontSize: 12,
                    color: "#ef4444",
                    fontWeight: 700,
                    marginBottom: 4,
                  }}
                >
                  ❌ Generation failed
                </p>
                <p style={{ fontSize: 11, color: "#ef4444" }}>{error}</p>
              </div>
            )}
          </Card>

          {/* Format info */}
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
              Output Format
            </p>
            {[
              ["Format", "PDF (landscape 1280×720)"],
              ["Pages", "6 slides"],
              ["Pipeline", "Python → Node → Puppeteer → PDF"],
              ["Branding", "Inter Intelligence · Dark Executive"],
              ["Data", "Live from migration_db (MySQL)"],
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
      </div>
    </div>
  );
}
