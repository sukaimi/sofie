import { useCallback, useEffect, useRef, useState } from "react";
import FeedbackMenu from "./FeedbackMenu";
import FileUpload from "./FileUpload";
import ImagePreview from "./ImagePreview";
import MessageBubble from "./MessageBubble";
import TypingIndicator from "./TypingIndicator";

/**
 * Main chat window — the only brand client interface.
 *
 * Composes all chat sub-components and manages the input state.
 * Scrolls to bottom on new messages. Shows upload zone when
 * Sofie asks for a brief.
 */
export default function ChatWindow({ messages, status, pipelineStatus, sendMessage }) {
  const [input, setInput] = useState("");
  const [showFeedback, setShowFeedback] = useState(false);
  const bottomRef = useRef(null);

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pipelineStatus]);

  // Show feedback menu only when last message is an image (no suggestions after)
  useEffect(() => {
    const last = messages[messages.length - 1];
    if (last?.type === "image") {
      setShowFeedback(true);
    } else if (last?.role === "sofie" && last?.type === "message") {
      // If Sofie sent a follow-up message after the image (e.g. suggestions),
      // hide the feedback menu — Sofie is driving the conversation
      setShowFeedback(false);
    }
  }, [messages]);

  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text) return;

    sendMessage("message", text);
    setInput("");
  }, [input, sendMessage]);

  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  const handleFileUploaded = useCallback(
    (filePath, filename) => {
      sendMessage("brief_uploaded", filename, { file_path: filePath });
    },
    [sendMessage]
  );

  const handleFeedbackSelect = useCallback(
    (key, label) => {
      if (key === "other") {
        setShowFeedback(false);
        // Focus text input for free-form feedback
        return;
      }
      sendMessage("feedback", `Change the ${label.toLowerCase()}`);
      setShowFeedback(false);
    },
    [sendMessage]
  );

  const handleConfirm = useCallback(() => {
    sendMessage("confirmation", "Yes, that's correct");
  }, [sendMessage]);

  // Check if the last Sofie message asks for confirmation
  const lastSofieMsg = [...messages].reverse().find((m) => m.role === "sofie");
  const awaitingConfirmation = lastSofieMsg?.content?.includes("Is this all correct?");

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        {messages.map((msg, i) => (
          <div key={i}>
            <MessageBubble message={msg} />
            {msg.type === "image" && msg.metadata?.output_paths && (
              <ImagePreview paths={msg.metadata.output_paths} jobId={msg.job_id} />
            )}
          </div>
        ))}

        {pipelineStatus && <TypingIndicator step={pipelineStatus} />}

        {showFeedback && <FeedbackMenu onSelect={handleFeedbackSelect} />}

        {awaitingConfirmation && (
          <div className="flex justify-center my-3">
            <button
              onClick={handleConfirm}
              className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg
                         hover:bg-indigo-700 transition-colors"
            >
              Yes, that's correct
            </button>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Upload zone — always visible so user can upload anytime */}
      <div className="px-4 pb-2">
        <FileUpload onUploaded={handleFileUploaded} />
      </div>

      {/* Input bar */}
      <div className="border-t border-gray-100 px-4 py-3">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a message..."
            rows={1}
            className="flex-1 resize-none rounded-xl border border-gray-200 px-4 py-2.5
                       text-sm focus:outline-none focus:border-indigo-300 focus:ring-1
                       focus:ring-indigo-200"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim()}
            className="px-4 py-2.5 bg-indigo-600 text-white text-sm rounded-xl
                       hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed
                       transition-colors"
          >
            Send
          </button>
        </div>

        {/* Connection status */}
        {status !== "connected" && (
          <div className="text-xs text-center mt-2 text-amber-500">
            {status === "connecting"
              ? "Connecting..."
              : status === "disconnected"
              ? "Reconnecting..."
              : "Connection error"}
          </div>
        )}

      </div>
    </div>
  );
}
