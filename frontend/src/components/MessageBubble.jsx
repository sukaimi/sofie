/**
 * Single chat message bubble.
 *
 * Sofie messages align left with a subtle background.
 * User messages align right with the brand accent colour.
 * System/status messages are centered and muted.
 * Markdown-style links [text](url) are rendered as clickable.
 */
export default function MessageBubble({ message }) {
  const { role, content, type } = message;

  if (type === "status") {
    return (
      <div className="flex justify-center my-2">
        <span className="text-xs text-gray-400 bg-gray-50 px-3 py-1 rounded-full">
          {content}
        </span>
      </div>
    );
  }

  const isSofie = role === "sofie" || role === "system";

  return (
    <div className={`flex ${isSofie ? "justify-start" : "justify-end"} mb-3`}>
      <div
        className={`max-w-[75%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${
          isSofie
            ? "bg-white text-gray-800 border border-gray-100 shadow-sm"
            : "bg-indigo-600 text-white"
        }`}
      >
        {isSofie && (
          <div className="text-xs font-medium text-indigo-600 mb-1">Sofie</div>
        )}
        <div className="whitespace-pre-wrap">
          <RenderContent content={content} isSofie={isSofie} />
        </div>
      </div>
    </div>
  );
}

/**
 * Renders text with markdown links and bold as interactive elements.
 */
function RenderContent({ content, isSofie }) {
  if (!content) return null;

  // Match [text](url) markdown links and **bold** text
  const parts = content.split(/(\[.*?\]\(.*?\)|\*\*.*?\*\*)/g);

  return parts.map((part, i) => {
    // Markdown link: [text](url)
    const linkMatch = part.match(/^\[(.*?)\]\((.*?)\)$/);
    if (linkMatch) {
      return (
        <a
          key={i}
          href={linkMatch[2]}
          target={linkMatch[2].startsWith("/") ? "_self" : "_blank"}
          rel="noopener noreferrer"
          className={`underline font-medium ${
            isSofie ? "text-indigo-600 hover:text-indigo-800" : "text-white/90 hover:text-white"
          }`}
        >
          {linkMatch[1]}
        </a>
      );
    }

    // Bold: **text**
    const boldMatch = part.match(/^\*\*(.*?)\*\*$/);
    if (boldMatch) {
      return <strong key={i}>{boldMatch[1]}</strong>;
    }

    return <span key={i}>{part}</span>;
  });
}
