import { LogIn, Sparkles, X } from "lucide-react";
import { FormEvent, useState } from "react";
import { api } from "../../api/client";
import type { AuthMode, NoticeKind } from "../../utils/constants";
import { getErrorMessage } from "../../utils/helpers";

interface AuthDialogProps {
  mode: AuthMode;
  onModeChange: (mode: AuthMode) => void;
  onClose: () => void;
  onLoginSuccess: (token: string) => Promise<void>;
  onNotice: (kind: NoticeKind, text: string) => void;
}

export function AuthDialog({
  mode,
  onModeChange,
  onClose,
  onLoginSuccess,
  onNotice,
}: AuthDialogProps) {
  const [username, setUsername] = useState("");
  const [nickname, setNickname] = useState("");
  const [password, setPassword] = useState("");
  const [bio, setBio] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    try {
      if (mode === "register") {
        await api.register({ username, nickname, password, bio });
        const token = await api.login({ username, password });
        await onLoginSuccess(token.access_token);
        return;
      } else {
        const token = await api.login({ username, password });
        await onLoginSuccess(token.access_token);
      }
    } catch (error) {
      onNotice("error", getErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="dialog-backdrop" role="presentation">
      <form className="auth-dialog" onSubmit={(event) => void submit(event)}>
        <div className="dialog-head">
          <div>
            <p className="eyebrow">{mode === "login" ? "Login" : "Register"}</p>
            <h2>{mode === "login" ? "登录账号" : "创建账号"}</h2>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="关闭">
            <X size={18} />
          </button>
        </div>
        <label>
          用户名
          <input required minLength={3} maxLength={32} value={username} onChange={(event) => setUsername(event.target.value)} />
        </label>
        {mode === "register" && (
          <label>
            昵称
            <input required minLength={1} maxLength={64} value={nickname} onChange={(event) => setNickname(event.target.value)} />
          </label>
        )}
        <label>
          密码
          <input required minLength={6} maxLength={128} type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
        </label>
        {mode === "register" && (
          <label>
            简介
            <textarea maxLength={280} rows={3} value={bio} onChange={(event) => setBio(event.target.value)} />
          </label>
        )}
        <button className="primary full" disabled={submitting}>
          {mode === "login" ? <LogIn size={17} /> : <Sparkles size={17} />}
          {submitting ? "提交中" : mode === "login" ? "登录" : "注册"}
        </button>
        <button
          type="button"
          className="ghost full"
          onClick={() => onModeChange(mode === "login" ? "register" : "login")}
        >
          {mode === "login" ? "没有账号？去注册" : "已有账号？去登录"}
        </button>
      </form>
    </div>
  );
}
