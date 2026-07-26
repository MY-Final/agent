# Repository Guidelines

## Project Structure & Module Organization

The repository contains `backend/` and `desktop/`. FastAPI starts from `backend/app/main.py`; keep routes in `app/api/v1/`, models in `app/models/`, schemas in `app/schemas/`, orchestration in `app/services/`, tender logic in `app/skills/`, and LangGraph code in `app/agent/`. The Vue/Tauri client lives in `desktop/`: API wrappers are in `src/api/`, pages in `src/views/`, shared UI in `src/components/`, Pinia stores in `src/stores/`, and Rust/Tauri configuration in `src-tauri/`. Uploaded documents remain in MinIO.

## Build, Test, and Development Commands

Run commands from `backend/` in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m app
```

Use `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` for hot reload. Verify startup at `/health` and inspect routes at `/docs`. Before submitting changes, run:

```powershell
python -m compileall -q app
python -m pip check
git diff --check
```

Run the desktop app from `desktop/`:

```powershell
npm install
npm run type-check
npm run tauri dev
```

## Coding Style & Naming Conventions

Target Python 3.11+, use four-space indentation, complete type annotations, and `snake_case` for modules/functions. For Vue, use TypeScript, two-space indentation, `PascalCase.vue` components, and camelCase identifiers. Keep backend I/O asynchronous and frontend requests inside `src/api/`. Preserve the response shape `{"code": 0, "msg": "中文说明", "data": ...}` while keeping protocol status values such as `completed` in English. Add comments only where control flow is non-obvious.

## Testing Guidelines

No automated suite or coverage threshold is configured yet. For API changes, exercise the affected route through Swagger or Apifox and verify PostgreSQL, Redis, and MinIO behavior. Agent changes must cover start, `wait_confirm`, restart recovery, confirm, completion, and duplicate-action conflicts. For desktop changes, run `npm run type-check`, `npm run build`, and manually verify the main workflow. New backend tests go in `backend/tests/` as `test_*.py`; frontend tests should live beside the feature or in `desktop/src/__tests__/`.

## Commit & Pull Request Guidelines

History follows Conventional Commit-style subjects with Chinese descriptions, for example `feat: 实现 LangGraph 单任务分析 Agent 流程`. Keep commits focused and use an appropriate prefix such as `feat:`, `fix:`, or `docs:`. Pull requests should summarize behavior changes, list verification commands, identify schema/config changes, and include representative API request/response examples.

## Security & Configuration

Never commit `backend/.env`, API keys, database passwords, or MinIO credentials. Update `.env.example` only with placeholders. Treat uploaded tender files and parsed results as sensitive data, and clean up temporary test records and LangGraph checkpoints after integration testing.
