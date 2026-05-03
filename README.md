# FootballDomain

FootballDomain 是一个足球球迷社区示例项目，包含 FastAPI 后端、SQLite 数据库和 Vite + React + TypeScript 前端。项目支持用户注册登录、球迷圈浏览、发帖、评论、点赞/点踩、投票、关注用户、数据分析和基础管理操作。

## 技术栈

- 后端：FastAPI、SQLite、PyJWT、Passlib/bcrypt
- 前端：Vite、React、TypeScript、lucide-react
- 测试：pytest、FastAPI TestClient、httpx
- 静态资源：`static/avatars`、`static/logos`

## 目录结构

```text
.
├── app/                 # FastAPI 后端应用
│   ├── api/             # API 路由
│   ├── core/            # 配置、安全、异常处理
│   ├── db/              # SQLite 连接与初始化
│   ├── repositories/    # 数据访问层
│   ├── schemas/         # Pydantic 请求/响应模型
│   └── services/        # 权限、评论、分析等业务逻辑
├── frontend/            # Vite + React 前端
├── sql/                 # 数据库建表与种子数据
├── static/              # 头像、球队 logo 等静态文件
├── tests/               # 后端接口测试
├── .env.example         # 环境变量示例
└── requirements.txt     # Python 依赖
```

## 环境准备

本项目约定使用以下 Python 虚拟环境：

```powershell
D:\PythonVEnv\FirstVEnv\Scripts\python.exe
```

安装后端依赖：

```powershell
D:\PythonVEnv\FirstVEnv\Scripts\python.exe -m pip install -r requirements.txt
```

安装前端依赖：

```powershell
cd frontend
npm install
```

## 配置

复制环境变量示例文件：

```powershell
Copy-Item .env.example .env
```

主要配置项：

```env
APP_NAME=FootballDomain
DATABASE_URL=sqlite:///./football_domain.db
JWT_SECRET_KEY=change-me-in-production
JWT_EXPIRE_MINUTES=120
STATIC_DIR=static
```

开发环境可以直接使用默认配置。生产环境必须修改 `JWT_SECRET_KEY`。

## 启动后端

在项目根目录运行：

```powershell
D:\PythonVEnv\FirstVEnv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

后端启动时会自动初始化 SQLite 数据库，并执行：

- `sql/001_init.sql`：创建表和索引
- `sql/002_seed.sql`：写入默认球迷圈数据

接口文档地址：

- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

## 启动前端

另开一个终端：

```powershell
cd frontend
npm run dev
```

默认访问：

```text
http://127.0.0.1:5173
```

前端开发服务器会把 `/api` 和 `/static` 代理到 `http://127.0.0.1:8000`，所以需要先启动后端。

## 常用脚本

后端测试：

```powershell
D:\PythonVEnv\FirstVEnv\Scripts\python.exe -m pytest
```

前端构建：

```powershell
cd frontend
npm run build
```

前端代码检查：

```powershell
cd frontend
npm run lint
```

## 主要功能

- 用户认证：注册、登录、获取当前用户
- 用户关系：查看资料、关注、取消关注、粉丝/关注列表
- 球迷圈：列表、详情、球迷圈帖子、球迷圈分析
- 帖子：发帖、详情、点赞、点踩、置顶、锁定
- 评论：评论、回复、评论点赞/点踩、树形排序
- 投票：帖子投票、单选/多选控制、防重复投票
- 分析：用户、球迷圈、帖子近期事件记录
- 管理：分配球迷圈圈主、停用用户、帖子置顶/锁定

## API 概览

认证：

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`

球迷圈：

- `GET /api/v1/fan-circles`
- `GET /api/v1/fan-circles/{circle_id}`
- `GET /api/v1/fan-circles/{circle_id}/posts`
- `POST /api/v1/fan-circles/{circle_id}/posts`
- `GET /api/v1/fan-circles/{circle_id}/analytics`

帖子与评论：

- `GET /api/v1/posts/{post_id}`
- `POST /api/v1/posts/{post_id}/like`
- `POST /api/v1/posts/{post_id}/dislike`
- `POST /api/v1/posts/{post_id}/vote`
- `GET /api/v1/posts/{post_id}/comments`
- `POST /api/v1/posts/{post_id}/comments`
- `POST /api/v1/comments/{comment_id}/reply`
- `POST /api/v1/comments/{comment_id}/like`
- `POST /api/v1/comments/{comment_id}/dislike`
- `GET /api/v1/posts/{post_id}/analytics`

用户：

- `GET /api/v1/users/{user_id}`
- `POST /api/v1/users/{user_id}/follow`
- `DELETE /api/v1/users/{user_id}/follow`
- `GET /api/v1/users/{user_id}/followers`
- `GET /api/v1/users/{user_id}/following`
- `GET /api/v1/users/{user_id}/analytics`

管理：

- `POST /api/v1/admin/fan-circles/{circle_id}/owner`
- `POST /api/v1/admin/posts/{post_id}/pin`
- `POST /api/v1/admin/posts/{post_id}/lock`
- `POST /api/v1/admin/users/{user_id}/deactivate`

需要登录的接口使用 Bearer Token：

```http
Authorization: Bearer <access_token>
```

## 管理员账号说明

种子数据只初始化球迷圈，不会创建默认管理员账号。开发调试时可以先通过注册接口创建用户，再把该用户角色改为 `super_admin`。

示例：把用户 ID 为 `1` 的账号设为超级管理员：

```powershell
D:\PythonVEnv\FirstVEnv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect('football_domain.db'); c.execute(\"UPDATE users SET role='super_admin', updated_at=CURRENT_TIMESTAMP WHERE id=1\"); c.commit(); c.close()"
```

## 数据库

默认数据库文件为：

```text
football_domain.db
```

如果需要重新初始化开发数据库，可以停止后端后删除该文件，再重新启动后端。启动过程会重新执行建表和种子脚本。

## 注意事项

- `frontend/src/App.tsx` 中的部分中文文本目前显示为乱码，建议后续统一用 UTF-8 重新保存并校对文案。
- `JWT_SECRET_KEY` 默认值只适合本地开发。
- 前端请求依赖 Vite 代理配置，直接打开构建产物时需要确保 API 地址可访问。
