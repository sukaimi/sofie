import { useEffect, useRef, useState } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'
import MessageBubble from './MessageBubble'
import TypingIndicator from './TypingIndicator'
import ImagePreview from './ImagePreview'

export default function ChatWindow({ conversationId }) {
  const { messages, sendMessage, isTyping, status, connected } = useWebSocket(conversationId)
  const [input, setInput] = useState('')
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping, status])

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!input.trim()) return
    sendMessage(input.trim())
    setInput('')
  }

  return (
    <div className="flex flex-col h-full bg-bg-chat">
      {/* Header */}
      <div className="flex items-center gap-3 px-6 py-4 border-b border-border">
        <div className="w-10 h-10 rounded-full bg-sofie flex items-center justify-center text-white font-semibold text-sm">
          S
        </div>
        <div>
          <h2 className="text-sm font-semibold text-text">Sofie</h2>
          <p className="text-xs text-text-muted">
            {connected ? 'Online' : 'Connecting...'}
            {status && ` — ${status}`}
          </p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-text-muted mt-20">
            <p className="text-lg font-medium">Welcome to SOFIE</p>
            <p className="text-sm mt-2">Tell Sofie what you need and she'll create it for you.</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i}>
            <MessageBubble role={msg.role} content={msg.content} />
            {msg.image && (
              <ImagePreview jobId={msg.image.jobId} imageUrl={msg.image.url} />
            )}
          </div>
        ))}
        {isTyping && <TypingIndicator />}
        {status && !isTyping && (
          <div className="flex items-center gap-2 text-sm text-text-muted">
            <div className="w-2 h-2 rounded-full bg-accent animate-pulse" />
            {status}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="px-6 py-4 border-t border-border">
        <div className="flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Tell Sofie what you need..."
            className="flex-1 px-4 py-3 rounded-xl border border-border bg-white text-sm focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent"
            disabled={!connected}
          />
          <button
            type="submit"
            disabled={!connected || !input.trim()}
            className="px-6 py-3 rounded-xl bg-accent text-white text-sm font-medium hover:bg-accent-light disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  )
}
