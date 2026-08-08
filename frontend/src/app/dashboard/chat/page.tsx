"use client";

/**
 * Advanced Dashboard Chat — Powered by Google Gemini
 * Features:
 * - Real-time streaming tokens with manual SSE decoding
 * - Conversational memory via session_id
 * - Self-Correction status updates
 * - Premium UI with PageWrapper and Status Sidebars
 */

import React, { useState, useEffect, useRef } from "react";
import styles from "./page.module.css";
import { useConversation } from "@/hooks/useConversation";
import { C, Card, Badge, PageWrapper } from "@/components/ui";
import Swal from "sweetalert2";

// Use relative paths for backend rewrites
const API_BASE = "/api";

interface StreamMessage {
  token?: string;
}

const SUGGESTED_QUESTIONS = [
  "Tell me about nurse shortages in Australia",
  "What are the requirements for Visa 190?",
  "Which IT occupations have the highest demand?",
];

const DATA_INDICATORS = [
  { label: "EOI Records", value: "8.3M+", detail: "2024–2026" },
  { label: "Shortage OSL", value: "Active", detail: "Phase 1-16 complete" },
  { label: "JSA Labour", value: "Synced", detail: "Skills & Demos" },
  { label: "NERO Index", value: "Ready", detail: "Regional Stability" },
];

