import React from "react";
// Shared UI primitives used across all pages

export const C = {
  bg:      "var(--bg)",
  surface: "var(--surface)",
  surfaceAlt: "var(--surface-alt)",
  border:  "var(--border)",
  text:    "var(--text)",
  muted:   "var(--muted)",
  dimmed:  "var(--dimmed)",
  blue:    "#2a8bff",
  green:   "#10b981",
  amber:   "#f59e0b",
  purple:  "#8b5cf6",
  red:     "#ef4444",
  cyan:    "#06b6d4",
  orange:  "#f97316",
  hover:   "var(--hover)",
};

export function Card({ children, style, className }: { children: React.ReactNode; style?: React.CSSProperties; className?: string }) {
  return (
    <div className={className} style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: 20, ...style }}>
      {children}
    </div>
  );
}

export function KPICard({ label, value, sub, color }: { label: string; value: string; sub: string; color: string }) {
  return (
    <Card>
      <p style={{ fontSize: 11, color: C.dimmed, textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 600, marginBottom: 6 }}>{label}</p>
      <p style={{ fontSize: 28, fontWeight: 800, color, lineHeight: 1, marginBottom: 5 }}>{value}</p>
      <p style={{ fontSize: 11, color: C.muted }}>{sub}</p>
    </Card>
  );
}

export function ChartHeader({ color, children }: { color: string; children: React.ReactNode }) {
  return (
    <p style={{ fontSize: 13, fontWeight: 600, color: C.text, marginBottom: 16, display: "flex", alignItems: "center", gap: 7 }}>
      <span style={{ width: 7, height: 7, borderRadius: "50%", background: color, display: "inline-block" }} />
      {children}
    </p>
  );
}

export function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span style={{ background: color + "20", color, fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 4, border: `1px solid ${color}40`, letterSpacing: "0.04em" }}>
      {label}
    </span>
  );
}

export function ChartTip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 8, padding: "10px 14px", fontSize: 12 }}>
      <p style={{ color: C.muted, marginBottom: 6 }}>{label}</p>
      {payload.map((p: any) => (
        <p key={p.name} style={{ color: p.color || C.muted, margin: "2px 0" }}>
          {p.name}: <strong style={{ color: C.text }}>{typeof p.value === "number" ? p.value.toLocaleString() : p.value}</strong>
        </p>
      ))}
    </div>
  );
}

export function PageWrapper({ title = "", sub, children }: { title?: string; sub?: string; children: React.ReactNode }) {
  return (
    <div className="page-wrapper-root" style={{ padding: "28px 32px", maxWidth: 1440 }}>
      <div style={{ marginBottom: 22 }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, color: "var(--text)", marginBottom: 4 }}>{title}</h1>
        {sub && <p style={{ fontSize: 12, color: C.muted }}>{sub}</p>}
      </div>
      {children}
    </div>
  );
}

export const Grid = {
  two:  { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 320px), 1fr))", gap: 16, marginBottom: 22 } as React.CSSProperties,
  three:{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 280px), 1fr))", gap: 16, marginBottom: 22 } as React.CSSProperties,
  four: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 200px), 1fr))", gap: 14, marginBottom: 22 } as React.CSSProperties,
};

export function Pagination({ page, totalPages, setPage }: { page: number, totalPages: number, setPage: (p: number | ((prev: number) => number)) => void }) {
  const [inputVal, setInputVal] = React.useState(String(page));
  
  React.useEffect(() => {
    setInputVal(String(page));
  }, [page]);

  const handleJump = () => {
    const p = parseInt(inputVal);
    if (!isNaN(p) && p >= 1 && p <= totalPages) {
      setPage(p);
    } else {
      setInputVal(String(page));
    }
  };

  if (totalPages <= 1) return null;
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 20px", borderTop: `1px solid ${C.border}`, background: "rgba(255,255,255,0.01)" }}>
      <button
        disabled={page === 1}
        onClick={() => setPage(p => Math.max(1, p - 1))}
        style={{ padding: "6px 14px", borderRadius: 8, border: `1px solid ${C.border}`, background: page === 1 ? "transparent" : C.surface, color: page === 1 ? C.dimmed : C.text, cursor: page === 1 ? "not-allowed" : "pointer", fontSize: 12, fontWeight: 600, transition: "all 0.2s" }}
      >
        Previous
      </button>
      
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ fontSize: 12, color: C.muted }}>Page</span>
        <input 
          value={inputVal}
          onChange={e => setInputVal(e.target.value)}
          onKeyDown={e => e.key === "Enter" && handleJump()}
          onBlur={handleJump}
          style={{ 
            width: 44, 
            textAlign: "center", 
            background: C.bg, 
            border: `1px solid ${C.border}`, 
            borderRadius: 6, 
            padding: "4px 0", 
            fontSize: 12, 
            fontWeight: 700, 
            color: C.blue,
            outline: "none"
          }}
        />
        <span style={{ fontSize: 12, color: C.muted }}>
          of <strong style={{ color: C.text }}>{totalPages}</strong>
        </span>
      </div>

      <button
        disabled={page === totalPages}
        onClick={() => setPage(p => Math.min(totalPages, p + 1))}
        style={{ padding: "6px 14px", borderRadius: 8, border: `1px solid ${C.border}`, background: page === totalPages ? "transparent" : C.surface, color: page === totalPages ? C.dimmed : C.text, cursor: page === totalPages ? "not-allowed" : "pointer", fontSize: 12, fontWeight: 600, transition: "all 0.2s" }}
      >
        Next
      </button>
    </div>
  );
}
