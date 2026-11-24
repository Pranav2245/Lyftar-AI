"""
Backend tests for Lyftr AI.
Uses the FastAPI test client with a temporary SQLite DB and mocked LLM calls.
"""
import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock

# Add parent of backend/ to sys.path so we can import backend.app.*
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# Configure env BEFORE importing the app
os.environ["DATABASE_URL"] = "sqlite:///./test_data/test.db"
os.environ["LLM_API_KEYS"] = "test_key_1,test_key_2"
os.environ["ENABLE_FAILURE_SIMULATION"] = "true"
os.environ["LLM_MODEL"] = "gpt-3.5-turbo"

os.makedirs("test_data", exist_ok=True)

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import Base, engine
from backend.app.llm_service import _response_cache

# Reset DB for every test module run
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helper: mock litellm.completion
# ---------------------------------------------------------------------------
def _mock_completion(**kwargs):
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = "Mocked reply"
    mock_resp.usage.prompt_tokens = 10
    mock_resp.usage.completion_tokens = 5
    return mock_resp


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the in-memory LLM cache before each test."""
    _response_cache.clear()
    yield
    _response_cache.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_ok(self):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["keys_configured"] == 2
        assert data["cache_enabled"] is True


class TestChat:
    @patch("backend.app.llm_service.litellm.completion", side_effect=_mock_completion)
    def test_basic_chat(self, mock_llm):
        r = client.post("/chat", json={
            "session_id": "test-s1",
            "message": "Hello",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["session_id"] == "test-s1"
        assert data["reply"] == "Mocked reply"
        meta = data["metadata"]
        assert meta["resolution_source"] == "LIVE_INFERENCE"
        assert meta["model"] == "gpt-3.5-turbo"
        assert isinstance(meta["latency_ms"], int)
        assert meta["input_tokens"] == 10
        assert meta["output_tokens"] == 5
        assert meta["key_id"] == "key_1"
        assert meta["fallback_attempts"] == 0

    @patch("backend.app.llm_service.litellm.completion", side_effect=_mock_completion)
    def test_cache_hit(self, mock_llm):
        """Same message in a NEW session should hit cache (same full_messages)."""
        # First call
        r1 = client.post("/chat", json={
            "session_id": "cache-s1",
            "message": "Cache test",
        })
        assert r1.status_code == 200
        assert r1.json()["metadata"]["resolution_source"] == "LIVE_INFERENCE"

        # Second call with a different session but identical first message
        r2 = client.post("/chat", json={
            "session_id": "cache-s2",
            "message": "Cache test",
        })
        assert r2.status_code == 200
        assert r2.json()["metadata"]["resolution_source"] == "LLM_CACHE"
        assert r2.json()["metadata"]["key_id"] is None

    def test_missing_message(self):
        r = client.post("/chat", json={"session_id": "s1"})
        assert r.status_code == 422

    def test_empty_message(self):
        r = client.post("/chat", json={"session_id": "s1", "message": "   "})
        assert r.status_code == 422

    def test_missing_session_id(self):
        r = client.post("/chat", json={"message": "hi"})
        assert r.status_code == 422


class TestFailover:
    @patch("backend.app.llm_service.litellm.completion", side_effect=_mock_completion)
    def test_simulate_key1_fail(self, mock_llm):
        r = client.post("/chat",
            json={"session_id": "fail-s1", "message": "Failover test"},
            headers={"X-Simulate-Failure": "key_1=429"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["metadata"]["key_id"] == "key_2"
        assert data["metadata"]["fallback_attempts"] == 1

    @patch("backend.app.llm_service.litellm.completion", side_effect=_mock_completion)
    def test_simulate_all_fail(self, mock_llm):
        r = client.post("/chat",
            json={"session_id": "fail-s2", "message": "All fail test"},
            headers={"X-Simulate-Failure": "*=429"},
        )
        assert r.status_code == 503
        assert r.json()["detail"] == "all providers unavailable"


class TestSessions:
    @patch("backend.app.llm_service.litellm.completion", side_effect=_mock_completion)
    def test_get_session_history(self, mock_llm):
        sid = "hist-s1"
        client.post("/chat", json={"session_id": sid, "message": "First"})
        r = client.get(f"/sessions/{sid}/messages")
        assert r.status_code == 200
        data = r.json()
        assert data["session_id"] == sid
        assert len(data["messages"]) == 2  # user + assistant
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][1]["role"] == "assistant"

    def test_unknown_session(self):
        r = client.get("/sessions/nonexistent-999/messages")
        assert r.status_code == 404
        assert r.json()["detail"] == "session not found"
