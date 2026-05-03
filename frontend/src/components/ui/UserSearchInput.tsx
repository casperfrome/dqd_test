import { Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../../api/client";
import type { UserBrief } from "../../api/types";
import { roleLabels } from "../../utils/constants";

export function UserSearchInput({
  value,
  onChange,
  placeholder = "搜索用户名或昵称",
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  const [results, setResults] = useState<UserBrief[]>([]);
  const [open, setOpen] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const doSearch = async (query: string) => {
    if (query.trim().length < 1) {
      setResults([]);
      setOpen(false);
      return;
    }
    try {
      const users = await api.searchUsers(query.trim());
      setResults(users);
      setOpen(users.length > 0);
    } catch {
      setResults([]);
    }
  };

  const handleInput = (text: string) => {
    onChange(text);
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    timerRef.current = setTimeout(() => void doSearch(text), 300);
  };

  useEffect(() => {
    return () => {
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current);
      }
    };
  }, []);

  return (
    <div className="user-search-wrap">
      <label className="user-search-label">
        <Search size={16} />
        <input
          value={value}
          onChange={(event) => handleInput(event.target.value)}
          onFocus={() => results.length > 0 && setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 200)}
          placeholder={placeholder}
          autoComplete="off"
        />
      </label>
      {open && results.length > 0 && (
        <div className="user-search-dropdown">
          {results.map((user) => (
            <button
              key={user.id}
              type="button"
              className="user-search-option"
              onMouseDown={() => {
                onChange(user.nickname);
                setOpen(false);
                setResults([]);
              }}
              onClick={() => {
                onChange(String(user.id));
                setOpen(false);
                setResults([]);
              }}
            >
              <img src={user.avatar_url} alt="" />
              <span>
                <strong>{user.nickname}</strong>
                <small>@{user.username}</small>
              </span>
              <small className="user-search-role">{roleLabels[user.role]}</small>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
