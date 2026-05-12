"""Admin API (кабинет + auth)."""

from fastapi import APIRouter

from app.api.admin import auth, cabinet, uploads

router = APIRouter()
router.include_router(auth.router, prefix="/auth")
router.include_router(cabinet.router)
router.include_router(uploads.router)
