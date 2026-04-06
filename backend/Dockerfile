FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

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
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY app.py .
COPY model_catalog.json .

RUN mkdir -p /app/storage

EXPOSE 8000

CMD ["python", "app.py", "--host", "0.0.0.0", "--port", "8000"]
