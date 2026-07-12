import io
from datetime import datetime
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.environmental_history import EnvironmentalHistory
from app.repositories.environment_repo import EnvironmentRepository
from app.repositories.room_repo import RoomRepository
from app.services.pdf_generator import generate_compliance_pdf


class ExportService:
    """Generates standard CSV compliance outputs, binary Excel spreadsheet reports, and ReportLab PDF documents."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.env_repo = EnvironmentRepository(db)
        self.room_repo = RoomRepository(db)

    async def generate_csv(
        self,
        room_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> str:
        """Compile matching environmental history records into a CSV text file."""
        room = await self.room_repo.get_by_id(room_id)
        room_name = room.name if room else "Server Room Alpha"

        records, _ = await self.env_repo.list_history(
            room_id=room_id,
            start_date=start_date,
            end_date=end_date,
            page=1,
            per_page=10000,  # Max export limit
        )

        output = io.StringIO()
        output.write("VISIONGUARD ENVIRONMENTAL MONITORING ARCHIVE REPORT\n")
        output.write(f"Site Room: {room_name}\n")
        output.write(f"Generated Date: {datetime.now().isoformat()}\n\n")
        output.write("Timestamp,Room,Camera,Temperature,Humidity,Smoke,Fire,Risk Level,Image Path\n")

        for r in records:
            smoke_text = "DETECTED" if r.smoke_detected else "CLEAR"
            fire_text = "DETECTED" if r.fire_detected else "CLEAR"
            ts_str = r.timestamp.isoformat()
            output.write(
                f'"{ts_str}","{room_name}","Camera-001",{r.temperature},{r.humidity},'
                f'"{smoke_text}","{fire_text}","{r.risk_level}","{r.image_path}"\n'
            )

        return output.getvalue()

    async def generate_excel(
        self,
        room_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> bytes:
        """Compile matching environmental history records into an Excel binary spreadsheet."""
        room = await self.room_repo.get_by_id(room_id)
        room_name = room.name if room else "Server Room Alpha"

        records, _ = await self.env_repo.list_history(
            room_id=room_id,
            start_date=start_date,
            end_date=end_date,
            page=1,
            per_page=10000,
        )

        wb = Workbook()
        ws = wb.active
        ws.title = "Environmental History"

        # Headers
        ws.append([
            "Timestamp", "Room", "Camera ID", "Temperature (°C)", 
            "Humidity (%RH)", "Smoke Status", "Fire Status", 
            "AI Risk Level", "Image Reference Path"
        ])

        for r in records:
            smoke_text = "DETECTED" if r.smoke_detected else "CLEAR"
            fire_text = "DETECTED" if r.fire_detected else "CLEAR"
            ws.append([
                r.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                room_name,
                "Camera-001",
                r.temperature,
                r.humidity,
                smoke_text,
                fire_text,
                r.risk_level.upper(),
                r.image_path
            ])

        # Write to byte buffer
        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()

    async def generate_pdf(
        self,
        room_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> bytes:
        """Compile matching environmental history records into a fully styled PDF document."""
        room = await self.room_repo.get_by_id(room_id)
        room_name = room.name if room else "Server Room Alpha"

        records, _ = await self.env_repo.list_history(
            room_id=room_id,
            start_date=start_date,
            end_date=end_date,
            page=1,
            per_page=10000,
        )

        return generate_compliance_pdf(
            room_name=room_name,
            records=records,
            start_date=start_date,
            end_date=end_date,
        )
