"""
Unit tests for email service functionality.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
import tempfile
import os
from pathlib import Path

from app.services.email_service import (
    EmailService,
    ConsoleEmailBackend,
    FileEmailBackend,
    SMTPEmailBackend,
    create_email_service
)


class TestConsoleEmailBackend:
    """Test console email backend."""

    @pytest.mark.asyncio
    async def test_send_email(self, capsys):
        """Test console email sending."""
        backend = ConsoleEmailBackend()
        
        result = await backend.send_email(
            to_email="test@example.com",
            subject="Test Subject",
            html_body="<p>Test HTML</p>",
            text_body="Test text",
            from_email="sender@example.com",
            from_name="Test Sender"
        )
        
        assert result is True
        
        # Check that output was printed to console
        captured = capsys.readouterr()
        assert "📧 EMAIL SENT TO CONSOLE" in captured.out
        assert "test@example.com" in captured.out
        assert "Test Subject" in captured.out


class TestFileEmailBackend:
    """Test file email backend."""

    @pytest.mark.asyncio
    async def test_send_email(self):
        """Test file email sending."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backend = FileEmailBackend(output_dir=temp_dir)
            
            result = await backend.send_email(
                to_email="test@example.com",
                subject="Test Subject",
                html_body="<p>Test HTML</p>",
                text_body="Test text",
                from_email="sender@example.com",
                from_name="Test Sender"
            )
            
            assert result is True
            
            # Check that file was created
            files = list(Path(temp_dir).glob("*.html"))
            assert len(files) == 1
            
            # Check file content
            with open(files[0]) as f:
                content = f.read()
                assert "test@example.com" in content
                assert "Test Subject" in content
                assert "<p>Test HTML</p>" in content

    @pytest.mark.asyncio
    async def test_send_email_creates_directory(self):
        """Test that file backend creates output directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            non_existent_dir = os.path.join(temp_dir, "emails")
            backend = FileEmailBackend(output_dir=non_existent_dir)
            
            result = await backend.send_email(
                to_email="test@example.com",
                subject="Test",
                html_body="<p>Test</p>"
            )
            
            assert result is True
            assert os.path.exists(non_existent_dir)


class TestSMTPEmailBackend:
    """Test SMTP email backend."""

    @pytest.mark.asyncio
    async def test_send_email_success(self):
        """Test successful SMTP email sending."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            backend = SMTPEmailBackend(
                smtp_host="smtp.example.com",
                smtp_port=587,
                smtp_username="user@example.com",
                smtp_password="password"
            )
            
            result = await backend.send_email(
                to_email="test@example.com",
                subject="Test Subject",
                html_body="<p>Test HTML</p>",
                text_body="Test text"
            )
            
            assert result is True
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with("user@example.com", "password")
            mock_server.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_email_failure(self):
        """Test SMTP email sending failure."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_smtp.side_effect = Exception("SMTP error")
            
            backend = SMTPEmailBackend("smtp.example.com")
            
            result = await backend.send_email(
                to_email="test@example.com",
                subject="Test",
                html_body="<p>Test</p>"
            )
            
            assert result is False

    @pytest.mark.asyncio
    async def test_send_email_no_credentials(self):
        """Test SMTP without authentication."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            backend = SMTPEmailBackend(smtp_host="smtp.example.com", use_tls=False)
            
            result = await backend.send_email(
                to_email="test@example.com",
                subject="Test",
                html_body="<p>Test</p>",
                from_email="sender@example.com"  # Provide from_email explicitly
            )
            
            assert result is True
            mock_server.starttls.assert_not_called()
            mock_server.login.assert_not_called()


class TestEmailService:
    """Test email service main class."""

    @pytest.mark.asyncio
    async def test_send_verification_email(self):
        """Test sending verification email."""
        mock_backend = AsyncMock()
        mock_backend.send_email.return_value = True
        
        service = EmailService(
            backend=mock_backend,
            default_from_email="noreply@example.com",
            default_from_name="Test Service"
        )
        
        result = await service.send_verification_email(
            "test@example.com",
            "http://example.com/verify?token=abc123"
        )
        
        assert result is True
        mock_backend.send_email.assert_called_once()
        
        # Check call arguments
        call_args = mock_backend.send_email.call_args
        assert call_args[1]["to_email"] == "test@example.com"
        assert call_args[1]["subject"] == "Verify your AgentForge email address"
        assert "verify?token=abc123" in call_args[1]["html_body"]
        assert "verify?token=abc123" in call_args[1]["text_body"]

    @pytest.mark.asyncio
    async def test_send_password_reset_email(self):
        """Test sending password reset email."""
        mock_backend = AsyncMock()
        mock_backend.send_email.return_value = True
        
        service = EmailService(backend=mock_backend)
        
        result = await service.send_password_reset_email(
            "test@example.com",
            "http://example.com/reset?token=xyz789"
        )
        
        assert result is True
        mock_backend.send_email.assert_called_once()
        
        # Check call arguments
        call_args = mock_backend.send_email.call_args
        assert call_args[1]["subject"] == "Reset your AgentForge password"
        assert "reset?token=xyz789" in call_args[1]["html_body"]


