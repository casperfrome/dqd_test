import { MessageCircle, ThumbsDown, ThumbsUp, Vote } from "lucide-react";
import type { PostSummary } from "../../api/types";
import { categoryLabels } from "../../utils/constants";
import { summarize } from "../../utils/helpers";

interface PostListItemProps {
  post: PostSummary;
  active: boolean;
  onSelect: () => void;
  onOpenProfile: (userId: number) => void;
}

export function PostListItem({ post, active, onSelect, onOpenProfile }: PostListItemProps) {
  return (
    <article className={`post-card ${active ? "active" : ""}`}>
      <button className="post-card-main" onClick={onSelect}>
        <div className="post-meta">
          <span>{categoryLabels[post.category]}</span>
          {post.is_pinned && <span className="status good">置顶</span>}
          {post.is_locked && <span className="status warn">锁定</span>}
        </div>
        <h3>{post.title}</h3>
        <p>{summarize(post.content)}</p>
        <div className="stats-row">
          <span>
            <ThumbsUp size={14} /> {post.like_count}
          </span>
          <span>
            <ThumbsDown size={14} /> {post.dislike_count}
          </span>
          <span>
            <MessageCircle size={14} /> {post.comment_count}
          </span>
          {post.has_poll && (
            <span>
              <Vote size={14} /> 投票
            </span>
          )}
        </div>
      </button>
      <button className="author-link" onClick={() => onOpenProfile(post.author.id)}>
        <img src={post.author.avatar_url} alt="" />
        {post.author.nickname}
      </button>
    </article>
  );
}
