import { Vote } from "lucide-react";
import { useState } from "react";
import type { PostDetail } from "../../api/types";

export function PollBox({ post, onVote }: { post: PostDetail; onVote: (optionIds: number[]) => Promise<void> }) {
  const [selected, setSelected] = useState<number[]>([]);
  const poll = post.poll;

  if (!poll) {
    return null;
  }

  const totalVotes = poll.options.reduce((total, option) => total + option.vote_count, 0);
  const toggle = (optionId: number) => {
    setSelected((current) => {
      if (poll.allow_multiple) {
        return current.includes(optionId)
          ? current.filter((id) => id !== optionId)
          : [...current, optionId];
      }
      return [optionId];
    });
  };

  return (
    <div className="poll-box">
      <div className="section-title">
        <h3>{poll.question}</h3>
        <span>{poll.allow_multiple ? "多选" : "单选"}</span>
      </div>
      {poll.options.map((option) => {
        const percent = totalVotes === 0 ? 0 : Math.round((option.vote_count / totalVotes) * 100);
        return (
          <button
            type="button"
            className={`poll-option ${selected.includes(option.id) ? "selected" : ""}`}
            key={option.id}
            onClick={() => toggle(option.id)}
          >
            <span>{option.option_text}</span>
            <strong>{option.vote_count} 票</strong>
            <i style={{ width: `${percent}%` }} />
          </button>
        );
      })}
      <button className="primary" disabled={selected.length === 0} onClick={() => void onVote(selected)}>
        <Vote size={17} />
        提交投票
      </button>
    </div>
  );
}
