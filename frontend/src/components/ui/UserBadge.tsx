import type { UserProfile } from "../../api/types";
import { roleLabels } from "../../utils/constants";

export function UserBadge({ user, onOpenProfile }: { user: UserProfile; onOpenProfile: () => void }) {
  return (
    <button className="user-badge" onClick={onOpenProfile}>
      <img src={user.avatar_url} alt="" />
      <span>
        <strong>{user.nickname}</strong>
        <small>{roleLabels[user.role]}</small>
      </span>
    </button>
  );
}
