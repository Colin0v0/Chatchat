# Local Development

This directory contains local development and build helpers.

## Files

- `docker-compose.dev-infra.yml`: local PostgreSQL + Redis for development.
- `docker-compose.build.yml`: optional image build helper.

The production compose file stays at the repository root as `docker-compose.yml`.

## Ports

Default local ports:

- Frontend: `http://127.0.0.1:5200`
- Backend: `http://127.0.0.1:8050`
- PostgreSQL: `127.0.0.1:5433`
- Redis: `127.0.0.1:6380`

## 1. Start Local Infrastructure

From the repository root:

```bash
docker compose -f dev/docker-compose.dev-infra.yml up -d
```

Check status:

```bash
docker compose -f dev/docker-compose.dev-infra.yml ps
```

Stop local infrastructure:

```bash
docker compose -f dev/docker-compose.dev-infra.yml down
```

Remove local database/cache volumes:

```bash
docker compose -f dev/docker-compose.dev-infra.yml down -v
```

## 2. Configure Backend

Create or update `backend/.env` or a named environment file loaded through `CHATCHAT_ENV`.

Minimum local infrastructure values:

```env
DATABASE_URL=postgresql+psycopg://chatchat_dev:chatchat_dev@127.0.0.1:5433/chatchat_dev
REDIS_URL=redis://127.0.0.1:6380/0
MODEL_CATALOG_PATH=./model_catalog.json
DEFAULT_PROVIDER=
DEFAULT_MODEL=
```

At least one model provider must be configured before chat requests can succeed.

## 3. Run Backend

Generic command:

```bash
cd backend
python app.py --reload --host 127.0.0.1 --port 8050
```

Windows PowerShell helper:

```powershell
cd backend
.\scripts\run_dev_backend.ps1
```

The PowerShell helper bootstraps the development database schema, applies Alembic migrations, and starts the backend with reload enabled.

## 4. Run Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

The Vite dev server proxies `/api` and `/media` to `http://127.0.0.1:8050` by default.

To point the frontend at another backend:

```bash
CHATCHAT_DEV_API_ORIGIN=http://127.0.0.1:8050 pnpm dev
```

## 5. Common Commands

Run backend tests:

```bash
PYTHONPATH=backend python -m pytest backend/tests
```

Build frontend:

```bash
cd frontend
pnpm build
```

Create a local user:

```bash
cd backend
python scripts/create_user.py --username alice --password secret123
```

## Notes

- Do not commit real API keys in environment files.
- Keep local-only overrides out of public docs.
- Use provider configuration and `backend/model_catalog.json` to enable models.
