export default function MessageBubble({ role, content }) {
  const isUser = role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`flex items-start gap-3 max-w-[80%] ${isUser ? 'flex-row-reverse' : ''}`}>
        {/* Avatar */}
        {!isUser && (
          <div className="w-8 h-8 rounded-full bg-sofie flex items-center justify-center text-white text-xs font-semibold shrink-0 mt-1">
            S
          </div>
        )}

        {/* Bubble */}
        <div
          className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${
            isUser
              ? 'bg-accent text-white rounded-br-md'
              : 'bg-bg-sidebar text-text rounded-bl-md'
          }`}
        >
          {content}
        </div>
      </div>
    </div>
  )
}
