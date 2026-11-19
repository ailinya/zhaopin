# ============================================================
# AI 智能招聘面试系统后端 Dockerfile
# 多阶段构建：builder（uv 装依赖）→ runtime（slim 运行时）
# 详细部署说明见 docs/07_deployment-v1.0.md（待写）
# ============================================================

# ============ Stage 1: Builder ============
FROM python:3.11-slim AS builder

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# 先复制依赖清单（利用 Docker 缓存）
COPY pyproject.toml ./
COPY uv.lock* ./

# 同步依赖到独立 venv（不安装项目本身）
RUN uv sync --frozen --no-install-project || uv sync --no-install-project

# 复制源码
COPY . .

# 安装项目本身
RUN uv sync --frozen || uv sync

# ============ Stage 2: Runtime ============
FROM python:3.11-slim AS runtime

# 安装运行时系统依赖
# - ffmpeg: Whisper 音频处理
# - libpango / libcairo: WeasyPrint PDF 渲染
# - libffi / libxml2: python 依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libxml2-dev \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户
RUN useradd --create-home --shell /bin/bash appuser
WORKDIR /app

# 从 builder 复制 venv 和源码
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appuser /app/app /app/app

# 环境变量：使用 venv 中的 python
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 切换到非 root 用户
USER appuser

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/healthz').raise_for_status()" || exit 1

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]