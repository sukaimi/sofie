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

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-100 px-6 py-4 flex items-center gap-3">
        <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center">
          <span className="text-white text-sm font-bold">S</span>
        </div>
        <div>
          <h1 className="text-sm font-semibold text-gray-900">SOFIE</h1>
          <p className="text-xs text-gray-400">Studio Orchestrator</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${
              status === "connected" ? "bg-green-400" : "bg-amber-400"
            }`}
          />
          <span className="text-xs text-gray-400">
            {status === "connected" ? "Online" : "Connecting"}
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
