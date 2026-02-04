# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LLM Smart Router - intelligent routing between local LLM (rnj-1 via LM Studio) and cloud models (Claude, Kimi, GPT-4o, Gemini). Hybrid Node.js + Python codebase with a PySide6 GUI, FastAPI REST API, and a Node.js router entry point.

## Commands

### Python Tests
```bash
pytest tests/ -v                          # All tests
pytest tests/test_conversation.py -v      # Conversation tests only
pytest tests/test_suite.py -v             # Integration suite (requires PySide6)
pytest -m "not slow" tests/ -v            # Skip slow tests
```

Note: `pytest.ini` sets `testpaths = src/tests` but the actual test files live in `tests/` at project root. Use explicit paths.

### Node.js Router
```bash
node router.js "question text"            # Direct routing
npm test                                  # Run test.js
```

### API Server
```bash
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

### GUI
```bash
python src/gui/main_window.py
```

### Conversation CLI
```bash
python -m conversation list
python -m conversation search "<query>"
python -m conversation export <id>
```

### Auto-Launch Chain
```bash
python -m launcher                  # フルチェーン実行
python -m launcher --skip-discord   # Discord Bot スキップ
python -m launcher --dry-run        # プレビュー
python -m launcher -v               # 詳細ログ
auto_launch.bat                     # Windows バッチ起動
```

## Architecture

### Dual Runtime
- **Node.js** (`router.js`): Main routing engine. Reads `config.yaml`, applies hard rules (deterministic triggers) then soft rules (weighted scoring), calls local or cloud model via HTTP/SDK.
- **Python** (`src/`): GUI, API server, conversation persistence, caching, security. Entry points are `src/api/main.py` (FastAPI), `src/gui/main_window.py` (PySide6), and `src/conversation/__main__.py` (CLI).

### Model Adapter Pattern
`src/models/base_model.py` defines `BaseModelAdapter` (ABC). Each model adapter implements `generate()`, `generate_stream()`, `count_tokens()`, `validate_config()`. Concrete adapters: `kimi_adapter.py`, `gpt4o_adapter.py`, `gemini_adapter.py`. Returns standardized `ModelResponse` dataclass.

### Routing Logic (config.yaml)
- **Hard rules**: keyword triggers → deterministic model selection (e.g., business terms → Claude, coding → Kimi)
- **Soft rules**: weighted scoring based on complexity, input size, cost
- **Intelligent triage**: local model evaluates task and returns JSON with model recommendation + confidence score
- **Fallback chain**: configurable per-rule fallback models

### Conversation System
`ConversationManager` (observer pattern) manages sessions with callbacks for UI updates. Uses file-based JSON storage. `ConversationDB` (`db_manager.py`) provides SQLite persistence. Both coexist — the manager is for in-memory/file ops, the DB for structured queries.

### Exception Hierarchy
`src/exceptions.py`: `LLMRouterError` base with `retryable` flag. Key subtypes: `APIError` (5xx = retryable), `AuthenticationError` (not retryable), `RateLimitError` (retryable with backoff), `AllModelsFailedError`. Use `is_retryable_error()` helper.

### Auto-Launch Chain
`src/launcher/orchestrator.py`: Sequentially launches LM Studio → model detection → OpenClaw verification → Discord Bot. Each stage has health check, retry, timeout, and dependency awareness. `ProcessManager` (`process_manager.py`) manages child processes with named registry. `LMStudioLauncher` (`lmstudio_launcher.py`) auto-detects and launches LM Studio. CLI entry point: `src/launcher/__main__.py`.

### Caching
`src/cache/sqlite_cache.py`: SQLite-based with TTL, thread-safe (RLock). Supports exact match and similarity-based lookup. Exclusion patterns for sensitive/realtime queries configured in `config.yaml`.

### Key Data Models
- `Conversation`: id, title, status (active/paused/closed/archived), topic_id, metadata
- `Message`: role (user/assistant/system), content, model, tokens
- `Topic`: hierarchical categorization with parent_id

## Test Infrastructure

- **conftest.py**: Provides `conversation_db`, `conversation_manager`, `factory` (ConversationFactory) fixtures, plus `EDGE_CASE_STRINGS` for parameterized edge case testing
- **Markers**: `@pytest.mark.slow`, `@pytest.mark.integration`, `@pytest.mark.edge_case`
- **Assertion helpers**: `assert_conversation_exists()`, `assert_message_count()`, `assert_topic_exists()` from conftest

## Configuration

- `config.yaml`: Model definitions, routing rules, cost pricing, cache settings, async concurrency limits
- `.env` / `.env.example`: API keys (`ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`), `LM_STUDIO_ENDPOINT`, `LM_STUDIO_PATH`, `DISCORD_BOT_TOKEN`, `DISCORD_PREFIX`, `LOG_LEVEL`, `EXCHANGE_RATE`
- CORS origins configured via `ALLOWED_ORIGINS` env var (comma-separated)

## Language & Conventions

- Project documentation and comments are in Japanese
- Python source lives under `src/` with `sys.path` manipulation to resolve imports (no installed package)
- GUI tests require PySide6 and a display context