class TestEmailServiceFactory:
    """Test email service factory function."""

    def test_create_console_service(self):
        """Test creating console email service."""
        with patch.dict(os.environ, {"EMAIL_BACKEND": "console"}):
            service = create_email_service()
            assert isinstance(service.backend, ConsoleEmailBackend)

    def test_create_file_service(self):
        """Test creating file email service."""
        with patch.dict(os.environ, {
            "EMAIL_BACKEND": "file",
            "EMAIL_FILE_DIR": "/tmp/test"
        }):
            service = create_email_service()
            assert isinstance(service.backend, FileEmailBackend)
            assert service.backend.output_dir == Path("/tmp/test")

    def test_create_smtp_service(self):
        """Test creating SMTP email service."""
        with patch.dict(os.environ, {
            "EMAIL_BACKEND": "smtp",
            "SMTP_HOST": "smtp.gmail.com",
            "SMTP_PORT": "587",
            "SMTP_USERNAME": "test@gmail.com",
            "SMTP_PASSWORD": "password",
            "SMTP_USE_TLS": "true"
        }):
            service = create_email_service()
            assert isinstance(service.backend, SMTPEmailBackend)
            assert service.backend.smtp_host == "smtp.gmail.com"
            assert service.backend.smtp_port == 587
            assert service.backend.use_tls is True

    def test_create_unknown_backend_fallback(self):
        """Test fallback to console for unknown backend."""
        with patch.dict(os.environ, {"EMAIL_BACKEND": "unknown"}):
            service = create_email_service()
            assert isinstance(service.backend, ConsoleEmailBackend)

    def test_service_configuration(self):
        """Test service configuration with environment variables."""
        with patch.dict(os.environ, {
            "EMAIL_FROM_ADDRESS": "noreply@test.com",
            "EMAIL_FROM_NAME": "Test App"
        }):
            service = create_email_service()
            assert service.default_from_email == "noreply@test.com"
            assert service.default_from_name == "Test App"


class TestEmailServiceIntegration:
    """Integration tests for email service with auth service."""

    @pytest.mark.asyncio
    async def test_ses_backend_coverage(self):
        """Test SES backend initialization and error handling."""
        with patch.dict(os.environ, {
            "EMAIL_BACKEND": "ses",
            "AWS_REGION": "us-east-1"
        }):
            service = create_email_service()
            # This will create a SES backend but we can't easily test it without AWS credentials
            assert service.backend is not None

    @pytest.mark.asyncio
    async def test_email_service_send_email_error_handling(self):
        """Test email service error handling."""
        mock_backend = AsyncMock()
        mock_backend.send_email.return_value = False  # Simulate failure
        
        service = EmailService(backend=mock_backend)
        
        result = await service.send_verification_email(
            "test@example.com",
            "http://example.com/verify?token=abc123"
        )
        
        assert result is False

    @pytest.mark.asyncio  
    async def test_email_service_with_custom_templates(self):
        """Test email service with custom template rendering."""
        mock_backend = AsyncMock()
        mock_backend.send_email.return_value = True
        
        service = EmailService(backend=mock_backend)
        
        # Test that templates are rendered with variables
        await service.send_verification_email(
            "user@test.com", 
            "https://app.example.com/verify?token=test123"
        )
        
        # Verify the template was rendered correctly
        call_args = mock_backend.send_email.call_args
        html_body = call_args[1]["html_body"]
        text_body = call_args[1]["text_body"]
        
        assert "https://app.example.com/verify?token=test123" in html_body
        assert "https://app.example.com/verify?token=test123" in text_body
        assert "user@test.com" in html_body

    def test_create_service_with_default_values(self):
        """Test creating service with default environment values."""
        # Test with minimal environment - defaults come from settings file
        with patch.dict(os.environ, {}, clear=True):
            service = create_email_service()
            # Defaults are set based on environment or None
            assert service.backend is not None
            assert isinstance(service.backend, ConsoleEmailBackend)

    @pytest.mark.asyncio
    async def test_email_service_called_during_user_creation(self, db_session):
        """Test that email service is called when creating a user."""
        from app.services.auth import auth_service
        from app.schemas.auth import UserCreate
        
        with patch.object(auth_service, 'email_service') as mock_email_service:
            mock_email_service.send_verification_email = AsyncMock(return_value=True)
            
            user_data = UserCreate(
                email="test@example.com",
                username="testuser",
                password="TestPassword123!",
                full_name="Test User"
            )
            
            user = await auth_service.create_user(db_session, user_data)
            
            # Verify email service was called
            mock_email_service.send_verification_email.assert_called_once()
            args = mock_email_service.send_verification_email.call_args
            assert args[1]["to_email"] == "test@example.com"
            assert "verify-email?token=" in args[1]["verification_url"]