import type { UserBrief } from "../../api/types";
import { roleLabels } from "../../utils/constants";
import { EmptyState } from "../ui/EmptyState";

interface UserListProps {
  title: string;
  users: UserBrief[];
  total: number;
  onLoadProfile: (userId: number) => void;
  onLoadMore?: () => Promise<void>;
}

export function UserList({ title, users, total, onLoadProfile, onLoadMore }: UserListProps) {
  return (
    <div className="panel user-list">
      <div className="section-title">
        <h2>{title}</h2>
        <span>{total}</span>
      </div>
      {users.map((user) => (
        <button key={user.id} className="user-row" onClick={() => onLoadProfile(user.id)}>
          <img src={user.avatar_url} alt="" />
          <span>
            <strong>{user.nickname}</strong>
            <small>@{user.username}</small>
          </span>
          <small>{roleLabels[user.role]}</small>
        </button>
      ))}
      {users.length === 0 && <EmptyState text="暂无数据。" />}
      {onLoadMore && users.length < total && (
        <button className="ghost full" onClick={() => void onLoadMore()}>
          加载更多（{users.length}/{total}）
        </button>
      )}
    </div>
  );
}
