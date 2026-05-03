import { ThumbsDown, ThumbsUp, X } from "lucide-react";
import { FormEvent, useState } from "react";
import type { CommentResponse } from "../../api/types";
import { formatDate } from "../../utils/helpers";

interface CommentItemProps {
  comment: CommentResponse;
  onCreateComment: (content: string, parentCommentId?: number | null) => Promise<void>;
  onReactComment: (commentId: number, action: "like" | "dislike") => Promise<void>;
  onOpenProfile: (userId: number) => void;
  canDelete: boolean;
  onDeleteComment: (commentId: number) => Promise<void>;
}

export function CommentItem({
  comment,
  onCreateComment,
  onReactComment,
  onOpenProfile,
  canDelete,
  onDeleteComment,
}: CommentItemProps) {
  const [replying, setReplying] = useState(false);
  const [reply, setReply] = useState("");
  const submitReply = async (event: FormEvent) => {
    event.preventDefault();
    if (!reply.trim()) {
      return;
    }
    await onCreateComment(reply.trim(), comment.id);
    setReply("");
    setReplying(false);
  };

  return (
    <div className="comment" style={{ marginLeft: `${Math.min(comment.depth, 4) * 18}px` }}>
      <button className="author-link" onClick={() => onOpenProfile(comment.author.id)}>
        <img src={comment.author.avatar_url} alt="" />
        {comment.author.nickname}
      </button>
      <p>{comment.content}</p>
      <div className="comment-actions">
        <span>{formatDate(comment.created_at)}</span>
        <button onClick={() => void onReactComment(comment.id, "like")}>
          <ThumbsUp size={14} /> {comment.like_count}
        </button>
        <button onClick={() => void onReactComment(comment.id, "dislike")}>
          <ThumbsDown size={14} /> {comment.dislike_count}
        </button>
        <button onClick={() => setReplying((value) => !value)}>回复</button>
        {canDelete && (
          <button className="danger-text" onClick={() => void onDeleteComment(comment.id)}>
            <X size={13} /> 删除
          </button>
        )}
      </div>
      {replying && (
        <form className="reply-form" onSubmit={(event) => void submitReply(event)}>
          <input
            value={reply}
            onChange={(event) => setReply(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && event.ctrlKey) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
            placeholder="回复内容"
          />
          <button className="primary" type="submit">
            发送
          </button>
        </form>
      )}
    </div>
  );
}
