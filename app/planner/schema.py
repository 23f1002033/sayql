from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class TimeRange(BaseModel):
    start: date
    end: date


class Filter(BaseModel):
    field: str
    value: str


class QueryPlan(BaseModel):
    workspace_id: str = "demo"
    metric: str
    dimensions: List[str] = Field(default_factory=list)
    filters: List[Filter] = Field(default_factory=list)
    time_range: TimeRange
    compare_to: Optional[TimeRange] = None
    grain: Optional[str] = None
    limit: int = 200
