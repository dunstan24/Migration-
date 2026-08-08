"use client";
import { C } from "@/components/ui";

export function Skeleton({ width, height, borderRadius = 8, style }: { width?: string | number, height?: string | number, borderRadius?: number, style?: React.CSSProperties }) {
  return (
    <div
      style={{
        width: width || "100%",
        height: height || 20,
        background: `linear-gradient(90deg, ${C.border}40 25%, ${C.border}80 50%, ${C.border}40 75%)`,
        backgroundSize: "200% 100%",
        borderRadius,
        animation: "shimmer 1.5s infinite linear",
        ...style
      }}
    >
      <style>{`
        @keyframes shimmer {
          0% { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
      `}</style>
    </div>
  );
}

export function SkeletonCircle({ size = 40 }: { size?: number }) {
  return <Skeleton width={size} height={size} borderRadius={size / 2} />;
}
