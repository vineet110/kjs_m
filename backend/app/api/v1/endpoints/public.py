from fastapi import APIRouter

router = APIRouter()

@router.get("/offers")
async def get_active_offers():
    return [{"id": 1, "text": "Instant Coffee spray-dried batches ready for Q4 dispatch"}]

@router.post("/leads")
async def create_category_lead():
    return {"status": "lead_created", "visitor_id": "v_sample_cookie"}
