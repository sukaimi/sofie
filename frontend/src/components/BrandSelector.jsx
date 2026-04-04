import { useState } from 'react'

const MAX_BRANDS = 3

export default function BrandSelector({ brands, onSelect, onCreate, onDelete }) {
  const [confirmDelete, setConfirmDelete] = useState(null)
  const isFull = brands.length >= MAX_BRANDS

  return (
    <div className="flex-1 flex items-center justify-center bg-bg p-8">
      <div className="max-w-lg w-full">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-primary">SOFIE</h1>
          <p className="text-xs text-text-light mt-1">Smart Output Factory for Image Execution</p>
          <p className="text-text-muted mt-3">
            Choose a brand to work with, or create a new one.
          </p>
        </div>

        <div className="space-y-3">
          {brands.map((brand) => (
            <div
              key={brand.id}
              className="flex items-center gap-3 p-4 bg-white rounded-xl border border-border hover:border-accent transition-colors cursor-pointer"
              onClick={() => onSelect(brand.id)}
            >
              <div className="w-10 h-10 rounded-lg bg-bg-sidebar flex items-center justify-center text-primary font-bold text-lg">
                {brand.name[0]}
              </div>
              <div className="flex-1">
                <p className="font-medium text-text">{brand.name}</p>
                <p className="text-xs text-text-muted">Click to start chatting</p>
              </div>

              {/* Delete button */}
              {confirmDelete === brand.id ? (
                <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
                  <button
                    onClick={() => { onDelete(brand.id); setConfirmDelete(null) }}
                    className="px-3 py-1 text-xs bg-error text-white rounded-lg"
                  >
                    Confirm
                  </button>
                  <button
                    onClick={() => setConfirmDelete(null)}
                    className="px-3 py-1 text-xs border border-border rounded-lg"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  onClick={(e) => { e.stopPropagation(); setConfirmDelete(brand.id) }}
                  className="text-text-light hover:text-error text-sm transition-colors"
                  title="Delete brand"
                >
                  ✕
                </button>
              )}
            </div>
          ))}

          {/* Create new brand */}
          {isFull ? (
            <div className="p-4 bg-bg-sidebar rounded-xl border border-border text-center">
              <p className="text-sm text-text-muted">
                {MAX_BRANDS}/{MAX_BRANDS} brands — delete one to add a new brand
              </p>
            </div>
          ) : (
            <button
              onClick={onCreate}
              className="w-full p-4 bg-white rounded-xl border-2 border-dashed border-border hover:border-accent text-text-muted hover:text-accent transition-colors"
            >
              + Create New Brand
            </button>
          )}
        </div>

        <p className="text-center text-xs text-text-light mt-6">
          Powered by Flux 2 Pro + Ollama
          <br />
          Qurious Media x Code&Canvas
        </p>
      </div>
    </div>
  )
}
