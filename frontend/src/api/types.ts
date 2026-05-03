export type UserRole = "super_admin" | "fan_circle_owner" | "normal_user";

export type PostCategory =
  | "discussion"
  | "news"
  | "transfer"
  | "match"
  | "off_topic";

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface MessageResponse {
  message: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserBrief {
  id: number;
  username: string;
  nickname: string;
  role: UserRole;
  avatar_url: string;
}

export interface UserProfile extends UserBrief {
  bio: string;
  following_count: number;
  followers_count: number;
  total_likes_received: number;
  total_dislikes_received: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface FanCircleSummary {
  id: number;
  club_name: string;
  board_name: string;
  league_name: string;
  logo_url: string;
  description: string;
  post_count: number;
  follower_count: number;
  created_at: string;
  updated_at: string;
  owner: UserBrief | null;
}

export type FanCircleDetail = FanCircleSummary;

export interface PollOptionResponse {
  id: number;
  option_text: string;
  vote_count: number;
}

export interface PollResponse {
  id: number;
  question: string;
  allow_multiple: boolean;
  expires_at: string | null;
  options: PollOptionResponse[];
}

export interface PostSummary {
  id: number;
  fan_circle_id: number;
  title: string;
  content: string;
  category: PostCategory;
  tags: string[];
  like_count: number;
  dislike_count: number;
  comment_count: number;
  has_poll: boolean;
  is_pinned: boolean;
  is_locked: boolean;
  created_at: string;
  updated_at: string;
  author: UserBrief;
}

export interface PostDetail extends PostSummary {
  club_name: string;
  board_name: string;
  league_name: string;
  poll: PollResponse | null;
}

export interface CommentAuthor {
  id: number;
  username: string;
  nickname: string;
  avatar_url: string;
}

export interface CommentResponse {
  id: number;
  post_id: number;
  parent_comment_id: number | null;
  depth: number;
  path: string;
  content: string;
  like_count: number;
  dislike_count: number;
  created_at: string;
  updated_at: string;
  author: CommentAuthor;
}

export interface AnalyticsEvent {
  id: number;
  event_type: string;
  created_at: string;
  actor_user_id: number | null;
  target_user_id?: number | null;
  fan_circle_id?: number | null;
  post_id?: number | null;
  comment_id?: number | null;
  metadata: Record<string, unknown>;
}

export interface AnalyticsResponse {
  summary: Record<string, unknown>;
  recent_events: AnalyticsEvent[];
}

export type DatabaseAccessLevel = "public" | "authenticated" | "super_admin";

export interface DatabaseAccessResponse {
  access_level: DatabaseAccessLevel;
}

export interface DatabaseAccessUpdateRequest {
  access_level: DatabaseAccessLevel;
}

export interface DatabaseColumn {
  name: string;
  comment: string;
  type: string;
  not_null: boolean;
  default_value: string | null;
  primary_key: boolean;
  primary_key_position: number;
}

export interface DatabaseForeignKey {
  id: number;
  sequence: number;
  from_column: string;
  to_table: string;
  to_column: string | null;
  on_update: string;
  on_delete: string;
}

export interface DatabaseIndex {
  name: string;
  unique: boolean;
  origin: string;
  columns: string[];
}

export interface DatabaseTable {
  name: string;
  comment: string;
  row_count: number;
  columns: DatabaseColumn[];
  foreign_keys: DatabaseForeignKey[];
  indexes: DatabaseIndex[];
  sample_rows: Record<string, unknown>[];
}

export interface DatabaseInfo {
  name: string;
  path: string;
  size_bytes: number;
  table_count: number;
  status: string;
  error: string | null;
  tables: DatabaseTable[];
}

export interface DatabaseCatalogResponse {
  access_level: DatabaseAccessLevel;
  databases: DatabaseInfo[];
}

export interface DatabaseAiChatRequest {
  question: string;
  session_id?: string | null;
  thinking_enabled?: boolean;
}

export interface DatabaseAiSource {
  fact_id: number;
  fact_type: string;
  title: string;
  source_database_path: string;
  source_table_name: string | null;
  source_column_name: string | null;
  snippet: string;
  score: number | null;
}

export interface DatabaseAiChatResponse {
  session_id: string;
  user_message_id: number;
  assistant_message_id: number;
  answer: string;
  sources: DatabaseAiSource[];
}

export interface DatabaseAiSessionSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface DatabaseAiMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  thinking_enabled: boolean;
  thinking_content: string;
  input_token_count: number;
  output_token_count: number;
  is_stopped: boolean;
  retrieved_fact_ids: number[];
  sources: DatabaseAiSource[];
  created_at: string;
}

export interface DatabaseAiSessionDetail extends DatabaseAiSessionSummary {
  messages: DatabaseAiMessage[];
}

export interface DatabaseAiFactsRebuildResponse {
  fact_count: number;
  rebuilt_at: string;
}

export interface DatabaseAiHealthResponse {
  ok: boolean;
  model: string;
  base_url: string;
  error: string | null;
  available_models: string[];
}

export interface CodeFileInfo {
  path: string;
  name: string;
  extension: string;
  language: string;
  size_bytes: number;
  line_count: number;
}

export interface CodeTreeNode {
  name: string;
  path: string;
  type: "directory" | "file";
  children: CodeTreeNode[];
  file: CodeFileInfo | null;
}

export interface CodeCatalogResponse {
  access_level: DatabaseAccessLevel;
  files: CodeFileInfo[];
  tree: CodeTreeNode[];
  file_count: number;
  total_size_bytes: number;
}

export interface CodeFileResponse extends CodeFileInfo {
  content: string;
}

export interface CodeAiChatRequest {
  question: string;
  session_id?: string | null;
  thinking_enabled?: boolean;
}

export interface CodeAiSource {
  fact_id: number;
  source_file_path: string;
  language: string;
  start_line: number;
  end_line: number;
  title: string;
  snippet: string;
  score: number | null;
}

export interface CodeAiChatResponse {
  session_id: string;
  user_message_id: number;
  assistant_message_id: number;
  answer: string;
  sources: CodeAiSource[];
}

export interface CodeAiSessionSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface CodeAiMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  thinking_enabled: boolean;
  thinking_content: string;
  input_token_count: number;
  output_token_count: number;
  is_stopped: boolean;
  retrieved_fact_ids: number[];
  sources: CodeAiSource[];
  created_at: string;
}

