ARG DOCKER_REGISTRY=docker.io
FROM ${DOCKER_REGISTRY}/library/python:3.11-slim

ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

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

COPY app ./app
COPY app.py .
COPY model_catalog.json .

RUN mkdir -p /app/storage

EXPOSE 8000

CMD ["python", "app.py", "--host", "0.0.0.0", "--port", "8000"]
