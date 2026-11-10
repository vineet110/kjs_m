from fastapi import APIRouter

from app.api.v1.endpoints import admin, assign, attendance, auth, boards, chat, content, employee, files, koko, public, tasks

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(public.router, prefix="/public", tags=["Public"])
api_router.include_router(koko.router, prefix="/koko", tags=["Koko AI"])
api_router.include_router(employee.router, prefix="/employee", tags=["Employee"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
api_router.include_router(attendance.router, prefix="/attendance", tags=["Attendance"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
api_router.include_router(files.router, prefix="/files", tags=["Files"])
api_router.include_router(boards.router, prefix="/boards", tags=["Order boards"])
api_router.include_router(assign.router, prefix="/assign", tags=["Auto-assign"])
api_router.include_router(content.router, prefix="/content", tags=["Website content"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
