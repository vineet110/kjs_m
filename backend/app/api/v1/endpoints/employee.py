from fastapi import APIRouter

router = APIRouter()

@router.patch("/me/availability")
async def update_availability(is_available: bool):
    return {"status": "updated", "is_available": is_available}
