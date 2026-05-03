import { Activity, Plus, RefreshCw, Send, Square } from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";
import { api } from "../../api/client";
import type { CodeAiMessage, CodeAiSessionSummary, CodeAiSource, DatabaseAiHealthResponse, UserProfile } from "../../api/types";
import { formatDate, getErrorMessage } from "../../utils/helpers";
import { EmptyState } from "../ui/EmptyState";
import { MarkdownMessage } from "../ui/MarkdownMessage";
import { CodeSources } from "./CodeSources";

interface CodeAiPanelProps {
  currentUser: UserProfile | null;
  onOpenSource: (source: CodeAiSource) => void;
}

export function CodeAiPanel({ currentUser, onOpenSource }: CodeAiPanelProps) {
  const [sessions, setSessions] = useState<CodeAiSessionSummary[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<CodeAiMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [thinkingEnabled, setThinkingEnabled] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loadingSession, setLoadingSession] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [aiStatus, setAiStatus] = useState<string | null>(null);
  const [health, setHealth] = useState<DatabaseAiHealthResponse | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const isSuperAdmin = currentUser?.role === "super_admin";

  const loadSession = async (sessionId: string) => {
    setLoadingSession(true);
    setAiError(null);
    try {
      const detail = await api.getCodeAiSession(sessionId);
      setSelectedSessionId(detail.id);
      setMessages(detail.messages);
    } catch (error) {
      setAiError(getErrorMessage(error));
    } finally {
      setLoadingSession(false);
    }
  };

  const loadSessions = async () => {
    try {
      const items = await api.listCodeAiSessions();
      setSessions(items);
      if (!selectedSessionId && items[0]) {
        await loadSession(items[0].id);
      }
    } catch (error) {
      setAiError(getErrorMessage(error));
    }
  };

  useEffect(() => {
    setSelectedSessionId(null);
    setMessages([]);
    void loadSessions();
  }, [currentUser?.id]);

  const stopGeneration = () => {
    abortRef.current?.abort();
  };

  const submitQuestion = async (event: FormEvent) => {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || busy) {
      return;
    }
    const controller = new AbortController();
    abortRef.current = controller;
    setBusy(true);
    setAiError(null);
    setAiStatus(null);
    const createdAt = new Date().toISOString();
    const assistantTempId = -Date.now();
    const userTempId = assistantTempId - 1;
    let streamError: string | null = null;
    let latestSources: CodeAiSource[] = [];
    setMessages((items) => [
      ...items,
      {
        id: userTempId,
        role: "user",
        content: trimmed,
        thinking_enabled: thinkingEnabled,
        thinking_content: "",
        input_token_count: 0,
        output_token_count: 0,
        retrieved_fact_ids: [],
        sources: [],
        created_at: createdAt,
      },
    ]);
    setQuestion("");

    const ensureAssistantMessage = () => {
      setMessages((items) =>
        items.some((message) => message.id === assistantTempId)
          ? items
          : [
              ...items,
              {
                id: assistantTempId,
                role: "assistant",
                content: "",
                thinking_enabled: thinkingEnabled,
                thinking_content: "",
                input_token_count: 0,
                output_token_count: 0,
                retrieved_fact_ids: [],
                sources: latestSources,
                created_at: new Date().toISOString(),
              },
            ],
      );
    };

    try {
      await api.streamCodeAiChat(
        {
          question: trimmed,
          session_id: selectedSessionId,
          thinking_enabled: thinkingEnabled,
        },
        (streamEvent) => {
          if (streamEvent.event === "session") {
            setSelectedSessionId(streamEvent.data.session_id);
            setMessages((items) =>
              items.map((message) =>
                message.id === userTempId
                  ? {
                      ...message,
                      id: streamEvent.data.user_message_id,
                      thinking_enabled: streamEvent.data.thinking_enabled,
                    }
                  : message,
              ),
            );
          }
          if (streamEvent.event === "sources") {
            latestSources = streamEvent.data.sources;
          }
          if (streamEvent.event === "thinking_delta") {
            ensureAssistantMessage();
            setMessages((items) =>
              items.map((message) =>
                message.id === assistantTempId
                  ? {
                      ...message,
                      thinking_enabled: true,
                      thinking_content: `${message.thinking_content}${streamEvent.data.delta}`,
                      sources: latestSources,
                    }
                  : message,
              ),
            );
          }
          if (streamEvent.event === "content_delta") {
            ensureAssistantMessage();
            setMessages((items) =>
              items.map((message) =>
                message.id === assistantTempId
                  ? {
                      ...message,
                      content: `${message.content}${streamEvent.data.delta}`,
                      sources: latestSources,
                    }
                  : message,
              ),
            );
          }
          if (streamEvent.event === "done") {
            latestSources = streamEvent.data.sources;
            setMessages((items) =>
              items.map((message) =>
                message.id === assistantTempId
                  ? {
                      ...message,
                      id: streamEvent.data.assistant_message_id,
                      thinking_enabled: streamEvent.data.thinking_enabled,
                      input_token_count: streamEvent.data.input_token_count,
                      output_token_count: streamEvent.data.output_token_count,
                      retrieved_fact_ids: streamEvent.data.sources.map((source) => source.fact_id),
                      sources: streamEvent.data.sources,
                    }
                  : message,
              ),
            );
          }
          if (streamEvent.event === "error") {
            streamError = streamEvent.data.message;
            setAiError(streamEvent.data.message);
          }
        },
        controller.signal,
      );
      if (!streamError && !controller.signal.aborted) {
        setAiStatus("回答已完成。");
      }
      setSessions(await api.listCodeAiSessions());
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) {
        setAiError(getErrorMessage(error));
      }
    } finally {
      setBusy(false);
      abortRef.current = null;
    }
  };

  const startNewSession = () => {
    setSelectedSessionId(null);
    setMessages([]);
    setAiError(null);
    setAiStatus(null);
  };

  const checkHealth = async () => {
    setAiError(null);
    try {
      const response = await api.getCodeAiHealth();
      setHealth(response);
      setAiStatus(response.ok ? `Ollama 可用：${response.model}` : response.error ?? "Ollama 不可用");
    } catch (error) {
      setAiError(getErrorMessage(error));
    }
  };

  const rebuildFacts = async () => {
    setBusy(true);
    setAiError(null);
    try {
      const response = await api.rebuildCodeAiFacts();
      setAiStatus(`代码事实库已重建：${response.fact_count} 条片段`);
    } catch (error) {
      setAiError(getErrorMessage(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel ai-chat-panel code-ai-panel">
      <div className="section-title">
        <div>
          <h2>代码问答</h2>
          <p className="muted">基于项目源码片段进行 RAG 回答，并定位到相关文件行号。</p>
        </div>
        <div className="toolbar">
          <button className="ghost" type="button" onClick={startNewSession}>
            <Plus size={17} />
            新会话
          </button>
          {isSuperAdmin && (
            <>
              <button className="ghost" type="button" onClick={() => void checkHealth()}>
                <Activity size={17} />
                健康检查
              </button>
              <button className="ghost" type="button" disabled={busy} onClick={() => void rebuildFacts()}>
                <RefreshCw size={17} />
                重建代码库
              </button>
            </>
          )}
        </div>
      </div>

      {(aiError || aiStatus || health) && (
        <div className={`ai-status ${aiError || health?.ok === false ? "error" : "success"}`}>
          <span>{aiError ?? aiStatus ?? (health?.ok ? "Ollama 可用" : health?.error)}</span>
        </div>
      )}

      <div className="ai-chat-grid">
        <div className="ai-session-list">
          <div className="section-title compact-title">
            <h3>会话</h3>
            <span>{sessions.length}</span>
          </div>
          {sessions.map((session) => (
            <button
              key={session.id}
              className={`ai-session-row ${selectedSessionId === session.id ? "active" : ""}`}
              onClick={() => void loadSession(session.id)}
            >
              <strong>{session.title}</strong>
              <small>{formatDate(session.updated_at)}</small>
            </button>
          ))}
          {sessions.length === 0 && <EmptyState text="还没有代码问答会话。" />}
        </div>

        <div className="ai-conversation">
          <div className="ai-message-list code-message-list">
            {messages.map((message) => (
              <div key={message.id} className={`ai-message ${message.role}`}>
                <span>{message.role === "user" ? "你" : "AI"}</span>
                {message.role === "assistant" ? (
                  <MarkdownMessage content={message.content} />
                ) : (
                  <p className="ai-message-body">{message.content}</p>
                )}
                {message.role === "assistant" && message.thinking_content && (
                  <details className="ai-thinking">
                    <summary>深度思考</summary>
                    <MarkdownMessage content={message.thinking_content} compact />
                  </details>
                )}
                {message.role === "assistant" &&
                  (message.input_token_count > 0 || message.output_token_count > 0) && (
                    <div className="ai-token-meta">
                      输入 {message.input_token_count} · 输出 {message.output_token_count}
                    </div>
                  )}
                {message.sources.length > 0 && <CodeSources sources={message.sources} onOpenSource={onOpenSource} />}
              </div>
            ))}
            {messages.length === 0 && (
              <EmptyState text={loadingSession ? "正在加载会话..." : "询问项目结构、函数职责、组件关系或接口实现。"} />
            )}
          </div>

          <form className="ai-chat-form" onSubmit={(event) => void submitQuestion(event)}>
            <label className="check-row ai-thinking-toggle">
              <input
                type="checkbox"
                checked={thinkingEnabled}
                onChange={(event) => setThinkingEnabled(event.target.checked)}
              />
              开启深度思考
            </label>
            <textarea
              rows={3}
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && event.ctrlKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              placeholder="例如：create_app 注册了哪些路由？数据库 AI 面板在哪里处理 SSE？"
            />
            {busy ? (
              <button className="danger" type="button" onClick={stopGeneration}>
                <Square size={17} />
                暂停生成
              </button>
            ) : (
              <button className="primary" type="submit" disabled={!question.trim()}>
                <Send size={17} />
                发送
              </button>
            )}
          </form>
        </div>
      </div>
    </div>
  );
}
