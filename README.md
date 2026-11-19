# 星浩AI - 智能招聘面试系统

> **作者**：星浩AI | **公众号**：星浩AI
> 基于 FastAPI + LangGraph + React 18 的现代化 AI 面试系统重构版本。

## 项目概述

一个面向企业 HR/技术招聘官的 AI 自动化面试系统。把整个招聘链路——**岗位 → 候选人 → 面试出题 → 在线语音面试 → 自动评估报告**——完整串起来。

**核心能力**：

- 🤖 **智能面试问题生成**：基于候选人简历和岗位要求，自动生成针对性面试问题
- 🎙️ **在线语音面试**：候选人通过网页进行语音回答，系统自动录音和转写（Whisper）
- 📊 **自动面试评估**：系统自动分析面试表现，生成详细的面试评估报告（LLM + WeasyPrint）
- 📋 **完整招聘管理**：支持岗位管理、候选人管理和面试流程管理
- ⏰ **定时自动处理**：LangGraph 工作流驱动状态机
- 📡 **实时进度推送**：SSE 推送面试状态变更

## 技术栈

### 后端
- **FastAPI 0.115+** - Web 框架
- **Python 3.11+** - 运行时
- **SQLAlchemy 2.0** (sync) - ORM
- **LangGraph 0.2+** - 工作流编排（4 节点 + interrupt + SqliteSaver）
- **SQLite WAL** - MVP 数据库（业务库 + checkpoint 库物理隔离）
- **Pydantic 2** - 数据校验
- **bcrypt + python-jose** - 鉴权（HR JWT + 候选人 token URL 双轨）
- **structlog** - 结构化 JSON 日志
- **uvicorn[standard]** - ASGI 服务器
- **APScheduler** - 进程内定时（卡住巡检）
- **uv** - 包管理

> 当前用 `Base.metadata.create_all()` 建表；**Alembic 计划 Phase 5 引入**。

### AI / LLM
- **DeepSeek** (默认) / **Qwen** / **GLM** - 大模型（OpenAI 兼容接口）
- **openai-whisper** - 语音识别（GPU large-v3 / CPU base）
- **WeasyPrint + Jinja2** - PDF 报告生成

### 前端
- **React 18.3** + **TypeScript 5.7**
- **Vite 6** - 构建工具
- **Tailwind CSS 4** (`@tailwindcss/vite`) - 样式
- **Radix UI** (25+ 原语，shadcn/ui 风格封装) - 无样式可访问组件
- **TanStack Query v5** - 数据获取/缓存
- **React Router v7** - SPA 路由
- **React Hook Form + Zod** - 表单 + 校验
- **Sonner** - Toast 通知
- **Recharts** - 图表
- **Axios** - HTTP 客户端（含 401 自动 refresh）
- **Lucide React** - 图标
- **date-fns** - 日期处理
- **pnpm** - 包管理

### 部署
- **Docker Compose** - 多容器编排
- **Nginx** - 反向代理 + 静态文件 + SSE 优化
- **多阶段 Dockerfile** - 镜像优化
- **GitHub Actions** - CI/CD（计划中）

## 目录结构

```
smart_interview_ai/                            # 项目根
├── README.md
├── .gitignore
├── .env.example                                # 环境变量模板（无密钥）
├── docker-compose.yml                          # api + nginx 两服务（nginx 同时托管前端 dist）
│
├── backend/                                    # FastAPI 后端
│   ├── pyproject.toml                          # uv 依赖 + ruff/mypy/pytest 配置
│   ├── Dockerfile                              # 多阶段构建
│   ├── interview.db                            # 业务数据库（SQLite WAL）
│   ├── workflow_checkpoints.db                 # LangGraph checkpoint（独立 DB）
│   ├── storage/{resumes,audio,reports,logs}/   # 运行时文件存储
│   ├── tests/                                  # 89 passed + 2 skipped（详见 docs/04）
│   └── app/
│       ├── main.py                             # FastAPI + lifespan（5 步启动）
│       ├── config.py                           # pydantic-settings
│       ├── database.py                         # SQLAlchemy 2.0 + WAL
│       ├── deps.py                             # 鉴权依赖注入
│       ├── core/                               # errors / security / main_loop / logging / i18n
│       ├── models/                             # 6 张表 + Repository
│       ├── schemas/                            # Pydantic（8 个文件按域拆分）
│       ├── api/                                # 6 个 FastAPI 路由 + 聚合
│       ├── services/                           # 11 个业务 + AI 服务
│       ├── workflow/                           # LangGraph（state / nodes / graph / DI / checkpointer）
│       ├── workers/scheduler.py                # APScheduler 卡住巡检
│       ├── prompts/                            # Jinja2 prompt 模板
│       └── templates/                          # PDF 报告模板
│
├── frontend/                                   # React 18 + Vite + TS
│   ├── package.json
│   ├── pnpm-lock.yaml / pnpm-workspace.yaml
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   └── src/
│       ├── routes.tsx                          # react-router 7 配置
│       ├── pages/                              # 8 个页面
│       ├── components/                         # 7 业务组件 + ui/（25+ Radix 封装）
│       ├── hooks/useSSE.ts                     # SSE 封装
│       ├── contexts/AuthContext.tsx            # 全局鉴权状态
│       ├── lib/                                # authStorage + cn 工具
│       ├── api/                                # axios 实例 + 5 个领域 SDK
│       ├── types/events.ts                     # 14 SSE 事件 TypeScript 类型
│       └── styles/globals.css
│
├── nginx/
│   ├── nginx.conf                              # SSE 优化版（proxy_buffering off）
│   └── ssl/
│
├── docs/                                       # 实现级规范（详见 docs/README.md）
│   ├── README.md                               # 总索引（全景图 + 6 类角色阅读路径）
│   ├── 00_requirements.md                      # 项目需求（v1.0）
│   ├── 01_architecture.md                      # 架构总览（实现级）
│   ├── 02_backend_api_spec-v1.0.md             # API 全量契约
│   ├── 03_data_model-v1.0.md                   # 6 表 ER + 字段
│   ├── 04_implementation-v1.0.md               # Week 1-3 实施总结
│   ├── 05_langgraph_workflow-v1.0.md           # 4 节点 + interrupt + DI
│   ├── 06_sse_events-v1.0.md                   # 14 事件契约
│   ├── 07_deployment-v1.0.md                   # 部署手册
│   └── 08_frontend_design_spec-v1.0.md         # 前端设计规范
│
├── tmp/                                        # 临时文件
│
├── 重构架构讨论.md                             # ~3500 行完整设计决策
└── 招聘候选人自动拉取-方案.md                  # 远期模块规划
```

