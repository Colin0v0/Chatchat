# Chatchat

个人本地推理工作台，首版聚焦：

- 本地 `Ollama` 推理
- 会话管理
- 流式聊天 UI
- 后续接入 RAG 的清晰扩展位

## Tech Stack

- Frontend: `React 19 + Vite + TypeScript`
- Backend: `FastAPI + SQLAlchemy + SQLite`
- Inference: `Ollama`

## Start

### 1. 启动 Ollama

先确认本机已经安装并启动 `Ollama`，并且至少拉了一个模型，例如：

```bash
ollama pull qwen2.5:7b
ollama serve
```

### 2. 启动后端

```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

打开 `http://127.0.0.1:5173`

## Structure

```text
backend/
  app/
    config.py
    database.py
    main.py
    models.py
    ollama.py
    schemas.py
frontend/
  src/
    components/
    lib/
    App.tsx
    index.css
storage/
```

## Next

下一阶段建议按这个顺序扩：

1. 文件上传与文档解析
2. 文本切片与 embedding
3. `Chroma` 检索
4. 引用来源展示
5. 知识库管理页
