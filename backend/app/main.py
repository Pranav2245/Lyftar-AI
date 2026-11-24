import os
import json
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from .database import engine, Base, get_db
from .models import Message
from .llm_service import get_chat_response

# ---------------------------------------------------------------------------
# Create tables on startup
# ---------------------------------------------------------------------------
Base.metadata.create_all(bind=engine)

app = FastAPI()

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    message: str = Field(..., min_length=1, max_length=4000)
    system_prompt: Optional[str] = None

    @field_validator("message")
    @classmethod
    def trim_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message cannot be empty after trimming")
        if len(v) > 4000:
            raise ValueError("message must be at most 4000 characters")
        return v


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    keys = [k.strip() for k in os.getenv("LLM_API_KEYS", "").split(",") if k.strip()]
    return {
        "status": "ok",
        "keys_configured": len(keys),
        "cache_enabled": True,
    }


# ---------------------------------------------------------------------------
# POST /chat
# ---------------------------------------------------------------------------
@app.post("/chat")
def chat_endpoint(
    request: ChatRequest,
    db: Session = Depends(get_db),
    x_simulate_failure: Optional[str] = Header(None, alias="X-Simulate-Failure"),
):
    now = datetime.now(timezone.utc).isoformat()

    # Retrieve prior history for this session
    history = (
        db.query(Message)
        .filter(Message.session_id == request.session_id)
        .order_by(Message.created_at)
        .all()
    )

    # Build messages list for LLM
    llm_messages: List[Dict[str, str]] = []
    if request.system_prompt:
        llm_messages.append({"role": "system", "content": request.system_prompt})
    for msg in history:
        llm_messages.append({"role": msg.role, "content": msg.content})
    llm_messages.append({"role": "user", "content": request.message})

    # Call LLM service (handles cache + fallback)
    result = get_chat_response(
        session_id=request.session_id,
        full_messages=llm_messages,
        simulate_header=x_simulate_failure,
    )

    # Persist user message
    user_msg = Message(
        session_id=request.session_id,
        role="user",
        content=request.message,
        metadata_json=None,
        created_at=now,
    )
    db.add(user_msg)

    # Persist assistant message
    assistant_msg = Message(
        session_id=request.session_id,
        role="assistant",
        content=result["reply"],
        metadata_json=json.dumps(result["metadata"]),
        created_at=now,
    )
    db.add(assistant_msg)
    db.commit()

    return result


# ---------------------------------------------------------------------------
# GET /sessions/{session_id}/messages
# ---------------------------------------------------------------------------
@app.get("/sessions/{session_id}/messages")
def get_session_messages(session_id: str, db: Session = Depends(get_db)):
    msgs = (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.created_at)
        .all()
    )
    if not msgs:
        raise HTTPException(status_code=404, detail="session not found")

    out_messages: List[Dict[str, Any]] = []
    for m in msgs:
        item: Dict[str, Any] = {"role": m.role, "content": m.content}
        if m.role == "assistant" and m.metadata_json:
            try:
                meta = json.loads(m.metadata_json)
                item["metadata"] = {
                    "resolution_source": meta.get("resolution_source"),
                    "input_tokens": meta.get("input_tokens"),
                    "output_tokens": meta.get("output_tokens"),
                }
            except Exception:
                item["metadata"] = {}
        out_messages.append(item)
    return {"session_id": session_id, "messages": out_messages}
