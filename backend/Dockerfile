# 默认使用 docker.io，compose / CI 仍可显式覆盖成私有镜像源。
ARG DOCKER_REGISTRY=docker.io
FROM ${DOCKER_REGISTRY}/library/python:3.11-slim

# Python 包源由 compose 显式传入，便于在国内构建机上固定依赖下载来源。
ARG PIP_INDEX_URL

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_CACHE_DIR=/root/.cache/pip
ENV PIP_INDEX_URL=${PIP_INDEX_URL}

WORKDIR /app

# 安装系统依赖（图像处理和音频处理需要）
RUN apt-get update && apt-get install -y \
    libxcb1 \
    libxrender1 \
    libxext6 \
    libsm6 \
    libice6 \
    libgl1 \
    libglib2.0-0 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    pip install -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app
COPY app.py .
COPY model_catalog.json .

RUN mkdir -p /app/storage

EXPOSE 8000

CMD ["python", "app.py", "--host", "0.0.0.0", "--port", "8000"]
