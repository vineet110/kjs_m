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
    # No saved transcript (first message, or an old weak chat id from another network): only the visitor's lines.
    question = data.messages[-1]
    # Only rows shaped like a chat line (an odd saved row, e.g. from older code, must never cause a 500)
    stored = [m for m in await content_service.stored_chat(db, data.chat_id, ip_hash) or [] if isinstance(m, dict)]
    # The same question sent again because its answer never arrived (the widget retries after a time-out):
    # answer it again in place, don't save it twice. Only when the browser has no reply after it: a visitor
    # who really says "yes" twice keeps Koko's question in between (re-review of #134)
    browser_got_reply = len(data.messages) >= 2 and data.messages[-2].role == "assistant"
    retry = (not browser_got_reply and len(stored) >= 2 and stored[-2].get("role") == "user"
             and stored[-2].get("content") == question.content and stored[-1].get("role") == "assistant")
    if retry:
        stored = stored[:-2]
    message_max, chat_max = cfg().koko.message_max, cfg().koko.chat_max
    if stored or retry:  # a retry with nothing saved left still uses only the question, never it twice
        past = []
        for m in stored:
            try:  # an odd saved row is skipped, never a 500 for the rest of the chat
                if not isinstance(m.get("content"), str):
                    continue  # a missing or null text is skipped, never sent as the word "None"
                past.append(ChatMessage(role=m["role"], content=m["content"][:message_max]))
            except Exception:  # noqa: BLE001
                continue
        # the newest lines that fit the same total as a request from the browser, starting with the visitor
        room = chat_max - len(question.content)
        while past and (sum(len(m.content) for m in past) > room or past[0].role != "user"):
            past.pop(0)
        messages = past + [question]
    else:
        # No saved chat: only the visitor's own lines, the newest that fit chat_max
        messages = [m for m in data.messages if m.role == "user"]
        while len(messages) > 1 and sum(len(m.content) for m in messages) > chat_max:
            messages.pop(0)
    # Only decides the catalogue card: first = no Koko line saved (a retried answer was just taken off, so a
    # reply that never arrived still gets its card) and none in the browser either
    first = not any(m.get("role") == "assistant" for m in stored) and not any(m.role == "assistant" for m in data.messages)
    reply, suggest, card = await koko_service.reply(db, messages, data.page, first=first)
    # Keep the transcript (Admin > Koko): appended under a row lock, never another visitor's chat (append_chat)
    if data.chat_id:
        await content_service.append_chat(db, data.chat_id, data.page, question.model_dump(),
                                          {"role": "assistant", "content": reply}, suggest, ip_hash, retry=retry)
    return KokoOut(reply=reply, suggest_enquiry=suggest, catalogue=card)
