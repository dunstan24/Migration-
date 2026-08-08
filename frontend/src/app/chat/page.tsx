"use client";

import React, { useState, useEffect, useRef } from "react";
import styles from "./chat.module.css";
import ConversationHistory from "@/components/ConversationHistory";
import { useConversation } from "@/hooks/useConversation";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import Swal from "sweetalert2";

const API_BASE = "/api";

interface StreamMessage {
  token?: string;
}

export default function ChatPage() {
  const { status } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/login");
    }
  }, [status, router]);

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
  const [showHistory, setShowHistory] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to latest message or streaming content
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  // Load draft input on mount
  useEffect(() => {
    const draft = localStorage.getItem("chat_draft_input");
    if (draft) {
      setInput(draft);
    }
  }, []);

  // Save draft input when it changes
  useEffect(() => {
    if (input !== "") {
      localStorage.setItem("chat_draft_input", input);
    } else {
      localStorage.removeItem("chat_draft_input");
    }
  }, [input]);

  const handleNewChat = async () => {
    const newSessionId = await createNewSession("New Chat");
    if (newSessionId) {
      setInput("");
      localStorage.removeItem("chat_draft_input");
      setStreamingContent("");
    }
  };

  const handleSendMessage = async () => {
    if (!input.trim() || streaming) return;

    const userMessage = input;
    setInput("");
    localStorage.removeItem("chat_draft_input");
    setStreamingContent("");

    try {
      // Get or create session
      const sid = await getOrCreateSession();
      if (!sid) {
        Swal.fire({ icon: 'error', title: 'Error', text: 'Failed to create session' });
        return;
      }

      // Add user message to UI immediately
      addMessage("user", userMessage);

      // Start streaming state
      setStreaming(true);
      let fullResponse = "";

      const response = await fetch(`${API_BASE}/llm/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMessage,
          session_id: sid,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error("No response body");
      }

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
                // ✅ Update UI in real-time — no more "stuck" feeling
                setStreamingContent(fullResponse);
              }
            } catch {
              // Ignore parse errors (partial SSE chunks are normal)
            }
          }
        }
      }

      // Streaming complete — commit to permanent messages list
      if (fullResponse) {
        addMessage("assistant", fullResponse);
      }
    } catch (error) {
      console.error("Error sending message:", error);
      addMessage(
        "assistant",
        `Error: ${error instanceof Error ? error.message : "Unknown error"}`,
      );
    } finally {
      setStreaming(false);
      setStreamingContent("");
    }
  };

  return (
    <div className={styles.container}>
      {/* History Sidebar */}
      {showHistory && (
        <div className={styles.historySidebar}>
          <ConversationHistory />
        </div>
      )}

      {/* Chat Main */}
      <div className={styles.chatMain}>
        {/* Header */}
        <div className={styles.header}>
          <button
            className={styles.toggleHistory}
            onClick={() => setShowHistory(!showHistory)}
            title="Toggle history"
          >
            {showHistory ? "◀" : "▶"}
          </button>
          <h1>Migration AI Chat</h1>
          <button className={styles.newChatBtn} onClick={handleNewChat}>
            + New Chat
          </button>
        </div>

        {/* Messages */}
        <div className={styles.messagesContainer}>
          {messages.length === 0 && !streaming ? (
            <div className={styles.emptyState}>
              <h2>Start a Conversation</h2>
              <p>
                Ask me about Australian migration visas, occupations, shortages,
                and more!
              </p>
              <div className={styles.exampleQuestions}>
                <button
                  onClick={() => {
                    setInput("Tell me about nurse shortages in Australia");
                  }}
                >
                  Tell me about nurse shortages
                </button>
                <button
                  onClick={() => {
                    setInput("Which IT occupations have the highest demand?");
                  }}
                >
                  Highest demand IT occupations
                </button>
              </div>
            </div>
          ) : (
            <div className={styles.messages}>
              {messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`${styles.message} ${styles[msg.role]}`}
                >
                  <div className={styles.messageRole}>
                    {msg.role === "user" ? "You" : "Assistant"}
                  </div>
                  <div className={styles.messageContent}>{msg.content}</div>
                </div>
              ))}

              {/* Live streaming message — updates word-by-word as tokens arrive */}
              {streaming && (
                <div className={`${styles.message} ${styles.assistant}`}>
                  <div className={styles.messageRole}>Assistant</div>
                  <div className={styles.messageContent}>
                    {streamingContent ? (
                      <>
                        {streamingContent}
                        <span className={styles.cursor}>▋</span>
                      </>
                    ) : (
                      <span className={styles.typing}>Thinking...</span>
                    )}
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input */}
        <div className={styles.inputArea}>
          <textarea
            className={styles.input}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSendMessage();
              }
            }}
            placeholder="Ask me anything about Australian migration..."
            disabled={streaming}
          />
          <button
            className={styles.sendBtn}
            onClick={handleSendMessage}
            disabled={!input.trim() || streaming}
          >
            {streaming ? "Responding..." : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}
