import { Activity } from "lucide-react";
import { useState } from "react";
import type { AnalyticsResponse, FanCircleDetail, PostDetail, UserProfile } from "../../api/types";
import { AnalyticsCard } from "./AnalyticsCard";

interface AnalyticsViewProps {
  currentUser: UserProfile | null;
  selectedCircle: FanCircleDetail | null;
  selectedPost: PostDetail | null;
  userAnalytics: AnalyticsResponse | null;
  circleAnalytics: AnalyticsResponse | null;
  postAnalytics: AnalyticsResponse | null;
  onLoadUserAnalytics: (userId: number) => void;
}

export function AnalyticsView({
  currentUser,
  selectedCircle,
  selectedPost,
  userAnalytics,
  circleAnalytics,
  postAnalytics,
  onLoadUserAnalytics,
}: AnalyticsViewProps) {
  const [userId, setUserId] = useState("");

  return (
    <section className="analytics-grid">
      <div className="panel">
        <div className="section-title">
          <h2>用户分析</h2>
          <span>{currentUser ? currentUser.nickname : "需登录"}</span>
        </div>
        <form
          className="lookup"
          onSubmit={(event) => {
            event.preventDefault();
            const id = Number(userId || currentUser?.id);
            if (Number.isFinite(id) && id > 0) {
              onLoadUserAnalytics(id);
            }
          }}
        >
          <Activity size={17} />
          <input value={userId} onChange={(event) => setUserId(event.target.value)} placeholder="用户 ID，默认当前用户" />
          <button className="ghost">加载</button>
        </form>
        <AnalyticsCard analytics={userAnalytics} emptyText="当前没有可展示的用户分析，或你没有权限查看。" />
      </div>

      <div className="panel">
        <div className="section-title">
          <h2>圈子分析</h2>
          <span>{selectedCircle?.club_name ?? "未选择"}</span>
        </div>
        <AnalyticsCard analytics={circleAnalytics} emptyText="选择球迷圈后显示圈子分析。" />
      </div>

      <div className="panel">
        <div className="section-title">
          <h2>帖子分析</h2>
          <span>{selectedPost ? `#${selectedPost.id}` : "未选择"}</span>
        </div>
        <AnalyticsCard analytics={postAnalytics} emptyText="选择帖子后显示互动分析。" />
      </div>
    </section>
  );
}
