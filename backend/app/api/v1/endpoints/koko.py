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
    await db.commit()  # give the connection back before the slow AI call
    # The same question sent again because its answer never arrived (the widget retries after a time-out):
    # answer it again in place, don't save it twice. Told apart by the question's turn id: the widget makes a
    # new one for every question it sends and keeps it when it repeats the request, so a visitor who really
    # asks the same thing again (or gets the same fixed reply twice) is never mistaken for a retry. An old
    # widget with no turn id: never a retry (at worst a question is saved twice).
    # (Known, accepted: an answer that never arrived stays in the AI's history if the visitor then asks
    # something else. Rare and harmless.)
    retry = content_service.is_retry_of(stored, data.turn_id)
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
            except (KeyError, TypeError, ValueError, AttributeError):  # (pydantic's ValidationError is a ValueError)
                continue
        # the newest lines that fit the same total as a request from the browser, starting with the visitor
        room = chat_max - len(question.content)
        while past and (sum(len(m.content) for m in past) > room or past[0].role != "user"):
            past.pop(0)
        messages = past + [question]
    else:
        # No saved chat: the visitor's own lines (the browser's Koko lines can't be trusted), newest within
        # chat_max. Kept, not just the last question: Koko picks products from earlier questions too ("and the
        # pack sizes?" after a coffee question)
        messages = [m for m in data.messages if m.role == "user"]
        while len(messages) > 1 and sum(len(m.content) for m in messages) > chat_max:
            messages.pop(0)
    # Only decides the catalogue card: first = no Koko line saved (a retried answer was just taken off, so a
    # reply that never arrived still gets its card) and none in the browser either
    first = not any(m.get("role") == "assistant" for m in stored) and not any(m.role == "assistant" for m in data.messages)
    reply, suggest, card = await koko_service.reply(db, messages, data.page, first=first)
    # Keep the transcript (Admin > Koko): appended under a row lock, never another visitor's chat (append_chat)
    if data.chat_id:
        saved_question = {**question.model_dump(), **({"turn": data.turn_id} if data.turn_id else {})}
        await content_service.append_chat(db, data.chat_id, data.page, saved_question,
                                          {"role": "assistant", "content": reply}, suggest, ip_hash)
    return KokoOut(reply=reply, suggest_enquiry=suggest, catalogue=card)
