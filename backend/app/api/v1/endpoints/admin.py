from fastapi import APIRouter

router = APIRouter() // object creation.

@router.get("/stats")
async def get_admin_stats():
    return {"total_tasks": 142, "completed": 98, "pending": 44}
