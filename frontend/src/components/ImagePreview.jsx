/**
 * Image preview component for composited output.
 *
 * The deliverable is the whole point — so it gets a framed reveal
 * with a labelled header and a proper download action per size.
 * Images are served from the backend file server.
 */
export default function ImagePreview({ paths, jobId }) {
  if (!paths || Object.keys(paths).length === 0) return null;

  return (
    <div className="flex flex-col gap-4 my-4 animate-fade-up">
      {Object.entries(paths).map(([size, path]) => {
        const filename = path.split("/").pop();
        const downloadUrl = `/api/job/${jobId}/download/${filename}`;

        return (
          <figure
            key={size}
            className="bg-surface rounded-2xl border border-hairline-strong overflow-hidden shadow-glow-sm"
          >
            <figcaption className="flex items-center justify-between px-4 py-2.5 border-b border-hairline">
              <span className="eyebrow">Delivered · {size}</span>
              <a
                href={downloadUrl}
                download={filename}
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
