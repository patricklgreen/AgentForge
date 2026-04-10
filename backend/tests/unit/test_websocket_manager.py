"""
Tests for WebSocket Manager
"""
import json
import pytest
from unittest.mock import AsyncMock, Mock, patch

from app.services.websocket_manager import ConnectionManager
from fastapi import WebSocket


@pytest.fixture
def manager():
    return ConnectionManager()


@pytest.fixture
def mock_websocket():
    websocket = Mock(spec=WebSocket)
    websocket.accept = AsyncMock()
    websocket.send_text = AsyncMock()
    return websocket


class TestConnectionManager:
    """Test the ConnectionManager class"""

    def test_init(self, manager):
        """Test manager initialization"""
        assert manager._connections == {}
        assert manager._redis is None

    @patch('app.services.websocket_manager.redis')
    async def test_get_redis_creates_client(self, mock_redis, manager):
        """Test Redis client creation"""
        mock_client = AsyncMock()
        # Make from_url return an awaitable
        async def mock_from_url(*args, **kwargs):
            return mock_client
        mock_redis.from_url = mock_from_url
        
        redis_client = await manager.get_redis()
        
        assert redis_client == mock_client

    @patch('app.services.websocket_manager.redis')
    async def test_get_redis_caches_client(self, mock_redis, manager):
        """Test Redis client caching"""
        mock_client = AsyncMock()
        # Make from_url return an awaitable
        async def mock_from_url(*args, **kwargs):
            return mock_client
        mock_redis.from_url = mock_from_url
        
        redis1 = await manager.get_redis()
        redis2 = await manager.get_redis()
        
        assert redis1 == redis2

    async def test_connect_new_run_id(self, manager, mock_websocket):
        """Test connecting to a new run_id"""
        await manager.connect(mock_websocket, "run123")
        
        assert "run123" in manager._connections
        assert mock_websocket in manager._connections["run123"]
        mock_websocket.accept.assert_called_once()

    async def test_connect_existing_run_id(self, manager, mock_websocket):
        """Test connecting to an existing run_id"""
        websocket2 = Mock(spec=WebSocket)
        websocket2.accept = AsyncMock()
        
        await manager.connect(mock_websocket, "run123")
        await manager.connect(websocket2, "run123")
        
        assert len(manager._connections["run123"]) == 2
        assert mock_websocket in manager._connections["run123"]
        assert websocket2 in manager._connections["run123"]

    def test_disconnect_existing_websocket(self, manager, mock_websocket):
        """Test disconnecting an existing WebSocket"""
        manager._connections["run123"] = [mock_websocket]
        
        manager.disconnect(mock_websocket, "run123")
        
        assert "run123" not in manager._connections

    def test_disconnect_last_websocket_cleans_up(self, manager, mock_websocket):
        """Test that disconnecting the last WebSocket removes the run_id"""
        websocket2 = Mock(spec=WebSocket)
        manager._connections["run123"] = [mock_websocket, websocket2]
        
        manager.disconnect(mock_websocket, "run123")
        
        assert "run123" in manager._connections
        assert mock_websocket not in manager._connections["run123"]
        assert len(manager._connections["run123"]) == 1
        
        manager.disconnect(websocket2, "run123")
        assert "run123" not in manager._connections

    def test_disconnect_nonexistent_websocket(self, manager, mock_websocket):
        """Test disconnecting a WebSocket that doesn't exist"""
        websocket2 = Mock(spec=WebSocket)
        manager._connections["run123"] = [websocket2]
        
        # Should not raise an exception
        manager.disconnect(mock_websocket, "run123")
        
        assert "run123" in manager._connections
        assert websocket2 in manager._connections["run123"]

    def test_disconnect_nonexistent_run_id(self, manager, mock_websocket):
        """Test disconnecting from a non-existent run_id"""
        # Should not raise an exception
        manager.disconnect(mock_websocket, "nonexistent_run")
        
        assert "nonexistent_run" not in manager._connections

    @patch('app.services.websocket_manager.ConnectionManager.get_redis')
    async def test_broadcast_to_run_success(self, mock_get_redis, manager, mock_websocket):
        """Test successful broadcast to run"""
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        
        manager._connections["run123"] = [mock_websocket]
        message = {"type": "test", "data": "hello"}
        
        await manager.broadcast_to_run("run123", message)
        
        expected_json = json.dumps(message, default=str)
        mock_websocket.send_text.assert_called_once_with(expected_json)
        mock_redis.publish.assert_called_once_with("run:run123", expected_json)

    @patch('app.services.websocket_manager.ConnectionManager.get_redis')
    async def test_broadcast_to_run_websocket_error(self, mock_get_redis, manager, mock_websocket):
        """Test broadcast with WebSocket error removes dead connection"""
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        mock_websocket.send_text.side_effect = Exception("Connection error")
        
        manager._connections["run123"] = [mock_websocket]
        message = {"type": "test", "data": "hello"}
        
        await manager.broadcast_to_run("run123", message)
        
        # Dead connection should be removed
        assert mock_websocket not in manager._connections["run123"]
        mock_redis.publish.assert_called_once()

    @patch('app.services.websocket_manager.ConnectionManager.get_redis')
    async def test_broadcast_to_run_redis_error(self, mock_get_redis, manager, mock_websocket):
        """Test broadcast continues despite Redis error"""
        mock_redis = AsyncMock()
        mock_redis.publish.side_effect = Exception("Redis error")
        mock_get_redis.return_value = mock_redis
        
        manager._connections["run123"] = [mock_websocket]
        message = {"type": "test", "data": "hello"}
        
        # Should not raise exception despite Redis error
        await manager.broadcast_to_run("run123", message)
        
        # WebSocket send should still work
        expected_json = json.dumps(message, default=str)
        mock_websocket.send_text.assert_called_once_with(expected_json)

    @patch('app.services.websocket_manager.ConnectionManager.get_redis')
    async def test_broadcast_to_run_nonexistent_run_id(self, mock_get_redis, manager):
        """Test broadcast to non-existent run_id"""
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        
        message = {"type": "test", "data": "hello"}
        
        # Should not raise exception
        await manager.broadcast_to_run("nonexistent_run", message)
        
        # Should still try to publish to Redis
        expected_json = json.dumps(message, default=str)
        mock_redis.publish.assert_called_once_with("run:nonexistent_run", expected_json)

    @patch('app.services.websocket_manager.ConnectionManager.broadcast_to_run')
    async def test_send_agent_event(self, mock_broadcast, manager):
        """Test sending an agent event"""
        await manager.send_agent_event(
            run_id="run123",
            event_type="start",
            agent_name="TestAgent",
            step="analysis",
            message="Starting analysis",
            data={"key": "value"}
        )
        
        expected_event = {
            "type": "start",
            "agent": "TestAgent", 
            "step": "analysis",
            "message": "Starting analysis",
            "data": {"key": "value"}
        }
        mock_broadcast.assert_called_once_with("run123", expected_event)

    @patch('app.services.websocket_manager.ConnectionManager.broadcast_to_run')
    async def test_send_agent_event_no_data(self, mock_broadcast, manager):
        """Test sending an agent event without data"""
        await manager.send_agent_event(
            run_id="run123",
            event_type="complete",
            agent_name="TestAgent",
            step="analysis", 
            message="Analysis complete"
        )
        
        expected_event = {
            "type": "complete",
            "agent": "TestAgent",
            "step": "analysis", 
            "message": "Analysis complete",
            "data": {}
        }
        mock_broadcast.assert_called_once_with("run123", expected_event)

    @patch('app.services.websocket_manager.ConnectionManager.broadcast_to_run')
    async def test_send_interrupt(self, mock_broadcast, manager):
        """Test sending an interrupt event"""
        payload = {"question": "How should we proceed?", "options": ["A", "B"]}
        
        await manager.send_interrupt(
            run_id="run123",
            step="review",
            payload=payload
        )
        
        expected_event = {
            "type": "interrupt",
            "step": "review",
            "payload": payload,
            "message": "Human review required at step: review"
        }
        mock_broadcast.assert_called_once_with("run123", expected_event)

    def test_connections_management(self, manager, mock_websocket):
        """Test internal connections management"""
        # Test that connections are properly stored and managed
        manager._connections["run123"] = [mock_websocket]
        
        # Access internal state for verification
        assert "run123" in manager._connections
        assert len(manager._connections["run123"]) == 1
        assert manager._connections["run123"][0] == mock_websocket

    async def test_json_serialization_in_broadcast(self, manager, mock_websocket):
        """Test JSON serialization handling in broadcast"""
        mock_websocket.send_text = AsyncMock()
        manager._connections["run123"] = [mock_websocket]
        
        # Test with complex data that needs default=str
        from datetime import datetime
        message = {
            "type": "test",
            "timestamp": datetime.now(),
            "data": {"nested": True}
        }
        
        with patch('app.services.websocket_manager.ConnectionManager.get_redis') as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            
            await manager.broadcast_to_run("run123", message)
            
            # Verify that JSON serialization was called
            mock_websocket.send_text.assert_called_once()
            sent_data = mock_websocket.send_text.call_args[0][0]
            
            # Should be valid JSON
            parsed = json.loads(sent_data)
            assert parsed["type"] == "test"
            assert "timestamp" in parsed
            assert parsed["data"]["nested"] is True