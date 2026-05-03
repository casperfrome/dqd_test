import { Check, LogIn, Plus } from "lucide-react";
import { FormEvent, useState } from "react";
import type { UserProfile, CreatePostRequest, PostCategory } from "../../api/types";
import type { AuthMode } from "../../utils/constants";
import { categoryLabels, categoryOptions } from "../../utils/constants";

interface CreatePostBoxProps {
  currentUser: UserProfile | null;
  onOpenAuth: (mode?: AuthMode) => void;
  onCreatePost: (payload: CreatePostRequest) => Promise<void>;
}

export function CreatePostBox({ currentUser, onOpenAuth, onCreatePost }: CreatePostBoxProps) {
  const [expanded, setExpanded] = useState(false);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [category, setCategory] = useState<PostCategory>("discussion");
  const [tags, setTags] = useState("");
  const [pollEnabled, setPollEnabled] = useState(false);
  const [pollQuestion, setPollQuestion] = useState("");
  const [allowMultiple, setAllowMultiple] = useState(false);
  const [pollOptions, setPollOptions] = useState("支持\n不支持");

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const payload: CreatePostRequest = {
      title,
      content,
      category,
      tags: tags
        .split(/[,\s，]+/)
        .map((tag) => tag.trim())
        .filter(Boolean)
        .slice(0, 10),
      poll: pollEnabled
        ? {
            question: pollQuestion,
            allow_multiple: allowMultiple,
            expires_at: null,
            options: pollOptions
              .split("\n")
              .map((option) => option.trim())
              .filter(Boolean)
              .slice(0, 10),
          }
        : null,
    };
    await onCreatePost(payload);
    setTitle("");
    setContent("");
    setTags("");
    setPollEnabled(false);
    setPollQuestion("");
    setPollOptions("支持\n不支持");
    setExpanded(false);
  };

  if (!currentUser) {
    return (
      <div className="compose compact">
        <span>登录后发布新帖、评论和投票。</span>
        <button className="primary" onClick={() => onOpenAuth("login")}>
          <LogIn size={17} />
          登录
        </button>
      </div>
    );
  }

  return (
    <form className={`compose ${expanded ? "expanded" : ""}`} onSubmit={(event) => void submit(event)}>
      {!expanded ? (
        <button type="button" className="compose-trigger" onClick={() => setExpanded(true)}>
          <Plus size={18} />
          发布一条新的圈内讨论
        </button>
      ) : (
        <>
          <input
            required
            maxLength={200}
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="标题"
          />
          <textarea
            required
            value={content}
            onChange={(event) => setContent(event.target.value)}
            placeholder="正文内容"
            rows={4}
          />
          <div className="form-grid">
            <label>
              分类
              <select value={category} onChange={(event) => setCategory(event.target.value as PostCategory)}>
                {categoryOptions.map((option) => (
                  <option key={option} value={option}>
                    {categoryLabels[option]}
                  </option>
                ))}
              </select>
            </label>
            <label>
              标签
              <input value={tags} onChange={(event) => setTags(event.target.value)} placeholder="欧冠 战术 阵容" />
            </label>
          </div>
          <label className="check-row">
            <input type="checkbox" checked={pollEnabled} onChange={(event) => setPollEnabled(event.target.checked)} />
            添加投票
          </label>
          {pollEnabled && (
            <div className="poll-editor">
              <input
                required
                maxLength={200}
                value={pollQuestion}
                onChange={(event) => setPollQuestion(event.target.value)}
                placeholder="投票问题"
              />
              <textarea
                value={pollOptions}
                onChange={(event) => setPollOptions(event.target.value)}
                rows={4}
                placeholder="每行一个选项，2-10 个"
              />
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={allowMultiple}
                  onChange={(event) => setAllowMultiple(event.target.checked)}
                />
                允许多选
              </label>
            </div>
          )}
          <div className="form-actions">
            <button type="button" className="ghost" onClick={() => setExpanded(false)}>
              取消
            </button>
            <button className="primary" type="submit">
              <Check size={17} />
              发布
            </button>
          </div>
        </>
      )}
    </form>
  );
}
