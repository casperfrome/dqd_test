import { ChevronRight, MessageCircle, Users } from "lucide-react";
import type { CreatePostRequest, CommentResponse, FanCircleDetail, FanCircleSummary, PostDetail, PostSummary, UserProfile } from "../../api/types";
import type { AuthMode } from "../../utils/constants";
import { EmptyState } from "../ui/EmptyState";
import { CircleHero } from "./CircleHero";
import { CreatePostBox } from "./CreatePostBox";
import { PostDetailPanel } from "./PostDetailPanel";
import { PostListItem } from "./PostListItem";

interface CirclesViewProps {
  circles: FanCircleSummary[];
  circleTotal: number;
  selectedCircle: FanCircleDetail | null;
  selectedCircleId: number | null;
  posts: PostSummary[];
  postTotal: number;
  selectedPost: PostDetail | null;
  comments: CommentResponse[];
  commentTotal: number;
  currentUser: UserProfile | null;
  canModerateSelectedPost: boolean;
  canDeleteSelectedPost: boolean;
  canDeleteComment: (commentAuthorId: number) => boolean;
  onSelectCircle: (circleId: number) => void;
  onSelectPost: (postId: number) => void;
  onCreatePost: (payload: CreatePostRequest) => Promise<void>;
  onReactPost: (action: "like" | "dislike") => Promise<void>;
  onVote: (optionIds: number[]) => Promise<void>;
  onCreateComment: (content: string, parentCommentId?: number | null) => Promise<void>;
  onReactComment: (commentId: number, action: "like" | "dislike") => Promise<void>;
  onOpenAuth: (mode?: AuthMode) => void;
  onOpenProfile: (userId: number) => void;
  onSetPostFlag: (flag: "pin" | "lock", value: boolean) => Promise<void>;
  onDeletePost: (postId: number) => Promise<void>;
  onDeleteComment: (commentId: number) => Promise<void>;
  onLoadMoreCircles: () => Promise<void>;
  onLoadMorePosts: () => Promise<void>;
  onLoadMoreComments: () => Promise<void>;
}

export function CirclesView({
  circles,
  circleTotal,
  selectedCircle,
  selectedCircleId,
  posts,
  postTotal,
  selectedPost,
  comments,
  commentTotal,
  currentUser,
  canModerateSelectedPost,
  canDeleteSelectedPost,
  canDeleteComment,
  onSelectCircle,
  onSelectPost,
  onCreatePost,
  onReactPost,
  onVote,
  onCreateComment,
  onReactComment,
  onOpenAuth,
  onOpenProfile,
  onSetPostFlag,
  onDeletePost,
  onDeleteComment,
  onLoadMoreCircles,
  onLoadMorePosts,
  onLoadMoreComments,
}: CirclesViewProps) {
  return (
    <section className="workspace-grid">
      <div className="panel circles-panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Fan Circles</p>
            <h2>俱乐部看板</h2>
          </div>
          <span className="metric-pill">{circleTotal} 个圈子</span>
        </div>
        <div className="circle-list">
          {circles.map((circle) => (
            <button
              className={`circle-row ${selectedCircleId === circle.id ? "active" : ""}`}
              key={circle.id}
              onClick={() => onSelectCircle(circle.id)}
            >
              <img src={circle.logo_url} alt="" />
              <span>
                <strong>{circle.club_name}</strong>
                <small>{circle.league_name}</small>
              </span>
              <ChevronRight size={16} />
            </button>
          ))}
          {circles.length === 0 && <EmptyState text="暂无球迷圈数据。" />}
          {circles.length < circleTotal && (
            <button className="ghost full" onClick={() => void onLoadMoreCircles()}>
              加载更多圈子（{circles.length}/{circleTotal}）
            </button>
          )}
        </div>
      </div>

      <div className="panel feed-panel">
        {selectedCircle ? (
          <>
            <CircleHero circle={selectedCircle} />
            <CreatePostBox currentUser={currentUser} onOpenAuth={onOpenAuth} onCreatePost={onCreatePost} />
            <div className="section-title">
              <h2>圈内帖子</h2>
              <span>{postTotal} 条</span>
            </div>
            <div className="post-list">
              {posts.map((post) => (
                <PostListItem
                  key={post.id}
                  post={post}
                  active={selectedPost?.id === post.id}
                  onSelect={() => onSelectPost(post.id)}
                  onOpenProfile={onOpenProfile}
                />
              ))}
              {posts.length === 0 && <EmptyState text="还没有帖子，成为第一个发帖的人！" icon={<MessageCircle size={22} />} />}
              {posts.length < postTotal && (
                <button className="ghost full" onClick={() => void onLoadMorePosts()}>
                  加载更多帖子（{posts.length}/{postTotal}）
                </button>
              )}
            </div>
          </>
        ) : (
          <EmptyState text="请从左侧选择一个球迷圈开始浏览。" icon={<Users size={22} />} />
        )}
      </div>

      <div className="panel detail-panel">
        {selectedPost ? (
          <PostDetailPanel
            post={selectedPost}
            comments={comments}
            commentTotal={commentTotal}
            canModerate={canModerateSelectedPost}
            canDeletePost={canDeleteSelectedPost}
            canDeleteComment={canDeleteComment}
            onReactPost={onReactPost}
            onVote={onVote}
            onCreateComment={onCreateComment}
            onReactComment={onReactComment}
            onOpenProfile={onOpenProfile}
            onSetPostFlag={onSetPostFlag}
            onDeletePost={onDeletePost}
            onDeleteComment={onDeleteComment}
            onLoadMoreComments={onLoadMoreComments}
          />
        ) : (
          <EmptyState text="从左侧选择帖子查看详情、评论和投票。" />
        )}
      </div>
    </section>
  );
}
