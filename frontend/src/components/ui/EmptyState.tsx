import { Eye } from "lucide-react";
import type { ReactNode } from "react";

export function EmptyState({ text, icon }: { text: string; icon?: ReactNode }) {
  return (
    <div className="empty-state">
      {icon ?? <Eye size={22} />}
      <span>{text}</span>
    </div>
  );
}
