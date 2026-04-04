export default function TypingIndicator() {
  return (
    <div className="flex items-start gap-3">
      <div className="w-8 h-8 rounded-full bg-sofie flex items-center justify-center text-white text-xs font-semibold shrink-0">
        S
      </div>
      <div className="px-4 py-3 rounded-2xl rounded-bl-md bg-bg-sidebar">
        <div className="flex gap-1.5">
          <span className="w-2 h-2 rounded-full bg-text-muted animate-bounce [animation-delay:0ms]" />
          <span className="w-2 h-2 rounded-full bg-text-muted animate-bounce [animation-delay:150ms]" />
          <span className="w-2 h-2 rounded-full bg-text-muted animate-bounce [animation-delay:300ms]" />
        </div>
      </div>
    </div>
  )
}
