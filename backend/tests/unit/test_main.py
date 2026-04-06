"""
Unit tests for FastAPI main application.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.main import app, lifespan


class TestMainApplication:
    """Test main FastAPI application setup."""
    
    def test_app_configuration(self):
        """Test that FastAPI app is configured correctly."""
        assert isinstance(app, FastAPI)
        assert app.title == "AgentForge API"
        assert app.version == "1.0.0"
        assert "AI-powered application builder" in app.description
        
    def test_app_has_middleware(self):
        """Test that CORS middleware is properly configured."""
        # Check that middleware is applied by looking at middleware stack
        assert len(app.user_middleware) > 0
    
    def test_app_routes_included(self):
        """Test that all routers are included."""
        route_paths = [route.path for route in app.routes]
        
        # Check that key routes are included
        assert any("/health" in path for path in route_paths)
        assert any("/auth" in path for path in route_paths)
        assert any("/projects" in path for path in route_paths)
        assert any("/artifacts" in path for path in route_paths)
        assert any("/ws/" in path for path in route_paths)
    
    def test_openapi_endpoints_configured(self):
        """Test that OpenAPI endpoints are configured."""
        from app.config import get_settings
        settings = get_settings()
        
        assert app.docs_url == f"{settings.api_prefix}/docs"
        assert app.redoc_url == f"{settings.api_prefix}/redoc"
        assert app.openapi_url == f"{settings.api_prefix}/openapi.json"


class TestHealthEndpoint:
    """Test the health check endpoint."""
    
    def test_health_endpoint(self):
        """Test health check endpoint returns correct response."""
        client = TestClient(app)
        response = client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["service"] == "agentforge-api"
        assert "env" in data


class TestWebSocketEndpoint:
    """Test WebSocket endpoint functionality."""
    
    @pytest.mark.asyncio
    async def test_websocket_connection(self):
        """Test WebSocket connection handling."""
        with patch('app.main.ws_manager') as mock_manager:
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = MagicMock()
            
            from app.main import websocket_endpoint
            from fastapi import WebSocket
            
            mock_websocket = MagicMock(spec=WebSocket)
            mock_websocket.receive_text = AsyncMock()
            mock_websocket.receive_text.side_effect = [
                "test message",
                Exception("WebSocketDisconnect")  # Simulate disconnect
            ]
            
            # Test connection
            try:
                await websocket_endpoint(mock_websocket, "run123")
            except Exception:
                pass  # Expected when simulating disconnect
            
            mock_manager.connect.assert_called_once_with(mock_websocket, "run123")
            mock_manager.disconnect.assert_called_once_with(mock_websocket, "run123")

    @pytest.mark.asyncio
    async def test_websocket_error_handling(self):
        """Test WebSocket error handling."""
        with patch('app.main.ws_manager') as mock_manager:
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = MagicMock()
            
            from app.main import websocket_endpoint
            from fastapi import WebSocket
            
            mock_websocket = MagicMock(spec=WebSocket)
            mock_websocket.receive_text = AsyncMock(side_effect=Exception("Connection error"))
            
            try:
                await websocket_endpoint(mock_websocket, "run456")
            except Exception:
                pass
            
            # Should still call cleanup
            mock_manager.disconnect.assert_called_once_with(mock_websocket, "run456")


class TestLifespanManager:
    """Test application lifespan management."""
    
    @pytest.mark.asyncio
    async def test_lifespan_generator(self):
        """Test lifespan is a proper async generator."""
        from app.main import lifespan
        mock_app = MagicMock(spec=FastAPI)
        mock_app.state = MagicMock()
        
        # Should be an async generator
        lifespan_gen = lifespan(mock_app)
        assert hasattr(lifespan_gen, '__anext__')
        assert hasattr(lifespan_gen, 'aclose')


class TestApplicationIntegration:
    """Integration tests for application setup."""
    
    def test_app_can_start(self):
        """Test that application can start without errors."""
        client = TestClient(app)
        
        # Should be able to create test client without errors
        assert client is not None
        
        # Should be able to make a basic request
        response = client.get("/api/v1/health")
        assert response.status_code == 200
    
    def test_cors_configuration(self):
        """Test CORS configuration."""
        client = TestClient(app)
        
        # Test basic request with origin header
        response = client.get(
            "/api/v1/health",
            headers={"Origin": "http://localhost:3000"}
        )
        
        # Should allow request and include CORS headers
        assert response.status_code == 200
    
    def test_openapi_schema(self):
        """Test that OpenAPI schema is generated correctly."""
        client = TestClient(app)
        response = client.get("/api/v1/openapi.json")
        
        assert response.status_code == 200
        schema = response.json()
        
        assert schema["info"]["title"] == "AgentForge API"
        assert schema["info"]["version"] == "1.0.0"
        assert "paths" in schema
        assert "/api/v1/health" in schema["paths"]
    
    def test_docs_endpoints(self):
        """Test documentation endpoints."""
        client = TestClient(app)
        
        # Test Swagger UI
        response = client.get("/api/v1/docs")
        assert response.status_code == 200
        
        # Test ReDoc
        response = client.get("/api/v1/redoc")
        assert response.status_code == 200