## 快速开始

### 开发环境（手动）

#### 后端

```bash
cd backend

# 安装 uv（如果还没装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 同步依赖
uv sync

# 初始化数据库
uv run python -c "from app.database import init_db; init_db()"

# 启动开发服务器
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

API 文档自动生成：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

#### 前端

```bash
cd frontend

# 安装依赖（使用 npm 或 pnpm）
npm install
# 或 pnpm install

# 启动开发服务器
npm run dev
# 或 pnpm dev
```

访问：http://localhost:5173

### 生产环境（Docker）

```bash
# 1. 复制环境变量模板
cp .env.example .env
# 编辑 .env 填入真实的 LLM API key

# 2. 启动
docker compose up -d

# 3. 查看日志
docker compose logs -f api
```

访问：
- Web: https://your-domain.com
- API: https://your-domain.com/api/

## 文档体系

| 文档 | 位置 | 说明 |
|---|---|---|
| **📑 文档总索引** | [`docs/README.md`](docs/README.md) | 新人 onboarding 入口（全景图 + 6 类角色阅读路径 + 关系矩阵）|
| **架构设计决策** | `重构架构讨论.md` | 完整设计决策（~3500 行）|
| **架构总览（实现级）** | `docs/01_architecture.md` | 一句话架构 + 5 层后端 + 4 层前端 + 12 项关键决策 |
| **后端 API 契约** | `docs/02_backend_api_spec-v1.0.md` | 所有端点的请求 / 响应 / 错误码 |
| **数据模型** | `docs/03_data_model-v1.0.md` | 6 表 ER + 字段定义 |
| **Week 1-3 实施总结** | `docs/04_implementation-v1.0.md` | 已解决 / 未解决限制 + 89 测试明细 |
| **LangGraph 详细规范** | `docs/05_langgraph_workflow-v1.0.md` | 4 节点 + interrupt + DI + 卡住巡检 |
| **SSE 事件契约** | `docs/06_sse_events-v1.0.md` | 14 事件 JSON Schema + 触发矩阵 + Nginx 配置 |
| **部署手册** | `docs/07_deployment-v1.0.md` | 本地开发 + Docker Compose 部署 |
| **前端设计规范** | `docs/08_frontend_design_spec-v1.0.md` | 8 页面 + 25+ 组件 + SSE 消费 + 鉴权 |
| **远期规划** | `招聘候选人自动拉取-方案.md` | candidate_fetcher 模块蓝图 |

## 关键设计原则

1. **单向依赖**：HTTP → Service → Model/Workflow
2. **边界清晰**：每层只暴露有限接口（Pydantic schema）
3. **横向不依赖**：api 不写 SQL、service 不 import FastAPI、workflow 节点只调 service
4. **状态机驱动**：`interviews.status` 0→1→2→3→4 是系统心跳
5. **可观测**：structlog JSON 日志 + AuditLog 全量审计
6. **可演进**：adapter 模式支持多平台拓展（Phase 5 candidate_fetcher）

## 路线图

- ✅ **Week 1**：后端核心（6 表 + 6 API + 4 节点 LangGraph + APScheduler + 89 测试）
- ✅ **Week 2**：WeasyPrint PDF / 简历解析 / DI 重构 / 候选人 portal / email / i18n / schema 拆分
- ✅ **Week 3**：React 18 + Vite + TS 前端（8 页面 + 25+ 组件 + useSSE + 鉴权 + 部署）
- 📅 **远期**：candidate_fetcher 模块（招聘网站自动拉取，方案见 `招聘候选人自动拉取-方案.md`）
- 📅 **Phase 5**：Postgres + Redis + 多 worker 水平扩展 + Alembic + 前端 e2e + GitHub Actions CI

## License

内部项目，私有。