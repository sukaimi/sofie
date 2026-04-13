/**
 * Guided feedback menu per PRD section 13.
 *
 * Offers structured options so Sofie can classify feedback
 * as actionable without guessing. 'Something else' falls through
 * to free-text input.
 */
const FEEDBACK_OPTIONS = [
  { key: "text", label: "Text", desc: "wording, size, or position" },
  { key: "layout", label: "Layout", desc: "element arrangement or spacing" },
  { key: "logo", label: "Logo", desc: "size or position" },
  { key: "image", label: "Image", desc: "crop or focus area" },
  { key: "colours", label: "Colours", desc: "overlay, tint, or contrast" },
];

export default function FeedbackMenu({ onSelect }) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 my-3">
      <p className="text-sm text-gray-600 mb-3">
        What would you like to change?
      </p>
      <div className="flex flex-col gap-2">
        {FEEDBACK_OPTIONS.map(({ key, label, desc }) => (
          <button
            key={key}
            onClick={() => onSelect(key, label)}
            className="text-left px-3 py-2 rounded-lg border border-gray-100
                       hover:border-indigo-200 hover:bg-indigo-50
                       transition-colors text-sm"
          >
            <span className="font-medium text-gray-800">{label}</span>
            <span className="text-gray-400 ml-2">— {desc}</span>
          </button>
        ))}
        <button
          onClick={() => onSelect("other", "Something else")}
          className="text-left px-3 py-2 rounded-lg border border-gray-100
                     hover:border-indigo-200 hover:bg-indigo-50
                     transition-colors text-sm"
        >
          <span className="font-medium text-gray-800">Something else</span>
          <span className="text-gray-400 ml-2">— describe it</span>
        </button>
      </div>
    </div>
  );
}
