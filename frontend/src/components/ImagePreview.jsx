import { useState } from 'react'

export default function ImagePreview({ jobId, imageUrl }) {
  const [loaded, setLoaded] = useState(false)

  return (
    <div className="flex justify-start pl-11 mt-2">
      <div className="max-w-[480px] w-full rounded-xl overflow-hidden shadow-md bg-white border border-border">
        {/* Image */}
        <div className="relative">
          {!loaded && (
            <div className="h-64 flex items-center justify-center bg-bg-sidebar">
              <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
            </div>
          )}
          <img
            src={imageUrl}
            alt="Generated visual"
            className={`w-full ${loaded ? 'block' : 'hidden'}`}
            onLoad={() => setLoaded(true)}
          />
        </div>

        {/* Actions */}
        <div className="flex gap-2 p-3">
          <a
            href={imageUrl}
            download={`sofie-${jobId}.png`}
            className="flex-1 text-center px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent-light transition-colors"
          >
            Download
          </a>
          <button className="flex-1 px-4 py-2 rounded-lg border border-border text-sm font-medium text-text-muted hover:bg-bg-sidebar transition-colors">
            Request Changes
          </button>
        </div>
      </div>
    </div>
  )
}
