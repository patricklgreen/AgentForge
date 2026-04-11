import io
import logging
import zipfile
from asyncio import get_event_loop
from functools import partial
from pathlib import Path
from typing import Any, Optional

import boto3
from botocore.config import Config

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class S3Service:
    """
    Async-safe wrapper around the synchronous boto3 S3 client.

    Every boto3 call is run in the default thread-pool executor so the
    asyncio event loop is never blocked.
    """

    def __init__(self) -> None:
        self._client: Optional[Any] = None

    @property
    def client(self) -> Any:
        if self._client is None:
            config = Config(
                region_name=settings.aws_region,
                retries={"max_attempts": 3, "mode": "adaptive"},
            )
            kwargs: dict[str, Any] = {
                "config": config,
                "region_name": settings.aws_region,
            }
            if settings.aws_access_key_id:
                kwargs["aws_access_key_id"] = settings.aws_access_key_id
                kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
            self._client = boto3.client("s3", **kwargs)
        return self._client

    async def _run(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Run a synchronous boto3 call in a thread-pool executor."""
        loop = get_event_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))

    # ─── Public methods ───────────────────────────────────────────────────────

    async def upload_content(
        self,
        content: str,
        s3_key: str,
        content_type: str = "text/plain",
    ) -> str:
        """Upload UTF-8 text content and return the S3 key."""
        await self._run(
            self.client.put_object,
            Bucket=settings.s3_bucket_name,
            Key=s3_key,
            Body=content.encode("utf-8"),
            ContentType=content_type,
        )
        logger.info(f"Uploaded to S3: {s3_key}")
        return s3_key

    async def download_content(self, s3_key: str) -> str:
        """Download and return the UTF-8 content of an S3 object."""
        response = await self._run(
            self.client.get_object,
            Bucket=settings.s3_bucket_name,
            Key=s3_key,
        )
        return response["Body"].read().decode("utf-8")

    async def upload_project_artifact(
        self,
        project_id: str,
        run_id: str,
        file_path: str,
        content: str,
    ) -> str:
        """
        Upload a single project file and return the S3 key.

        Key format: projects/{project_id}/runs/{run_id}/{file_path}
        """
        s3_key = f"projects/{project_id}/runs/{run_id}/{file_path}"
        content_type = self._get_content_type(file_path)
        return await self.upload_content(content, s3_key, content_type)

    async def create_project_zip(
        self,
        project_id: str,
        run_id: str,
        files: list[dict[str, str]],
    ) -> str:
        """
        Create a ZIP archive of all project files and upload to S3.

        Args:
            files: List of dicts with "path" and "content" keys.

        Returns:
            The S3 key of the uploaded ZIP.
        """
        # Deduplicate files by path, keeping the last occurrence
        # This prevents zipfile warnings about duplicate entries
        file_dict = {}
        for file_info in files:
            path = file_info["path"]
            file_dict[path] = file_info.get("content", "")
        
        logger.info(f"Creating ZIP with {len(file_dict)} unique files (deduped from {len(files)} total)")
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for path, content in file_dict.items():
                zf.writestr(path, content)

        zip_buffer.seek(0)
        s3_key = f"projects/{project_id}/runs/{run_id}/project.zip"
        await self._run(
            self.client.put_object,
            Bucket=settings.s3_bucket_name,
            Key=s3_key,
            Body=zip_buffer.getvalue(),
            ContentType="application/zip",
        )
        logger.info(f"Project ZIP uploaded: {s3_key}")
        return s3_key

    async def get_presigned_url(
        self, s3_key: str, expiry: int = 3600
    ) -> str:
        """Generate a pre-signed GET URL valid for `expiry` seconds."""
        return await self._run(  # type: ignore[return-value]
            self.client.generate_presigned_url,
            "get_object",
            Params={"Bucket": settings.s3_bucket_name, "Key": s3_key},
            ExpiresIn=expiry,
        )

    async def object_exists(self, s3_key: str) -> bool:
        """Return True if the S3 object exists."""
        try:
            await self._run(
                self.client.head_object,
                Bucket=settings.s3_bucket_name,
                Key=s3_key,
            )
            return True
        except Exception:
            return False

    async def delete_object(self, s3_key: str) -> bool:
        """Delete an S3 object. Returns True if successful."""
        try:
            await self._run(
                self.client.delete_object,
                Bucket=settings.s3_bucket_name,
                Key=s3_key,
            )
            logger.info(f"Deleted S3 object: {s3_key}")
            return True
        except Exception as e:
            logger.warning(f"Failed to delete S3 object {s3_key}: {e}")
            return False

    async def delete_objects_by_prefix(self, prefix: str) -> int:
        """Delete all S3 objects with the given prefix. Returns count of deleted objects."""
        try:
            # List objects with the prefix
            response = await self._run(
                self.client.list_objects_v2,
                Bucket=settings.s3_bucket_name,
                Prefix=prefix,
            )
            
            if "Contents" not in response:
                logger.info(f"No objects found with prefix: {prefix}")
                return 0
            
            # Prepare objects for deletion
            objects_to_delete = [{"Key": obj["Key"]} for obj in response["Contents"]]
            
            if not objects_to_delete:
                return 0
            
            # Delete objects in batch
            await self._run(
                self.client.delete_objects,
                Bucket=settings.s3_bucket_name,
                Delete={"Objects": objects_to_delete},
            )
            
            count = len(objects_to_delete)
            logger.info(f"Deleted {count} S3 objects with prefix: {prefix}")
            return count
            
        except Exception as e:
            logger.error(f"Failed to delete S3 objects with prefix {prefix}: {e}")
            return 0

    # ─── Utilities ────────────────────────────────────────────────────────────

    @staticmethod
    def _get_content_type(file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        mapping: dict[str, str] = {
            ".py":         "text/x-python",
            ".ts":         "application/typescript",
            ".tsx":        "application/typescript",
            ".js":         "application/javascript",
            ".jsx":        "application/javascript",
            ".json":       "application/json",
            ".yaml":       "text/yaml",
            ".yml":        "text/yaml",
            ".md":         "text/markdown",
            ".html":       "text/html",
            ".css":        "text/css",
            ".tf":         "text/plain",
            ".sh":         "text/x-sh",
            ".dockerfile": "text/plain",
            ".sql":        "text/x-sql",
            ".java":       "text/x-java-source",
            ".cs":         "text/x-csharp",
            ".go":         "text/x-go",
            ".rs":         "text/x-rustsrc",
        }
        return mapping.get(ext, "text/plain")


# Module-level singleton
s3_service = S3Service()
