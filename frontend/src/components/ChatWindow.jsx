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
 * Shows a welcome state (with the upload as the primary CTA) before
 * the conversation starts, then a compact upload affordance after.
 */
export default function ChatWindow({ messages, status, pipelineStatus, sendMessage }) {
  const [input, setInput] = useState("");
  const [showFeedback, setShowFeedback] = useState(false);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  const hasConversation = messages.length > 0;

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
        inputRef.current?.focus();
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
      <div className="flex-1 overflow-y-auto scroll-dark px-4 py-6">
        {!hasConversation && !pipelineStatus ? (
          <WelcomeState onUploaded={handleFileUploaded} />
        ) : (
          messages.map((msg, i) => (
            <div key={i}>
              <MessageBubble message={msg} />
              {msg.type === "image" && msg.metadata?.output_paths && (
                <ImagePreview paths={msg.metadata.output_paths} jobId={msg.job_id} />
              )}
            </div>
          ))
        )}

        {pipelineStatus && <TypingIndicator step={pipelineStatus} />}

        {showFeedback && <FeedbackMenu onSelect={handleFeedbackSelect} />}

        {awaitingConfirmation && (
          <div className="flex justify-center my-4">
            <button
              onClick={handleConfirm}
              className="px-5 py-2.5 bg-accent text-white text-sm font-medium rounded-lg
                         shadow-glow hover:brightness-110 transition
                         focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-bright"
            >
              Yes, that's correct
            </button>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Contextual upload — compact strip once the conversation is underway */}
      {hasConversation && (
        <div className="px-4 pb-2">
          <FileUpload onUploaded={handleFileUploaded} compact />
        </div>
      )}

      {/* Input bar */}
      <div className="border-t border-hairline px-4 py-3">
        <div className="flex gap-2 items-end">
          <label htmlFor="chat-input" className="sr-only">
            Message Sofie
          </label>
          <textarea
            id="chat-input"
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Message Sofie…"
            rows={1}
            className="flex-1 resize-none rounded-xl bg-surface border border-hairline
                       px-4 py-2.5 text-sm text-ink placeholder:text-muted-dim
                       focus:outline-none focus:border-accent-bright
                       focus:ring-1 focus:ring-accent-bright/40"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim()}
            className="px-4 py-2.5 bg-accent text-white text-sm font-medium rounded-xl
                       shadow-glow hover:brightness-110
                       disabled:opacity-30 disabled:shadow-none disabled:cursor-not-allowed
                       transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-bright"
          >
            Send
          </button>
        </div>

        {/* Connection status */}
        {status !== "connected" && (
          <div className="text-xs text-center mt-2 text-warn">
            {status === "connecting"
              ? "Connecting…"
              : status === "disconnected"
              ? "Reconnecting…"
              : "Connection error"}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * First-run welcome — replaces the empty void with a real invitation.
 * The upload dropzone is the primary call to action here.
 */
function WelcomeState({ onUploaded }) {
  return (
    <div className="h-full flex flex-col items-center justify-center text-center px-2 animate-fade-up">
      <span className="eyebrow">Creative studio, on demand</span>
      <h2 className="font-display font-extrabold uppercase tracking-tight leading-[0.95]
                     text-ink text-4xl sm:text-5xl mt-4 mb-4 text-balance max-w-[16ch]">
        Drop your brief.<br />I&apos;ll take it from here.
      </h2>
      <p className="text-muted text-sm max-w-sm mb-8">
        Hi, I&apos;m Sofie. Send me your brief and I&apos;ll brief the team, compose it,
        and QA it — you&apos;ll see every step.
      </p>
      <div className="w-full max-w-md">
        <FileUpload onUploaded={onUploaded} />
      </div>
      <p className="text-xs text-muted-dim mt-4">
        …or just type a message below to say hi.
      </p>
    </div>
  );
}
