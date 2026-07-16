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
    <div className="bg-surface border border-hairline rounded-2xl p-4 my-3 animate-fade-up">
      <p className="eyebrow mb-3">What would you like to change?</p>
      <div className="flex flex-col gap-2">
        {[...FEEDBACK_OPTIONS, { key: "other", label: "Something else", desc: "describe it" }].map(
          ({ key, label, desc }) => (
            <button
              key={key}
              onClick={() => onSelect(key, label)}
              className="text-left px-3 py-2.5 rounded-lg border border-hairline bg-surface-2
                         hover:border-accent-bright/60 hover:bg-accent/10 transition text-sm
                         focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-bright"
            >
              <span className="font-medium text-ink">{label}</span>
              <span className="text-muted-dim ml-2">— {desc}</span>
            </button>
          )
        )}
      </div>
    </div>
  );
}
