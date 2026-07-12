from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.core.dependencies import get_current_user
from app.schemas.alert import AlertRead, AlertAcknowledge, AlertResolve
from app.schemas.common import APIResponse
from app.services.alert_service import AlertService

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("", response_model=APIResponse[list[AlertRead]])
async def get_alerts(
    room_id: str | None = None,
    status: str | None = None,
    severity: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Fetch environmental threshold violation alerts."""
    service = AlertService(db)
    alerts = await service.get_alerts(room_id, status, severity)
    return APIResponse(success=True, data=[AlertRead.from_orm(a) for a in alerts])


@router.patch("/{alert_id}/acknowledge", response_model=APIResponse[AlertRead])
async def acknowledge_alert(
    alert_id: str,
    payload: AlertAcknowledge,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Acknowledge an active environmental threshold violation alert."""
    service = AlertService(db)
    alert = await service.acknowledge_alert(alert_id, payload.operator)
    return APIResponse(success=True, message="Alert acknowledged.", data=AlertRead.from_orm(alert))


@router.patch("/{alert_id}/resolve", response_model=APIResponse[AlertRead])
async def resolve_alert(
    alert_id: str,
    payload: AlertResolve,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Resolve an environmental violation alert with resolution notes."""
    service = AlertService(db)
    alert = await service.resolve_alert(alert_id, payload.operator, payload.resolution_notes)
    return APIResponse(success=True, message="Alert resolved.", data=AlertRead.from_orm(alert))
