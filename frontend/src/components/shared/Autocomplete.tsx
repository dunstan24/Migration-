import { useEffect, useRef } from "react";
import { C } from "@/components/ui";

export interface AutocompleteSuggestion {
  anzsco_code: string;
  occupation: string;
}

export function Autocomplete({
  inputValue,
  onInputChange,
  suggestions,
  onSelectSuggestion,
  isLoading,
  isOpen,
  setIsOpen,
}: {
  inputValue: string;
  onInputChange: (value: string) => void;
  suggestions: AutocompleteSuggestion[];
  onSelectSuggestion: (suggestion: AutocompleteSuggestion) => void;
  isLoading: boolean;
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
}) {
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [setIsOpen]);

  return (
    <div style={{ position: "relative" }} ref={dropdownRef}>
      <div style={{ position: "relative" as const }}>
        <span
          style={{
            position: "absolute" as const,
            left: 14,
            top: "50%",
            transform: "translateY(-50%)",
            color: C.muted,
            fontSize: 14,
          }}
        >
          🔍
        </span>
        <input
          value={inputValue}
          onChange={(e) => {
            onInputChange(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          placeholder="Type occupation name or ANZSCO code (e.g., '2212' or 'software engineer')…"
          style={{
            width: "100%",
            padding: "9px 14px 9px 38px",
            borderRadius: 8,
            fontSize: 12,
            border: `1px solid ${inputValue ? C.cyan : C.border}`,
            background: C.bg,
            color: C.text,
            outline: "none",
            boxSizing: "border-box" as const,
            transition: "all 0.2s",
          }}
        />
        {inputValue && (
          <button
            onClick={() => {
              onInputChange("");
              setIsOpen(false);
            }}
            style={{
              position: "absolute" as const,
              right: 12,
              top: "50%",
              transform: "translateY(-50%)",
              background: "none",
              border: "none",
              color: C.muted,
              cursor: "pointer",
              fontSize: 16,
            }}
          >
            ×
          </button>
        )}
      </div>

      {/* Dropdown */}
      {isOpen && inputValue && (
        <div
          style={{
            position: "absolute" as const,
            top: "100%",
            left: 0,
            right: 0,
            background: C.surface,
            border: `1px solid ${C.border}`,
            borderTop: "none",
            borderRadius: "0 0 8px 8px",
            maxHeight: 300,
            overflowY: "auto",
            zIndex: 1000,
            boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
          }}
        >
          {isLoading ? (
            <div
              style={{
                padding: 16,
                textAlign: "center",
                color: C.muted,
                fontSize: 12,
              }}
            >
              Loading suggestions…
            </div>
          ) : suggestions.length === 0 ? (
            <div
              style={{
                padding: 16,
                textAlign: "center",
                color: C.muted,
                fontSize: 12,
              }}
            >
              No matches found
            </div>
          ) : (
            suggestions.map((suggestion, index) => (
              <div
                key={`${suggestion.anzsco_code}-${index}`}
                onClick={() => {
                  onSelectSuggestion(suggestion);
                  setIsOpen(false);
                }}
                style={{
                  padding: "10px 14px",
                  borderBottom: `1px solid ${C.border}`,
                  cursor: "pointer",
                  background: index % 2 === 0 ? "transparent" : C.surfaceAlt,
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLElement).style.background =
                    C.border + "30";
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLElement).style.background =
                    index % 2 === 0 ? "transparent" : C.surfaceAlt;
                }}
              >
                <div>
                  <div style={{ fontSize: 12, color: C.text, fontWeight: 500 }}>
                    {suggestion.occupation}
                  </div>
                  <div
                    style={{
                      fontSize: 10,
                      color: C.muted,
                      marginTop: 2,
                      fontFamily: "monospace",
                    }}
                  >
                    {suggestion.anzsco_code}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
