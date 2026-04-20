/**
 * Pipeline progress indicator — shows current step instead of just dots.
 */

const STEP_LABELS = {
  parsing_brief: "Parsing your brief",
  validating_brief: "Validating brief details",
  font_check: "Checking font compatibility",
  validating_assets: "Downloading and checking assets",
  art_direction: "Planning the composition",
  generating_hero: "Generating hero image",
  compositing: "Compositing layers",
  qa_check: "Running quality checks",
};

function getLabel(step) {
  if (!step) return "Working on it";

  // Direct match
  if (STEP_LABELS[step]) return STEP_LABELS[step];

  // Match partial keys (e.g. "compositing_1080x1080_attempt_1")
  for (const [key, label] of Object.entries(STEP_LABELS)) {
    if (step.startsWith(key)) return label;
  }

  // Match "qa_check_1080x1350" etc
  if (step.startsWith("qa_check")) return "Running quality checks";

  // Fallback: humanize the raw status
  return step.replace(/_/g, " ");
}

export default function TypingIndicator({ step }) {
  const label = getLabel(step);

  return (
    <div className="flex justify-start mb-3">
      <div className="bg-white border border-gray-100 shadow-sm px-4 py-3 rounded-2xl">
        <div className="text-xs font-medium text-indigo-600 mb-1">Sofie</div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-600">{label}</span>
          <span className="flex gap-1">
            <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:0ms]" />
            <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:150ms]" />
            <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:300ms]" />
          </span>
        </div>
      </div>
    </div>
  );
}
