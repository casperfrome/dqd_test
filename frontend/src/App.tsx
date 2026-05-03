import {
  Activity,
  BarChart3,
  Bell,
  Check,
  ChevronRight,
  CircleUserRound,
  Code2,
  Database,
  Eye,
  File,
  FileCode,
  Flag,
  Folder,
  FolderOpen,
  Lock,
  LogIn,
  LogOut,
  MessageCircle,
  Pin,
  Plus,
  RefreshCw,
  Search,
  Send,
  Shield,
  Sparkles,
  Square,
  ThumbsDown,
  ThumbsUp,
  Unlock,
  Users,
  Vote,
  X,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ApiError,
  api,
  clearStoredToken,
  getStoredToken,
  setStoredToken,
} from "./api/client";
import type {
  AnalyticsResponse,
  CodeAiMessage,
  CodeAiSessionSummary,
  CodeAiSource,
  CodeCatalogResponse,
  CodeFileResponse,
  CodeTreeNode,
  CommentResponse,
  CreatePostRequest,
  DatabaseAccessLevel,
  DatabaseAiHealthResponse,
  DatabaseAiMessage,
  DatabaseAiSessionSummary,
  DatabaseAiSource,
  DatabaseCatalogResponse,
  DatabaseInfo,
  DatabaseTable,
  FanCircleDetail,
  FanCircleSummary,
  PostCategory,
  PostDetail,
  PostSummary,
  UserBrief,
  UserProfile,
} from "./api/types";

type ViewKey = "circles" | "profile" | "analytics" | "admin" | "databases" | "code";
type AuthMode = "login" | "register";
type NoticeKind = "success" | "error" | "info";

interface Notice {
  kind: NoticeKind;
  text: string;
}

const categoryLabels: Record<PostCategory, string> = {
  discussion: "讨论",
  news: "新闻",
  transfer: "转会",
  match: "比赛",
  off_topic: "闲聊",
};

const categoryOptions = Object.keys(categoryLabels) as PostCategory[];

const roleLabels: Record<string, string> = {
  super_admin: "超级管理员",
  fan_circle_owner: "圈主",
  normal_user: "普通用户",
};

const databaseAccessLabels: Record<DatabaseAccessLevel, string> = {
  public: "公开访问",
  authenticated: "登录用户",
  super_admin: "超级管理员",
};

const aiFactTypeLabels: Record<string, string> = {
  database: "数据库",
  table: "表",
  column: "字段",
  index: "索引",
  foreign_key: "外键",
  sample_rows: "样例",
};

function getErrorMessage(error: unknown) {
  if (error instanceof ApiError || error instanceof Error) {
    return error.message;
  }
  return "操作失败";
}

function staticUrl(path: string) {
  return path.startsWith("http") ? path : path;
}

function formatDate(value: string) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function summarize(content: string, maxLength = 96) {
  return content.length > maxLength ? `${content.slice(0, maxLength)}...` : content;
}

