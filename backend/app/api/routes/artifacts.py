import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.project import Artifact
from app.schemas.project import ArtifactContent, ArtifactResponse, DownloadUrlResponse
from app.services.s3 import s3_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.get("/project/{project_id}", response_model=list[ArtifactResponse])
async def get_project_artifacts(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[Artifact]:
    result = await db.execute(
        select(Artifact)
        .where(Artifact.project_id == project_id)
        .order_by(Artifact.created_at)
    )
    return list(result.scalars().all())


@router.get("/{artifact_id}/content", response_model=ArtifactContent)
async def get_artifact_content(
    artifact_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ArtifactContent:
    artifact = await db.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    content = await s3_service.download_content(artifact.s3_key)
    return ArtifactContent(
        content=content,
        language=artifact.language,
        file_path=artifact.file_path,
    )


@router.get("/{artifact_id}/download-url", response_model=DownloadUrlResponse)
async def get_download_url(
    artifact_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> DownloadUrlResponse:
    artifact = await db.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    url = await s3_service.get_presigned_url(artifact.s3_key)
    return DownloadUrlResponse(url=url)
