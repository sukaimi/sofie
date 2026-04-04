import { useCallback, useEffect, useState } from 'react'
import ChatWindow from './components/ChatWindow'
import BrandSelector from './components/BrandSelector'

function App() {
  const [brands, setBrands] = useState(null) // null = loading
  const [conversationId, setConversationId] = useState(null)
  const [activeBrand, setActiveBrand] = useState(null) // {id, name} or null for onboarding

  // Load brands on mount
  useEffect(() => {
    fetch('/api/brands')
      .then((r) => r.json())
      .then(setBrands)
      .catch(() => setBrands([]))
  }, [])

  const refreshBrands = useCallback(() => {
    fetch('/api/brands')
      .then((r) => r.json())
      .then(setBrands)
  }, [])

  const handleSelectBrand = useCallback((brandId) => {
    const brand = brands.find((b) => b.id === brandId)
    fetch('/api/conversations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ brand_id: brandId }),
    })
      .then((r) => r.json())
      .then((data) => {
        setConversationId(data.id)
        setActiveBrand(brand)
      })
  }, [brands])

  const handleCreateBrand = useCallback(() => {
    // Create conversation with no brand — triggers onboarding
    fetch('/api/conversations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ brand_id: null }),
    })
      .then((r) => r.json())
      .then((data) => {
        setConversationId(data.id)
        setActiveBrand({ id: null, name: 'New Brand' })
      })
  }, [])

  const handleDeleteBrand = useCallback((brandId) => {
    fetch(`/api/brands/${brandId}`, { method: 'DELETE' })
      .then(() => refreshBrands())
  }, [refreshBrands])

  const handleBack = useCallback(() => {
    setConversationId(null)
    setActiveBrand(null)
    refreshBrands()
  }, [refreshBrands])

  const handleBrandCreated = useCallback((brandId, brandName) => {
    setActiveBrand({ id: brandId, name: brandName })
    refreshBrands()
  }, [refreshBrands])

  // Loading
  if (brands === null) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-bg text-text-muted">
        Loading...
      </div>
    )
  }

  // Brand selection screen
  if (!conversationId) {
    return (
      <BrandSelector
        brands={brands}
        onSelect={handleSelectBrand}
        onCreate={handleCreateBrand}
        onDelete={handleDeleteBrand}
      />
    )
  }

  // Chat screen
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
            <p className="font-medium text-text mt-0.5">
              {activeBrand?.name || 'Setting up...'}
            </p>
          </div>
        </div>
        <button
          onClick={handleBack}
          className="mx-4 mt-4 px-3 py-2 rounded-lg border border-border text-sm text-text-muted hover:bg-white transition-colors"
        >
          ← Switch Brand
        </button>
        <div className="mt-auto px-6 py-4 text-xs text-text-light">
          Powered by Flux 2 Pro + Ollama
          <br />
          Qurious Media x Code&Canvas
        </div>
      </aside>

      {/* Main chat */}
      <main className="flex-1 flex flex-col min-w-0">
        <ChatWindow
          conversationId={conversationId}
          onBrandCreated={handleBrandCreated}
        />
      </main>
    </div>
  )
}

export default App
