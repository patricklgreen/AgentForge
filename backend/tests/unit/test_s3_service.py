"""
Unit tests for S3 service.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
from app.services.s3 import S3Service


class TestS3Service:
    """Test S3 storage service."""

    def test_init(self):
        """Test service initialization."""
        service = S3Service()
        assert service.bucket_name == "agentforge-artifacts"
        assert service.client is None

    @pytest.mark.asyncio
    async def test_get_client(self):
        """Test client creation."""
        with patch('boto3.client') as mock_boto:
            mock_client = MagicMock()
            mock_boto.return_value = mock_client
            
            service = S3Service()
            client = await service.get_client()
            
            assert client == mock_client
            mock_boto.assert_called_once_with('s3', region_name='us-east-1')

    @pytest.mark.asyncio
    async def test_upload_content(self):
        """Test content upload."""
        mock_client = AsyncMock()
        mock_client.put_object.return_value = {"ETag": '"test-etag"'}
        
        with patch.object(S3Service, 'get_client', return_value=mock_client):
            service = S3Service()
            result = await service.upload_content("test content", "test/key.txt")
            
            assert result == "test/key.txt"
            mock_client.put_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_content(self):
        """Test content download."""
        mock_client = AsyncMock()
        mock_body = MagicMock()
        mock_body.read.return_value = b"test content"
        mock_client.get_object.return_value = {"Body": mock_body}
        
        with patch.object(S3Service, 'get_client', return_value=mock_client):
            service = S3Service()
            result = await service.download_content("test/key.txt")
            
            assert result == "test content"
            mock_client.get_object.assert_called_once_with(
                Bucket="agentforge-artifacts",
                Key="test/key.txt"
            )

    @pytest.mark.asyncio
    async def test_object_exists_true(self):
        """Test object existence check - exists."""
        mock_client = AsyncMock()
        mock_client.head_object.return_value = {}
        
        with patch.object(S3Service, 'get_client', return_value=mock_client):
            service = S3Service()
            result = await service.object_exists("test/key.txt")
            
            assert result is True

    @pytest.mark.asyncio
    async def test_object_exists_false(self):
        """Test object existence check - not exists."""
        mock_client = AsyncMock()
        mock_client.head_object.side_effect = Exception("Not found")
        
        with patch.object(S3Service, 'get_client', return_value=mock_client):
            service = S3Service()
            result = await service.object_exists("test/key.txt")
            
            assert result is False

    @pytest.mark.asyncio
    async def test_get_presigned_url(self):
        """Test presigned URL generation."""
        mock_client = AsyncMock()
        mock_client.generate_presigned_url.return_value = "https://signed-url.example.com"
        
        with patch.object(S3Service, 'get_client', return_value=mock_client):
            service = S3Service()
            result = await service.get_presigned_url("test/key.txt")
            
            assert result == "https://signed-url.example.com"
            mock_client.generate_presigned_url.assert_called_once_with(
                'get_object',
                Params={'Bucket': 'agentforge-artifacts', 'Key': 'test/key.txt'},
                ExpiresIn=3600
            )

    @pytest.mark.asyncio
    async def test_upload_project_artifact(self):
        """Test project artifact upload."""
        mock_client = AsyncMock()
        mock_client.put_object.return_value = {"ETag": '"test-etag"'}
        
        project_id = uuid.uuid4()
        
        with patch.object(S3Service, 'get_client', return_value=mock_client):
            service = S3Service()
            result = await service.upload_project_artifact(
                project_id, "test.py", "print('hello')"
            )
            
            expected_key = f"projects/{project_id}/artifacts/test.py"
            assert result == expected_key
            mock_client.put_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_project_zip(self):
        """Test project ZIP creation."""
        mock_client = AsyncMock()
        mock_client.put_object.return_value = {"ETag": '"test-etag"'}
        mock_client.list_objects_v2.return_value = {
            "Contents": [{"Key": f"projects/{uuid.uuid4()}/artifacts/test.py"}]
        }
        mock_client.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=b"test content"))
        }
        
        project_id = uuid.uuid4()
        
        with patch.object(S3Service, 'get_client', return_value=mock_client):
            service = S3Service()
            result = await service.create_project_zip(project_id, "test-project")
            
            expected_key = f"projects/{project_id}/test-project.zip"
            assert result == expected_key
            mock_client.put_object.assert_called()

    @pytest.mark.asyncio
    async def test_delete_object(self):
        """Test object deletion."""
        mock_client = AsyncMock()
        mock_client.delete_object.return_value = {}
        
        with patch.object(S3Service, 'get_client', return_value=mock_client):
            service = S3Service()
            result = await service.delete_object("test/key.txt")
            
            assert result is True
            mock_client.delete_object.assert_called_once_with(
                Bucket="agentforge-artifacts",
                Key="test/key.txt"
            )