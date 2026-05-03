import {
  BarChart3,
  Bell,
  CircleUserRound,
  Code2,
  Database,
  Flag,
  LogIn,
  LogOut,
  RefreshCw,
  Shield,
  Users,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  clearStoredToken,
  getStoredToken,
  setStoredToken,
} from "./api/client";
import type {
  AnalyticsResponse,
  CommentResponse,
  CreatePostRequest,
  DatabaseAccessLevel,
  DatabaseCatalogResponse,
  FanCircleDetail,
  FanCircleSummary,
  PostDetail,
  PostSummary,
  UserBrief,
  UserProfile,
} from "./api/types";
import { AdminView } from "./components/admin/AdminView";
import { AnalyticsView } from "./components/analytics/AnalyticsView";
import { AuthDialog } from "./components/auth/AuthDialog";
import { CirclesView } from "./components/circles/CirclesView";
import { CodeQaView } from "./components/code/CodeQaView";
import { DatabasesView } from "./components/databases/DatabasesView";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { ProfileView } from "./components/profile/ProfileView";
import { NavButton } from "./components/ui/NavButton";
import { UserBadge } from "./components/ui/UserBadge";
import type { AuthMode, Notice, NoticeKind, ViewKey } from "./utils/constants";
import { viewTitle } from "./utils/constants";
import { getErrorMessage } from "./utils/helpers";

