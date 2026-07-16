/**
 * Image preview component for composited output.
 *
 * The deliverable is the whole point — so it gets a framed reveal
 * with a labelled header and a proper download action per size.
 * Images are served from the backend file server.
 */

/**
 * Force a real file download with a guaranteed filename + extension.
 *
 * Some browsers (notably Safari/iOS) ignore the anchor `download`
 * attribute and drop the extension. Fetching the file as a blob and
 * triggering a same-document object-URL download keeps the exact name
 * everywhere; falls back to opening the URL if the fetch fails.
 */
async function downloadFile(url, name) {
  try {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const blob = await resp.blob();
    const objectUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = objectUrl;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(objectUrl);
  } catch {
    window.open(url, "_blank", "noopener");
  }
}

export default function ImagePreview({ paths, jobId }) {
  if (!paths || Object.keys(paths).length === 0) return null;

  return (
    <div className="flex flex-col gap-4 my-4 animate-fade-up">
      {Object.entries(paths).map(([size, path]) => {
        const rawName = path.split("/").pop() || `composited_${size}`;
        // Guarantee an extension on the saved file (defaults to .jpg).
        const downloadName = /\.[a-z0-9]+$/i.test(rawName)
          ? rawName
          : `${rawName}.jpg`;
        const downloadUrl = `/api/job/${jobId}/download/${rawName}`;

        return (
          <figure
            key={size}
            className="bg-surface rounded-2xl border border-hairline-strong overflow-hidden shadow-glow-sm"
          >
            <figcaption className="flex items-center justify-between px-4 py-2.5 border-b border-hairline">
              <span className="eyebrow">Delivered · {size}</span>
              <a
                href={downloadUrl}
                download={downloadName}
                onClick={(e) => {
                  e.preventDefault();
                  downloadFile(downloadUrl, downloadName);
                }}
                className="text-xs font-medium text-white bg-accent px-3 py-1.5 rounded-lg
                           hover:brightness-110 transition
                           focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-bright"
              >
                Download
              </a>
            </figcaption>
            <img
              src={downloadUrl}
              alt={`Composited ${size} output`}
              loading="lazy"
              className="w-full max-h-[28rem] object-contain bg-ground"
            />
          </figure>
        );
      })}
    </div>
  );
}
