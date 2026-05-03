import { LogIn, Plus } from "lucide-react";
import { useState } from "react";
import type { UserBrief, UserProfile } from "../../api/types";
import type { AuthMode } from "../../utils/constants";
import { roleLabels } from "../../utils/constants";
import { EmptyState } from "../ui/EmptyState";
import { Metric } from "../ui/Metric";
import { UserSearchInput } from "../ui/UserSearchInput";
import { UserList } from "./UserList";

interface ProfileViewProps {
  currentUser: UserProfile | null;
  profileUser: UserProfile | null;
  followers: UserBrief[];
  followerTotal: number;
  following: UserBrief[];
  followingTotal: number;
  onOpenAuth: (mode?: AuthMode) => void;
  onLoadProfile: (userId: number) => void;
  onFollow: (shouldFollow: boolean) => Promise<void>;
  onLoadMoreFollowers: () => Promise<void>;
  onLoadMoreFollowing: () => Promise<void>;
}

export function ProfileView({
  currentUser,
  profileUser,
  followers,
  followerTotal,
  following,
  followingTotal,
  onOpenAuth,
  onLoadProfile,
  onFollow,
  onLoadMoreFollowers,
  onLoadMoreFollowing,
}: ProfileViewProps) {
  const [lookup, setLookup] = useState("");

  if (!currentUser && !profileUser) {
    return (
      <section className="single-panel">
        <EmptyState text="登录后查看个人资料、粉丝和关注列表。" />
        <button className="primary" onClick={() => onOpenAuth("login")}>
          <LogIn size={17} />
          登录
        </button>
      </section>
    );
  }

  return (
    <section className="profile-grid">
      <div className="panel profile-card">
        <form
          className="lookup"
          onSubmit={(event) => {
            event.preventDefault();
            const trimmed = lookup.trim();
            if (!trimmed) return;
            const id = Number(trimmed);
            if (Number.isFinite(id) && id > 0) {
              onLoadProfile(id);
            }
          }}
        >
          <UserSearchInput
            value={lookup}
            onChange={setLookup}
            placeholder="搜索用户名或昵称，或输入用户 ID"
          />
          <button className="ghost" type="submit">查看</button>
        </form>

        {profileUser && (
          <>
            <div className="profile-head">
              <img src={profileUser.avatar_url} alt="" />
              <div>
                <p className="eyebrow">{roleLabels[profileUser.role]}</p>
                <h2>{profileUser.nickname}</h2>
                <span>@{profileUser.username}</span>
              </div>
            </div>
            <p className="bio">{profileUser.bio || "这个用户还没有填写简介。"}</p>
            <div className="metric-grid">
              <Metric label="关注" value={profileUser.following_count} />
              <Metric label="粉丝" value={profileUser.followers_count} />
              <Metric label="获赞" value={profileUser.total_likes_received} />
              <Metric label="点踩" value={profileUser.total_dislikes_received} />
            </div>
            {currentUser && currentUser.id !== profileUser.id && (
              <div className="toolbar">
                <button className="primary" onClick={() => void onFollow(true)}>
                  <Plus size={17} />
                  关注
                </button>
                <button className="ghost" onClick={() => void onFollow(false)}>
                  取消关注
                </button>
              </div>
            )}
          </>
        )}
      </div>

      <UserList title="粉丝" users={followers} total={followerTotal} onLoadProfile={onLoadProfile} onLoadMore={onLoadMoreFollowers} />
      <UserList title="正在关注" users={following} total={followingTotal} onLoadProfile={onLoadProfile} onLoadMore={onLoadMoreFollowing} />
    </section>
  );
}
