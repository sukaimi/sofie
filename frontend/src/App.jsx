import { useEffect, useState } from 'react'
import ChatWindow from './components/ChatWindow'

function App() {
  const [conversationId, setConversationId] = useState(null)
  const [brandId] = useState('example-brand')

  useEffect(() => {
    // Create a conversation on mount
    fetch('/api/conversations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ brand_id: brandId }),
    })
      .then((r) => r.json())
      .then((data) => setConversationId(data.id))
      .catch((err) => console.error('Failed to create conversation:', err))
  }, [brandId])

  return (
    <div className="flex h-full w-full bg-bg">
      {/* Sidebar */}
      <aside className="hidden md:flex flex-col w-72 bg-bg-sidebar border-r border-border">
        <div className="px-6 py-5">
          <h1 className="text-xl font-bold text-primary">SOFIE</h1>
          <p className="text-xs text-text-muted mt-1">Creative Account Manager</p>
        </div>
        <div className="px-4 mt-4">
          <div className="px-3 py-2 rounded-lg bg-white border border-border text-sm">
            <span className="text-text-muted text-xs">Brand</span>
            <p className="font-medium text-text mt-0.5">Kopi Kita</p>
          </div>
        </div>
        <div className="mt-auto px-6 py-4 text-xs text-text-light">
          Powered by Flux 2 Pro + Ollama
        </div>
      </aside>

      {/* Main chat */}
      <main className="flex-1 flex flex-col min-w-0">
        {conversationId ? (
          <ChatWindow conversationId={conversationId} />
        ) : (
          <div className="flex-1 flex items-center justify-center text-text-muted">
            Starting conversation...
          </div>
        )}
      </main>
    </div>
  )
}

export default App
