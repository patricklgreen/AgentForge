import uuid
from datetime import datetime
from typing import Any, Optional, List

from pydantic import BaseModel, Field, HttpUrl

from app.models.project import AgentStep, ProjectStatus, RunStatus


class VisualReference(BaseModel):
    type: str = Field(..., description="'url' or 'upload'")
    url: Optional[HttpUrl] = Field(None, description="URL to external image/mockup")
    file_name: Optional[str] = Field(None, description="Name of uploaded file")
    s3_key: Optional[str] = Field(None, description="S3 key for uploaded file")
    description: Optional[str] = Field(None, description="Description of what this reference shows")


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=20)
    requirements: str = Field(
        ..., min_length=50, description="Detailed business requirements"
    )
    target_language: str = Field(..., description="e.g., Python, TypeScript, Java")
    target_framework: Optional[str] = Field(
        None, description="e.g., FastAPI, NestJS, Spring Boot"
    )
    visual_references: Optional[List[VisualReference]] = Field(
        default_factory=list, description="Visual references (mockups, designs, screenshots)"
    )


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    requirements: str
    target_language: str
    target_framework: Optional[str]
    visual_references: Optional[dict]
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RunEventResponse(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    event_type: str
    agent_name: Optional[str]
    step: Optional[str]
    message: str
    data: Optional[dict]
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectRunResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    thread_id: str
    status: RunStatus
    current_step: Optional[str]
    interrupt_payload: Optional[dict]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    events: list[RunEventResponse] = []

    model_config = {"from_attributes": True}


class HumanFeedback(BaseModel):
    action: str = Field(..., pattern="^(approve|reject|modify)$")
    feedback: Optional[str] = None
    modifications: Optional[dict[str, Any]] = None


class FeedbackResponse(BaseModel):
    status: str
    action: str


class CancelResponse(BaseModel):
    status: str
    message: str


class RunStateResponse(BaseModel):
    state: Optional[dict[str, Any]]


class ArtifactResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    run_id: Optional[uuid.UUID]
    name: str
    artifact_type: str
    file_path: str
    language: Optional[str]
    size_bytes: Optional[int]
    is_approved: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ArtifactContent(BaseModel):
    content: str
    language: Optional[str]
    file_path: str


class DownloadUrlResponse(BaseModel):
    url: str
