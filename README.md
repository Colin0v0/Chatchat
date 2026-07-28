# Chatchat

[简体中文](README.zh-CN.md) | English

Chatchat is a self-hosted AI workspace for individuals and teams. It brings multi-model chat, private knowledge retrieval, multimodal attachments, voice features, memory management, and per-user data isolation into one web application.

## Features

- Multi-model chat through a configurable provider and model catalog.
- Streaming responses with text, reasoning, sources, and context events.
- Private knowledge bases with vector retrieval, reranking, and query rewriting.
- Optional web search with cited sources in the chat context.
- Image and document attachments, plus audio transcription and text-to-speech.
- Global, conversation, work, candidate, and document memories.
- User-scoped accounts, conversations, knowledge bases, memories, and settings.

## Architecture

```text
Chatchat/
  backend/      FastAPI, SQLAlchemy, and model orchestration
  dev/          Local development and build helpers
  frontend/     React, Vite, and TypeScript workspace
  docs/         Architecture, feature, configuration, and deployment docs
  storage/      Runtime user data (ignored by Git)
```

## Quick start

Prerequisites: Python, Node.js with pnpm, Docker, Docker Compose, PostgreSQL, and Redis.

```bash
# Start PostgreSQL and Redis for local development.
docker compose -f dev/docker-compose.dev-infra.yml up -d

# Create your local backend configuration. Never commit this file.
cp backend/.env.example backend/.env

# Start the backend.
cd backend
python app.py --reload --host 127.0.0.1 --port 8050
```

In another terminal:

```bash
cd frontend
pnpm install
pnpm dev
```

Edit `backend/.env` to configure at least one model provider and set `DEFAULT_PROVIDER` and `DEFAULT_MODEL`. See the [local development guide](dev/README.md) for details.

## Configuration and privacy

- `backend/.env` contains local configuration and API keys. It is ignored by Git.
- `storage/` contains runtime data such as uploaded files, generated media, and knowledge-base source files. It is ignored by Git.
- `backend/.env.example` contains safe placeholders only; use it as the configuration template.
- When deploying publicly, use a strong account password, restrict `CORS_ALLOWED_ORIGINS`, and enable `AUTH_COOKIE_SECURE=true` behind HTTPS.

## Documentation

- [Documentation index](docs/README.md)
- [Architecture](docs/architecture.md)
- [Configuration](docs/configuration.md)
- [Deployment](docs/deployment.md)
- [Development](docs/development.md)

## Development

Run backend tests:

```bash
PYTHONPATH=backend python -m pytest backend/tests
```

Build the frontend:

```bash
cd frontend
pnpm build
```

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) and report vulnerabilities according to [SECURITY.md](SECURITY.md).

## License

Chatchat is released under the [MIT License](LICENSE).
