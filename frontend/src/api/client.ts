import type {
  AnalyticsResponse,
  CodeAiChatRequest,
  CodeAiChatResponse,
  CodeAiSessionDetail,
  CodeAiSessionSummary,
  CodeAiStopRequest,
  CodeAiStreamEvent,
  CodeCatalogResponse,
  CodeFileResponse,
  CommentResponse,
  CreateCommentRequest,
  CreatePostRequest,
  DatabaseAccessResponse,
  DatabaseAccessUpdateRequest,
  DatabaseAiChatRequest,
  DatabaseAiChatResponse,
  DatabaseAiFactsRebuildResponse,
  DatabaseAiHealthResponse,
  DatabaseAiSessionDetail,
  DatabaseAiSessionSummary,
  DatabaseAiStopRequest,
  DatabaseAiStreamEvent,
  DatabaseCatalogResponse,
  FanCircleDetail,
  FanCircleSummary,
  LoginRequest,
  MessageResponse,
  PaginatedResponse,
  PostDetail,
  PostSummary,
  RegisterRequest,
  TokenResponse,
  UserBrief,
  UserProfile,
} from "./types";

const TOKEN_KEY = "football-domain-token";
const AI_CLIENT_KEY = "football-domain-ai-client-id";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function getStoredToken(): string | null {
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearStoredToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}

export function getAiClientId(): string {
  const current = window.localStorage.getItem(AI_CLIENT_KEY);
  if (current) {
    return current;
  }
  const next =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  window.localStorage.setItem(AI_CLIENT_KEY, next);
  return next;
}

function queryString(params?: Record<string, string | number | boolean | null | undefined>) {
  const search = new URLSearchParams();
  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  });
  const value = search.toString();
  return value ? `?${value}` : "";
}

async function parseError(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
    if (Array.isArray(payload.detail)) {
      return payload.detail
        .map((item: { msg?: string } | unknown) =>
          typeof item === "object" && item !== null && "msg" in item
            ? String((item as { msg?: string }).msg)
            : JSON.stringify(item),
        )
        .join("；");
    }
    return JSON.stringify(payload);
  } catch {
    return response.statusText || "请求失败";
  }
}

