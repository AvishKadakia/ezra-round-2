from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


def to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


ArtifactType = Literal["image", "pdf"]
ArtifactStatus = Literal["processing", "ready", "failed", "archived"]
CommentKind = Literal["question", "decision", "blocker", "praise"]
ShareExpiryHours = Literal[24, 36, 72]
JobStatus = Literal["queued", "running", "succeeded", "failed"]


class PageSummary(CamelModel):
    page_number: int
    summary: str
    image_url: Optional[str] = None


class ArtifactOut(CamelModel):
    id: str
    title: str
    description: str = ""
    type: ArtifactType
    tags: list[str] = Field(default_factory=list)
    category: str = "general"
    owner_name: str
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime] = None
    status: ArtifactStatus
    comment_count: int = 0
    artifact_url: str
    thumbnail_url: Optional[str] = None
    document_summary: Optional[str] = None
    feedback_summary: Optional[str] = None
    page_summaries: list[PageSummary] = Field(default_factory=list)
    processing_error: Optional[str] = None
    rating: Optional[float] = None


class CommentCreate(CamelModel):
    body: str
    kind: Optional[CommentKind] = None


class CommentOut(CamelModel):
    id: str
    artifact_id: str
    author_name: str
    body: str
    created_at: datetime
    kind: Optional[CommentKind] = None


class ShareLinkCreate(CamelModel):
    expires_in_hours: ShareExpiryHours = 72
    access: Literal["anyone_with_link"] = "anyone_with_link"


class ShareLinkOut(CamelModel):
    url: str
    expires_at: datetime
    expires_in_hours: int


class DocumentSummaryOut(CamelModel):
    document_summary: str
    page_summaries: list[PageSummary] = Field(default_factory=list)


class FeedbackSummaryOut(CamelModel):
    feedback_summary: str | None = None


class ProcessingJobOut(CamelModel):
    id: str
    artifact_id: str
    job_type: str
    status: JobStatus
    attempts: int
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class MetricsOut(CamelModel):
    total_documents: int
    total_comments: int


class HealthOut(CamelModel):
    ok: bool
    service: str
