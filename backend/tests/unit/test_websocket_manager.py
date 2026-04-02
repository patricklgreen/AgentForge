"""
Unit tests for WebSocket manager.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
from fastapi import WebSocket
from app.services.websocket_manager import WebSocketManager


class TestWebSocketManager:
    """Test WebSocket connection manager."""

    def test_init(self):
        """Test manager initialization."""
        manager = WebSocketManager()
        assert len(manager.active_connections) == 0

    @pytest.mark.asyncio
    async def test_connect(self):
        """Test WebSocket connection."""
        manager = WebSocketManager()
        mock_websocket = AsyncMock()
        
        await manager.connect(mock_websocket, "user123")
        
        assert "user123" in manager.active_connections
        assert mock_websocket in manager.active_connections["user123"]
        mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test WebSocket disconnection."""
        manager = WebSocketManager()
        mock_websocket = AsyncMock()
        
        # Connect first
        await manager.connect(mock_websocket, "user123")
        assert "user123" in manager.active_connections
        
        # Then disconnect
        manager.disconnect(mock_websocket, "user123")
        assert mock_websocket not in manager.active_connections.get("user123", [])

    @pytest.mark.asyncio
    async def test_send_personal_message(self):
        """Test sending personal message."""
        manager = WebSocketManager()
        mock_websocket = AsyncMock()
        
        await manager.connect(mock_websocket, "user123")
        await manager.send_personal_message("Hello", "user123")
        
        mock_websocket.send_text.assert_called_once_with("Hello")

    @pytest.mark.asyncio
    async def test_send_personal_message_no_connection(self):
        """Test sending message to non-connected user."""
        manager = WebSocketManager()
        
        # Should not raise exception
        await manager.send_personal_message("Hello", "nonexistent_user")

    @pytest.mark.asyncio
    async def test_broadcast(self):
        """Test broadcasting message."""
        manager = WebSocketManager()
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        
        await manager.connect(mock_ws1, "user1")
        await manager.connect(mock_ws2, "user2")
        
        await manager.broadcast("Broadcast message")
        
        mock_ws1.send_text.assert_called_once_with("Broadcast message")
        mock_ws2.send_text.assert_called_once_with("Broadcast message")

    @pytest.mark.asyncio
    async def test_send_agent_event(self):
        """Test sending agent event."""
        manager = WebSocketManager()
        mock_websocket = AsyncMock()
        
        await manager.connect(mock_websocket, "user123")
        
        event_data = {
            "type": "agent_update",
            "agent": "requirements_analyst",
            "status": "running"
        }
        
        await manager.send_agent_event("user123", "run456", event_data)
        
        mock_websocket.send_text.assert_called_once()
        sent_data = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_data["type"] == "agent_event"
        assert sent_data["run_id"] == "run456"
        assert sent_data["data"] == event_data

    @pytest.mark.asyncio
    async def test_send_interrupt(self):
        """Test sending interrupt event."""
        manager = WebSocketManager()
        mock_websocket = AsyncMock()
        
        await manager.connect(mock_websocket, "user123")
        
        interrupt_data = {
            "step": "requirements_review",
            "title": "Review Requirements",
            "description": "Please review the requirements",
            "data": {"requirements": ["req1", "req2"]}
        }
        
        await manager.send_interrupt("user123", "run456", interrupt_data)
        
        mock_websocket.send_text.assert_called_once()
        sent_data = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_data["type"] == "interrupt"
        assert sent_data["run_id"] == "run456"
        assert sent_data["data"] == interrupt_data

    @pytest.mark.asyncio
    async def test_broadcast_to_run(self):
        """Test broadcasting to specific run subscribers."""
        manager = WebSocketManager()
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        mock_ws3 = AsyncMock()
        
        # Connect users
        await manager.connect(mock_ws1, "user1")
        await manager.connect(mock_ws2, "user2")
        await manager.connect(mock_ws3, "user3")
        
        # Subscribe users to different runs
        manager.run_subscribers["run123"] = ["user1", "user2"]
        manager.run_subscribers["run456"] = ["user3"]
        
        event_data = {"status": "completed"}
        await manager.broadcast_to_run("run123", event_data)
        
        # Only users subscribed to run123 should receive the message
        mock_ws1.send_text.assert_called_once()
        mock_ws2.send_text.assert_called_once()
        mock_ws3.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_connection_cleanup_on_error(self):
        """Test connection cleanup when send fails."""
        manager = WebSocketManager()
        mock_websocket = AsyncMock()
        mock_websocket.send_text.side_effect = Exception("Connection closed")
        
        await manager.connect(mock_websocket, "user123")
        await manager.send_personal_message("Hello", "user123")
        
        # Connection should be removed after error
        assert mock_websocket not in manager.active_connections.get("user123", [])

    def test_get_connection_count(self):
        """Test getting total connection count."""
        manager = WebSocketManager()
        
        # Initially 0
        assert manager.get_connection_count() == 0
        
        # Add some mock connections
        manager.active_connections["user1"] = [MagicMock(), MagicMock()]
        manager.active_connections["user2"] = [MagicMock()]
        
        assert manager.get_connection_count() == 3

    def test_get_user_connections(self):
        """Test getting connections for specific user."""
        manager = WebSocketManager()
        mock_ws1 = MagicMock()
        mock_ws2 = MagicMock()
        
        manager.active_connections["user1"] = [mock_ws1, mock_ws2]
        
        connections = manager.get_user_connections("user1")
        assert len(connections) == 2
        assert mock_ws1 in connections
        assert mock_ws2 in connections
        
        # Non-existent user
        connections = manager.get_user_connections("nonexistent")
        assert len(connections) == 0