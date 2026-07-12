from datetime import datetime
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import io

from app.database.session import get_db
from app.core.dependencies import get_current_user
from app.services.export_service import ExportService

router = APIRouter(prefix="/exports", tags=["Exports"])


@router.get("/history")
async def export_history(
    room_id: str = "room-001",
    format: str = Query("csv", description="csv | excel | pdf"),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Download environmental history reports as spreadsheet or PDF compliance documents."""
    service = ExportService(db)
    filename = f"visionguard_history_{room_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    if format.lower() == "excel":
        content = await service.generate_excel(room_id, start_date, end_date)
        return StreamingResponse(
            io.BytesIO(content),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}.xlsx"},
        )
    elif format.lower() == "pdf":
        content = await service.generate_pdf(room_id, start_date, end_date)
        return StreamingResponse(
            io.BytesIO(content),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}.pdf"},
        )
    else:
        content = await service.generate_csv(room_id, start_date, end_date)
        return StreamingResponse(
            io.BytesIO(content.encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}.csv"},
        )
