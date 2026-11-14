from fastapi import APIRouter

from app.api.v1.endpoints import admin, assign, attendance, auth, boards, chat, complaints, content, employee, files, harvest, koko, public, tasks
from app.core.modules import area

api_router = APIRouter()
# `dependencies=area(...)`: every route of that router belongs to one portal area (config/modules.ini)

api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(public.router, prefix="/public", tags=["Public"])
api_router.include_router(koko.router, prefix="/koko", tags=["Koko AI"])
api_router.include_router(employee.router, prefix="/employee", tags=["Employee"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])  # areas set per route
api_router.include_router(harvest.router, prefix="/admin/harvest", tags=["Lead Harvester"],
                          dependencies=area("lead_harvester"))
api_router.include_router(attendance.router, prefix="/attendance", tags=["Attendance"], dependencies=area("attendance"))
api_router.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
api_router.include_router(complaints.router, prefix="/complaints", tags=["Complaints"])  # always on, no area
api_router.include_router(files.router, prefix="/files", tags=["Files"])  # area of each file's owner: file_service
api_router.include_router(boards.router, prefix="/boards", tags=["Order boards"], dependencies=area("order_boards"))
api_router.include_router(assign.router, prefix="/assign", tags=["Auto-assign"], dependencies=area("batches"))
api_router.include_router(content.router, prefix="/content", tags=["Website content"],
                          dependencies=area("website_admin"))
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"], dependencies=area("chat"))
# The live connection has no Request, so a route dependency would break it: it checks the area itself
api_router.include_router(chat.ws_router, prefix="/chat", tags=["Chat"])
