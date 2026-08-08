"use client";
import { C, Card } from "@/components/ui";
import { ScoreBadge } from "./ScoreBadge";

export function PredictorCard({ 
  title, 
  subtitle, 
  value, 
  score, 
  icon = "🎯",
  loading = false 
}: { 
  title: string; 
  subtitle: string; 
  value: string; 
  score?: number; 
  icon?: string;
  loading?: boolean;
}) {
  return (
    <Card style={{ position: "relative", overflow: "hidden" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
        <div>
          <p style={{ fontSize: 11, fontWeight: 700, color: C.muted, textTransform: "uppercase", letterSpacing: "0.05em" }}>{title}</p>
          <p style={{ fontSize: 10, color: C.dimmed }}>{subtitle}</p>
        </div>
        <div style={{ textAlign: "right" }}>
          {score !== undefined ? (
            <p style={{ fontSize: 20, fontWeight: 900, color: C.blue, lineHeight: 1 }}>
              {(score * 100).toFixed(0)}%
            </p>
          ) : (
            <span style={{ fontSize: 18 }}>{icon}</span>
          )}
        </div>
      </div>
      
      <div style={{ marginBottom: 14 }}>
        <p style={{ fontSize: 24, fontWeight: 900, color: C.text, lineHeight: 1.2 }}>{value}</p>
      </div>

      {score !== undefined && (
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <ScoreBadge score={score} />
          <span style={{ fontSize: 11, color: C.muted }}>confidence rating</span>
        </div>
      )}
    </Card>
  );
}
