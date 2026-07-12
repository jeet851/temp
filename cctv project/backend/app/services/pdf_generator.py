"""
VisionGuard — PDF Compliance Report Generator (Phase 3).

Uses ReportLab to generate a highly professional PDF document containing:
  - Header / Title block with metadata
  - High/low/average statistics summary tables
  - Dynamic compliance charts generated via Matplotlib (compiled to vector/raster bytes)
  - Detailed environmental history logs table
"""

import io
from datetime import datetime
from typing import List

# Lazy import support for reporting libraries
try:
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend, required for headless/FastAPI servers
    import matplotlib.pyplot as plt
    has_reporting = True
except ImportError:
    matplotlib = None
    plt = None
    has_reporting = False

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        Image,
        KeepTogether,
    )
    has_reportlab = True
except ImportError:
    colors = None
    letter = None
    getSampleStyleSheet = None
    ParagraphStyle = None
    inch = None
    SimpleDocTemplate = None
    Paragraph = None
    Spacer = None
    Table = None
    TableStyle = None
    Image = None
    KeepTogether = None
    has_reportlab = False

from app.models.environmental_history import EnvironmentalHistory


def generate_compliance_pdf(
    room_name: str,
    records: List[EnvironmentalHistory],
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> bytes:
    """
    Generate a styled PDF report in memory using ReportLab.
    Returns the PDF as raw bytes.
    """
    if not has_reportlab:
        raise RuntimeError("ReportLab is not installed on this system. Cannot generate PDF reports.")

    buffer = io.BytesIO()

    # Setup document template
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    story = []

    # ── Styles Setup ────────────────────────────────────────────────────────
    styles = getSampleStyleSheet()

    # Dark Slate & Teal Brand Colors
    primary_color = colors.HexColor("#0F172A")    # Dark Slate
    secondary_color = colors.HexColor("#0D9488")  # Teal Accent
    text_muted_color = colors.HexColor("#64748B") # Muted Gray
    border_color = colors.HexColor("#E2E8F0")     # Light Border Gray

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=primary_color,
        spaceAfter=6,
    )

    subtitle_style = ParagraphStyle(
        "ReportSubTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        textColor=secondary_color,
        spaceAfter=15,
    )

    meta_label_style = ParagraphStyle(
        "MetaLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=primary_color,
    )

    meta_val_style = ParagraphStyle(
        "MetaValue",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=11,
        textColor=text_muted_color,
    )

    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=primary_color,
        spaceAfter=8,
        keepWithNext=True,
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white,
    )

    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=primary_color,
    )

    # ── 1. Header Block / Metadata ──────────────────────────────────────────
    story.append(Paragraph("VisionGuard Compliance Audit Report", title_style))
    story.append(Paragraph("ENVIRONMENTAL TELEMETRY RETRIEVAL", subtitle_style))

    # Metadata grid (Room Name, Capture Range, Generation Date, System Version)
    range_str = "All Time"
    if start_date or end_date:
        s_str = start_date.strftime("%Y-%m-%d") if start_date else "Beginning"
        e_str = end_date.strftime("%Y-%m-%d") if end_date else "Present"
        range_str = f"{s_str} to {e_str}"

    meta_data = [
        [
            Paragraph("Monitoring Room Zone:", meta_label_style),
            Paragraph(room_name, meta_val_style),
            Paragraph("Export Generated:", meta_label_style),
            Paragraph(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), meta_val_style),
        ],
        [
            Paragraph("Telemetry Date Range:", meta_label_style),
            Paragraph(range_str, meta_val_style),
            Paragraph("System Version:", meta_label_style),
            Paragraph("v2.4.0-Compliance", meta_val_style),
        ]
    ]

    meta_table = Table(meta_data, colWidths=[130, 140, 110, 150])
    meta_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, -1), (-1, -1), 1, border_color),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 15))

    # ── 2. Statistics Summary Cards ─────────────────────────────────────────
    temp_values = [r.temperature for r in records] if records else []
    hum_values = [r.humidity for r in records] if records else []

    min_temp = min(temp_values) if temp_values else 0.0
    max_temp = max(temp_values) if temp_values else 0.0
    avg_temp = round(sum(temp_values) / len(temp_values), 1) if temp_values else 0.0

    min_hum = min(hum_values) if hum_values else 0.0
    max_hum = max(hum_values) if hum_values else 0.0
    avg_hum = round(sum(hum_values) / len(hum_values), 1) if hum_values else 0.0

    # Dashboard-like cards table
    card_label_style = ParagraphStyle(
        "CardLabel", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=10, textColor=text_muted_color
    )
    card_value_style = ParagraphStyle(
        "CardValue", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=secondary_color
    )
    card_header_style = ParagraphStyle(
        "CardHeader", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10, leading=12, textColor=primary_color
    )

    stats_data = [
        [
            Paragraph("TEMPERATURE METRICS (°C)", card_header_style),
            Paragraph("HUMIDITY METRICS (%RH)", card_header_style),
        ],
        [
            Table([
                [Paragraph("Min Temp", card_label_style), Paragraph("Max Temp", card_label_style), Paragraph("Average", card_label_style)],
                [Paragraph(f"{min_temp}°", card_value_style), Paragraph(f"{max_temp}°", card_value_style), Paragraph(f"{avg_temp}°", card_value_style)]
            ], colWidths=[80, 80, 80]),
            Table([
                [Paragraph("Min Hum", card_label_style), Paragraph("Max Hum", card_label_style), Paragraph("Average", card_label_style)],
                [Paragraph(f"{min_hum}%", card_value_style), Paragraph(f"{max_hum}%", card_value_style), Paragraph(f"{avg_hum}%", card_value_style)]
            ], colWidths=[80, 80, 80]),
        ]
    ]

    stats_table = Table(stats_data, colWidths=[265, 265])
    stats_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 1, border_color),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, border_color),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 15))

    # ── 3. Chart Generation (Matplotlib) ───────────────────────────────────
    if records:
        try:
            if not has_reporting or plt is None:
                raise RuntimeError("Matplotlib is not installed on this system. Chart plotting is disabled.")

            # We plot the last 30 readings for trend clarity
            plot_records = records[:30][::-1]  # chronological order
            timestamps = [r.timestamp.strftime("%H:%M") for r in plot_records]
            temps = [r.temperature for r in plot_records]
            hums = [r.humidity for r in plot_records]

            fig, ax1 = plt.subplots(figsize=(6.5, 2.0))

            # Primary Y-axis: Temperature
            color = "#0D9488"
            ax1.set_xlabel("Time (HH:MM)", color="#475569", fontsize=8)
            ax1.set_ylabel("Temp (°C)", color=color, fontsize=8)
            ax1.plot(timestamps, temps, color=color, linewidth=2, label="Temperature")
            ax1.tick_params(axis="y", labelcolor=color, labelsize=7)
            ax1.tick_params(axis="x", labelcolor="#475569", labelsize=6, rotation=45)
            ax1.grid(True, linestyle=":", alpha=0.5)

            # Secondary Y-axis: Humidity
            ax2 = ax1.twinx()
            color = "#F59E0B"
            ax2.set_ylabel("Hum (%RH)", color=color, fontsize=8)
            ax2.plot(timestamps, hums, color=color, linewidth=1.5, linestyle="--", label="Humidity")
            ax2.tick_params(axis="y", labelcolor=color, labelsize=7)

            plt.title("Environmental Compliance Waveform (Last 30 Records)", fontsize=9, fontweight="bold", color="#0F172A")
            fig.tight_layout()

            # Save chart to bytes
            chart_buffer = io.BytesIO()
            plt.savefig(chart_buffer, format="png", dpi=200)
            plt.close(fig)
            chart_buffer.seek(0)

            # Insert Image
            chart_flowable = Image(chart_buffer, width=5.5 * inch, height=1.7 * inch)
            chart_container = Table([[chart_flowable]], colWidths=[530])
            chart_container.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]))
            story.append(KeepTogether([
                Paragraph("Trend Tracking Waveform", section_heading),
                chart_container
            ]))
        except Exception as chart_err:
            logger_log = Paragraph(f"Chart plotting disabled: {str(chart_err)}", meta_val_style)
            story.append(logger_log)

    # ── 4. Telemetry History Table ──────────────────────────────────────────
    table_headers = [
        Paragraph("Timestamp", table_header_style),
        Paragraph("Temp (°C)", table_header_style),
        Paragraph("Humidity (%)", table_header_style),
        Paragraph("Smoke", table_header_style),
        Paragraph("Fire", table_header_style),
        Paragraph("Risk Level", table_header_style),
        Paragraph("Status", table_header_style),
    ]

    table_rows = [table_headers]

    for index, r in enumerate(records[:100]):  # Limit to first 100 rows for size safety
        # Text values
        smoke_text = "DETECTED" if r.smoke_detected else "CLEAR"
        fire_text = "DETECTED" if r.fire_detected else "CLEAR"
        risk_text = r.risk_level.upper()

        # Alert level formatting
        temp_status = "NORMAL"
        temp_style = table_cell_style
        if r.temperature >= 32.0 or r.humidity >= 75.0:
            temp_status = "CRITICAL"
            temp_style = ParagraphStyle("CritCell", parent=table_cell_style, textColor=colors.HexColor("#EF4444"), fontName="Helvetica-Bold")
        elif r.temperature >= 28.0 or r.humidity >= 65.0:
            temp_status = "WARNING"
            temp_style = ParagraphStyle("WarnCell", parent=table_cell_style, textColor=colors.HexColor("#F59E0B"), fontName="Helvetica-Bold")

        smoke_style = ParagraphStyle("SmokeCol", parent=table_cell_style, textColor=colors.HexColor("#EF4444") if r.smoke_detected else primary_color)
        fire_style = ParagraphStyle("FireCol", parent=table_cell_style, textColor=colors.HexColor("#EF4444") if r.fire_detected else primary_color)

        table_rows.append([
            Paragraph(r.timestamp.strftime("%Y-%m-%d %H:%M:%S"), table_cell_style),
            Paragraph(f"{r.temperature}°C", temp_style),
            Paragraph(f"{r.humidity}%", temp_style),
            Paragraph(smoke_text, smoke_style),
            Paragraph(fire_text, fire_style),
            Paragraph(risk_text, temp_style),
            Paragraph(temp_status, temp_style),
        ])

    history_table = Table(
        table_rows,
        colWidths=[120, 65, 65, 70, 70, 70, 70],
        repeatRows=1,
    )

    # Alternate row background colors
    t_style = [
        ("BACKGROUND", (0, 0), (-1, 0), secondary_color),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, border_color),
    ]

    for i in range(1, len(table_rows)):
        bg_col = colors.HexColor("#F8FAFC") if i % 2 == 0 else colors.white
        t_style.append(("BACKGROUND", (0, i), (-1, i), bg_col))

    history_table.setStyle(TableStyle(t_style))

    story.append(KeepTogether([
        Paragraph("Compliance Telemetry Archive (First 100 Records)", section_heading),
        history_table
    ]))

    # Build the document
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes
