from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config.ini import cfg
from app.core.errors import AppError
from app.core.deps import visitor_keys
from app.core.rate_limit import koko_limiter
from app.schemas.lead import CHAT_MAX, MESSAGE_MAX, ChatMessage, KokoIn, KokoOut
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
    stored = await content_service.stored_chat(db, data.chat_id, ip_hash) or []
    # The same question sent again (the widget retries after a time-out): answer it again in place, don't
    # save it twice
    if (len(stored) >= 2 and stored[-2].get("role") == "user" and stored[-2].get("content") == question.content
            and stored[-1].get("role") == "assistant"):
        stored = stored[:-2]
    if stored:
        past = []
        for m in stored:
            try:  # an odd saved row is skipped, never a 500 for the rest of the chat
                past.append(ChatMessage(role=m["role"], content=str(m["content"])[:MESSAGE_MAX]))
            except Exception:  # noqa: BLE001
                continue
        # the newest lines that fit the same total as a request from the browser, starting with the visitor
        room = CHAT_MAX - len(question.content)
        while past and (sum(len(m.content) for m in past) > room or past[0].role != "user"):
            past.pop(0)
        messages = past + [question]
    else:
        messages = [m for m in data.messages if m.role == "user"]
    # Only decides the catalogue card: from what the browser has shown (the widget keeps its own error lines
    # to itself), so a reply that never arrived still gets its card next time
    first = not any(m.role == "assistant" for m in data.messages)
    reply, suggest, card = await koko_service.reply(db, messages, data.page, first=first)
    if data.chat_id:  # keep the transcript (Admin > Koko) so we can improve the facts
        earlier = stored if stored else [m.model_dump() for m in messages[:-1]]  # the whole saved chat, not the cut
        convo = earlier + [question.model_dump(), {"role": "assistant", "content": reply}]
        await content_service.save_chat(db, data.chat_id, data.page, convo, suggest, ip_hash)
    return KokoOut(reply=reply, suggest_enquiry=suggest, catalogue=card)
