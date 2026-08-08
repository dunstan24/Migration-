import { useState, useCallback, useEffect } from "react";
import Swal from "sweetalert2";

// Use relative paths that go through Next.js rewrites
const API_BASE = "/api";

export interface ConversationMessage {
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface ConversationSession {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export const useConversation = () => {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isClient, setIsClient] = useState(false);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [loading, setLoading] = useState(false);

  // Load session from localStorage on client side
  // (Moved to after loadSession definition)

  // Create a new conversation session
  const createNewSession = useCallback(async (title?: string) => {
    try {
      console.log("[useConversation] Creating new session with title:", title);
      setLoading(true);
      const res = await fetch(`${API_BASE}/conversation/sessions/new`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });

      if (res.ok) {
        const data = await res.json();
        console.log("[useConversation] Session created:", data.session_id);
        setSessionId(data.session_id);
        localStorage.setItem("current_session_id", data.session_id);
        setMessages([]);
        return data.session_id;
      } else {
        const errorText = await res.text();
        console.error(
          "[useConversation] Session creation failed:",
          res.status,
          errorText,
        );
        throw new Error(`HTTP ${res.status}: ${errorText}`);
      }
    } catch (error) {
      console.error("[useConversation] Failed to create session:", error);
      Swal.fire({
        icon: 'error',
        title: 'Session Error',
        text: `Failed to create session: ${error instanceof Error ? error.message : String(error)}`
      });
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  // Get or create a session
  const getOrCreateSession = useCallback(async () => {
    if (sessionId) {
      console.log("[useConversation] Using existing session:", sessionId);
      return sessionId;
    }
    console.log("[useConversation] No existing session, creating new one");
    return createNewSession();
  }, [sessionId, createNewSession]);

  // Load messages from a session
  const loadSession = useCallback(async (sid: string) => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/conversation/history/${sid}`);
      if (res.ok) {
        const data = await res.json();
        setMessages(data.messages || []);
        setSessionId(sid);
        localStorage.setItem("current_session_id", sid);
      }
    } catch (error) {
      console.error("Failed to load session:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  // Load session from localStorage on client side
  useEffect(() => {
    setIsClient(true);
    const stored = localStorage.getItem("current_session_id");
    if (stored) {
      setSessionId(stored);
      // Automatically load the session history to persist messages when user navigates away and comes back
      loadSession(stored);
    }
  }, [loadSession]);

  // Add message to local state (messages are saved by backend during chat)
  const addMessage = useCallback(
    (role: "user" | "assistant", content: string) => {
      const now = new Date().toISOString();
      console.log(
        `[useConversation] Adding ${role} message, length: ${content.length}`,
      );
      setMessages((prev) => [...prev, { role, content, created_at: now }]);
    },
    [],
  );

  // Delete a session
  const deleteSession = useCallback(
    async (sid: string) => {
      try {
        const res = await fetch(`${API_BASE}/conversation/delete/${sid}`, {
          method: "DELETE",
        });
        if (res.ok) {
          if (sessionId === sid) {
            setSessionId(null);
            localStorage.removeItem("current_session_id");
            setMessages([]);
          }
          return true;
        }
      } catch (error) {
        console.error("Failed to delete session:", error);
      }
      return false;
    },
    [sessionId],
  );

  // Clear current conversation
  const clearConversation = useCallback(() => {
    setSessionId(null);
    localStorage.removeItem("current_session_id");
    setMessages([]);
  }, []);

  return {
    sessionId,
    messages,
    loading,
    createNewSession,
    getOrCreateSession,
    loadSession,
    addMessage,
    deleteSession,
    clearConversation,
  };
};

export default useConversation;