export default function DashboardChatPage() {
  const {
    sessionId,
    messages,
    loading,
    createNewSession,
    getOrCreateSession,
    addMessage,
  } = useConversation();

  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [lastMessageTime, setLastMessageTime] = useState<Date | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    if (messages.length > 0) {
      setLastMessageTime(new Date());
    }
  }, [messages, streamingContent]);

  const handleNewChat = async () => {
    const newSessionId = await createNewSession("New Chat");
    if (newSessionId) {
      setInput("");
      setStreamingContent("");
    }
  };

  const handleSendMessage = async (customMsg?: string) => {
    const userMessage = customMsg || input;
    if (!userMessage.trim() || streaming) return;

    setInput("");
    setStreamingContent("");

    try {
      // Get or create session
      const sid = await getOrCreateSession();
      if (!sid) {
        Swal.fire({ icon: 'error', title: 'Error', text: 'Session initialization failed.' });
        return;
      }

      // Add user message to UI
      addMessage("user", userMessage);

      setStreaming(true);
      let fullResponse = "";

      // 5-minute timeout for deep data queries
      const abortController = new AbortController();
      const timeoutId = setTimeout(() => abortController.abort(), 300000);

      const response = await fetch(`${API_BASE}/llm/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMessage,
          session_id: sid,
        }),
        signal: abortController.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(
          `Terminal error: ${response.status} ${response.statusText}`,
        );
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) throw new Error("Stream reader not available.");

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const jsonStr = line.slice(6).trim();
            if (jsonStr === "[DONE]") continue;

            try {
              const data = JSON.parse(jsonStr) as StreamMessage;
              if (data.token) {
                fullResponse += data.token;
                setStreamingContent(fullResponse);
              }
            } catch {
              // Ignore partial JSON chunks
            }
          }
        }
      }

      // Finalize message
      if (fullResponse) {
        addMessage("assistant", fullResponse);
      }
    } catch (error) {
      console.error("Chat Error:", error);
      const msg = error instanceof Error ? error.message : "Network error";
      addMessage(
        "assistant",
        `⚠️ Error: ${msg}. Please check if the backend is running.`,
      );
    } finally {
      setStreaming(false);
      setStreamingContent("");
    }
  };

  return (
    <PageWrapper
      title="Migration Advisor Chat"
      sub="Advanced Data Intelligence with Self-Correction & Real-time Verification"
    >
      <div className={styles.mainGrid}>
        {/* LEFT COLUMN: CHAT WINDOW */}
        <Card className={styles.chatCard}>
          {/* Header */}
          <div className={styles.chatHeader}>
            <div className={styles.chatTitleGroup}>
              <div
                className={styles.statusDot}
                style={{ background: streaming ? C.amber : C.green }}
              ></div>
              <div>
                <p className={styles.expertName}>
                  Migration Expert (Gemini 2.5)
                </p>
                <p className={styles.expertSub}>
                  Verified Database & RAG 2.0 Ingested
                </p>
              </div>
            </div>
            <button onClick={handleNewChat} className={styles.resetBtn}>
              Reset Chat
            </button>
          </div>

          {/* Messages Area */}
          <div className={styles.messagesList}>
            {messages.length === 0 && !streaming ? (
              <div className={styles.emptyState}>
                <div className={styles.emptyIcon}>✦</div>
                <h3>Ask about Australian Migration</h3>
                <p>
                  Knowledge base is indexed with 25,000+ localized documents.
                </p>

                <div className={styles.suggestedGrid}>
                  {SUGGESTED_QUESTIONS.map((q) => (
                    <button
                      key={q}
                      onClick={() => handleSendMessage(q)}
                      className={styles.suggestedItem}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className={styles.messageGroup}>
                {messages.map((m, i) => (
                  <div
                    key={i}
                    className={`${styles.message} ${styles[m.role]}`}
                  >
                    <div className={styles.messageLabel}>
                      {m.role === "user" ? "You" : "Advisor"}
                    </div>
                    <div className={styles.messageContent}>{m.content}</div>
                  </div>
                ))}

                {streaming && (
                  <div className={`${styles.message} ${styles.assistant}`}>
                    <div className={styles.messageLabel}>Advisor</div>
                    <div className={styles.messageContent}>
                      {streamingContent || "Thinking..."}
                      <span className={styles.pulseCursor}>▋</span>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          {/* Input Area */}
          <div className={styles.inputSection}>
            <div className={styles.inputContainer}>
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSendMessage();
                  }
                }}
                placeholder="Type your migration query here..."
                disabled={streaming}
                className={styles.textField}
              />
              <button
                onClick={() => handleSendMessage()}
                disabled={streaming || !input.trim()}
                className={styles.sendIconBtn}
              >
                {streaming ? "..." : "→"}
              </button>
            </div>
          </div>
        </Card>

        {/* RIGHT COLUMN: STATUS & INFO */}
        <div className={styles.sidebar}>
          <Card className={styles.sidebarCard}>
            <h4>System Intelligence</h4>
            <div className={styles.statusList}>
              <div className={styles.statItem}>
                <span className={styles.statLabel}>Self-Correction</span>
                <Badge label="ACTIVE" color={C.blue} />
              </div>
              <div className={styles.statItem}>
                <span className={styles.statLabel}>Typo Protection</span>
                <Badge label="ENABLED" color={C.green} />
              </div>
              <div className={styles.divider}></div>
              <p className={styles.sidebarNote}>
                AI will retry queries with alternative strategies if initial
                results are suspicious.
              </p>
            </div>
          </Card>

          <Card className={styles.sidebarCard}>
            <h4>Knowledge Base</h4>
            <div className={styles.dataGrid}>
              {DATA_INDICATORS.map((d) => (
                <div key={d.label} className={styles.dataIndicator}>
                  <div className={styles.indicatorHead}>
                    <span className={styles.indicatorLabel}>{d.label}</span>
                    <span className={styles.indicatorValue}>{d.value}</span>
                  </div>
                  <div className={styles.indicatorSub}>{d.detail}</div>
                </div>
              ))}
            </div>
          </Card>

          <div className={styles.activeSession} title={sessionId || ""}>
            <span className={styles.sessionLabel}>Active Session:</span>
            <span className={styles.sessionHash}>
              {sessionId ? sessionId.substring(0, 8) : "None"}
            </span>
          </div>
        </div>
      </div>
    </PageWrapper>
  );
}
