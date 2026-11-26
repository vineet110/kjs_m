from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config.ini import cfg
from app.core.errors import AppError
from app.core.deps import visitor_keys
from app.core.rate_limit import koko_limiter
from app.schemas.lead import ChatMessage, KokoIn, KokoOut
from app.services import content_service, koko_service

router = APIRouter()


@router.post("/chat", response_model=KokoOut)
async def koko_chat(data: KokoIn, request: Request, db: AsyncSession = Depends(get_db)):
    if not cfg().features.koko:  # switched off in config/features.ini: no AI calls at all (CR8)
        raise AppError(404, "feature_off", "Koko is not available right now.")
    ip_hash, rate = visitor_keys(request)
    koko_limiter.check(rate)  # so nobody can burn our LLM quota
    # The browser sends the whole chat, Koko's past replies included, so a visitor could put words in Koko's
    # mouth (R71). What Koko said comes from our saved transcript; from the browser only the new question.
    # No saved transcript (first message, or the visitor's network changed): only the visitor's own lines.
    question = data.messages[-1]
    stored = await content_service.stored_chat(db, data.chat_id, ip_hash)
    if stored:
        # (a saved reply can be longer than a visitor's message may be: cut, never refused)
        past = [ChatMessage(role=m["role"], content=str(m["content"])[:2000]) for m in stored[-18:]]
        while past and past[0].role != "user":  # the model's history starts with the visitor
            past.pop(0)
        messages = past + [question]
    else:
        messages = [m for m in data.messages if m.role == "user"]
    first = not stored and not any(m.role == "assistant" for m in data.messages)  # only decides the card
    reply, suggest, card = await koko_service.reply(db, messages, data.page, first=first)
    if data.chat_id:  # keep the transcript (Admin > Koko) so we can improve the facts
        earlier = stored if stored else [m.model_dump() for m in messages[:-1]]  # the whole saved chat, not the cut
        convo = earlier + [question.model_dump(), {"role": "assistant", "content": reply}]
        await content_service.save_chat(db, data.chat_id, data.page, convo, suggest, ip_hash)
    return KokoOut(reply=reply, suggest_enquiry=suggest, catalogue=card)
