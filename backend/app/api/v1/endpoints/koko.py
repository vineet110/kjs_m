from fastapi import APIRouter

router = APIRouter()

@router.post("/chat")
async def koko_chat():
    return {"reply": "I am Koko. How can I assist you with KJS manufacturing & packaging services?"}
