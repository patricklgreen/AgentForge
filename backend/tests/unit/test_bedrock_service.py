"""
Unit tests for Bedrock service.
"""
import json
import pytest
from botocore.exceptions import EndpointConnectionError
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.bedrock import BedrockService
from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel


class MockResponse(BaseModel):
    test_field: str


class TestBedrockService:
    """Test Bedrock AI service."""

    def test_init(self):
        """Test service initialization."""
        service = BedrockService()
        assert service._client is None
        assert service._llm_cache == {}

    @pytest.mark.asyncio
    async def test_client_property_creates_boto3_client(self):
        """Test client property creates boto3 client."""
        with patch('boto3.client') as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.return_value = mock_client
            
            service = BedrockService()
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
            
            service = BedrockService()
            client1 = service.client
            client2 = service.client
            
            assert client1 == client2
            # boto3.client should only be called once due to caching
            mock_boto3.assert_called_once()

    def test_get_llm_returns_chatbedrock(self):
        """Test get_llm returns ChatBedrock instance."""
        with patch('boto3.client'):
            service = BedrockService()
            
            with patch('app.services.bedrock.ChatBedrock') as mock_chatbedrock:
                mock_llm = MagicMock()
                mock_chatbedrock.return_value = mock_llm
                
                llm = service.get_llm()
                
                assert llm == mock_llm
                mock_chatbedrock.assert_called_once()

    def test_get_llm_creates_fresh_instances(self):
        """Each get_llm call builds a new ChatBedrock (no stale boto clients)."""
        with patch('boto3.client'):
            service = BedrockService()
            
            with patch('app.services.bedrock.ChatBedrock') as mock_chatbedrock:
                mock_llm1 = MagicMock()
                mock_llm2 = MagicMock()
                mock_chatbedrock.side_effect = [mock_llm1, mock_llm2]
                
                llm1 = service.get_llm(model_id="claude-3-haiku", temperature=0.1)
                llm2 = service.get_llm(model_id="claude-3-haiku", temperature=0.1)
                
                assert llm1 is mock_llm1
                assert llm2 is mock_llm2
                assert mock_chatbedrock.call_count == 2

    def test_get_llm_different_configs_create_different_instances(self):
        """Test get_llm creates different instances for different configs."""
        with patch('boto3.client'):
            service = BedrockService()
            
            with patch('app.services.bedrock.ChatBedrock') as mock_chatbedrock:
                mock_llm1 = MagicMock()
                mock_llm2 = MagicMock()
                mock_chatbedrock.side_effect = [mock_llm1, mock_llm2]
                
                llm1 = service.get_llm(model_id="claude-3-haiku", temperature=0.1)
                llm2 = service.get_llm(model_id="claude-3-sonnet", temperature=0.1)
                
                assert llm1 != llm2
                assert mock_chatbedrock.call_count == 2

    def test_get_fast_llm_returns_haiku_model(self):
        """Test get_fast_llm returns Haiku model with correct config."""
        with patch('boto3.client'):
            service = BedrockService()
            
            with patch('app.services.bedrock.ChatBedrock') as mock_chatbedrock:
                mock_llm = MagicMock()
                mock_chatbedrock.return_value = mock_llm
                
                llm = service.get_fast_llm()
                
                # Verify it was called with Haiku model - check the actual model ID used
                call_args = mock_chatbedrock.call_args
                assert call_args is not None
                assert "haiku" in str(call_args).lower()

    @pytest.mark.asyncio
    async def test_invoke_with_json_output_success(self):
        """Test invoke_with_json_output with successful parsing."""
        with patch('boto3.client'):
            service = BedrockService()
            
            with patch.object(service, 'invoke', new_callable=AsyncMock) as mock_invoke:
                mock_invoke.return_value = (
                    '{"test_field": "test_value"}',
                    {"model_id": "m", "input_tokens": 1, "output_tokens": 2},
                )
                
                result, usage = await service.invoke_with_json_output(
                    "test system", 
                    "test prompt"
                )
                
                assert result == {"test_field": "test_value"}
                assert usage["model_id"] == "m"
                mock_invoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_invoke_with_json_output_json_error(self):
        """Test invoke_with_json_output with JSON parsing error."""
        with patch('boto3.client'):
            service = BedrockService()
            
            with patch.object(service, 'invoke', new_callable=AsyncMock) as mock_invoke:
                mock_invoke.return_value = (
                    "invalid json",
                    {"model_id": "m", "input_tokens": 0, "output_tokens": 0},
                )
                
                with pytest.raises(json.JSONDecodeError):
                    await service.invoke_with_json_output(
                        "test system", 
                        "test prompt"
                    )

    @pytest.mark.asyncio
    async def test_invoke_structured_success(self):
        """Test invoke_structured with successful validation."""
        with patch('boto3.client'):
            service = BedrockService()
            
            with patch.object(service, 'invoke_with_json_output', new_callable=AsyncMock) as mock_invoke:
                mock_invoke.return_value = (
                    {"test_field": "test_value"},
                    {"model_id": "m", "input_tokens": 1, "output_tokens": 2},
                )
                
                result = await service.invoke_structured(
                    "test system", 
                    "test prompt",
                    MockResponse
                )
                
                assert isinstance(result, MockResponse)
                assert result.test_field == "test_value"

    @pytest.mark.asyncio
    async def test_invoke_method(self):
        """Test invoke method."""
        with patch('boto3.client'):
            service = BedrockService()
            
            mock_llm = AsyncMock()
            mock_response = MagicMock()
            mock_response.content = "test response"
            mock_llm.ainvoke.return_value = mock_response
            
            with patch.object(service, '_new_chat_bedrock', return_value=mock_llm):
                content, usage = await service.invoke(
                    "test system",
                    "test user message"
                )
                
                assert content == "test response"
                assert usage["model_id"]
                mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_invoke_retries_on_endpoint_connection_error(self):
        """Transient disconnect / offline: retry then succeed."""
        with patch("boto3.client"):
            service = BedrockService()
            mock_llm = AsyncMock()
            mock_response = MagicMock()
            mock_response.content = "recovered"
            err = EndpointConnectionError(endpoint_url="https://bedrock-runtime.us-east-1.amazonaws.com")
            mock_llm.ainvoke.side_effect = [err, mock_response]
            with patch.object(service, "_new_chat_bedrock", return_value=mock_llm):
                with patch("app.services.bedrock.asyncio.sleep", new_callable=AsyncMock):
                    content, _ = await service.invoke("s", "u")
            assert content == "recovered"
            assert mock_llm.ainvoke.call_count == 2

    @pytest.mark.asyncio
    async def test_invoke_retries_on_connection_message(self):
        """String form of endpoint errors (wrapped exceptions) still retries."""
        with patch("boto3.client"):
            service = BedrockService()
            mock_llm = AsyncMock()
            mock_response = MagicMock()
            mock_response.content = "ok"
            msg = 'Could not connect to the endpoint URL: "https://bedrock-runtime.us-east-1.amazonaws.com/..."'
            mock_llm.ainvoke.side_effect = [Exception(msg), mock_response]
            with patch.object(service, "_new_chat_bedrock", return_value=mock_llm):
                with patch("app.services.bedrock.asyncio.sleep", new_callable=AsyncMock):
                    content, _ = await service.invoke("s", "u")
            assert content == "ok"
            assert mock_llm.ainvoke.call_count == 2

    def test_clear_cache(self):
        """Test clear_cache method."""
        with patch('boto3.client'):
            service = BedrockService()
            
            # Add something to cache
            service._llm_cache["test"] = MagicMock()
            assert len(service._llm_cache) == 1
            
            service.clear_cache()
            assert len(service._llm_cache) == 0

    def test_parse_json_response_with_code_block(self):
        """Test _parse_json_response with JSON in code block."""
        content = '''Here's the JSON:
```json
{"test": "value"}
```
That's it!'''
        
        result = BedrockService._parse_json_response(content)
        assert result == {"test": "value"}

    def test_parse_json_response_plain_json(self):
        """Test _parse_json_response with plain JSON."""
        content = '{"test": "value"}'
        
        result = BedrockService._parse_json_response(content)
        assert result == {"test": "value"}

    def test_parse_json_response_with_fences(self):
        """Test _parse_json_response with markdown fences."""
        content = '''```
{"test": "value"}
```'''
        
        result = BedrockService._parse_json_response(content)
        assert result == {"test": "value"}

    def test_parse_json_response_with_curly_braces(self):
        """Test _parse_json_response with JSON in curly braces."""
        content = 'Some text {"test": "value"} more text'
        
        result = BedrockService._parse_json_response(content)
        assert result == {"test": "value"}

    @pytest.mark.asyncio
    async def test_client_creation_with_aws_credentials(self):
        """Test client creation when AWS credentials are provided."""
        with patch('boto3.client') as mock_boto3, \
             patch('app.services.bedrock.settings') as mock_settings:
            
            # Create mock settings object with attributes
            mock_settings.aws_region = "us-west-2"
            mock_settings.aws_access_key_id = "test_key"  
            mock_settings.aws_secret_access_key = "test_secret"
            
            mock_client = MagicMock()
            mock_boto3.return_value = mock_client
            
            service = BedrockService()
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
             patch('app.services.bedrock.settings') as mock_settings:
            
            # Create mock settings object with no credentials
            mock_settings.aws_region = "us-east-1"
            mock_settings.aws_access_key_id = None
            mock_settings.aws_secret_access_key = None
            
            mock_client = MagicMock()
            mock_boto3.return_value = mock_client
            
            service = BedrockService()
            client = service.client
            
            # Verify boto3.client was called without credentials
            mock_boto3.assert_called_once()
            call_kwargs = mock_boto3.call_args[1]
            assert "aws_access_key_id" not in call_kwargs
            assert "aws_secret_access_key" not in call_kwargs
            assert call_kwargs["region_name"] == "us-east-1"