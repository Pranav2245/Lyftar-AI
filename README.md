# LLM Chatbot with Key Failover and Response Caching

A resilient full-stack AI chat application built with React, FastAPI, SQLite, and LiteLLM. Implements multi-turn conversational context, automatic key pool failover, and request-level in-memory response caching.

---

## 1. Live URLs
- **Frontend URL:** [Deploy to Vercel/Netlify and place URL here]
- **Backend URL:** [Deploy to Render/Railway and place URL here]
- **Health Endpoint:** `[BACKEND_URL]/health`

---

## 2. Run Locally

### With Docker (Recommended)
Make sure Docker and Docker Compose are installed.

```bash
# Start both frontend and backend
make up

# Stop services
make down
```
- Frontend will be available at: `http://localhost:3000`
- Backend API will be available at: `http://localhost:8000`
- SQLite database is persisted under Docker volume mounted at `/data/app.db`.

### Without Docker

#### Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env  # update your API keys in .env
uvicorn backend.app.main:app --env-file ../.env --host 0.0.0.0 --port 8000
```

#### Frontend
```bash
cd frontend
npm install
npm run dev
```
Visit `http://localhost:3000` in your browser.

#### Running Tests
```bash
pytest -q backend/tests/test_backend.py
```

---

## 3. Design Decisions

### Key Fallback Architecture
- The key pool supports any number of keys specified in `LLM_API_KEYS` (ordered `key_1`, `key_2`, ...).
- On each incoming request, the backend iterates sequentially through the pool.
- If a provider encounters a transient failure (`429 RateLimit`, `500`, `502`, `503`, or connection error), it increments `fallback_attempts` and seamlessly falls back to the next configured key.
- The user never experiences an unhandled crash or broken UI. If all configured keys fail, a structured `503 {"detail": "all providers unavailable"}` is returned.

### Response Caching
- Cache key is computed using a deterministic SHA-256 hash of the model name combined with the exact full message array (`system prompt + session history + new message`).
- When a cached resolution is hit:
  - Returns `resolution_source: "LLM_CACHE"`
  - `key_id: null`
  - `fallback_attempts: 0`
  - Token counts reflect the stored generation tokens.
  - Latency is near 0ms, faster than any network inference.

### Storage & Resilience
- Stored using SQLite via SQLAlchemy with `check_same_thread=False`.
- Session messages persist both `user` and `assistant` turns, tracking ISO-8601 UTC timestamps and serialization metadata for auditing.
- Container restarts retain all history via Docker volume `/data`.

### Failure Simulation Hook
- Supports request header `X-Simulate-Failure: <key_id>=<status>` (e.g., `key_1=429`, `*=429`).
- Active only when `ENABLE_FAILURE_SIMULATION=true`.