function formatFileSize(value: number) {
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function formatCellValue(value: unknown) {
  if (value === null || value === undefined) {
    return "NULL";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function App() {
  const [view, setView] = useState<ViewKey>("circles");
  const [circles, setCircles] = useState<FanCircleSummary[]>([]);
  const [circleTotal, setCircleTotal] = useState(0);
  const [selectedCircleId, setSelectedCircleId] = useState<number | null>(null);
  const [selectedCircle, setSelectedCircle] = useState<FanCircleDetail | null>(null);
  const [posts, setPosts] = useState<PostSummary[]>([]);
  const [postTotal, setPostTotal] = useState(0);
  const [selectedPostId, setSelectedPostId] = useState<number | null>(null);
  const [selectedPost, setSelectedPost] = useState<PostDetail | null>(null);
  const [comments, setComments] = useState<CommentResponse[]>([]);
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [profileUser, setProfileUser] = useState<UserProfile | null>(null);
  const [followers, setFollowers] = useState<UserBrief[]>([]);
  const [following, setFollowing] = useState<UserBrief[]>([]);
  const [circleAnalytics, setCircleAnalytics] = useState<AnalyticsResponse | null>(null);
  const [postAnalytics, setPostAnalytics] = useState<AnalyticsResponse | null>(null);
  const [userAnalytics, setUserAnalytics] = useState<AnalyticsResponse | null>(null);
  const [databaseCatalog, setDatabaseCatalog] = useState<DatabaseCatalogResponse | null>(null);
  const [selectedDatabasePath, setSelectedDatabasePath] = useState<string | null>(null);
  const [selectedTableName, setSelectedTableName] = useState<string | null>(null);
  const [authOpen, setAuthOpen] = useState(false);
  const [authMode, setAuthMode] = useState<AuthMode>("login");
  const [notice, setNotice] = useState<Notice | null>(null);
  const [busy, setBusy] = useState(false);

  const selectedCirclePosts = useMemo(
    () => [...posts].sort((a, b) => Number(b.is_pinned) - Number(a.is_pinned)),
    [posts],
  );

  const selectedDatabase = useMemo(() => {
    if (!databaseCatalog?.databases.length) {
      return null;
    }
    return (
      databaseCatalog.databases.find((database) => database.path === selectedDatabasePath) ??
      databaseCatalog.databases[0]
    );
  }, [databaseCatalog, selectedDatabasePath]);

  const selectedTable = useMemo(() => {
    if (!selectedDatabase?.tables.length) {
      return null;
    }
    return (
      selectedDatabase.tables.find((table) => table.name === selectedTableName) ??
      selectedDatabase.tables[0]
    );
  }, [selectedDatabase, selectedTableName]);

  const canModerateSelectedPost =
    !!currentUser &&
    !!selectedPost &&
    (currentUser.role === "super_admin" ||
      (currentUser.role === "fan_circle_owner" &&
        selectedCircle?.owner?.id === currentUser.id));

  const showNotice = (kind: NoticeKind, text: string) => {
    setNotice({ kind, text });
  };

  const openAuth = (mode: AuthMode = "login") => {
    setAuthMode(mode);
    setAuthOpen(true);
  };

  const requireLogin = () => {
    if (currentUser) {
      return true;
    }
    openAuth("login");
    showNotice("info", "请先登录后再继续操作。");
    return false;
  };

  const refreshSession = async () => {
    if (!getStoredToken()) {
      return;
    }
    try {
      const user = await api.me();
      setCurrentUser(user);
      setProfileUser(user);
    } catch (error) {
      clearStoredToken();
      setCurrentUser(null);
      setProfileUser(null);
      showNotice("error", getErrorMessage(error));
    }
  };

  const loadCircles = async () => {
    setBusy(true);
    try {
      const response = await api.listFanCircles();
      setCircles(response.items);
      setCircleTotal(response.total);
      setSelectedCircleId((current) => current ?? response.items[0]?.id ?? null);
    } catch (error) {
      showNotice("error", getErrorMessage(error));
    } finally {
      setBusy(false);
    }
  };

  const loadCircle = async (circleId: number) => {
    try {
      const [circle, circlePosts, analytics] = await Promise.all([
        api.getFanCircle(circleId),
        api.getCirclePosts(circleId),
        api.getFanCircleAnalytics(circleId),
      ]);
      setSelectedCircle(circle);
      setPosts(circlePosts.items);
      setPostTotal(circlePosts.total);
      setCircleAnalytics(analytics);
      setSelectedPostId((current) => current ?? circlePosts.items[0]?.id ?? null);
    } catch (error) {
      showNotice("error", getErrorMessage(error));
    }
  };

  const loadPost = async (postId: number) => {
    try {
      const [post, commentPage, analytics] = await Promise.all([
        api.getPost(postId),
        api.listComments(postId),
        api.getPostAnalytics(postId),
      ]);
      setSelectedPost(post);
      setComments(commentPage.items);
      setPostAnalytics(analytics);
    } catch (error) {
      showNotice("error", getErrorMessage(error));
    }
  };

  const loadProfile = async (userId: number) => {
    try {
      const [user, followerPage, followingPage] = await Promise.all([
        api.getUser(userId),
        api.listFollowers(userId),
        api.listFollowing(userId),
      ]);
      setProfileUser(user);
      setFollowers(followerPage.items);
      setFollowing(followingPage.items);
    } catch (error) {
      showNotice("error", getErrorMessage(error));
    }
  };

  const loadUserAnalytics = async (userId: number) => {
    try {
      setUserAnalytics(await api.getUserAnalytics(userId));
    } catch (error) {
      setUserAnalytics(null);
      showNotice("error", getErrorMessage(error));
    }
  };

  const loadDatabases = async () => {
    setBusy(true);
    try {
      const response = await api.listDatabases();
      setDatabaseCatalog(response);
      const nextDatabase =
        response.databases.find((database) => database.path === selectedDatabasePath) ??
        response.databases[0] ??
        null;
      setSelectedDatabasePath(nextDatabase?.path ?? null);
      const nextTable =
        nextDatabase?.tables.find((table) => table.name === selectedTableName) ??
        nextDatabase?.tables[0] ??
        null;
      setSelectedTableName(nextTable?.name ?? null);
    } catch (error) {
      setDatabaseCatalog(null);
      showNotice("error", getErrorMessage(error));
    } finally {
      setBusy(false);
    }
  };

  const updateDatabaseAccess = async (accessLevel: DatabaseAccessLevel) => {
    try {
      await api.updateDatabaseAccess({ access_level: accessLevel });
      await loadDatabases();
      showNotice("success", "数据库板块访问权限已更新。");
    } catch (error) {
      showNotice("error", getErrorMessage(error));
    }
  };

  const reloadAll = async () => {
    await loadCircles();
    if (selectedCircleId) {
      await loadCircle(selectedCircleId);
    }
    if (selectedPostId) {
      await loadPost(selectedPostId);
    }
    if (currentUser) {
      await loadProfile(currentUser.id);
    }
    if (view === "databases") {
      await loadDatabases();
    }
  };

  useEffect(() => {
    void refreshSession();
    void loadCircles();
  }, []);

  useEffect(() => {
    if (selectedCircleId) {
      void loadCircle(selectedCircleId);
    }
  }, [selectedCircleId]);

  useEffect(() => {
    if (selectedPostId) {
      void loadPost(selectedPostId);
    }
  }, [selectedPostId]);

  useEffect(() => {
    if (currentUser) {
      void loadProfile(currentUser.id);
      void loadUserAnalytics(currentUser.id);
    } else {
      setUserAnalytics(null);
      setFollowers([]);
      setFollowing([]);
    }
  }, [currentUser]);

  useEffect(() => {
    if (view === "databases") {
      void loadDatabases();
    }
  }, [view]);

  const handleLoginSuccess = async (token: string) => {
    setStoredToken(token);
    const user = await api.me();
    setCurrentUser(user);
    setProfileUser(user);
    setAuthOpen(false);
    showNotice("success", `欢迎回来，${user.nickname}`);
  };

  const logout = () => {
    clearStoredToken();
    setCurrentUser(null);
    setProfileUser(null);
    setFollowers([]);
    setFollowing([]);
    showNotice("info", "已退出登录。");
  };

  const createPost = async (payload: CreatePostRequest) => {
    if (!selectedCircleId || !requireLogin()) {
      return;
    }
    try {
      const post = await api.createPost(selectedCircleId, payload);
      setSelectedPostId(post.id);
      await loadCircle(selectedCircleId);
      showNotice("success", "帖子已发布。");
    } catch (error) {
      showNotice("error", getErrorMessage(error));
    }
  };

  const reactToPost = async (action: "like" | "dislike") => {
    if (!selectedPost || !requireLogin()) {
      return;
    }
    try {
      const post =
        action === "like"
          ? await api.likePost(selectedPost.id)
          : await api.dislikePost(selectedPost.id);
      setSelectedPost(post);
      setPosts((items) => items.map((item) => (item.id === post.id ? post : item)));
      showNotice("success", action === "like" ? "已点赞。" : "已点踩。");
    } catch (error) {
      showNotice("error", getErrorMessage(error));
    }
  };

  const votePost = async (optionIds: number[]) => {
    if (!selectedPost || !requireLogin()) {
      return;
    }
    try {
      setSelectedPost(await api.votePost(selectedPost.id, optionIds));
      showNotice("success", "投票已提交。");
    } catch (error) {
      showNotice("error", getErrorMessage(error));
    }
  };

  const createComment = async (content: string, parentCommentId: number | null = null) => {
    if (!selectedPost || !requireLogin()) {
      return;
    }
    try {
      if (parentCommentId) {
        await api.replyComment(parentCommentId, {
          content,
          parent_comment_id: null,
        });
      } else {
        await api.createComment(selectedPost.id, {
          content,
          parent_comment_id: null,
        });
      }
      await loadPost(selectedPost.id);
      showNotice("success", parentCommentId ? "回复已发布。" : "评论已发布。");
    } catch (error) {
      showNotice("error", getErrorMessage(error));
    }
  };

  const reactToComment = async (commentId: number, action: "like" | "dislike") => {
    if (!requireLogin()) {
      return;
    }
    try {
      const updated =
        action === "like"
          ? await api.likeComment(commentId)
          : await api.dislikeComment(commentId);
      setComments((items) => items.map((item) => (item.id === commentId ? updated : item)));
      showNotice("success", action === "like" ? "已点赞评论。" : "已点踩评论。");
    } catch (error) {
      showNotice("error", getErrorMessage(error));
    }
  };

  const followProfile = async (shouldFollow: boolean) => {
    if (!profileUser || !requireLogin()) {
      return;
    }
    try {
      if (shouldFollow) {
        await api.followUser(profileUser.id);
      } else {
        await api.unfollowUser(profileUser.id);
      }
      await loadProfile(profileUser.id);
      showNotice("success", shouldFollow ? "已关注用户。" : "已取消关注。");
    } catch (error) {
      showNotice("error", getErrorMessage(error));
    }
  };

  const setPostFlag = async (flag: "pin" | "lock", value: boolean) => {
    if (!selectedPost || !requireLogin()) {
      return;
    }
    try {
      const post =
        flag === "pin"
          ? await api.setPostPinned(selectedPost.id, value)
          : await api.setPostLocked(selectedPost.id, value);
      setSelectedPost(post);
      setPosts((items) => items.map((item) => (item.id === post.id ? post : item)));
      showNotice("success", flag === "pin" ? "置顶状态已更新。" : "锁定状态已更新。");
    } catch (error) {
      showNotice("error", getErrorMessage(error));
    }
  };

  const assignOwner = async (circleId: number, ownerUserId: number) => {
    if (!requireLogin()) {
      return;
    }
    try {
      await api.assignCircleOwner(circleId, ownerUserId);
      await loadCircles();
      if (selectedCircleId === circleId) {
        await loadCircle(circleId);
      }
      showNotice("success", "圈主已分配。");
    } catch (error) {
      showNotice("error", getErrorMessage(error));
    }
  };

  const deactivateUser = async (userId: number) => {
    if (!requireLogin()) {
      return;
    }
    try {
      await api.deactivateUser(userId);
      showNotice("success", "用户已停用。");
    } catch (error) {
      showNotice("error", getErrorMessage(error));
    }
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Flag size={24} />
          </div>
          <div>
            <strong>FootballDomain</strong>
            <span>球迷社区控制台</span>
          </div>
        </div>

        <nav className="nav">
          <NavButton icon={<Users size={18} />} active={view === "circles"} onClick={() => setView("circles")}>
            球迷圈
          </NavButton>
          <NavButton icon={<CircleUserRound size={18} />} active={view === "profile"} onClick={() => setView("profile")}>
            我的资料
          </NavButton>
          <NavButton icon={<BarChart3 size={18} />} active={view === "analytics"} onClick={() => setView("analytics")}>
            分析
          </NavButton>
          <NavButton icon={<Shield size={18} />} active={view === "admin"} onClick={() => setView("admin")}>
            管理
          </NavButton>
          <NavButton icon={<Database size={18} />} active={view === "databases"} onClick={() => setView("databases")}>
            数据库
          </NavButton>
          <NavButton icon={<Code2 size={18} />} active={view === "code"} onClick={() => setView("code")}>
            代码问答
          </NavButton>
        </nav>

        <div className="sidebar-footer">
          {currentUser ? (
            <UserBadge user={currentUser} onOpenProfile={() => setView("profile")} />
          ) : (
            <button className="primary full" onClick={() => openAuth("login")}>
              <LogIn size={18} />
              登录 / 注册
            </button>
          )}
          {currentUser && (
            <button className="ghost full" onClick={logout}>
              <LogOut size={18} />
              退出登录
            </button>
          )}
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <p className="eyebrow">专业社区</p>
            <h1>{viewTitle(view)}</h1>
          </div>
          <div className="topbar-actions">
            <button className="ghost" onClick={() => void reloadAll()} disabled={busy}>
              <RefreshCw size={17} />
              刷新
            </button>
            <button className="icon-button" title="通知">
              <Bell size={18} />
            </button>
          </div>
        </header>

        {notice && (
          <div className={`notice ${notice.kind}`}>
            <span>{notice.text}</span>
            <button onClick={() => setNotice(null)} aria-label="关闭提示">
              <X size={16} />
            </button>
          </div>
        )}

        {view === "circles" && (
          <CirclesView
            circles={circles}
            circleTotal={circleTotal}
            selectedCircle={selectedCircle}
            selectedCircleId={selectedCircleId}
            posts={selectedCirclePosts}
            postTotal={postTotal}
            selectedPost={selectedPost}
            comments={comments}
            currentUser={currentUser}
            canModerateSelectedPost={canModerateSelectedPost}
            onSelectCircle={(circleId) => {
              setSelectedCircleId(circleId);
              setSelectedPostId(null);
              setSelectedPost(null);
              setComments([]);
            }}
            onSelectPost={setSelectedPostId}
            onCreatePost={createPost}
            onReactPost={reactToPost}
            onVote={votePost}
            onCreateComment={createComment}
            onReactComment={reactToComment}
            onOpenAuth={openAuth}
            onOpenProfile={(userId) => {
              void loadProfile(userId);
              setView("profile");
            }}
            onSetPostFlag={setPostFlag}
          />
        )}

        {view === "profile" && (
          <ProfileView
            currentUser={currentUser}
            profileUser={profileUser}
            followers={followers}
            following={following}
            onOpenAuth={openAuth}
            onLoadProfile={(userId) => void loadProfile(userId)}
            onFollow={followProfile}
          />
        )}

        {view === "analytics" && (
          <AnalyticsView
            currentUser={currentUser}
            selectedCircle={selectedCircle}
            selectedPost={selectedPost}
            userAnalytics={userAnalytics}
            circleAnalytics={circleAnalytics}
            postAnalytics={postAnalytics}
            onLoadUserAnalytics={(userId) => void loadUserAnalytics(userId)}
          />
        )}

        {view === "admin" && (
          <AdminView
            currentUser={currentUser}
            selectedCircle={selectedCircle}
            selectedPost={selectedPost}
            canModerateSelectedPost={canModerateSelectedPost}
            onOpenAuth={openAuth}
            onAssignOwner={assignOwner}
            onDeactivateUser={deactivateUser}
            onSetPostFlag={setPostFlag}
          />
        )}

        {view === "databases" && (
          <DatabasesView
            catalog={databaseCatalog}
            currentUser={currentUser}
            selectedDatabase={selectedDatabase}
            selectedTable={selectedTable}
            selectedDatabasePath={selectedDatabasePath}
            selectedTableName={selectedTableName}
            onSelectDatabase={(path) => {
              const database = databaseCatalog?.databases.find((item) => item.path === path) ?? null;
              setSelectedDatabasePath(path);
              setSelectedTableName(database?.tables[0]?.name ?? null);
            }}
            onSelectTable={setSelectedTableName}
            onRefresh={loadDatabases}
            onUpdateAccess={updateDatabaseAccess}
          />
        )}

        {view === "code" && <CodeQaView currentUser={currentUser} />}
      </main>

      {authOpen && (
        <AuthDialog
          mode={authMode}
          onModeChange={setAuthMode}
          onClose={() => setAuthOpen(false)}
          onLoginSuccess={handleLoginSuccess}
          onNotice={showNotice}
        />
      )}
    </div>
  );
}

function viewTitle(view: ViewKey) {
  const titles: Record<ViewKey, string> = {
    circles: "球迷圈总览",
    profile: "用户资料",
    analytics: "社区分析",
    admin: "权限管理",
    databases: "数据库",
    code: "代码问答",
  };
  return titles[view];
}

function NavButton({
  active,
  icon,
  children,
  onClick,
}: {
  active: boolean;
  icon: React.ReactNode;
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button className={`nav-item ${active ? "active" : ""}`} onClick={onClick}>
      {icon}
      {children}
    </button>
  );
}

function UserBadge({ user, onOpenProfile }: { user: UserProfile; onOpenProfile: () => void }) {
  return (
    <button className="user-badge" onClick={onOpenProfile}>
      <img src={staticUrl(user.avatar_url)} alt="" />
      <span>
        <strong>{user.nickname}</strong>
        <small>{roleLabels[user.role]}</small>
      </span>
    </button>
  );
}

function CirclesView({
  circles,
  circleTotal,
  selectedCircle,
  selectedCircleId,
  posts,
  postTotal,
  selectedPost,
  comments,
  currentUser,
  canModerateSelectedPost,
  onSelectCircle,
  onSelectPost,
  onCreatePost,
  onReactPost,
  onVote,
  onCreateComment,
  onReactComment,
  onOpenAuth,
  onOpenProfile,
  onSetPostFlag,
}: {
  circles: FanCircleSummary[];
  circleTotal: number;
  selectedCircle: FanCircleDetail | null;
  selectedCircleId: number | null;
  posts: PostSummary[];
  postTotal: number;
  selectedPost: PostDetail | null;
  comments: CommentResponse[];
  currentUser: UserProfile | null;
  canModerateSelectedPost: boolean;
  onSelectCircle: (circleId: number) => void;
  onSelectPost: (postId: number) => void;
  onCreatePost: (payload: CreatePostRequest) => Promise<void>;
  onReactPost: (action: "like" | "dislike") => Promise<void>;
  onVote: (optionIds: number[]) => Promise<void>;
  onCreateComment: (content: string, parentCommentId?: number | null) => Promise<void>;
  onReactComment: (commentId: number, action: "like" | "dislike") => Promise<void>;
  onOpenAuth: (mode?: AuthMode) => void;
  onOpenProfile: (userId: number) => void;
  onSetPostFlag: (flag: "pin" | "lock", value: boolean) => Promise<void>;
}) {
  return (
    <section className="workspace-grid">
      <div className="panel circles-panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Fan Circles</p>
            <h2>俱乐部看板</h2>
          </div>
          <span className="metric-pill">{circleTotal} 个圈子</span>
        </div>
        <div className="circle-list">
          {circles.map((circle) => (
            <button
              className={`circle-row ${selectedCircleId === circle.id ? "active" : ""}`}
              key={circle.id}
              onClick={() => onSelectCircle(circle.id)}
            >
              <img src={staticUrl(circle.logo_url)} alt="" />
              <span>
                <strong>{circle.club_name}</strong>
                <small>{circle.league_name}</small>
              </span>
              <ChevronRight size={16} />
            </button>
          ))}
          {circles.length === 0 && <EmptyState text="暂无球迷圈数据。" />}
        </div>
      </div>

      <div className="panel feed-panel">
        {selectedCircle ? (
          <>
            <CircleHero circle={selectedCircle} />
            <CreatePostBox currentUser={currentUser} onOpenAuth={onOpenAuth} onCreatePost={onCreatePost} />
            <div className="section-title">
              <h2>圈内帖子</h2>
              <span>{postTotal} 条</span>
            </div>
            <div className="post-list">
              {posts.map((post) => (
                <PostListItem
                  key={post.id}
                  post={post}
                  active={selectedPost?.id === post.id}
                  onSelect={() => onSelectPost(post.id)}
                  onOpenProfile={onOpenProfile}
                />
              ))}
              {posts.length === 0 && <EmptyState text="还没有帖子，登录后发布第一条讨论。" />}
            </div>
          </>
        ) : (
          <EmptyState text="请选择一个球迷圈。" />
        )}
      </div>

      <div className="panel detail-panel">
        {selectedPost ? (
          <PostDetailPanel
            post={selectedPost}
            comments={comments}
            canModerate={canModerateSelectedPost}
            onReactPost={onReactPost}
            onVote={onVote}
            onCreateComment={onCreateComment}
            onReactComment={onReactComment}
            onOpenProfile={onOpenProfile}
            onSetPostFlag={onSetPostFlag}
          />
        ) : (
          <EmptyState text="从左侧选择帖子查看详情、评论和投票。" />
        )}
      </div>
    </section>
  );
}

function CircleHero({ circle }: { circle: FanCircleDetail }) {
  return (
    <div className="circle-hero">
      <img src={staticUrl(circle.logo_url)} alt="" />
      <div>
        <p className="eyebrow">{circle.league_name}</p>
        <h2>{circle.board_name}</h2>
        <p>{circle.description}</p>
        <div className="stats-row">
          <span>{circle.post_count} 帖子</span>
          <span>{circle.follower_count} 关注</span>
          <span>圈主：{circle.owner?.nickname ?? "待分配"}</span>
        </div>
      </div>
    </div>
  );
}

function CreatePostBox({
  currentUser,
  onOpenAuth,
  onCreatePost,
}: {
  currentUser: UserProfile | null;
  onOpenAuth: (mode?: AuthMode) => void;
  onCreatePost: (payload: CreatePostRequest) => Promise<void>;
}) {
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

function PostListItem({
  post,
  active,
  onSelect,
  onOpenProfile,
}: {
  post: PostSummary;
  active: boolean;
  onSelect: () => void;
  onOpenProfile: (userId: number) => void;
}) {
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
        <img src={staticUrl(post.author.avatar_url)} alt="" />
        {post.author.nickname}
      </button>
    </article>
  );
}

function PostDetailPanel({
  post,
  comments,
  canModerate,
  onReactPost,
  onVote,
  onCreateComment,
  onReactComment,
  onOpenProfile,
  onSetPostFlag,
}: {
  post: PostDetail;
  comments: CommentResponse[];
  canModerate: boolean;
  onReactPost: (action: "like" | "dislike") => Promise<void>;
  onVote: (optionIds: number[]) => Promise<void>;
  onCreateComment: (content: string, parentCommentId?: number | null) => Promise<void>;
  onReactComment: (commentId: number, action: "like" | "dislike") => Promise<void>;
  onOpenProfile: (userId: number) => void;
  onSetPostFlag: (flag: "pin" | "lock", value: boolean) => Promise<void>;
}) {
  return (
    <article className="post-detail">
      <div className="post-detail-head">
        <div className="post-meta">
          <span>{post.club_name}</span>
          <span>{categoryLabels[post.category]}</span>
          <span>{formatDate(post.created_at)}</span>
        </div>
        <h2>{post.title}</h2>
        <button className="author-link" onClick={() => onOpenProfile(post.author.id)}>
          <img src={staticUrl(post.author.avatar_url)} alt="" />
          {post.author.nickname}
        </button>
      </div>

      <p className="post-content">{post.content}</p>

      <div className="tag-row">
        {post.tags.map((tag) => (
          <span key={tag}>#{tag}</span>
        ))}
      </div>

      <div className="toolbar">
        <button className="ghost" onClick={() => void onReactPost("like")}>
          <ThumbsUp size={17} />
          {post.like_count}
        </button>
        <button className="ghost" onClick={() => void onReactPost("dislike")}>
          <ThumbsDown size={17} />
          {post.dislike_count}
        </button>
        {canModerate && (
          <>
            <button className="ghost" onClick={() => void onSetPostFlag("pin", !post.is_pinned)}>
              <Pin size={17} />
              {post.is_pinned ? "取消置顶" : "置顶"}
            </button>
            <button className="ghost" onClick={() => void onSetPostFlag("lock", !post.is_locked)}>
              {post.is_locked ? <Unlock size={17} /> : <Lock size={17} />}
              {post.is_locked ? "解锁" : "锁定"}
            </button>
          </>
        )}
      </div>

      {post.poll && <PollBox post={post} onVote={onVote} />}

      <CommentComposer locked={post.is_locked} onSubmit={(content) => onCreateComment(content)} />

      <div className="comments">
        <div className="section-title">
          <h3>评论</h3>
          <span>{comments.length} 条</span>
        </div>
        {comments.map((comment) => (
          <CommentItem
            key={comment.id}
            comment={comment}
            onCreateComment={onCreateComment}
            onReactComment={onReactComment}
            onOpenProfile={onOpenProfile}
          />
        ))}
        {comments.length === 0 && <EmptyState text="暂无评论。" />}
      </div>
    </article>
  );
}

function PollBox({ post, onVote }: { post: PostDetail; onVote: (optionIds: number[]) => Promise<void> }) {
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

function CommentComposer({
  locked,
  onSubmit,
}: {
  locked?: boolean;
  onSubmit: (content: string) => Promise<void>;
}) {
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
        placeholder={locked ? "帖子已锁定，不能继续评论。" : "写下你的观点"}
      />
      <button className="primary" type="submit" disabled={locked || !content.trim()}>
        <MessageCircle size={17} />
        评论
      </button>
    </form>
  );
}

function CommentItem({
  comment,
  onCreateComment,
  onReactComment,
  onOpenProfile,
}: {
  comment: CommentResponse;
  onCreateComment: (content: string, parentCommentId?: number | null) => Promise<void>;
  onReactComment: (commentId: number, action: "like" | "dislike") => Promise<void>;
  onOpenProfile: (userId: number) => void;
}) {
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
        <img src={staticUrl(comment.author.avatar_url)} alt="" />
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
      </div>
      {replying && (
        <form className="reply-form" onSubmit={(event) => void submitReply(event)}>
          <input value={reply} onChange={(event) => setReply(event.target.value)} placeholder="回复内容" />
          <button className="primary" type="submit">
            发送
          </button>
        </form>
      )}
    </div>
  );
}

function ProfileView({
  currentUser,
  profileUser,
  followers,
  following,
  onOpenAuth,
  onLoadProfile,
  onFollow,
}: {
  currentUser: UserProfile | null;
  profileUser: UserProfile | null;
  followers: UserBrief[];
  following: UserBrief[];
  onOpenAuth: (mode?: AuthMode) => void;
  onLoadProfile: (userId: number) => void;
  onFollow: (shouldFollow: boolean) => Promise<void>;
}) {
  const [lookup, setLookup] = useState("");

  if (!currentUser && !profileUser) {
    return (
      <section className="single-panel">
        <EmptyState text="登录后查看个人资料、粉丝和关注列表。" />
        <button className="primary" onClick={() => onOpenAuth("login")}>
          <LogIn size={17} />
          登录
        </button>
      </section>
    );
  }

  return (
    <section className="profile-grid">
      <div className="panel profile-card">
        <form
          className="lookup"
          onSubmit={(event) => {
            event.preventDefault();
            const id = Number(lookup);
            if (Number.isFinite(id) && id > 0) {
              onLoadProfile(id);
            }
          }}
        >
          <Search size={17} />
          <input value={lookup} onChange={(event) => setLookup(event.target.value)} placeholder="输入用户 ID 查看资料" />
          <button className="ghost">查看</button>
        </form>

        {profileUser && (
          <>
            <div className="profile-head">
              <img src={staticUrl(profileUser.avatar_url)} alt="" />
              <div>
                <p className="eyebrow">{roleLabels[profileUser.role]}</p>
                <h2>{profileUser.nickname}</h2>
                <span>@{profileUser.username}</span>
              </div>
            </div>
            <p className="bio">{profileUser.bio || "这个用户还没有填写简介。"}</p>
            <div className="metric-grid">
              <Metric label="关注" value={profileUser.following_count} />
              <Metric label="粉丝" value={profileUser.followers_count} />
              <Metric label="获赞" value={profileUser.total_likes_received} />
              <Metric label="点踩" value={profileUser.total_dislikes_received} />
            </div>
            {currentUser && currentUser.id !== profileUser.id && (
              <div className="toolbar">
                <button className="primary" onClick={() => void onFollow(true)}>
                  <Plus size={17} />
                  关注
                </button>
                <button className="ghost" onClick={() => void onFollow(false)}>
                  取消关注
                </button>
              </div>
            )}
          </>
        )}
      </div>

      <UserList title="粉丝" users={followers} onLoadProfile={onLoadProfile} />
      <UserList title="正在关注" users={following} onLoadProfile={onLoadProfile} />
    </section>
  );
}

function Metric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="metric">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function UserList({
  title,
  users,
  onLoadProfile,
}: {
  title: string;
  users: UserBrief[];
  onLoadProfile: (userId: number) => void;
}) {
  return (
    <div className="panel user-list">
      <div className="section-title">
        <h2>{title}</h2>
        <span>{users.length}</span>
      </div>
      {users.map((user) => (
        <button key={user.id} className="user-row" onClick={() => onLoadProfile(user.id)}>
          <img src={staticUrl(user.avatar_url)} alt="" />
          <span>
            <strong>{user.nickname}</strong>
            <small>@{user.username}</small>
          </span>
          <small>{roleLabels[user.role]}</small>
        </button>
      ))}
      {users.length === 0 && <EmptyState text="暂无数据。" />}
    </div>
  );
}

function AnalyticsView({
  currentUser,
  selectedCircle,
  selectedPost,
  userAnalytics,
  circleAnalytics,
  postAnalytics,
  onLoadUserAnalytics,
}: {
  currentUser: UserProfile | null;
  selectedCircle: FanCircleDetail | null;
  selectedPost: PostDetail | null;
  userAnalytics: AnalyticsResponse | null;
  circleAnalytics: AnalyticsResponse | null;
  postAnalytics: AnalyticsResponse | null;
  onLoadUserAnalytics: (userId: number) => void;
}) {
  const [userId, setUserId] = useState("");

  return (
    <section className="analytics-grid">
      <div className="panel">
        <div className="section-title">
          <h2>用户分析</h2>
          <span>{currentUser ? currentUser.nickname : "需登录"}</span>
        </div>
        <form
          className="lookup"
          onSubmit={(event) => {
            event.preventDefault();
            const id = Number(userId || currentUser?.id);
            if (Number.isFinite(id) && id > 0) {
              onLoadUserAnalytics(id);
            }
          }}
        >
          <Activity size={17} />
          <input value={userId} onChange={(event) => setUserId(event.target.value)} placeholder="用户 ID，默认当前用户" />
          <button className="ghost">加载</button>
        </form>
        <AnalyticsCard analytics={userAnalytics} emptyText="当前没有可展示的用户分析，或你没有权限查看。" />
      </div>

      <div className="panel">
        <div className="section-title">
          <h2>圈子分析</h2>
          <span>{selectedCircle?.club_name ?? "未选择"}</span>
        </div>
        <AnalyticsCard analytics={circleAnalytics} emptyText="选择球迷圈后显示圈子分析。" />
      </div>

      <div className="panel">
        <div className="section-title">
          <h2>帖子分析</h2>
          <span>{selectedPost ? `#${selectedPost.id}` : "未选择"}</span>
        </div>
        <AnalyticsCard analytics={postAnalytics} emptyText="选择帖子后显示互动分析。" />
      </div>
    </section>
  );
}

function AnalyticsCard({ analytics, emptyText }: { analytics: AnalyticsResponse | null; emptyText: string }) {
  if (!analytics) {
    return <EmptyState text={emptyText} />;
  }
  return (
    <div className="analytics-card">
      <div className="summary-grid">
        {Object.entries(analytics.summary).map(([key, value]) => (
          <div className="metric" key={key}>
            <strong>{String(value)}</strong>
            <span>{key}</span>
          </div>
        ))}
      </div>
      <div className="event-list">
        {analytics.recent_events.map((event) => (
          <div className="event-row" key={event.id}>
            <span>{event.event_type}</span>
            <small>{formatDate(event.created_at)}</small>
            <code>{JSON.stringify(event.metadata)}</code>
          </div>
        ))}
      </div>
    </div>
  );
}

function CodeQaView({ currentUser }: { currentUser: UserProfile | null }) {
  const [catalog, setCatalog] = useState<CodeCatalogResponse | null>(null);
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<CodeFileResponse | null>(null);
  const [filter, setFilter] = useState("");
  const [loadingCatalog, setLoadingCatalog] = useState(false);
  const [loadingFile, setLoadingFile] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [focusLine, setFocusLine] = useState<number | null>(null);

  const filteredFiles = useMemo(() => {
    const keyword = filter.trim().toLowerCase();
    if (!keyword) {
      return catalog?.files ?? [];
    }
    return (catalog?.files ?? []).filter((file) => file.path.toLowerCase().includes(keyword));
  }, [catalog, filter]);

  const loadFile = async (path: string, line?: number) => {
    setLoadingFile(true);
    setError(null);
    try {
      const file = await api.getCodeFile(path);
      setSelectedFilePath(file.path);
      setSelectedFile(file);
      setFocusLine(line ?? null);
    } catch (loadError) {
      setError(getErrorMessage(loadError));
    } finally {
      setLoadingFile(false);
    }
  };

  const loadCatalog = async () => {
    setLoadingCatalog(true);
    setError(null);
    try {
      const response = await api.getCodeCatalog();
      setCatalog(response);
      const nextPath =
        response.files.find((file) => file.path === selectedFilePath)?.path ??
        response.files[0]?.path ??
        null;
      setSelectedFilePath(nextPath);
      if (nextPath) {
        await loadFile(nextPath);
      } else {
        setSelectedFile(null);
      }
    } catch (loadError) {
      setCatalog(null);
      setSelectedFile(null);
      setError(getErrorMessage(loadError));
    } finally {
      setLoadingCatalog(false);
    }
  };

  useEffect(() => {
    void loadCatalog();
  }, [currentUser?.id]);

  useEffect(() => {
    if (focusLine === null) {
      return;
    }
    window.requestAnimationFrame(() => {
      document.querySelector(`[data-code-line="${focusLine}"]`)?.scrollIntoView({
        block: "center",
      });
    });
  }, [selectedFile?.path, focusLine]);

  if (!catalog) {
    return (
      <section className="single-panel">
        <EmptyState text={loadingCatalog ? "正在加载项目代码..." : "暂无代码目录数据，或当前账号没有查看权限。"} />
        {error && <p className="muted">{error}</p>}
        <button className="primary" onClick={() => void loadCatalog()}>
          <RefreshCw size={17} />
          重新加载
        </button>
      </section>
    );
  }

  return (
    <section className="code-page">
      <CodeAiPanel
        currentUser={currentUser}
        onOpenSource={(source) => void loadFile(source.source_file_path, source.start_line)}
      />

      <div className="code-workspace panel">
        <div className="section-title">
          <div>
            <h2>项目代码</h2>
            <p className="muted">
              {catalog.file_count} 个文件 · {formatFileSize(catalog.total_size_bytes)} · 权限：
              {databaseAccessLabels[catalog.access_level]}
            </p>
          </div>
          <div className="toolbar">
            <button className="ghost" type="button" disabled={loadingCatalog} onClick={() => void loadCatalog()}>
              <RefreshCw size={17} />
              刷新代码
            </button>
          </div>
        </div>

        {error && <div className="ai-status error">{error}</div>}

        <div className="code-browser">
          <aside className="code-tree-panel">
            <label className="code-search">
              <Search size={16} />
              <input
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
                placeholder="搜索文件路径"
              />
            </label>
            {filter.trim() ? (
              <div className="code-file-results">
                {filteredFiles.map((file) => (
                  <button
                    key={file.path}
                    className={`code-file-row ${selectedFilePath === file.path ? "active" : ""}`}
                    onClick={() => void loadFile(file.path)}
                  >
                    <FileCode size={15} />
                    <span>{file.path}</span>
                  </button>
                ))}
                {filteredFiles.length === 0 && <EmptyState text="没有匹配的代码文件。" />}
              </div>
            ) : (
              <CodeFileTree
                nodes={catalog.tree}
                selectedPath={selectedFilePath}
                onSelect={(path) => void loadFile(path)}
              />
            )}
          </aside>

          <div className="code-editor-panel">
            <div className="code-tabbar">
              {selectedFile ? (
                <div className="code-tab active">
                  <FileCode size={15} />
                  <span>{selectedFile.path}</span>
                </div>
              ) : (
                <div className="code-tab">未选择文件</div>
              )}
              {selectedFile && (
                <span className="code-file-meta">
                  {selectedFile.language} · {selectedFile.line_count} 行 · {formatFileSize(selectedFile.size_bytes)}
                </span>
              )}
            </div>

            <div className="code-editor">
              {selectedFile ? (
                selectedFile.content.split(/\r?\n/).map((line, index) => {
                  const lineNumber = index + 1;
                  return (
                    <div
                      key={lineNumber}
                      className={`code-line ${focusLine === lineNumber ? "focused" : ""}`}
                      data-code-line={lineNumber}
                    >
                      <span className="code-line-number">{lineNumber}</span>
                      <code>{line || " "}</code>
                    </div>
                  );
                })
              ) : (
                <EmptyState text={loadingFile ? "正在加载代码..." : "请选择左侧文件查看内容。"} />
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function CodeFileTree({
  nodes,
  selectedPath,
  onSelect,
}: {
  nodes: CodeTreeNode[];
  selectedPath: string | null;
  onSelect: (path: string) => void;
}) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    setExpanded(new Set(nodes.filter((node) => node.type === "directory").map((node) => node.path)));
  }, [nodes]);

  const toggle = (path: string) => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  const renderNode = (node: CodeTreeNode, depth = 0): React.ReactNode => {
    if (node.type === "file") {
      return (
        <button
          key={node.path}
          className={`code-file-row ${selectedPath === node.path ? "active" : ""}`}
          style={{ paddingLeft: 10 + depth * 14 }}
          onClick={() => onSelect(node.path)}
        >
          <File size={15} />
          <span>{node.name}</span>
        </button>
      );
    }
    const isOpen = expanded.has(node.path);
    return (
      <div className="code-tree-group" key={node.path}>
        <button
          className="code-folder-row"
          style={{ paddingLeft: 10 + depth * 14 }}
          onClick={() => toggle(node.path)}
        >
          <ChevronRight size={14} className={isOpen ? "open" : ""} />
          {isOpen ? <FolderOpen size={15} /> : <Folder size={15} />}
          <span>{node.name}</span>
        </button>
        {isOpen && node.children.map((child) => renderNode(child, depth + 1))}
      </div>
    );
  };

  return <div className="code-tree">{nodes.map((node) => renderNode(node))}</div>;
}

function CodeAiPanel({
  currentUser,
  onOpenSource,
}: {
  currentUser: UserProfile | null;
  onOpenSource: (source: CodeAiSource) => void;
}) {
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
      setQuestion("");
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

function CodeSources({
  sources,
  onOpenSource,
}: {
  sources: CodeAiSource[];
  onOpenSource: (source: CodeAiSource) => void;
}) {
  return (
    <div className="code-sources">
      {sources.slice(0, 8).map((source) => (
        <button key={source.fact_id} type="button" onClick={() => onOpenSource(source)}>
          {source.source_file_path}:{source.start_line}-{source.end_line}
        </button>
      ))}
    </div>
  );
}

function DatabasesView({
  catalog,
  currentUser,
  selectedDatabase,
  selectedTable,
  selectedDatabasePath,
  selectedTableName,
  onSelectDatabase,
  onSelectTable,
  onRefresh,
  onUpdateAccess,
}: {
  catalog: DatabaseCatalogResponse | null;
  currentUser: UserProfile | null;
  selectedDatabase: DatabaseInfo | null;
  selectedTable: DatabaseTable | null;
  selectedDatabasePath: string | null;
  selectedTableName: string | null;
  onSelectDatabase: (path: string) => void;
  onSelectTable: (tableName: string) => void;
  onRefresh: () => Promise<void>;
  onUpdateAccess: (accessLevel: DatabaseAccessLevel) => Promise<void>;
}) {
  const [draftAccess, setDraftAccess] = useState<DatabaseAccessLevel>(catalog?.access_level ?? "public");
  const isSuperAdmin = currentUser?.role === "super_admin";
  const databaseCount = catalog?.databases.length ?? 0;
  const tableCount = catalog?.databases.reduce((total, database) => total + database.table_count, 0) ?? 0;

  useEffect(() => {
    setDraftAccess(catalog?.access_level ?? "public");
  }, [catalog?.access_level]);

  if (!catalog) {
    return (
      <section className="single-panel">
        <EmptyState text="暂无数据库目录数据，或当前账号没有查看权限。" />
        <button className="primary" onClick={() => void onRefresh()}>
          <RefreshCw size={17} />
          重新加载
        </button>
      </section>
    );
  }

  return (
    <section className="database-page">
      <div className="database-summary panel">
        <Metric label="数据库文件" value={databaseCount} />
        <Metric label="数据表" value={tableCount} />
        <Metric label="访问权限" value={databaseAccessLabels[catalog.access_level]} />
        {isSuperAdmin && (
          <form
            className="access-control"
            onSubmit={(event) => {
              event.preventDefault();
              void onUpdateAccess(draftAccess);
            }}
          >
            <label>
              板块权限
              <select value={draftAccess} onChange={(event) => setDraftAccess(event.target.value as DatabaseAccessLevel)}>
                <option value="public">公开访问</option>
                <option value="authenticated">登录用户</option>
                <option value="super_admin">超级管理员</option>
              </select>
            </label>
            <button className="primary" type="submit">
              <Check size={17} />
              保存权限
            </button>
          </form>
        )}
      </div>

      <div className="database-grid">
        <div className="panel database-list">
          <div className="section-title">
            <h2>数据库文件</h2>
            <span>{databaseCount}</span>
          </div>
          {catalog.databases.map((database) => (
            <button
              key={database.path}
              className={`database-row ${selectedDatabasePath === database.path ? "active" : ""}`}
              onClick={() => onSelectDatabase(database.path)}
            >
              <span>
                <strong>{database.name}</strong>
                <small>{database.path}</small>
              </span>
              <small>{formatFileSize(database.size_bytes)}</small>
            </button>
          ))}
          {catalog.databases.length === 0 && <EmptyState text="项目目录下没有可读取的 SQLite 数据库文件。" />}
        </div>

        <div className="panel table-list">
          <div className="section-title">
            <h2>数据表</h2>
            <span>{selectedDatabase?.table_count ?? 0}</span>
          </div>
          {selectedDatabase?.error && <p className="muted">{selectedDatabase.error}</p>}
          {selectedDatabase?.tables.map((table) => (
            <button
              key={table.name}
              className={`table-row ${selectedTableName === table.name ? "active" : ""}`}
              onClick={() => onSelectTable(table.name)}
            >
              <span>
                <strong>{table.name}</strong>
                <small>{table.comment}</small>
              </span>
              <small>{table.row_count} 行</small>
            </button>
          ))}
          {selectedDatabase && selectedDatabase.tables.length === 0 && <EmptyState text="当前数据库没有可展示的数据表。" />}
        </div>

        <div className="panel table-detail">
          {selectedTable ? (
            <>
              <div className="section-title">
                <div>
                  <h2>{selectedTable.name}</h2>
                  <p className="muted">{selectedTable.comment}</p>
                </div>
                <span>{selectedTable.row_count} 行</span>
              </div>

              <div className="schema-table-wrap">
                <table className="schema-table">
                  <thead>
                    <tr>
                      <th>字段</th>
                      <th>中文注释</th>
                      <th>类型</th>
                      <th>约束</th>
                      <th>默认值</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedTable.columns.map((column) => (
                      <tr key={column.name}>
                        <td>
                          <code>{column.name}</code>
                        </td>
                        <td>{column.comment}</td>
                        <td>{column.type || "-"}</td>
                        <td>
                          {[
                            column.primary_key ? "主键" : null,
                            column.not_null ? "非空" : null,
                          ]
                            .filter(Boolean)
                            .join(" / ") || "-"}
                        </td>
                        <td>{column.default_value ?? "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="section-title compact-title">
                <h3>随机示例数据</h3>
                <span>最多 5 条</span>
              </div>
              <SampleRowsTable table={selectedTable} />
            </>
          ) : (
            <EmptyState text="请选择一个数据表查看结构和示例数据。" />
          )}
        </div>
      </div>

      <DatabaseAiPanel currentUser={currentUser} />
    </section>
  );
}

function SampleRowsTable({ table }: { table: DatabaseTable }) {
  const columnNames = table.columns.map((column) => column.name);
  if (table.sample_rows.length === 0) {
    return <EmptyState text="当前表暂无示例数据。" />;
  }
  return (
    <div className="sample-table-wrap">
      <table className="sample-table">
        <thead>
          <tr>
            {columnNames.map((columnName) => (
              <th key={columnName}>{columnName}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.sample_rows.map((row, index) => (
            <tr key={index}>
              {columnNames.map((columnName) => (
                <td key={columnName}>{formatCellValue(row[columnName])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DatabaseAiPanel({ currentUser }: { currentUser: UserProfile | null }) {
  const [sessions, setSessions] = useState<DatabaseAiSessionSummary[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<DatabaseAiMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [thinkingEnabled, setThinkingEnabled] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loadingSession, setLoadingSession] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [aiStatus, setAiStatus] = useState<string | null>(null);
  const [health, setHealth] = useState<DatabaseAiHealthResponse | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const isSuperAdmin = currentUser?.role === "super_admin";

  const loadSessions = async () => {
    try {
      const items = await api.listDatabaseAiSessions();
      setSessions(items);
      if (!selectedSessionId && items[0]) {
        await loadSession(items[0].id);
      }
    } catch (error) {
      setAiError(getErrorMessage(error));
    }
  };

  const loadSession = async (sessionId: string) => {
    setLoadingSession(true);
    setAiError(null);
    try {
      const detail = await api.getDatabaseAiSession(sessionId);
      setSelectedSessionId(detail.id);
      setMessages(detail.messages);
    } catch (error) {
      setAiError(getErrorMessage(error));
    } finally {
      setLoadingSession(false);
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
    let latestSources: DatabaseAiSource[] = [];
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
      await api.streamDatabaseAiChat(
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
      setQuestion("");
      setSessions(await api.listDatabaseAiSessions());
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
      const response = await api.getDatabaseAiHealth();
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
      const response = await api.rebuildDatabaseAiFacts();
      setAiStatus(`AI 事实库已重建：${response.fact_count} 条事实`);
    } catch (error) {
      setAiError(getErrorMessage(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel ai-chat-panel">
      <div className="section-title">
        <div>
          <h2>AI 聊天</h2>
          <p className="muted">基于数据库结构、中文注释和样例数据进行 RAG 回答。</p>
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
                重建事实库
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
          {sessions.length === 0 && <EmptyState text="还没有 AI 聊天会话。" />}
        </div>

        <div className="ai-conversation">
          <div className="ai-message-list">
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
                {message.sources.length > 0 && <AiSources sources={message.sources} />}
              </div>
            ))}
            {messages.length === 0 && (
              <EmptyState text={loadingSession ? "正在加载会话..." : "询问数据库表结构、字段含义或样例数据。"} />
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
              placeholder="例如：users 表保存了哪些字段？帖子和评论如何关联？"
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

function MarkdownMessage({ content, compact = false }: { content: string; compact?: boolean }) {
  return (
    <div className={`ai-message-body markdown-body ${compact ? "compact" : ""}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content || " "}</ReactMarkdown>
    </div>
  );
}

function AiSources({ sources }: { sources: DatabaseAiSource[] }) {
  return (
    <div className="ai-sources">
      {sources.slice(0, 6).map((source) => (
        <span key={source.fact_id}>
          {aiFactTypeLabels[source.fact_type] ?? source.fact_type}
          {source.source_table_name ? ` · ${source.source_table_name}` : ""}
          {source.source_column_name ? `.${source.source_column_name}` : ""}
        </span>
      ))}
    </div>
  );
}

function AdminView({
  currentUser,
  selectedCircle,
  selectedPost,
  canModerateSelectedPost,
  onOpenAuth,
  onAssignOwner,
  onDeactivateUser,
  onSetPostFlag,
}: {
  currentUser: UserProfile | null;
  selectedCircle: FanCircleDetail | null;
  selectedPost: PostDetail | null;
  canModerateSelectedPost: boolean;
  onOpenAuth: (mode?: AuthMode) => void;
  onAssignOwner: (circleId: number, ownerUserId: number) => Promise<void>;
  onDeactivateUser: (userId: number) => Promise<void>;
  onSetPostFlag: (flag: "pin" | "lock", value: boolean) => Promise<void>;
}) {
  const [circleId, setCircleId] = useState("");
  const [ownerId, setOwnerId] = useState("");
  const [deactivateId, setDeactivateId] = useState("");
  const isSuperAdmin = currentUser?.role === "super_admin";

  if (!currentUser) {
    return (
      <section className="single-panel">
        <EmptyState text="登录后根据角色显示可用管理操作。" />
        <button className="primary" onClick={() => onOpenAuth("login")}>
          <LogIn size={17} />
          登录
        </button>
      </section>
    );
  }

  return (
    <section className="admin-grid">
      <div className="panel">
        <div className="section-title">
          <h2>当前权限</h2>
          <span>{roleLabels[currentUser.role]}</span>
        </div>
        <p className="muted">
          管理操作直接调用后端权限校验。无权限时会显示后端返回的错误提示。
        </p>
        <div className="summary-grid">
          <Metric label="当前圈子" value={selectedCircle?.id ?? "-"} />
          <Metric label="当前帖子" value={selectedPost?.id ?? "-"} />
          <Metric label="可管理帖子" value={canModerateSelectedPost ? "是" : "否"} />
        </div>
      </div>

      <div className="panel">
        <div className="section-title">
          <h2>帖子管理</h2>
          <span>{selectedPost ? selectedPost.title : "未选择帖子"}</span>
        </div>
        <div className="toolbar vertical">
          <button
            className="ghost"
            disabled={!selectedPost}
            onClick={() => selectedPost && void onSetPostFlag("pin", !selectedPost.is_pinned)}
          >
            <Pin size={17} />
            {selectedPost?.is_pinned ? "取消置顶" : "置顶帖子"}
          </button>
          <button
            className="ghost"
            disabled={!selectedPost}
            onClick={() => selectedPost && void onSetPostFlag("lock", !selectedPost.is_locked)}
          >
            {selectedPost?.is_locked ? <Unlock size={17} /> : <Lock size={17} />}
            {selectedPost?.is_locked ? "解锁帖子" : "锁定帖子"}
          </button>
        </div>
      </div>

      {isSuperAdmin && (
        <>
          <form
            className="panel admin-form"
            onSubmit={(event) => {
              event.preventDefault();
              const parsedCircleId = Number(circleId || selectedCircle?.id);
              const parsedOwnerId = Number(ownerId);
              if (parsedCircleId > 0 && parsedOwnerId > 0) {
                void onAssignOwner(parsedCircleId, parsedOwnerId);
              }
            }}
          >
            <div className="section-title">
              <h2>分配圈主</h2>
              <span>super_admin</span>
            </div>
            <input value={circleId} onChange={(event) => setCircleId(event.target.value)} placeholder="圈子 ID，默认当前圈子" />
            <input required value={ownerId} onChange={(event) => setOwnerId(event.target.value)} placeholder="圈主用户 ID" />
            <button className="primary">
              <Shield size={17} />
              分配
            </button>
          </form>

          <form
            className="panel admin-form"
            onSubmit={(event) => {
              event.preventDefault();
              const id = Number(deactivateId);
              if (id > 0) {
                void onDeactivateUser(id);
              }
            }}
          >
            <div className="section-title">
              <h2>停用用户</h2>
              <span>super_admin</span>
            </div>
            <input required value={deactivateId} onChange={(event) => setDeactivateId(event.target.value)} placeholder="用户 ID" />
            <button className="danger">
              <Lock size={17} />
              停用
            </button>
          </form>
        </>
      )}
    </section>
  );
}

function AuthDialog({
  mode,
  onModeChange,
  onClose,
  onLoginSuccess,
  onNotice,
}: {
  mode: AuthMode;
  onModeChange: (mode: AuthMode) => void;
  onClose: () => void;
  onLoginSuccess: (token: string) => Promise<void>;
  onNotice: (kind: NoticeKind, text: string) => void;
}) {
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
        onNotice("success", "注册成功，请登录。");
        onModeChange("login");
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

function EmptyState({ text }: { text: string }) {
  return (
    <div className="empty-state">
      <Eye size={22} />
      <span>{text}</span>
    </div>
  );
}

export default App;
