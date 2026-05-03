import { Lock, MessageCircle, Pin, ThumbsDown, ThumbsUp, Unlock, X } from "lucide-react";
import type { CommentResponse, PostDetail } from "../../api/types";
import { categoryLabels } from "../../utils/constants";
import { formatDate } from "../../utils/helpers";
import { EmptyState } from "../ui/EmptyState";
import { CommentComposer } from "./CommentComposer";
import { CommentItem } from "./CommentItem";
import { PollBox } from "./PollBox";

interface PostDetailPanelProps {
  post: PostDetail;
  comments: CommentResponse[];
  commentTotal: number;
  canModerate: boolean;
  canDeletePost: boolean;
  canDeleteComment: (commentAuthorId: number) => boolean;
  onReactPost: (action: "like" | "dislike") => Promise<void>;
  onVote: (optionIds: number[]) => Promise<void>;
  onCreateComment: (content: string, parentCommentId?: number | null) => Promise<void>;
  onReactComment: (commentId: number, action: "like" | "dislike") => Promise<void>;
  onOpenProfile: (userId: number) => void;
  onSetPostFlag: (flag: "pin" | "lock", value: boolean) => Promise<void>;
  onDeletePost: (postId: number) => Promise<void>;
  onDeleteComment: (commentId: number) => Promise<void>;
  onLoadMoreComments: () => Promise<void>;
}

export function PostDetailPanel({
  post,
  comments,
  commentTotal,
  canModerate,
  canDeletePost,
  canDeleteComment,
  onReactPost,
  onVote,
  onCreateComment,
  onReactComment,
  onOpenProfile,
  onSetPostFlag,
  onDeletePost,
  onDeleteComment,
  onLoadMoreComments,
}: PostDetailPanelProps) {
  return (
    <article className="post-detail">
      <div className="post-detail-head">
        <div className="post-meta">
          <span>{post.club_name}</span>
          <span>{categoryLabels[post.category]}</span>
          <span>{formatDate(post.created_at)}</span>
        </div>
        <h2>{post.title}</h2>
        <button className="author-link" onClick={() => onOpenProfile(post.author.id)}>
          <img src={post.author.avatar_url} alt="" />
          {post.author.nickname}
        </button>
      </div>

      <p className="post-content">{post.content}</p>

      <div className="tag-row">
        {post.tags.map((tag) => (
          <span key={tag}>#{tag}</span>
        ))}
      </div>

      <div className="toolbar">
        <button className="ghost" onClick={() => void onReactPost("like")}>
          <ThumbsUp size={17} />
          {post.like_count}
        </button>
        <button className="ghost" onClick={() => void onReactPost("dislike")}>
          <ThumbsDown size={17} />
          {post.dislike_count}
        </button>
        {canModerate && (
          <>
            <button className="ghost" onClick={() => void onSetPostFlag("pin", !post.is_pinned)}>
              <Pin size={17} />
              {post.is_pinned ? "取消置顶" : "置顶"}
            </button>
            <button className="ghost" onClick={() => void onSetPostFlag("lock", !post.is_locked)}>
              {post.is_locked ? <Unlock size={17} /> : <Lock size={17} />}
              {post.is_locked ? "解锁" : "锁定"}
            </button>
          </>
        )}
        {canDeletePost && (
          <button className="ghost danger-text" onClick={() => void onDeletePost(post.id)}>
            <X size={17} />
            删除帖子
          </button>
        )}
      </div>

      {post.poll && <PollBox post={post} onVote={onVote} />}

      <CommentComposer locked={post.is_locked} onSubmit={(content) => onCreateComment(content)} />

      <div className="comments">
        <div className="section-title">
          <h3>评论</h3>
          <span>{commentTotal} 条</span>
        </div>
        {comments.map((comment) => (
          <CommentItem
            key={comment.id}
            comment={comment}
            onCreateComment={onCreateComment}
            onReactComment={onReactComment}
            onOpenProfile={onOpenProfile}
            canDelete={canDeleteComment(comment.author.id)}
            onDeleteComment={onDeleteComment}
          />
        ))}
        {comments.length === 0 && <EmptyState text="还没有评论，来抢沙发！" icon={<MessageCircle size={22} />} />}
        {comments.length < commentTotal && (
          <button className="ghost full" onClick={() => void onLoadMoreComments()}>
            加载更多评论（{comments.length}/{commentTotal}）
          </button>
        )}
      </div>
    </article>
  );
}
