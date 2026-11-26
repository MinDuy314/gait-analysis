from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid
from datetime import datetime


class ReportType(str, Enum):
    individual = "individual"
    professional = "professional"


class ReportStatus(str, Enum):
    generated = "generated"
    failed = "failed"


class GaitReport(BaseModel):
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    report_type: ReportType
    subject_id: str
    session_id: str
    assessment_id: Optional[str] = None
    status: ReportStatus = ReportStatus.generated
    content_md: str = ""
    content_html: Optional[str] = None
    report_data: Dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    limitations: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)
