import { useMemo } from "react";
import ChatWindow from "./components/ChatWindow";
import useWebSocket from "./hooks/useWebSocket";

/**
 * Root app component — single-page chat interface.
 *
 * Generates a conversation ID on mount and maintains it for the
 * session. No routing needed — chat is the only view.
 */
export default function App() {
  const conversationId = useMemo(
    () => `CONV-${crypto.randomUUID().replace(/-/g, "").slice(0, 12)}`,
    []
  );

  const { messages, status, pipelineStatus, sendMessage } =
    useWebSocket(conversationId);

  const online = status === "connected";

  return (
    <div className="h-screen flex flex-col bg-ground text-ink">
      {/* Header */}
      <header className="border-b border-hairline px-5 sm:px-6 py-3.5 flex items-center gap-3">
        <div className="w-9 h-9 rounded-[10px] bg-accent shadow-glow-sm flex items-center justify-center">
          <span className="font-display font-black text-white text-lg leading-none -translate-y-px">
            S
          </span>
        </div>
        <div className="leading-tight">
          <h1 className="font-display font-extrabold tracking-wide text-[15px] text-ink">
            SOFIE
          </h1>
          <p className="text-[10px] uppercase tracking-[0.14em] text-muted-dim">
            Studio Orchestrator
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${
              online ? "bg-good shadow-[0_0_8px_#46B26B]" : "bg-warn"
            }`}
          />
          <span className="text-xs text-muted">
            {online ? "Online" : "Connecting"}
          </span>
        </div>
      </header>

      {/* Chat */}
      <main className="flex-1 overflow-hidden max-w-3xl w-full mx-auto">
        <ChatWindow
          messages={messages}
          status={status}
          pipelineStatus={pipelineStatus}
          sendMessage={sendMessage}
        />
      </main>
    </div>
  );
}
