from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import client_ip
from app.core.rate_limit import koko_limiter
from app.core.security import hash_ip
from app.schemas.lead import KokoIn, KokoOut
from app.services import koko_service

router = APIRouter()


@router.post("/chat", response_model=KokoOut)
async def koko_chat(data: KokoIn, request: Request, db: AsyncSession = Depends(get_db)):
    koko_limiter.check(hash_ip(client_ip(request)))  # so nobody can burn our LLM quota
    reply, suggest = await koko_service.reply(db, data.messages)
    return KokoOut(reply=reply, suggest_enquiry=suggest)
