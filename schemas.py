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


class TravelRiskArgs(BaseModel):
    activity_type: str
    current_location: str
    backup_location: str
    itinerary_path: Optional[str] = None
    venue_plan_path: Optional[str] = None
    risk_threshold: int = 3


class TravelRiskResult(BaseModel):
    activity_type: str
    current_location: str
    backup_location: str
    weather_summary: str
    weather_risk_score: int
    overall_risk: Literal["low", "medium", "high"]
    risk_factors: List[str]
    recommendations: List[str]
    route_status: Optional[Dict[str, Any]] = None
    local_plan_summary: Optional[str] = None


class TrafficRouteArgs(BaseModel):
    origin: str
    destination: str
    mode: Literal["driving", "transit", "walking"] = "driving"


class TrafficRouteResult(BaseModel):
    origin: str
    destination: str
    mode: str
    status: str
    travel_time_minutes: int
    distance_km: float
    api: str
    simulated: bool = True
    error: Optional[str] = None
