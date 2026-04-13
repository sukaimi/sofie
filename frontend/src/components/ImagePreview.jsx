/**
 * Image preview component for composited output.
 *
 * Shows the generated visual inline in chat with a download link.
 * Images are served from the backend file server.
 */
export default function ImagePreview({ paths, jobId }) {
  if (!paths || Object.keys(paths).length === 0) return null;

  return (
    <div className="flex flex-col gap-3 my-3">
      {Object.entries(paths).map(([size, path]) => {
        const filename = path.split("/").pop();
        const downloadUrl = `/api/job/${jobId}/download/${filename}`;

        return (
          <div key={size} className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
            <img
              src={downloadUrl}
              alt={`${size} output`}
              className="w-full max-h-96 object-contain bg-gray-50"
            />
            <div className="flex items-center justify-between px-4 py-2 border-t border-gray-50">
              <span className="text-xs text-gray-500">{size}</span>
              <a
                href={downloadUrl}
                download={filename}
                className="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
              >
                Download
              </a>
            </div>
          </div>
        );
      })}
    </div>
  );
}
