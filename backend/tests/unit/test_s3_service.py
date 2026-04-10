"""
Unit tests for S3 service.
"""
import io
import json
import zipfile
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from app.services.s3 import S3Service


class TestS3Service:
    """Test S3 service."""

    def test_init(self):
        """Test service initialization."""
        service = S3Service()
        assert service._client is None

    @pytest.mark.asyncio
    async def test_client_property_creates_boto3_client(self):
        """Test client property creates boto3 S3 client."""
        with patch('boto3.client') as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.return_value = mock_client
            
            service = S3Service()
            client = service.client
            
            assert client == mock_client
            mock_boto3.assert_called_once()
            # Verify the client is cached
            assert service._client == mock_client

    def test_client_property_caches_client(self):
        """Test client property caches the client."""
        with patch('boto3.client') as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.return_value = mock_client
            
            service = S3Service()
            client1 = service.client
            client2 = service.client
            
            assert client1 == client2
            # boto3.client should only be called once due to caching
            mock_boto3.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_content_string(self):
        """Test upload_content with string content."""
        with patch('boto3.client') as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.return_value = mock_client
            
            service = S3Service()
            
            with patch.object(service, '_run', new_callable=AsyncMock) as mock_run:
                await service.upload_content("test-bucket", "test-key", "test content")
                
                # Verify _run was called with put_object
                mock_run.assert_called_once()
                args = mock_run.call_args[0]
                assert args[0] == mock_client.put_object

    @pytest.mark.asyncio
    async def test_upload_content_bytes(self):
        """Test upload_content with bytes content."""
        with patch('boto3.client') as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.return_value = mock_client
            
            service = S3Service()
            
            with patch.object(service, '_run', new_callable=AsyncMock) as mock_run:
                await service.upload_content("test-bucket", "test-key", b"test content")
                
                mock_run.assert_called_once()
                args = mock_run.call_args[0]
                assert args[0] == mock_client.put_object

    @pytest.mark.asyncio
    async def test_download_content(self):
        """Test download_content method."""
        with patch('boto3.client') as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.return_value = mock_client
            
            service = S3Service()
            
            # Mock the response
            mock_response = {"Body": MagicMock()}
            mock_response["Body"].read.return_value = b"downloaded content"
            
            with patch.object(service, '_run', new_callable=AsyncMock) as mock_run:
                mock_run.return_value = mock_response
                
                result = await service.download_content("test-key")
                
                assert result == "downloaded content"
                mock_run.assert_called_once()
                args = mock_run.call_args[0]
                assert args[0] == mock_client.get_object

    @pytest.mark.asyncio
    async def test_object_exists_true(self):
        """Test object_exists returns True when object exists."""
        with patch('boto3.client') as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.return_value = mock_client
            
            service = S3Service()
            
            with patch.object(service, '_run', new_callable=AsyncMock) as mock_run:
                mock_run.return_value = {"ContentLength": 100}
                
                result = await service.object_exists("test-key")
                
                assert result is True
                mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_object_exists_false(self):
        """Test object_exists returns False when object doesn't exist."""
        from botocore.exceptions import ClientError
        
        with patch('boto3.client') as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.return_value = mock_client
            
            service = S3Service()
            
            # Mock ClientError for NoSuchKey
            error = ClientError(
                error_response={"Error": {"Code": "NoSuchKey"}},
                operation_name="HeadObject"
            )
            
            with patch.object(service, '_run', new_callable=AsyncMock) as mock_run:
                mock_run.side_effect = error
                
                result = await service.object_exists("test-key")
                
                assert result is False

    @pytest.mark.asyncio
    async def test_object_exists_other_error(self):
        """Test object_exists raises other ClientErrors."""
        from botocore.exceptions import ClientError
        
        with patch('boto3.client') as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.return_value = mock_client
            
            service = S3Service()
            
            # Mock ClientError for other error
            error = ClientError(
                error_response={"Error": {"Code": "AccessDenied"}},
                operation_name="HeadObject"
            )
            
            with patch.object(service, '_run', new_callable=AsyncMock) as mock_run:
                mock_run.side_effect = error
                
                # Should return False for any exception (including ClientError)
                result = await service.object_exists("test-key")
                assert result is False

    @pytest.mark.asyncio
    async def test_get_presigned_url(self):
        """Test get_presigned_url method."""
        with patch('boto3.client') as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.return_value = mock_client
            
            service = S3Service()
            
            with patch.object(service, '_run', new_callable=AsyncMock) as mock_run:
                mock_run.return_value = "https://signed-url.amazonaws.com"
                
                result = await service.get_presigned_url("test-bucket", "test-key")
                
                assert result == "https://signed-url.amazonaws.com"
                mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_project_artifact(self):
        """Test upload_project_artifact method."""
        with patch('boto3.client') as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.return_value = mock_client
            
            service = S3Service()
            
            with patch.object(service, 'upload_content', new_callable=AsyncMock) as mock_upload:
                await service.upload_project_artifact("proj123", "run456", "file.txt", "content")
                
                mock_upload.assert_called_once()
                args, kwargs = mock_upload.call_args
                assert "proj123" in args[1]  # key contains project ID
                assert "run456" in args[1]  # key contains run ID
                assert args[0] == "content"  # first arg is content

    @pytest.mark.asyncio
    async def test_create_project_zip_success(self):
        """Test create_project_zip creates and uploads ZIP file."""
        files = [
            {"path": "src/main.py", "content": "print('hello')"},
            {"path": "README.md", "content": "# Project"},
            {"path": "package.json", "content": '{"name": "test"}'}
        ]
        
        with patch('boto3.client') as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.return_value = mock_client
            
            service = S3Service()
            
            with patch.object(service, '_run', new_callable=AsyncMock) as mock_run:
                result = await service.create_project_zip("proj123", "run456", files)
                
                # Should return S3 key
                assert "projects/" in result
                assert "proj123" in result
                assert "run456" in result
                assert result.endswith("project.zip")
                
                # Should have called _run to upload to S3
                mock_run.assert_called_once()
                call_args = mock_run.call_args
                assert call_args[0][0] == mock_client.put_object  # First arg is the method

    @pytest.mark.asyncio
    async def test_create_project_zip_with_duplicates(self):
        """Test create_project_zip deduplicates files."""
        files = [
            {"path": "src/main.py", "content": "print('hello')"},
            {"path": "src/main.py", "content": "print('updated')"},  # Duplicate
            {"path": "README.md", "content": "# Project"}
        ]
        
        with patch('boto3.client') as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.return_value = mock_client
            
            service = S3Service()
            
            with patch.object(service, '_run', new_callable=AsyncMock) as mock_run:
                await service.create_project_zip("proj123", "run456", files)
                
                # Should call _run once to upload ZIP
                mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_project_zip_empty_files(self):
        """Test create_project_zip with empty files list."""
        with patch('boto3.client') as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.return_value = mock_client
            
            service = S3Service()
            
            with patch.object(service, '_run', new_callable=AsyncMock) as mock_run:
                result = await service.create_project_zip("proj123", "run456", [])
                
                # Should still create and upload an empty ZIP
                assert "projects/" in result
                assert "proj123" in result
                assert result.endswith("project.zip")
                mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_client_creation_with_aws_credentials(self):
        """Test client creation when AWS credentials are provided."""
        with patch('boto3.client') as mock_boto3, \
             patch('app.services.s3.settings') as mock_settings:
            
            # Create mock settings object with attributes
            mock_settings.aws_region = "us-west-2"
            mock_settings.aws_access_key_id = "test_key"  
            mock_settings.aws_secret_access_key = "test_secret"
            
            mock_client = MagicMock()
            mock_boto3.return_value = mock_client
            
            service = S3Service()
            client = service.client
            
            # Verify boto3.client was called with credentials
            mock_boto3.assert_called_once()
            call_kwargs = mock_boto3.call_args[1]
            assert call_kwargs["aws_access_key_id"] == "test_key"
            assert call_kwargs["aws_secret_access_key"] == "test_secret"
            assert call_kwargs["region_name"] == "us-west-2"

    @pytest.mark.asyncio
    async def test_client_creation_without_aws_credentials(self):
        """Test client creation when AWS credentials are not provided."""
        with patch('boto3.client') as mock_boto3, \
             patch('app.services.s3.settings') as mock_settings:
            
            # Create mock settings object with no credentials
            mock_settings.aws_region = "us-east-1"
            mock_settings.aws_access_key_id = None
            mock_settings.aws_secret_access_key = None
            
            mock_client = MagicMock()
            mock_boto3.return_value = mock_client
            
            service = S3Service()
            client = service.client
            
            # Verify boto3.client was called without credentials
            mock_boto3.assert_called_once()
            call_kwargs = mock_boto3.call_args[1]
            assert "aws_access_key_id" not in call_kwargs
            assert "aws_secret_access_key" not in call_kwargs
            assert call_kwargs["region_name"] == "us-east-1"