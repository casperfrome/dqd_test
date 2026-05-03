import type { CodeAiSource } from "../../api/types";

interface CodeSourcesProps {
  sources: CodeAiSource[];
  onOpenSource: (source: CodeAiSource) => void;
}

export function CodeSources({ sources, onOpenSource }: CodeSourcesProps) {
  return (
    <div className="code-sources">
      {sources.slice(0, 8).map((source) => (
        <button key={source.fact_id} type="button" onClick={() => onOpenSource(source)}>
          {source.source_file_path}:{source.start_line}-{source.end_line}
        </button>
      ))}
    </div>
  );
}