export interface CodeAiSessionDetail extends CodeAiSessionSummary {
  messages: CodeAiMessage[];
}

export type DatabaseAiStreamEvent =
  | {
      event: "session";
      data: {
        session_id: string;
        user_message_id: number;
        thinking_enabled: boolean;
        stream_id: string;
      };
    }
  | {
      event: "sources";
      data: {
        sources: DatabaseAiSource[];
      };
    }
  | {
      event: "thinking_delta";
      data: {
        delta: string;
      };
    }
  | {
      event: "content_delta";
      data: {
        delta: string;
      };
    }
  | {
      event: "done";
      data: {
        session_id: string;
        assistant_message_id: number;
        thinking_enabled: boolean;
        input_token_count: number;
        output_token_count: number;
        sources: DatabaseAiSource[];
      };
    }
  | {
      event: "interrupted";
      data: {
        session_id: string;
        assistant_message_id: number;
      };
    }
  | {
      event: "error";
      data: {
        message: string;
      };
    };

export type CodeAiStreamEvent =
  | {
      event: "session";
      data: {
        session_id: string;
        user_message_id: number;
        thinking_enabled: boolean;
        stream_id: string;
      };
    }
  | {
      event: "sources";
      data: {
        sources: CodeAiSource[];
      };
    }
  | {
      event: "thinking_delta";
      data: {
        delta: string;
      };
    }
  | {
      event: "content_delta";
      data: {
        delta: string;
      };
    }
  | {
      event: "done";
      data: {
        session_id: string;
        assistant_message_id: number;
        thinking_enabled: boolean;
        input_token_count: number;
        output_token_count: number;
        sources: CodeAiSource[];
      };
    }
  | {
      event: "interrupted";
      data: {
        session_id: string;
        assistant_message_id: number;
      };
    }
  | {
      event: "error";
      data: {
        message: string;
      };
    };

export interface RegisterRequest {
  username: string;
  nickname: string;
  password: string;
  bio: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface CreatePostRequest {
  title: string;
  content: string;
  category: PostCategory;
  tags: string[];
  poll: PollCreateRequest | null;
}

export interface PollCreateRequest {
  question: string;
  allow_multiple: boolean;
  expires_at: string | null;
  options: string[];
}

export interface CreateCommentRequest {
  content: string;
  parent_comment_id: number | null;
}

export interface DatabaseAiStopRequest {
  stream_id: string;
}

export interface CodeAiStopRequest {
  stream_id: string;
}
