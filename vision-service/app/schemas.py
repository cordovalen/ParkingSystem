from pydantic import BaseModel, Field

class PlateCandidate(BaseModel):
    raw_text: str
    normalized_text: str
    confidence: float = Field(ge=0.0, le=1.0)

class PlateRecognitionResponse(BaseModel):
    plate: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: str
    processing_time_ms: int
    candidates: list[PlateCandidate] = []