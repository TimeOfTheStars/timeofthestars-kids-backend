"""Admin API (кабинет + auth)."""

from fastapi import APIRouter

from app.api.admin import auth, cabinet, stats, uploads

router = APIRouter()
router.include_router(auth.router, prefix="/auth")
router.include_router(cabinet.router)
router.include_router(stats.router)
router.include_router(uploads.router)
