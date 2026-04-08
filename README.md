# Chatchat

Local chat workspace with:
- host Ollama inference
- FastAPI backend
- React frontend
- built-in Obsidian RAG (markdown only)

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
OBSIDIAN_VAULT_HOST_PATH=E:/360MoveData/Users/29220/Documents/COLIN_all_in_one_note
RAG_VAULT_PATH=/data/obsidian
RAG_INDEX_PATH=/app/storage/rag/index.json
RAG_EMBEDDING_MODEL=nomic-embed-text
RAG_TOP_K=4
RAG_SECTION_MAX_CHARS=1400
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

## Multi-Env Setup

Backend config now supports layered env files:

- default: `backend/.env`
- named env: set `CHATCHAT_ENV=<name>` to also load `backend/.env.<name>`
- explicit file: set `CHATCHAT_ENV_FILE=<path>` to load an additional env file

Examples:

```powershell
$env:CHATCHAT_ENV = "dev.windows"
python app.py --reload
```

```bash
CHATCHAT_ENV=deploy.wsl python app.py --host 0.0.0.0 --port 8000
```

Reference templates:

- [backend/.env.dev.windows.example](backend/.env.dev.windows.example)
- [backend/.env.deploy.wsl.example](backend/.env.deploy.wsl.example)

Copy them to real env files before use, for example:

- `backend/.env.dev.windows`
- `backend/.env.deploy.wsl`

### SSH Tunnel For Remote Model Router

If your OpenAI-compatible model service is reachable only through SSH, open a local tunnel first:

```bash
ssh -N -L 18000:127.0.0.1:8000 user@remote-host
```

Then point:

```env
OPENAI_LOCAL_BASE_URL=http://127.0.0.1:18000/v1
OPENAI_LOCAL_API_KEY=sk-local
```

If the tunnel runs on Windows but the backend runs inside WSL2 or Docker, use the address reachable from that runtime instead of blindly reusing Windows paths.

### Audio Dependency

Audio transcription is now optional. If `funasr` is not installed in the current environment, disable it:

```env
AUDIO_TRANSCRIPTION_ENABLED=false
AUDIO_TRANSCRIPTION_EAGER_LOAD=false
```

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

Build Obsidian RAG index (markdown files split by `##`):

```bash
curl -X POST http://127.0.0.1:8000/api/rag/reindex
```

Check RAG status:

```bash
curl http://127.0.0.1:8000/api/rag/status
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
- Mounts Obsidian vault read-only at `/data/obsidian`
- Indexes `.md` files and retrieves context when `RAG` is enabled

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

## RAG Notes

Current implementation:
1. scans only `.md` files
2. splits by level-2 headings (`##`)
3. embeds sections with `nomic-embed-text` via host Ollama
4. injects retrieved sections as system context when `RAG` toggle is on
