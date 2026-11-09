from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config.ini import cfg
from app.core.errors import AppError
from app.core.deps import visitor_keys
from app.core.rate_limit import koko_limiter
from app.schemas.lead import KokoIn, KokoOut
from app.services import content_service, koko_service

router = APIRouter()


@router.post("/chat", response_model=KokoOut)
async def koko_chat(data: KokoIn, request: Request, db: AsyncSession = Depends(get_db)):
    if not cfg().features.koko:  # switched off in config/features.ini: no AI calls at all (CR8)
        raise AppError(404, "feature_off", "Koko is not available right now.")
    ip_hash, rate = visitor_keys(request)
    koko_limiter.check(rate)  # so nobody can burn our LLM quota
    reply, suggest = await koko_service.reply(db, data.messages)
    if data.chat_id:  # keep the transcript (Admin > Koko) so we can improve the facts
        convo = [m.model_dump() for m in data.messages] + [{"role": "assistant", "content": reply}]
        await content_service.save_chat(db, data.chat_id, data.page, convo, suggest, ip_hash)
    return KokoOut(reply=reply, suggest_enquiry=suggest)
