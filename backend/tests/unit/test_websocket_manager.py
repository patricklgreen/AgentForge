"""
Unit tests for WebSocket connection manager.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
from fastapi import WebSocket
from app.services.websocket_manager import ConnectionManager


class TestConnectionManager:
    """Test ConnectionManager functionality."""

    def test_init(self):
        """Test manager initialization."""
        manager = ConnectionManager()
        assert manager._connections == {}
        assert manager._redis is None

    @pytest.mark.asyncio
    async def test_connect(self):
        """Test WebSocket connection."""
        manager = ConnectionManager()
        mock_websocket = AsyncMock()
        
        await manager.connect(mock_websocket, "run123")
        
        assert "run123" in manager._connections
        assert mock_websocket in manager._connections["run123"]
        mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_multiple_to_same_run(self):
        """Test multiple WebSocket connections to same run."""
        manager = ConnectionManager()
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        
        await manager.connect(mock_ws1, "run123")
        await manager.connect(mock_ws2, "run123")
        
        assert len(manager._connections["run123"]) == 2
        assert mock_ws1 in manager._connections["run123"]
        assert mock_ws2 in manager._connections["run123"]

    def test_disconnect(self):
        """Test WebSocket disconnection."""
        manager = ConnectionManager()
        mock_websocket = AsyncMock()
        
        # Set up connection manually
        manager._connections["run123"] = [mock_websocket]
        
        manager.disconnect(mock_websocket, "run123")
        
        assert "run123" not in manager._connections

    def test_disconnect_nonexistent_connection(self):
        """Test disconnecting nonexistent connection."""
        manager = ConnectionManager()
        mock_websocket = AsyncMock()
        
        # Should not raise exception
        manager.disconnect(mock_websocket, "nonexistent_run")

    def test_disconnect_with_multiple_connections(self):
        """Test disconnecting one of multiple connections."""
        manager = ConnectionManager()
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        
        manager._connections["run123"] = [mock_ws1, mock_ws2]
        
        manager.disconnect(mock_ws1, "run123")
        
        assert "run123" in manager._connections
        assert len(manager._connections["run123"]) == 1
        assert mock_ws2 in manager._connections["run123"]
        assert mock_ws1 not in manager._connections["run123"]

    @pytest.mark.asyncio
    async def test_broadcast_to_run(self):
        """Test broadcasting message to run."""
        manager = ConnectionManager()
        mock_websocket = AsyncMock()
        
        manager._connections["run123"] = [mock_websocket]
        
        event = {"type": "test", "message": "Hello"}
        await manager.broadcast_to_run("run123", event)
        
        mock_websocket.send_text.assert_called_once()
        sent_data = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_data == event

    @pytest.mark.asyncio
    async def test_broadcast_to_nonexistent_run(self):
        """Test broadcasting to nonexistent run."""
        manager = ConnectionManager()
        
        event = {"type": "test", "message": "Hello"}
        # Should not raise exception
        await manager.broadcast_to_run("nonexistent_run", event)

    @pytest.mark.asyncio
    async def test_broadcast_with_connection_error(self):
        """Test broadcasting with WebSocket connection error."""
        manager = ConnectionManager()
        mock_websocket = AsyncMock()
        mock_websocket.send_text.side_effect = Exception("Connection error")
        
        manager._connections["run123"] = [mock_websocket]
        
        event = {"type": "test", "message": "Hello"}
        await manager.broadcast_to_run("run123", event)
        
        # Connection should be removed after error, but empty list may remain
        assert mock_websocket not in manager._connections.get("run123", [])

    @pytest.mark.asyncio
    async def test_send_agent_event(self):
        """Test sending agent event."""
        manager = ConnectionManager()
        mock_websocket = AsyncMock()
        
        manager._connections["run123"] = [mock_websocket]
        
        await manager.send_agent_event(
            "run123", 
            "agent_update", 
            "requirements_analyst", 
            "analysis", 
            "Analyzing requirements"
        )
        
        mock_websocket.send_text.assert_called_once()
        sent_data = json.loads(mock_websocket.send_text.call_args[0][0])
        
        assert sent_data["type"] == "agent_update"
        assert sent_data["agent"] == "requirements_analyst"
        assert sent_data["step"] == "analysis"
        assert sent_data["message"] == "Analyzing requirements"
        assert sent_data["data"] == {}

    @pytest.mark.asyncio
    async def test_send_agent_event_with_data(self):
        """Test sending agent event with additional data."""
        manager = ConnectionManager()
        mock_websocket = AsyncMock()
        
        manager._connections["run123"] = [mock_websocket]
        
        extra_data = {"progress": 50, "status": "in_progress"}
        await manager.send_agent_event(
            "run123", 
            "progress_update", 
            "code_generator", 
            "generation", 
            "Generating code",
            extra_data
        )
        
        mock_websocket.send_text.assert_called_once()
        sent_data = json.loads(mock_websocket.send_text.call_args[0][0])
        
        assert sent_data["data"] == extra_data

    @pytest.mark.asyncio
    async def test_send_interrupt(self):
        """Test sending interrupt event."""
        manager = ConnectionManager()
        mock_websocket = AsyncMock()
        
        manager._connections["run123"] = [mock_websocket]
        
        interrupt_payload = {
            "title": "Review Requirements",
            "description": "Please review the requirements",
            "data": {"requirements": ["req1", "req2"]}
        }
        
        await manager.send_interrupt("run123", "requirements_review", interrupt_payload)
        
        mock_websocket.send_text.assert_called_once()
        sent_data = json.loads(mock_websocket.send_text.call_args[0][0])
        
        assert sent_data["type"] == "interrupt"
        assert sent_data["step"] == "requirements_review"
        assert sent_data["payload"] == interrupt_payload
        assert "Human review required" in sent_data["message"]

    @pytest.mark.asyncio
    async def test_get_redis(self):
        """Test Redis connection initialization."""
        manager = ConnectionManager()
        mock_redis_instance = AsyncMock()
        
        with patch('redis.asyncio.from_url', return_value=mock_redis_instance):
            redis_client = await manager.get_redis()
            
            assert redis_client == mock_redis_instance
            assert manager._redis == mock_redis_instance

    @pytest.mark.asyncio
    async def test_redis_publish_in_broadcast(self):
        """Test Redis publishing in broadcast_to_run."""
        manager = ConnectionManager()
        mock_redis_client = AsyncMock()
        
        with patch('redis.asyncio.from_url', return_value=mock_redis_client):
            event = {"type": "test", "message": "Hello"}
            await manager.broadcast_to_run("run123", event)
            
            mock_redis_client.publish.assert_called_once_with(
                "run:run123", 
                json.dumps(event, default=str)
            )

    @pytest.mark.asyncio
    async def test_redis_publish_error_handling(self):
        """Test Redis publish error handling."""
        manager = ConnectionManager()
        mock_redis_client = AsyncMock()
        mock_redis_client.publish.side_effect = Exception("Redis error")
        
        with patch('redis.asyncio.from_url', return_value=mock_redis_client):
            event = {"type": "test", "message": "Hello"}
            # Should not raise exception despite Redis error
            await manager.broadcast_to_run("run123", event)

    @pytest.mark.asyncio
    async def test_multiple_runs_isolation(self):
        """Test that runs are properly isolated."""
        manager = ConnectionManager()
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        
        await manager.connect(mock_ws1, "run1")
        await manager.connect(mock_ws2, "run2")
        
        event = {"type": "test", "message": "Hello run1"}
        await manager.broadcast_to_run("run1", event)
        
        # Only run1 connection should receive the message
        mock_ws1.send_text.assert_called_once()
        mock_ws2.send_text.assert_not_called()