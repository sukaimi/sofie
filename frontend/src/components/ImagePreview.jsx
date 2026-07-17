/**
 * Image preview component for composited output.
 *
 * The deliverable is the whole point — so it gets a framed reveal
 * with a labelled header and a proper download action per size.
 */

/**
 * Download the file with a guaranteed filename + extension.
 *
 * Fetches the file as a blob and triggers a same-document download. The
 * object URL is revoked on a delay — revoking it immediately (before the
 * browser has finished reading the blob) makes some browsers save a
 * UUID-named or nameless file. Falls back to same-tab navigation because a
 * window.open() after an awaited fetch is commonly blocked as a popup.
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
    // Give the browser time to capture the blob + filename before cleanup.
    setTimeout(() => {
      a.remove();
      URL.revokeObjectURL(objectUrl);
    }, 4000);
  } catch {
    // This is a real navigation, not a popup, so it remains allowed after the
    // asynchronous fetch has lost the original user-activation token. The
    // server's Content-Disposition header turns the navigation into a download.
    window.location.assign(url);
  }
}

export default function ImagePreview({ paths, jobId }) {
  if (!paths || Object.keys(paths).length === 0) return null;

  return (
    <div className="flex flex-col gap-4 my-4 animate-fade-up">
      {Object.entries(paths).map(([size, path]) => {
        const filename = path.split("/").pop() || `composited_${size}`;
        const downloadName = /\.[a-z0-9]+$/i.test(filename)
          ? filename
          : `${filename}.jpg`;
        const downloadUrl = `/api/job/${encodeURIComponent(jobId)}/download/${encodeURIComponent(filename)}`;

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
