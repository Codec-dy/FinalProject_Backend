from pydantic import BaseModel
from typing import Optional


class VehicleVisualizationResponse(BaseModel):
    success: bool
    make: str
    model: str
    year: int
    generation: Optional[str] = None
    model_url: Optional[str] = None
    watermarked: bool = False
    fallback: bool = False
    message: Optional[str] = None