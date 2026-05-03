import type { DatabaseAiSource } from "../../api/types";
import { aiFactTypeLabels } from "../../utils/constants";

export function AiSources({ sources }: { sources: DatabaseAiSource[] }) {
  return (
    <div className="ai-sources">
      {sources.slice(0, 6).map((source) => (
        <span key={source.fact_id}>
          {aiFactTypeLabels[source.fact_type] ?? source.fact_type}
          {source.source_table_name ? ` · ${source.source_table_name}` : ""}
          {source.source_column_name ? `.${source.source_column_name}` : ""}
        </span>
      ))}
    </div>
  );
}
