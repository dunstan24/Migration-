"use client";
import { C } from "@/components/ui";

export function FormLabel({ text, sub }: { text: string; sub?: string }) {
  return (
    <div style={{ marginBottom: 6 }}>
      <p
        style={{
          fontSize: 11,
          fontWeight: 700,
          color: C.muted,
          textTransform: "uppercase",
          letterSpacing: "0.07em",
        }}
      >
        {text}
      </p>
      {sub && (
        <p style={{ fontSize: 10, color: "#374151", marginTop: 1 }}>{sub}</p>
      )}
    </div>
  );
}
