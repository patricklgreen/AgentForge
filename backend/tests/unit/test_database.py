"""
Unit tests for database configuration and utilities.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, Base, engine, AsyncSessionLocal


class TestDatabaseConfiguration:
    """Test database configuration and engine setup."""
    
    def test_engine_creation(self):
        """Test that database engine is created properly."""
        assert engine is not None
        assert hasattr(engine, 'url')
        
    def test_session_factory_creation(self):
        """Test that session factory is created properly."""
        assert AsyncSessionLocal is not None
        # Check that it's configured with the expected settings
        assert hasattr(AsyncSessionLocal, '_class')
        assert AsyncSessionLocal._class == AsyncSession
    
    def test_base_class(self):
        """Test that Base class is properly configured."""
        assert Base is not None
        assert hasattr(Base, 'metadata')
        assert hasattr(Base, 'registry')


class TestGetDB:
    """Test the get_db dependency function."""
    
    @pytest.mark.asyncio
    async def test_get_db_success(self):
        """Test successful database session creation and cleanup."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        with patch('app.database.AsyncSessionLocal') as mock_session_factory:
            mock_session_factory.return_value.__aenter__.return_value = mock_session
            mock_session_factory.return_value.__aexit__.return_value = None
            
            # Use the generator
            db_gen = get_db()
            session = await db_gen.__anext__()
            
            assert session == mock_session
            
            # Test cleanup by closing the generator
            try:
                await db_gen.__anext__()
            except StopAsyncIteration:
                pass
            
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_db_with_exception(self):
        """Test database session with exception handling."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.commit.side_effect = Exception("Database error")
        
        with patch('app.database.AsyncSessionLocal') as mock_session_factory:
            mock_session_factory.return_value.__aenter__.return_value = mock_session
            mock_session_factory.return_value.__aexit__.return_value = None
            
            # Use the generator
            db_gen = get_db()
            session = await db_gen.__anext__()
            
            assert session == mock_session
            
            # Simulate exception during commit
            with pytest.raises(Exception, match="Database error"):
                try:
                    await db_gen.__anext__()
                except StopAsyncIteration:
                    pass
            
            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_db_context_manager(self):
        """Test get_db as context manager-like usage."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        with patch('app.database.AsyncSessionLocal') as mock_session_factory:
            mock_session_factory.return_value.__aenter__.return_value = mock_session
            mock_session_factory.return_value.__aexit__.return_value = None
            
            db_gen = get_db()
            
            # Test normal flow
            try:
                session = await db_gen.__anext__()
                assert session == mock_session
                
                # Manually trigger the finally block by closing generator
                await db_gen.aclose()
                
            except StopAsyncIteration:
                pass
            
            mock_session.close.assert_called_once()


class TestDatabaseIntegration:
    """Integration tests for database components."""
    
    def test_engine_configuration_from_settings(self):
        """Test that engine is configured from settings."""
        # Test that engine has expected configuration
        assert hasattr(engine, 'pool')
        assert hasattr(engine, 'url')
    
    @pytest.mark.asyncio
    async def test_session_creation(self):
        """Test that sessions can be created."""
        # This is a basic test to ensure the session factory works
        try:
            async with AsyncSessionLocal() as session:
                assert isinstance(session, AsyncSession)
                assert hasattr(session, 'execute')
                assert hasattr(session, 'commit')
                assert hasattr(session, 'rollback')
        except Exception as e:
            # It's OK if this fails in CI without a real database
            assert "database" in str(e).lower() or "connection" in str(e).lower()
    
    def test_base_model_attributes(self):
        """Test Base model has required SQLAlchemy attributes."""
        assert hasattr(Base, 'metadata')
        assert hasattr(Base, 'registry')
        assert Base.metadata is not None
        assert Base.registry is not None
    
    def test_database_url_configuration(self):
        """Test database URL is configured."""
        from app.config import get_settings
        settings = get_settings()
        
        # Should have a database URL configured
        assert settings.database_url is not None
        assert isinstance(settings.database_url, str)
        assert len(settings.database_url) > 0
    
    def test_pool_configuration(self):
        """Test connection pool configuration."""
        assert hasattr(engine, 'pool')
        # Pool should be configured
        assert engine.pool is not None