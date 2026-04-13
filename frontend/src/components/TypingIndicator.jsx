/**
 * Animated typing indicator shown when Sofie is processing.
 *
 * Three bouncing dots — simple CSS animation, no JS timer needed.
 */
export default function TypingIndicator() {
  return (
    <div className="flex justify-start mb-3">
      <div className="bg-white border border-gray-100 shadow-sm px-4 py-3 rounded-2xl">
        <div className="text-xs font-medium text-indigo-600 mb-1">Sofie</div>
        <div className="flex gap-1">
          <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:0ms]" />
          <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:150ms]" />
          <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:300ms]" />
        </div>
      </div>
    </div>
  );
}
