from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.rooms import router as rooms_router
from app.api.v1.cameras import router as cameras_router
from app.api.v1.environment import router as env_router
from app.api.v1.alerts import router as alerts_router
from app.api.v1.settings import router as settings_router
from app.api.v1.exports import router as exports_router
from app.api.v1.users import router as users_router
from app.api.v1.ocr import router as ocr_router  # Phase 2: OCR Pipeline

api_v1_router = APIRouter()

api_v1_router.include_router(auth_router)
api_v1_router.include_router(dashboard_router)
api_v1_router.include_router(rooms_router)
api_v1_router.include_router(cameras_router)
api_v1_router.include_router(env_router)
api_v1_router.include_router(alerts_router)
api_v1_router.include_router(settings_router)
api_v1_router.include_router(exports_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(ocr_router)   # Phase 2: OCR Pipeline
