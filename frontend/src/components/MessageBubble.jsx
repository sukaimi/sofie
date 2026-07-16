/**
 * Single chat message bubble.
 *
 * Sofie messages align left on a dark surface with a red '// SOFIE' label.
 * User messages align right in the brand red.
 * System/status messages are centered and muted.
 * Markdown-style links [text](url) and **bold** are rendered inline.
 */
export default function MessageBubble({ message }) {
  const { role, content, type } = message;

  if (type === "status") {
    return (
      <div className="flex justify-center my-2">
        <span className="text-xs text-muted bg-surface border border-hairline px-3 py-1 rounded-full">
          {content}
        </span>
      </div>
    );
  }

  const isSofie = role === "sofie" || role === "system";

  return (
    <div className={`flex ${isSofie ? "justify-start" : "justify-end"} mb-3 animate-fade-up`}>
      <div
        className={`max-w-[80%] px-4 py-3 text-sm leading-relaxed ${
          isSofie
            ? "bg-surface text-ink border border-hairline rounded-[4px_16px_16px_16px]"
            : "bg-accent text-white rounded-[16px_4px_16px_16px] shadow-glow"
        }`}
      >
        {isSofie && (
          <div className="eyebrow mb-1.5">Sofie</div>
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
            isSofie
              ? "text-accent-bright hover:text-white"
              : "text-white/90 hover:text-white"
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
