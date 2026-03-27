# Chatchat

Local chat workspace with:
- host Ollama inference
- FastAPI backend
- React frontend
- a clean path to add RAG later

## Stack

- Frontend: `React 19 + Vite + TypeScript`
- Backend: `FastAPI + SQLAlchemy + SQLite`
- Inference: host `Ollama`
- Orchestration: `Docker Compose`

## Docker First

This repo now supports one-command startup for:
- `frontend`
- `backend`

Ollama is expected to run on the host machine, not inside Docker.

The next step can be a separate `rag` service without rewriting the current app shape.

## Quick Start

### 1. Prepare env

Copy the example file:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

If you want DeepSeek or another OpenAI-compatible provider, fill:

```env
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_API_KEY=your_real_key
OPENAI_MODEL_ALLOWLIST=deepseek-chat,deepseek-reasoner
DEFAULT_PROVIDER=openai
DEFAULT_MODEL=deepseek-chat
```

If you want Ollama by default, keep:

```env
OLLAMA_BASE_URL=http://host.docker.internal:11434
DEFAULT_PROVIDER=ollama
DEFAULT_MODEL=qwen2.5:7b
```

### 2. Start all services

Make sure Ollama is already running on your host:

```bash
ollama serve
```

```bash
docker compose up --build
```

### 3. Open the app

- Frontend: [http://127.0.0.1:3300](http://127.0.0.1:3300)
- Backend API: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)
- Host Ollama API: [http://127.0.0.1:11434](http://127.0.0.1:11434)

## Common Commands

Start in background:

```bash
docker compose up -d --build
```

Stop:

```bash
docker compose down
```

View logs:

```bash
docker compose logs -f
```

Pull an Ollama model on the host:

```bash
ollama pull qwen2.5:7b
```

List Ollama models:

```bash
ollama list
```

## Services

### `frontend`

- Built with Vite
- Served by Nginx
- Proxies `/api` to `backend`

### `backend`

- Runs `python app.py --host 0.0.0.0 --port 8000`
- Stores SQLite data in a Docker volume
- Connects to host Ollama via `host.docker.internal`

## Files Added For Docker

```text
docker-compose.yml
.env.example
backend/
  Dockerfile
  .dockerignore
  .env.example
frontend/
  Dockerfile
  .dockerignore
  nginx.conf
```

## Why Docker Before RAG

This is the right order.

Once the base services are containerized, adding RAG becomes much cleaner:
- add a dedicated `rag` service
- mount your Obsidian vault into that service
- keep vector storage isolated
- let `backend` call `rag` over HTTP

That avoids turning the current backend into a monolith while also avoiding a duplicate Ollama install in Docker.

## Next Step

Recommended next move:
1. add a dedicated `rag` service
2. mount your Obsidian vault read-only
3. build indexing + retrieval there
4. let the backend call it only when `RAG` is enabled
