import { AnalyticsResponse } from "../../api/types";
import { EmptyState } from "../ui/EmptyState";
import { formatDate } from "../../utils/helpers";

export function AnalyticsCard({ analytics, emptyText }: { analytics: AnalyticsResponse | null; emptyText: string }) {
  if (!analytics) {
    return <EmptyState text={emptyText} />;
  }
  return (
    <div className="analytics-card">
      <div className="summary-grid">
        {Object.entries(analytics.summary).map(([key, value]) => (
          <div className="metric" key={key}>
            <strong>{String(value)}</strong>
            <span>{key}</span>
          </div>
        ))}
      </div>
      <div className="event-list">
        {analytics.recent_events.map((event) => (
          <div className="event-row" key={event.id}>
            <span>{event.event_type}</span>
            <small>{formatDate(event.created_at)}</small>
            <code>{JSON.stringify(event.metadata)}</code>
          </div>
        ))}
      </div>
    </div>
  );
}
