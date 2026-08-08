/**
 * hooks/useSSE.js
 * Server-Sent Events hook for Claude streaming chat.
 * Matches README spec: reads stream token by token via res.body.getReader()
 */
import { useState, useCallback } from "react";

/**
 * streamChat — low-level SSE reader
 * POST /api/llm/chat → SSE stream → calls onToken per chunk
 */
export async function streamChat(message, sessionId, onToken, onDone, onError) {
  try {
<<<<<<< HEAD
    // Use relative paths that go through Next.js rewrites
    const res = await fetch("/api/llm/chat", {
=======
    const apiBaseUrl =
      typeof window !== "undefined" ? "" : (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000");
    const res = await fetch(`${apiBaseUrl}/api/llm/chat`, {
>>>>>>> 19d9ef25318a8872011672c306f477146d948b87
      method: "POST",
      body: JSON.stringify({ message, session_id: sessionId }),
      headers: { "Content-Type": "application/json" },
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });

      // Parse SSE format: "data: {...}\n\n"
      const lines = chunk.split("\n");
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6).trim();
          if (data === "[DONE]") {
            onDone?.();
            return;
          }
          try {
            const parsed = JSON.parse(data);
            if (parsed.token) onToken(parsed.token);
          } catch {
            // raw text fallback
            if (data) onToken(data);
          }
        }
      }
    }
    onDone?.();
  } catch (err) {
    onError?.(err.message || "Stream error");
  }
}

/**
 * useSSE hook
 * Returns: { messages, isStreaming, sendMessage, clearMessages }
 */
export function useSSE(sessionId) {
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState(null);

  const sendMessage = useCallback(
    async (text) => {
      if (!text.trim() || isStreaming) return;

      // Add user message
      const userMsg = { role: "user", content: text, id: Date.now() };
      setMessages((prev) => [...prev, userMsg]);

      // Add empty assistant message to stream into
      const assistantId = Date.now() + 1;
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "", id: assistantId, streaming: true },
      ]);
      setIsStreaming(true);
      setError(null);

      await streamChat(
        text,
        sessionId,
        (token) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: m.content + token } : m,
            ),
          );
        },
        () => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, streaming: false } : m,
            ),
          );
          setIsStreaming(false);
        },
        (err) => {
          setError(err);
          setIsStreaming(false);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: "Error: " + err, streaming: false }
                : m,
            ),
          );
        },
      );
    },
    [isStreaming, sessionId],
  );

  const clearMessages = useCallback(() => setMessages([]), []);

  return { messages, isStreaming, error, sendMessage, clearMessages };
}
