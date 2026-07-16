import { useCallback, useEffect, useRef, useState } from "react";

/**
 * WebSocket hook for real-time chat with Sofie.
 *
 * Handles connection lifecycle, auto-reconnect, and message parsing.
 * Returns send function and message state so components stay declarative.
 */
export default function useWebSocket(conversationId) {
  const [messages, setMessages] = useState([]);
  const [status, setStatus] = useState("connecting");
  const [pipelineStatus, setPipelineStatus] = useState("");
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const pendingRef = useRef([]);

  const connect = useCallback(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const ws = new WebSocket(`${protocol}//${host}/ws/${conversationId}`);

    ws.onopen = () => {
      setStatus("connected");
      // Flush any messages queued while the socket was down (e.g. a brief
      // re-uploaded during the reconnect after a validation block).
      const queued = pendingRef.current;
      pendingRef.current = [];
      for (const payload of queued) {
        try {
          ws.send(payload);
        } catch {
          pendingRef.current.push(payload);
        }
      }
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === "status") {
          setPipelineStatus(data.content);
        } else {
          setMessages((prev) => [...prev, data]);
          if (data.type !== "status") {
            setPipelineStatus("");
          }
        }
      } catch {
        // Non-JSON message — treat as plain text from Sofie
        setMessages((prev) => [
          ...prev,
          { type: "message", role: "sofie", content: event.data },
        ]);
      }
    };

    ws.onclose = () => {
      setStatus("disconnected");
      // Auto-reconnect after 3 seconds
      reconnectTimer.current = setTimeout(connect, 3000);
    };

    ws.onerror = () => {
      setStatus("error");
    };

    wsRef.current = ws;
  }, [conversationId]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  const sendMessage = useCallback((type, content, metadata = {}) => {
    const payload = JSON.stringify({ type, content, metadata });

    // Optimistically echo user-authored messages regardless of socket state.
    if (type === "message" || type === "feedback") {
      setMessages((prev) => [
        ...prev,
        { type: "message", role: "user", content },
      ]);
    }

    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(payload);
    } else {
      // Socket is connecting/reconnecting — queue and flush on open so the
      // message (e.g. a re-uploaded brief) isn't silently dropped.
      pendingRef.current.push(payload);
    }
  }, []);

  return { messages, status, pipelineStatus, sendMessage };
}