function App() {
  const [view, setView] = useState<ViewKey>("circles");
  const [circles, setCircles] = useState<FanCircleSummary[]>([]);
  const [circleTotal, setCircleTotal] = useState(0);
  const [circlePage, setCirclePage] = useState(1);
  const [selectedCircleId, setSelectedCircleId] = useState<number | null>(null);
  const [selectedCircle, setSelectedCircle] = useState<FanCircleDetail | null>(null);
  const [posts, setPosts] = useState<PostSummary[]>([]);
  const [postTotal, setPostTotal] = useState(0);
  const [postPage, setPostPage] = useState(1);
  const [selectedPostId, setSelectedPostId] = useState<number | null>(null);
  const [selectedPost, setSelectedPost] = useState<PostDetail | null>(null);
  const [comments, setComments] = useState<CommentResponse[]>([]);
  const [commentTotal, setCommentTotal] = useState(0);
  const [commentPage, setCommentPage] = useState(1);
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [profileUser, setProfileUser] = useState<UserProfile | null>(null);
  const [followers, setFollowers] = useState<UserBrief[]>([]);
  const [followerTotal, setFollowerTotal] = useState(0);
  const [followerPage, setFollowerPage] = useState(1);
  const [following, setFollowing] = useState<UserBrief[]>([]);
  const [followingTotal, setFollowingTotal] = useState(0);
  const [followingPage, setFollowingPage] = useState(1);
  const [circleAnalytics, setCircleAnalytics] = useState<AnalyticsResponse | null>(null);
  const [postAnalytics, setPostAnalytics] = useState<AnalyticsResponse | null>(null);
  const [userAnalytics, setUserAnalytics] = useState<AnalyticsResponse | null>(null);
  const [databaseCatalog, setDatabaseCatalog] = useState<DatabaseCatalogResponse | null>(null);
  const [selectedDatabasePath, setSelectedDatabasePath] = useState<string | null>(null);
  const [selectedTableName, setSelectedTableName] = useState<string | null>(null);
  const [authOpen, setAuthOpen] = useState(false);
  const [authMode, setAuthMode] = useState<AuthMode>("login");
  const [notices, setNotices] = useState<Notice[]>([]);
  const [busy, setBusy] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">(
    () => (localStorage.getItem("theme") as "light" | "dark") ?? "light",
  );
  const noticeIdRef = useRef(0);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

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

  const canDeleteSelectedPost = canModerateSelectedPost || (
    !!currentUser && !!selectedPost && currentUser.id === selectedPost.author.id
  );

  const canDeleteComment = (commentAuthorId: number) =>
    !!currentUser &&
    (currentUser.id === commentAuthorId || canModerateSelectedPost);

  const showNotice = (kind: NoticeKind, text: string) => {
    const id = ++noticeIdRef.current;
    setNotices((prev) => [...prev, { id, kind, text }]);
    setTimeout(() => {
      setNotices((prev) => prev.filter((n) => n.id !== id));
    }, 5000);
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
      const response = await api.listFanCircles(1);
      setCircles(response.items);
      setCircleTotal(response.total);
      setCirclePage(1);
      setSelectedCircleId((current) => current ?? response.items[0]?.id ?? null);
    } catch (error) {
      showNotice("error", getErrorMessage(error));
    } finally {
      setBusy(false);
    }
  };

  const loadMoreCircles = async () => {
    const nextPage = circlePage + 1;
    try {
      const response = await api.listFanCircles(nextPage);
      setCircles((prev) => [...prev, ...response.items]);
      setCirclePage(nextPage);
      setCircleTotal(response.total);
    } catch (error) {
      showNotice("error", getErrorMessage(error));
    }
  };

  const loadCircle = async (circleId: number) => {
    setBusy(true);
    try {
      const [circle, circlePosts, analytics] = await Promise.all([
        api.getFanCircle(circleId),
        api.getCirclePosts(circleId, 1),
        api.getFanCircleAnalytics(circleId),
      ]);
      setSelectedCircle(circle);
      setPosts(circlePosts.items);
      setPostTotal(circlePosts.total);
      setPostPage(1);
      setCircleAnalytics(analytics);
      setSelectedPostId((current) => current ?? circlePosts.items[0]?.id ?? null);
    } catch (error) {
      showNotice("error", getErrorMessage(error));
    } finally {
      setBusy(false);
    }
  };

  const loadMorePosts = async () => {
    if (!selectedCircleId) return;
    const nextPage = postPage + 1;
    try {
      const response = await api.getCirclePosts(selectedCircleId, nextPage);
      setPosts((prev) => [...prev, ...response.items]);
      setPostPage(nextPage);
      setPostTotal(response.total);
    } catch (error) {
      showNotice("error", getErrorMessage(error));
    }
  };

  const loadPost = async (postId: number) => {
    try {
      const [post, commentPageRes, analytics] = await Promise.all([
        api.getPost(postId),
        api.listComments(postId, 1),
        api.getPostAnalytics(postId),
      ]);
      setSelectedPost(post);
      setComments(commentPageRes.items);
      setCommentTotal(commentPageRes.total);
      setCommentPage(1);
      setPostAnalytics(analytics);
    } catch (error) {
      showNotice("error", getErrorMessage(error));
    }
  };

  const loadMoreComments = async () => {
    if (!selectedPostId) return;
    const nextPage = commentPage + 1;
    try {
      const response = await api.listComments(selectedPostId, nextPage);
      setComments((prev) => [...prev, ...response.items]);
      setCommentPage(nextPage);
      setCommentTotal(response.total);
    } catch (error) {
      showNotice("error", getErrorMessage(error));
    }
  };

  const loadProfile = async (userId: number) => {
    try {
      const [user, followerPageRes, followingPageRes] = await Promise.all([
        api.getUser(userId),
        api.listFollowers(userId, 1),
        api.listFollowing(userId, 1),
      ]);
      setProfileUser(user);
      setFollowers(followerPageRes.items);
      setFollowerTotal(followerPageRes.total);
      setFollowerPage(1);
      setFollowing(followingPageRes.items);
      setFollowingTotal(followingPageRes.total);
      setFollowingPage(1);
    } catch (error) {
      showNotice("error", getErrorMessage(error));
    }
  };

  const loadMoreFollowers = async () => {
    if (!profileUser) return;
    const nextPage = followerPage + 1;
    try {
      const response = await api.listFollowers(profileUser.id, nextPage);
      setFollowers((prev) => [...prev, ...response.items]);
      setFollowerPage(nextPage);
      setFollowerTotal(response.total);
    } catch (error) {
      showNotice("error", getErrorMessage(error));
    }
  };

  const loadMoreFollowing = async () => {
    if (!profileUser) return;
    const nextPage = followingPage + 1;
    try {
      const response = await api.listFollowing(profileUser.id, nextPage);
      setFollowing((prev) => [...prev, ...response.items]);
      setFollowingPage(nextPage);
      setFollowingTotal(response.total);
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

  const deletePost = async (postId: number) => {
    if (!confirm("确定要删除这个帖子吗？所有评论也将被删除。")) {
      return;
    }
    try {
      await api.deletePost(postId);
      setSelectedPost(null);
      setSelectedPostId(null);
      setComments([]);
      showNotice("success", "帖子已删除。");
      if (selectedCircleId) {
        await loadCircle(selectedCircleId);
      }
    } catch (error) {
      showNotice("error", getErrorMessage(error));
    }
  };

  const deleteComment = async (commentId: number) => {
    if (!confirm("确定要删除这条评论吗？")) {
      return;
    }
    try {
      await api.deleteComment(commentId);
      showNotice("success", "评论已删除。");
      if (selectedPostId) {
        await loadPost(selectedPostId);
      }
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
          <button
            className="ghost full"
            onClick={() => setTheme(theme === "light" ? "dark" : "light")}
            title={theme === "light" ? "切换到深色模式" : "切换到浅色模式"}
          >
            <span>{theme === "light" ? "🌙" : "☀️"}</span>
            {theme === "light" ? "深色模式" : "浅色模式"}
          </button>
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

        {notices.length > 0 && (
          <div className="notice-stack">
            {notices.map((n) => (
              <div key={n.id} className={`notice ${n.kind}`}>
                <span>{n.text}</span>
                <button onClick={() => setNotices((prev) => prev.filter((x) => x.id !== n.id))} aria-label="关闭提示">
                  <X size={16} />
                </button>
              </div>
            ))}
          </div>
        )}

        {view === "circles" && (
          <ErrorBoundary>
            <CirclesView
              circles={circles}
              circleTotal={circleTotal}
              selectedCircle={selectedCircle}
              selectedCircleId={selectedCircleId}
              posts={selectedCirclePosts}
              postTotal={postTotal}
              selectedPost={selectedPost}
              comments={comments}
              commentTotal={commentTotal}
              currentUser={currentUser}
              canModerateSelectedPost={canModerateSelectedPost}
              canDeleteSelectedPost={canDeleteSelectedPost}
              canDeleteComment={canDeleteComment}
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
              onDeletePost={deletePost}
              onDeleteComment={deleteComment}
              onLoadMoreCircles={loadMoreCircles}
              onLoadMorePosts={loadMorePosts}
              onLoadMoreComments={loadMoreComments}
            />
          </ErrorBoundary>
        )}

        {view === "profile" && (
          <ErrorBoundary>
            <ProfileView
              currentUser={currentUser}
              profileUser={profileUser}
              followers={followers}
              followerTotal={followerTotal}
              following={following}
              followingTotal={followingTotal}
              onOpenAuth={openAuth}
              onLoadProfile={(userId) => void loadProfile(userId)}
              onFollow={followProfile}
              onLoadMoreFollowers={loadMoreFollowers}
              onLoadMoreFollowing={loadMoreFollowing}
            />
          </ErrorBoundary>
        )}

        {view === "analytics" && (
          <ErrorBoundary>
            <AnalyticsView
              currentUser={currentUser}
              selectedCircle={selectedCircle}
              selectedPost={selectedPost}
              userAnalytics={userAnalytics}
              circleAnalytics={circleAnalytics}
              postAnalytics={postAnalytics}
              onLoadUserAnalytics={(userId) => void loadUserAnalytics(userId)}
            />
          </ErrorBoundary>
        )}

        {view === "admin" && (
          <ErrorBoundary>
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
          </ErrorBoundary>
        )}

        {view === "databases" && (
          <ErrorBoundary>
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
          </ErrorBoundary>
        )}

        {view === "code" && (
          <ErrorBoundary>
            <CodeQaView currentUser={currentUser} />
          </ErrorBoundary>
        )}
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

export default App;
