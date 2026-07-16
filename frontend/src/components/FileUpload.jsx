import { useCallback, useRef, useState } from "react";

/**
 * Brief upload component — accepts .docx files only.
 *
 * Uploads via POST to /upload-brief, then notifies the WebSocket
 * handler so the pipeline can start processing. Renders as a full
 * dropzone by default, or a compact strip when `compact` is set.
 */
export default function FileUpload({ onUploaded, compact = false }) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef(null);

  const handleUpload = useCallback(
    async (file) => {
      if (!file.name.endsWith(".docx")) {
        setError("Only .docx files are accepted");
        return;
      }

      setUploading(true);
      setError("");

      try {
        const formData = new FormData();
        formData.append("file", file);

        const resp = await fetch("/api/upload-brief", {
          method: "POST",
          body: formData,
        });

        if (!resp.ok) {
          const data = await resp.json();
          setError(data.error || "Upload failed");
          return;
        }

        const data = await resp.json();
        onUploaded(data.file_path, data.filename);
      } catch {
        setError("Upload failed. Please try again.");
      } finally {
        setUploading(false);
      }
    },
    [onUploaded]
  );

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault();
      const file = e.dataTransfer.files[0];
      if (file) handleUpload(file);
    },
    [handleUpload]
  );

  const openPicker = () => inputRef.current?.click();
  const onKeyDown = (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      openPicker();
    }
  };

  const fileInput = (
    <input
      ref={inputRef}
      type="file"
      accept=".docx"
      className="hidden"
      onChange={(e) => {
        const file = e.target.files?.[0];
        if (file) handleUpload(file);
      }}
    />
  );

  // Compact strip — used once the conversation is underway.
  if (compact) {
    return (
      <div>
        {fileInput}
        <button
          type="button"
          onClick={openPicker}
          disabled={uploading}
          className="w-full flex items-center justify-center gap-2 rounded-lg border border-hairline
                     bg-surface px-3 py-2 text-xs text-muted hover:text-ink hover:border-accent-bright/60
                     transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-bright"
        >
          <span aria-hidden="true" className="text-accent-bright">＋</span>
          {uploading ? "Uploading…" : "Attach another brief (.docx)"}
        </button>
        {error && <p className="text-xs text-accent-bright mt-2 text-center">{error}</p>}
      </div>
    );
  }

  // Full dropzone — used in the welcome state.
  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="Upload a brief — .docx files only. Drag and drop, or activate to browse."
      onDrop={handleDrop}
      onDragOver={(e) => e.preventDefault()}
      onClick={openPicker}
      onKeyDown={onKeyDown}
      className="group border-2 border-dashed border-hairline-strong rounded-2xl p-7 text-center
                 bg-surface/50 hover:border-accent-bright hover:bg-surface transition cursor-pointer
                 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-bright"
    >
      {fileInput}

      {uploading ? (
        <p className="text-sm text-muted">Uploading…</p>
      ) : (
        <>
          <div className="mx-auto mb-3 w-10 h-10 rounded-xl bg-accent/15 text-accent-bright
                          flex items-center justify-center text-lg group-hover:bg-accent/25 transition">
            <span aria-hidden="true">↑</span>
          </div>
          <p className="text-sm text-ink font-medium mb-1">
            Drop your brief here, or click to browse
          </p>
          <p className="text-xs text-muted-dim uppercase tracking-wider">.docx only</p>
        </>
      )}

      {error && <p className="text-xs text-accent-bright mt-3">{error}</p>}
    </div>
  );
}
