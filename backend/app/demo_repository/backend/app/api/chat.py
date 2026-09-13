from app.services.ai import generate_reply
from fastapi import APIRouter

router = APIRouter()

@router.post("/api/chat")
async def chat(payload: dict[str, str]) -> dict[str, str]:
    return {"reply": generate_reply(payload["message"])}
