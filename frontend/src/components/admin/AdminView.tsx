import { Lock, LogIn, Pin, Shield, Unlock } from "lucide-react";
import { useState } from "react";
import type { FanCircleDetail, PostDetail, UserProfile } from "../../api/types";
import type { AuthMode } from "../../utils/constants";
import { roleLabels } from "../../utils/constants";
import { EmptyState } from "../ui/EmptyState";
import { Metric } from "../ui/Metric";
import { UserSearchInput } from "../ui/UserSearchInput";

interface AdminViewProps {
  currentUser: UserProfile | null;
  selectedCircle: FanCircleDetail | null;
  selectedPost: PostDetail | null;
  canModerateSelectedPost: boolean;
  onOpenAuth: (mode?: AuthMode) => void;
  onAssignOwner: (circleId: number, ownerUserId: number) => Promise<void>;
  onDeactivateUser: (userId: number) => Promise<void>;
  onSetPostFlag: (flag: "pin" | "lock", value: boolean) => Promise<void>;
}

export function AdminView({
  currentUser,
  selectedCircle,
  selectedPost,
  canModerateSelectedPost,
  onOpenAuth,
  onAssignOwner,
  onDeactivateUser,
  onSetPostFlag,
}: AdminViewProps) {
  const [circleId, setCircleId] = useState("");
  const [ownerSearch, setOwnerSearch] = useState("");
  const [ownerUserId, setOwnerUserId] = useState<number | null>(null);
  const [deactivateSearch, setDeactivateSearch] = useState("");
  const [deactivateUserId, setDeactivateUserId] = useState<number | null>(null);
  const isSuperAdmin = currentUser?.role === "super_admin";

  if (!currentUser) {
    return (
      <section className="single-panel">
        <EmptyState text="登录后根据角色显示可用管理操作。" />
        <button className="primary" onClick={() => onOpenAuth("login")}>
          <LogIn size={17} />
          登录
        </button>
      </section>
    );
  }

  return (
    <section className="admin-grid">
      <div className="panel">
        <div className="section-title">
          <h2>当前权限</h2>
          <span>{roleLabels[currentUser.role]}</span>
        </div>
        <p className="muted">
          管理操作直接调用后端权限校验。无权限时会显示后端返回的错误提示。
        </p>
        <div className="summary-grid">
          <Metric label="当前圈子" value={selectedCircle?.id ?? "-"} />
          <Metric label="当前帖子" value={selectedPost?.id ?? "-"} />
          <Metric label="可管理帖子" value={canModerateSelectedPost ? "是" : "否"} />
        </div>
      </div>

      <div className="panel">
        <div className="section-title">
          <h2>帖子管理</h2>
          <span>{selectedPost ? selectedPost.title : "未选择帖子"}</span>
        </div>
        <div className="toolbar vertical">
          <button
            className="ghost"
            disabled={!selectedPost}
            onClick={() => selectedPost && void onSetPostFlag("pin", !selectedPost.is_pinned)}
          >
            <Pin size={17} />
            {selectedPost?.is_pinned ? "取消置顶" : "置顶帖子"}
          </button>
          <button
            className="ghost"
            disabled={!selectedPost}
            onClick={() => selectedPost && void onSetPostFlag("lock", !selectedPost.is_locked)}
          >
            {selectedPost?.is_locked ? <Unlock size={17} /> : <Lock size={17} />}
            {selectedPost?.is_locked ? "解锁帖子" : "锁定帖子"}
          </button>
        </div>
      </div>

      {isSuperAdmin && (
        <>
          <form
            className="panel admin-form"
            onSubmit={(event) => {
              event.preventDefault();
              const parsedCircleId = Number(circleId || selectedCircle?.id);
              if (parsedCircleId > 0 && ownerUserId) {
                void onAssignOwner(parsedCircleId, ownerUserId);
              }
            }}
          >
            <div className="section-title">
              <h2>分配圈主</h2>
              <span>super_admin</span>
            </div>
            <input value={circleId} onChange={(event) => setCircleId(event.target.value)} placeholder="圈子 ID，默认当前圈子" />
            <UserSearchInput
              value={ownerSearch}
              onChange={(value) => {
                setOwnerSearch(value);
                const id = Number(value);
                setOwnerUserId(Number.isFinite(id) && id > 0 ? id : null);
              }}
              placeholder="搜索圈主用户名或昵称"
            />
            {ownerUserId && <p className="muted">用户 ID：{ownerUserId}</p>}
            <button className="primary" disabled={!ownerUserId}>
              <Shield size={17} />
              分配
            </button>
          </form>

          <form
            className="panel admin-form"
            onSubmit={(event) => {
              event.preventDefault();
              if (deactivateUserId) {
                void onDeactivateUser(deactivateUserId);
              }
            }}
          >
            <div className="section-title">
              <h2>停用用户</h2>
              <span>super_admin</span>
            </div>
            <UserSearchInput
              value={deactivateSearch}
              onChange={(value) => {
                setDeactivateSearch(value);
                const id = Number(value);
                setDeactivateUserId(Number.isFinite(id) && id > 0 ? id : null);
              }}
              placeholder="搜索要停用的用户名或昵称"
            />
            {deactivateUserId && <p className="muted">用户 ID：{deactivateUserId}</p>}
            <button className="danger" disabled={!deactivateUserId}>
              <Lock size={17} />
              停用
            </button>
          </form>
        </>
      )}
    </section>
  );
}
