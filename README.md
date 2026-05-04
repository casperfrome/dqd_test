# FootballDomain

足球球迷社区示例项目，提供球迷圈、发帖、评论、投票、关注、管理和 AI 问答功能。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | FastAPI · SQLite · PyJWT · Passlib/bcrypt |
| 前端 | Vite · React 19 · TypeScript · lucide-react |
| AI | Ollama（本地 LLM）· RAG · FTS5 |
| 测试 | pytest · FastAPI TestClient · httpx |

## 目录结构

```text
.
├── app/
│   ├── api/             # 路由（auth/users/posts/fan_circles/admin/databases/code）
│   ├── core/            # 配置、JWT/密码、异常处理、工具函数
│   ├── db/              # SQLite 连接与启动初始化
│   ├── repositories/    # 数据访问层（CRUD + AI 对话记录）
│   ├── schemas/         # Pydantic 请求/响应模型
│   └── services/        # 业务逻辑、权限、AI 问答、RAG
├── frontend/
│   └── src/
│       ├── App.tsx                  # 主组件
│       ├── styles.css               # 全局样式
│       ├── api/                     # HTTP 客户端与 TypeScript 类型
│       ├── utils/                   # 常量与工具函数
│       └── components/
│           ├── ui/                  # 通用组件（EmptyState/Metric/NavButton 等）
│           ├── auth/                # 登录注册弹窗
│           ├── circles/             # 球迷圈、帖子、评论、投票
│           ├── profile/             # 个人主页、用户列表
│           ├── analytics/           # 活动分析面板
│           ├── admin/               # 管理面板
│           ├── databases/           # 数据库 AI 问答
│           └── code/                # 代码知识库 AI 问答
├── sql/
│   ├── 001_init.sql             # 建表、索引、FTS 虚拟表
│   ├── 002_add_embeddings.sql   # AI 嵌入向量支持
│   └── 002_seed.sql             # 默认球迷圈数据
├── static/                      # SVG 头像与球队 Logo
├── tests/                       # 后端接口测试（pytest）
├── .env.example                 # 环境变量模板
├── .gitignore
└── requirements.txt             # Python 依赖
```

## 快速开始

### 1. 安装依赖

```powershell
# 后端
D:\PythonVEnv\FirstVEnv\Scripts\python.exe -m pip install -r requirements.txt

# 前端
cd frontend
npm install
```

### 2. 配置环境变量

```powershell
Copy-Item .env.example .env
```

`.env` 关键配置项：

```env
JWT_SECRET_KEY=change-me-in-production   # 生产环境必须修改
DATABASE_URL=sqlite:///./football_domain.db
OLLAMA_BASE_URL=http://127.0.0.1:11434   # AI 功能需要本地 Ollama
AI_CHAT_MODEL=qwen3:8b
```

开发环境其余配置保持默认即可。

### 3. 启动后端

```powershell
D:\PythonVEnv\FirstVEnv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

后端启动时自动执行 `sql/001_init.sql`（建表）和 `sql/002_seed.sql`（写入默认球迷圈）。

- Swagger UI：`http://127.0.0.1:8000/docs`
- OpenAPI JSON：`http://127.0.0.1:8000/openapi.json`

### 4. 启动前端

```powershell
cd frontend
npm run dev
```

访问 `http://127.0.0.1:5173`。前端通过 Vite 代理将 `/api` 和 `/static` 转发到后端，**需先启动后端**。

## 常用命令

```powershell
# 运行测试
D:\PythonVEnv\FirstVEnv\Scripts\python.exe -m pytest

# 前端构建
cd frontend && npm run build

# 前端代码检查
cd frontend && npm run lint

# 预览生产构建
cd frontend && npm run preview
```

## 主要功能

- **用户认证**：注册、登录、JWT Bearer Token
- **用户关系**：查看资料、关注 / 取消关注、粉丝 / 关注列表
- **球迷圈**：列表、详情、圈内发帖、活动分析
- **帖子**：分类发帖（讨论 / 新闻 / 转会 / 赛事 / 灌水）、点赞 / 点踩、置顶 / 锁定
- **评论**：树形回复、评论点赞 / 点踩
- **投票**：帖子内投票、单选 / 多选、防重复投票
- **分析**：用户 / 球迷圈 / 帖子近期事件记录
- **管理**：分配圈主、停用用户、帖子管理
- **AI 问答**：基于 Ollama + RAG，支持数据库结构问答和代码知识库问答

## API 概览

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 注册 |
| POST | `/api/v1/auth/login` | 登录，返回 access_token |
| GET  | `/api/v1/auth/me` | 获取当前用户 |

### 球迷圈

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/v1/fan-circles` | 球迷圈列表 |
| GET  | `/api/v1/fan-circles/{id}` | 球迷圈详情 |
| GET  | `/api/v1/fan-circles/{id}/posts` | 圈内帖子 |
| POST | `/api/v1/fan-circles/{id}/posts` | 发帖 |
| GET  | `/api/v1/fan-circles/{id}/analytics` | 活动分析 |

### 帖子与评论

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/v1/posts/{id}` | 帖子详情 |
| POST | `/api/v1/posts/{id}/like` | 点赞 |
| POST | `/api/v1/posts/{id}/dislike` | 点踩 |
| POST | `/api/v1/posts/{id}/vote` | 投票 |
| GET  | `/api/v1/posts/{id}/comments` | 评论列表 |
| POST | `/api/v1/posts/{id}/comments` | 发评论 |
| POST | `/api/v1/comments/{id}/reply` | 回复评论 |
| POST | `/api/v1/comments/{id}/like` | 评论点赞 |
| POST | `/api/v1/comments/{id}/dislike` | 评论点踩 |

### 用户

| 方法 | 路径 | 说明 |
|------|------|------|
| GET    | `/api/v1/users/{id}` | 用户资料 |
| POST   | `/api/v1/users/{id}/follow` | 关注 |
| DELETE | `/api/v1/users/{id}/follow` | 取消关注 |
| GET    | `/api/v1/users/{id}/followers` | 粉丝列表 |
| GET    | `/api/v1/users/{id}/following` | 关注列表 |

### 管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/admin/fan-circles/{id}/owner` | 分配圈主 |
| POST | `/api/v1/admin/posts/{id}/pin` | 置顶帖子 |
| POST | `/api/v1/admin/posts/{id}/lock` | 锁定帖子 |
| POST | `/api/v1/admin/users/{id}/deactivate` | 停用用户 |

需要认证的接口携带：

```http
Authorization: Bearer <access_token>
```

## 管理员账号

种子数据不创建默认管理员。开发调试时先注册账号，再手动提权：

```powershell
D:\PythonVEnv\FirstVEnv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect('football_domain.db'); c.execute(\"UPDATE users SET role='super_admin', updated_at=CURRENT_TIMESTAMP WHERE id=1\"); c.commit(); c.close()"
```

## 数据库

默认数据库文件为 `football_domain.db`（已加入 `.gitignore`）。

重新初始化开发数据库：停止后端 → 删除 `.db` 文件 → 重新启动，后端会自动重建。

## AI 功能说明

AI 问答依赖本地 [Ollama](https://ollama.com) 服务，默认模型为 `qwen3:8b`。

```powershell
# 拉取模型（首次使用）
ollama pull qwen3:8b
```

未启动 Ollama 时，社区核心功能不受影响，仅 `/api/v1/databases/chat` 和 `/api/v1/code/chat` 等接口不可用。

## 注意事项

- 生产环境必须修改 `JWT_SECRET_KEY`。
- 前端请求依赖 Vite 代理配置，构建产物部署时需确保后端 API 地址可访问。