async function request<T>(
  path: string,
  options: RequestInit & { token?: string | null } = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  const token = options.token ?? getStoredToken();

  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(path, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const message = await parseError(response);
    if (response.status === 401) {
      clearStoredToken();
    }
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

function parseSseBlock(block: string): DatabaseAiStreamEvent | null {
  let event = "";
  const dataLines: string[] = [];
  block.split(/\r?\n/).forEach((line) => {
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  });
  if (!event) {
    return null;
  }
  return {
    event,
    data: JSON.parse(dataLines.join("\n") || "{}"),
  } as DatabaseAiStreamEvent;
}

async function requestSse<TEvent extends DatabaseAiStreamEvent | CodeAiStreamEvent>(
  path: string,
  options: RequestInit & { signal?: AbortSignal },
  onEvent: (event: TEvent) => void,
): Promise<void> {
  const headers = new Headers(options.headers);
  const token = getStoredToken();
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response: Response;
  try {
    response = await fetch(path, {
      ...options,
      headers,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      return;
    }
    throw error;
  }

  if (!response.ok) {
    const message = await parseError(response);
    if (response.status === 401) {
      clearStoredToken();
    }
    throw new ApiError(response.status, message);
  }
  if (!response.body) {
    throw new ApiError(response.status, "浏览器不支持流式响应。");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    let separatorIndex = buffer.indexOf("\n\n");
    while (separatorIndex >= 0) {
      const block = buffer.slice(0, separatorIndex).trim();
      buffer = buffer.slice(separatorIndex + 2);
      const event = parseSseBlock(block);
      if (event) {
        onEvent(event as TEvent);
      }
      separatorIndex = buffer.indexOf("\n\n");
    }
  }

  buffer += decoder.decode();
  const finalEvent = parseSseBlock(buffer.trim());
  if (finalEvent) {
    onEvent(finalEvent as TEvent);
  }
}

export const api = {
  register(payload: RegisterRequest) {
    return request<UserProfile>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  login(payload: LoginRequest) {
    return request<TokenResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  me() {
    return request<UserProfile>("/api/v1/auth/me");
  },
  listFanCircles(page = 1, pageSize = 20) {
    return request<PaginatedResponse<FanCircleSummary>>(
      `/api/v1/fan-circles${queryString({ page, page_size: pageSize })}`,
    );
  },
  getFanCircle(circleId: number) {
    return request<FanCircleDetail>(`/api/v1/fan-circles/${circleId}`);
  },
  getFanCircleAnalytics(circleId: number) {
    return request<AnalyticsResponse>(`/api/v1/fan-circles/${circleId}/analytics`);
  },
  getCirclePosts(circleId: number, page = 1, pageSize = 20) {
    return request<PaginatedResponse<PostSummary>>(
      `/api/v1/fan-circles/${circleId}/posts${queryString({
        page,
        page_size: pageSize,
      })}`,
    );
  },
  createPost(circleId: number, payload: CreatePostRequest) {
    return request<PostDetail>(`/api/v1/fan-circles/${circleId}/posts`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  getPost(postId: number) {
    return request<PostDetail>(`/api/v1/posts/${postId}`);
  },
  likePost(postId: number) {
    return request<PostDetail>(`/api/v1/posts/${postId}/like`, { method: "POST" });
  },
  dislikePost(postId: number) {
    return request<PostDetail>(`/api/v1/posts/${postId}/dislike`, {
      method: "POST",
    });
  },
  votePost(postId: number, optionIds: number[]) {
    return request<PostDetail>(`/api/v1/posts/${postId}/vote`, {
      method: "POST",
      body: JSON.stringify({ option_ids: optionIds }),
    });
  },
  getPostAnalytics(postId: number) {
    return request<AnalyticsResponse>(`/api/v1/posts/${postId}/analytics`);
  },
  listComments(postId: number, page = 1, pageSize = 50) {
    return request<PaginatedResponse<CommentResponse>>(
      `/api/v1/posts/${postId}/comments${queryString({
        page,
        page_size: pageSize,
      })}`,
    );
  },
  createComment(postId: number, payload: CreateCommentRequest) {
    return request<CommentResponse>(`/api/v1/posts/${postId}/comments`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  replyComment(commentId: number, payload: CreateCommentRequest) {
    return request<CommentResponse>(`/api/v1/comments/${commentId}/reply`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  likeComment(commentId: number) {
    return request<CommentResponse>(`/api/v1/comments/${commentId}/like`, {
      method: "POST",
    });
  },
  dislikeComment(commentId: number) {
    return request<CommentResponse>(`/api/v1/comments/${commentId}/dislike`, {
      method: "POST",
    });
  },
  getUser(userId: number) {
    return request<UserProfile>(`/api/v1/users/${userId}`);
  },
  followUser(userId: number) {
    return request<MessageResponse>(`/api/v1/users/${userId}/follow`, {
      method: "POST",
    });
  },
  unfollowUser(userId: number) {
    return request<MessageResponse>(`/api/v1/users/${userId}/follow`, {
      method: "DELETE",
    });
  },
  listFollowers(userId: number, page = 1, pageSize = 20) {
    return request<PaginatedResponse<UserBrief>>(
      `/api/v1/users/${userId}/followers${queryString({
        page,
        page_size: pageSize,
      })}`,
    );
  },
  listFollowing(userId: number, page = 1, pageSize = 20) {
    return request<PaginatedResponse<UserBrief>>(
      `/api/v1/users/${userId}/following${queryString({
        page,
        page_size: pageSize,
      })}`,
    );
  },
  getUserAnalytics(userId: number) {
    return request<AnalyticsResponse>(`/api/v1/users/${userId}/analytics`);
  },
  listDatabases() {
    return request<DatabaseCatalogResponse>("/api/v1/databases");
  },
  getDatabaseAccess() {
    return request<DatabaseAccessResponse>("/api/v1/databases/access");
  },
  updateDatabaseAccess(payload: DatabaseAccessUpdateRequest) {
    return request<DatabaseAccessResponse>("/api/v1/databases/access", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },
  chatWithDatabaseAi(payload: DatabaseAiChatRequest) {
    return request<DatabaseAiChatResponse>("/api/v1/databases/ai/chat/complete", {
      method: "POST",
      headers: { "X-AI-Client-Id": getAiClientId() },
      body: JSON.stringify(payload),
    });
  },
  streamDatabaseAiChat(payload: DatabaseAiChatRequest, onEvent: (event: DatabaseAiStreamEvent) => void, signal?: AbortSignal) {
    return requestSse(
      "/api/v1/databases/ai/chat",
      {
        method: "POST",
        headers: { "X-AI-Client-Id": getAiClientId() },
        body: JSON.stringify(payload),
        signal,
      },
      onEvent,
    );
  },
  listDatabaseAiSessions() {
    return request<DatabaseAiSessionSummary[]>("/api/v1/databases/ai/sessions", {
      headers: { "X-AI-Client-Id": getAiClientId() },
    });
  },
  getDatabaseAiSession(sessionId: string) {
    return request<DatabaseAiSessionDetail>(`/api/v1/databases/ai/sessions/${sessionId}`, {
      headers: { "X-AI-Client-Id": getAiClientId() },
    });
  },
  rebuildDatabaseAiFacts() {
    return request<DatabaseAiFactsRebuildResponse>("/api/v1/databases/ai/facts/rebuild", {
      method: "POST",
    });
  },
  stopDatabaseAiChat(payload: DatabaseAiStopRequest) {
    return request<{ ok: boolean }>("/api/v1/databases/ai/chat/stop", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  getDatabaseAiHealth() {
    return request<DatabaseAiHealthResponse>("/api/v1/databases/ai/health");
  },
  getCodeCatalog() {
    return request<CodeCatalogResponse>("/api/v1/code/catalog");
  },
  getCodeFile(path: string) {
    return request<CodeFileResponse>(`/api/v1/code/file${queryString({ path })}`);
  },
  chatWithCodeAi(payload: CodeAiChatRequest) {
    return request<CodeAiChatResponse>("/api/v1/code/ai/chat/complete", {
      method: "POST",
      headers: { "X-AI-Client-Id": getAiClientId() },
      body: JSON.stringify(payload),
    });
  },
  streamCodeAiChat(payload: CodeAiChatRequest, onEvent: (event: CodeAiStreamEvent) => void, signal?: AbortSignal) {
    return requestSse<CodeAiStreamEvent>(
      "/api/v1/code/ai/chat",
      {
        method: "POST",
        headers: { "X-AI-Client-Id": getAiClientId() },
        body: JSON.stringify(payload),
        signal,
      },
      onEvent,
    );
  },
  listCodeAiSessions() {
    return request<CodeAiSessionSummary[]>("/api/v1/code/ai/sessions", {
      headers: { "X-AI-Client-Id": getAiClientId() },
    });
  },
  getCodeAiSession(sessionId: string) {
    return request<CodeAiSessionDetail>(`/api/v1/code/ai/sessions/${sessionId}`, {
      headers: { "X-AI-Client-Id": getAiClientId() },
    });
  },
  rebuildCodeAiFacts() {
    return request<DatabaseAiFactsRebuildResponse>("/api/v1/code/ai/facts/rebuild", {
      method: "POST",
    });
  },
  stopCodeAiChat(payload: CodeAiStopRequest) {
    return request<{ ok: boolean }>("/api/v1/code/ai/chat/stop", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  getCodeAiHealth() {
    return request<DatabaseAiHealthResponse>("/api/v1/code/ai/health");
  },
  assignCircleOwner(circleId: number, ownerUserId: number) {
    return request<MessageResponse>(`/api/v1/admin/fan-circles/${circleId}/owner`, {
      method: "POST",
      body: JSON.stringify({ owner_user_id: ownerUserId }),
    });
  },
  setPostPinned(postId: number, value: boolean) {
    return request<PostDetail>(`/api/v1/admin/posts/${postId}/pin`, {
      method: "POST",
      body: JSON.stringify({ value }),
    });
  },
  setPostLocked(postId: number, value: boolean) {
    return request<PostDetail>(`/api/v1/admin/posts/${postId}/lock`, {
      method: "POST",
      body: JSON.stringify({ value }),
    });
  },
  deactivateUser(userId: number) {
    return request<MessageResponse>(`/api/v1/admin/users/${userId}/deactivate`, {
      method: "POST",
    });
  },
};
