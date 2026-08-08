"use client";
import { C } from "@/components/ui";

export function ScoreBadge({ score, label }: { score: number, label?: string }) {
  const n = score > 1 ? score / 100 : score;
  const color = n >= 0.8 ? C.green : n >= 0.6 ? C.blue : n >= 0.4 ? C.amber : C.red;
  const text = label || (n >= 0.8 ? "High" : n >= 0.6 ? "Good" : n >= 0.4 ? "Moderate" : "Low");

  return (
    <span
      style={{
        background: `${color}15`,
        color,
        fontSize: 10,
        fontWeight: 700,
        padding: "3px 8px",
        borderRadius: 5,
        border: `1px solid ${color}40`,
        textTransform: "uppercase",
        letterSpacing: "0.04em"
      }}
    >
      {text}
    </span>
  );
}
