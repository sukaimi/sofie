import { useCallback, useRef, useState } from "react";

/**
 * Brief upload component — accepts .docx files only.
 *
 * Uploads via POST to /upload-brief, then notifies the WebSocket
 * handler so the pipeline can start processing.
 */
export default function FileUpload({ onUploaded }) {
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

  return (
    <div
      onDrop={handleDrop}
      onDragOver={(e) => e.preventDefault()}
      className="border-2 border-dashed border-gray-200 rounded-xl p-6 text-center
                 hover:border-indigo-300 transition-colors cursor-pointer"
      onClick={() => inputRef.current?.click()}
    >
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

      {uploading ? (
        <p className="text-sm text-gray-500">Uploading...</p>
      ) : (
        <>
          <p className="text-sm text-gray-600 mb-1">
            Drop your brief here or click to browse
          </p>
          <p className="text-xs text-gray-400">.docx files only</p>
        </>
      )}

      {error && <p className="text-xs text-red-500 mt-2">{error}</p>}
    </div>
  );
}
