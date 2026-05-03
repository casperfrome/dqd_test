import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function MarkdownMessage({ content, compact = false }: { content: string; compact?: boolean }) {
  return (
    <div className={`ai-message-body markdown-body ${compact ? "compact" : ""}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content || " "}</ReactMarkdown>
    </div>
  );
}
