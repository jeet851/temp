from pydantic import BaseModel, Field


class ThresholdRead(BaseModel):
    """System environmental threshold values model."""

    tempWarning: float = Field(..., alias="temp_warning")
    tempCritical: float = Field(..., alias="temp_critical")
    humWarning: float = Field(..., alias="hum_warning")
    humCritical: float = Field(..., alias="hum_critical")

    class Config:
        from_attributes = True
        populate_by_name = True


class ThresholdUpdate(BaseModel):
    """Payload to update system environmental threshold values."""

    temp_warning: float
    temp_critical: float
    hum_warning: float
    hum_critical: float
