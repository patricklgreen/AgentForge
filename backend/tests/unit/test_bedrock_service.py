"""
Unit tests for Bedrock service.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.bedrock import BedrockService


class TestBedrockService:
    """Test Bedrock AI service."""

    def test_init(self):
        """Test service initialization."""
        service = BedrockService()
        assert service.region == "us-east-1"
        assert service.client is None

    @pytest.mark.asyncio
    async def test_get_client(self):
        """Test client creation."""
        with patch('boto3.client') as mock_boto:
            mock_client = MagicMock()
            mock_boto.return_value = mock_client
            
            service = BedrockService()
            client = await service.get_client()
            
            assert client == mock_client
            mock_boto.assert_called_once_with('bedrock-runtime', region_name='us-east-1')

    @pytest.mark.asyncio
    async def test_invoke_model(self):
        """Test model invocation."""
        mock_client = AsyncMock()
        mock_client.invoke_model.return_value = {
            'body': MagicMock(read=MagicMock(return_value=b'{"completion": "test response"}'))
        }
        
        with patch.object(BedrockService, 'get_client', return_value=mock_client):
            service = BedrockService()
            result = await service.invoke_model("test prompt", "test-model-id")
            
            assert result == "test response"
            mock_client.invoke_model.assert_called_once()

    @pytest.mark.asyncio
    async def test_invoke_model_with_streaming(self):
        """Test model invocation with streaming."""
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.__aiter__.return_value = [
            {"chunk": {"bytes": b'{"completion": "test"}'}},
            {"chunk": {"bytes": b'{"completion": " response"}'}}
        ]
        mock_client.invoke_model_with_response_stream.return_value = {"body": mock_response}
        
        with patch.object(BedrockService, 'get_client', return_value=mock_client):
            service = BedrockService()
            result = []
            async for chunk in service.invoke_model_stream("test prompt", "test-model-id"):
                result.append(chunk)
            
            assert len(result) == 2
            assert result[0] == "test"
            assert result[1] == " response"

    def test_get_llm(self):
        """Test LLM instance creation."""
        service = BedrockService()
        llm = service.get_llm("test-model-id")
        
        assert llm is not None
        assert hasattr(llm, 'model_id')

    def test_get_fast_llm(self):
        """Test fast LLM instance creation."""
        service = BedrockService()
        fast_llm = service.get_fast_llm()
        
        assert fast_llm is not None
        assert hasattr(fast_llm, 'model_id')