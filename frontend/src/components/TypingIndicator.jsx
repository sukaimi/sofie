/**
 * Pipeline progress indicator — shows live step detail from the backend.
 */
export default function TypingIndicator({ step }) {
  const label = step || "Working on it";

  return (
    <div className="flex justify-start mb-3 animate-fade-up">
      <div className="bg-surface border border-hairline px-4 py-3 rounded-[4px_16px_16px_16px]">
        <div className="eyebrow mb-1.5">Sofie</div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted">{label}</span>
          <span className="flex gap-1">
            <span className="w-1.5 h-1.5 bg-accent-bright rounded-full animate-bounce [animation-delay:0ms]" />
            <span className="w-1.5 h-1.5 bg-accent-bright rounded-full animate-bounce [animation-delay:150ms]" />
            <span className="w-1.5 h-1.5 bg-accent-bright rounded-full animate-bounce [animation-delay:300ms]" />
          </span>
        </div>
      </div>
    </div>
  );
}
