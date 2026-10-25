from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, HttpUrl


class WebFetchArgs(BaseModel):
    location: str
    units: Literal["metric", "imperial"] = "metric"


class GetWeatherResult(BaseModel):
    location: str
    latitude: float
    longitude: float
    temperature: Optional[float] = None
    summary: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None


class SummarizePDFArgs(BaseModel):
    path: Optional[str] = None
    pages: Optional[List[int]] = None
    summary_length: Literal["short", "medium", "long"] = "short"


class SummarizePDFResult(BaseModel):
    summary: str
    highlights: Optional[List[str]] = None
    source_pages: Optional[List[int]] = None
