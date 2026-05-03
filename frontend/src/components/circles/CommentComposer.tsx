import { MessageCircle } from "lucide-react";
import { FormEvent, useState } from "react";

interface CommentComposerProps {
  locked?: boolean;
  onSubmit: (content: string) => Promise<void>;
}

export function CommentComposer({ locked, onSubmit }: CommentComposerProps) {
  const [content, setContent] = useState("");
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!content.trim()) {
      return;
    }
    await onSubmit(content.trim());
    setContent("");
  };

  return (
    <form className="comment-compose" onSubmit={(event) => void submit(event)}>
      <textarea
        rows={3}
        disabled={locked}
        value={content}
        onChange={(event) => setContent(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && event.ctrlKey) {
            event.preventDefault();
            event.currentTarget.form?.requestSubmit();
          }
        }}
        placeholder={locked ? "帖子已锁定，不能继续评论。" : "写下你的观点"}
      />
      <button className="primary" type="submit" disabled={locked || !content.trim()}>
        <MessageCircle size={17} />
        评论
      </button>
    </form>
  );
}
