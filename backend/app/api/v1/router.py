from fastapi import APIRouter

from app.api.v1.endpoints import admin, auth, employee, koko, public

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(public.router, prefix="/public", tags=["Public"])
api_router.include_router(koko.router, prefix="/koko", tags=["Koko AI"])
api_router.include_router(employee.router, prefix="/employee", tags=["Employee"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
