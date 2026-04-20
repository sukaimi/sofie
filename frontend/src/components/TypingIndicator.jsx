/**
 * Pipeline progress indicator — shows live step detail from the backend.
 */
export default function TypingIndicator({ step }) {
  const label = step || "Working on it";

  return (
    <div className="flex justify-start mb-3">
      <div className="bg-white border border-gray-100 shadow-sm px-4 py-3 rounded-2xl">
        <div className="text-xs font-medium text-indigo-600 mb-1">Sofie</div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-600">{label}</span>
          <span className="flex gap-1">
            <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:0ms]" />
            <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:150ms]" />
            <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:300ms]" />
          </span>
        </div>
      </div>
    </div>
  );
}
