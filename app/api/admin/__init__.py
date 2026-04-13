"""Admin API (кабинет + auth)."""

from fastapi import APIRouter

from app.api.admin import auth, cabinet

router = APIRouter()
router.include_router(auth.router, prefix="/auth")
router.include_router(cabinet.router)
