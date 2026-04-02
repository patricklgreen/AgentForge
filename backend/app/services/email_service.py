"""
Email service for AgentForge - supports multiple backends for different environments.

For local development:
- Console: Log emails to console
- File: Save emails to local files
- SMTP: Use local or external SMTP server

For production:
- SES: AWS Simple Email Service
"""

import json
import logging
import smtplib
from abc import ABC, abstractmethod
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import os

logger = logging.getLogger(__name__)


class EmailBackend(ABC):
    """Abstract base class for email backends."""
    
    @abstractmethod
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
    ) -> bool:
        """Send an email."""
        pass


class ConsoleEmailBackend(EmailBackend):
    """Email backend that logs emails to console - useful for development."""
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
    ) -> bool:
        """Log email to console."""
        sender = f"{from_name} <{from_email}>" if from_name and from_email else (from_email or "noreply@agentforge.dev")
        
        print("\n" + "="*80)
        print(f"📧 EMAIL SENT TO CONSOLE")
        print("="*80)
        print(f"From: {sender}")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(f"Time: {datetime.now().isoformat()}")
        print("-" * 80)
        if text_body:
            print("TEXT BODY:")
            print(text_body)
            print("-" * 40)
        print("HTML BODY:")
        print(html_body)
        print("="*80)
        
        logger.info(f"Console email sent to {to_email}: {subject}")
        return True


class FileEmailBackend(EmailBackend):
    """Email backend that saves emails to files - useful for development."""
    
    def __init__(self, output_dir: str = "tmp/emails"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
    ) -> bool:
        """Save email to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_subject = "".join(c for c in subject if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_subject = safe_subject.replace(' ', '_')[:50]
        
        filename = f"{timestamp}_{safe_subject}_{to_email.replace('@', '_at_')}.html"
        filepath = self.output_dir / filename
        
        sender = f"{from_name} <{from_email}>" if from_name and from_email else (from_email or "noreply@agentforge.dev")
        
        email_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{subject}</title>
    <style>
        .email-header {{
            background: #f3f4f6;
            padding: 20px;
            border-bottom: 2px solid #e5e7eb;
            margin-bottom: 20px;
        }}
        .email-meta {{
            font-family: monospace;
            font-size: 14px;
            color: #6b7280;
        }}
        .email-body {{
            padding: 20px;
        }}
    </style>
</head>
<body>
    <div class="email-header">
        <div class="email-meta">
            <strong>📧 AgentForge Email (Development Mode)</strong><br>
            <strong>From:</strong> {sender}<br>
            <strong>To:</strong> {to_email}<br>
            <strong>Subject:</strong> {subject}<br>
            <strong>Time:</strong> {datetime.now().isoformat()}<br>
            <strong>File:</strong> {filename}
        </div>
    </div>
    <div class="email-body">
        {html_body}
    </div>
    {f'<hr><h3>Plain Text Version:</h3><pre>{text_body}</pre>' if text_body else ''}
</body>
</html>
        """
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(email_content)
            
            logger.info(f"Email saved to file: {filepath}")
            print(f"📧 Email saved to: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to save email to file: {e}")
            return False


class SMTPEmailBackend(EmailBackend):
    """Email backend using SMTP - works with Gmail, Outlook, local SMTP, etc."""
    
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int = 587,
        smtp_username: Optional[str] = None,
        smtp_password: Optional[str] = None,
        use_tls: bool = True,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.use_tls = use_tls
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
    ) -> bool:
        """Send email via SMTP."""
        try:
            # Use SMTP username as from_email if not provided
            sender_email = from_email or self.smtp_username
            if not sender_email:
                raise ValueError("No sender email configured")
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{from_name} <{sender_email}>" if from_name else sender_email
            msg['To'] = to_email
            
            # Add text and HTML parts
            if text_body:
                text_part = MIMEText(text_body, 'plain')
                msg.attach(text_part)
            
            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                
                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)
                
                server.send_message(msg)
            
            logger.info(f"SMTP email sent to {to_email}: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send SMTP email to {to_email}: {e}")
            return False


class EmailService:
    """Main email service that delegates to configured backend."""
    
    def __init__(self, backend: EmailBackend, default_from_email: str = None, default_from_name: str = "AgentForge"):
        self.backend = backend
        self.default_from_email = default_from_email
        self.default_from_name = default_from_name
    
    async def send_verification_email(self, to_email: str, verification_url: str) -> bool:
        """Send email verification email."""
        subject = "Verify your AgentForge email address"
        
        html_body = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="text-align: center; margin-bottom: 30px;">
                <h1 style="color: #1e40af; font-size: 28px; margin-bottom: 10px;">AgentForge</h1>
                <h2 style="color: #1f2937; font-size: 24px; margin: 0;">Verify Your Email Address</h2>
            </div>
            
            <div style="background: white; border-radius: 8px; padding: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px;">
                <p>Hi there!</p>
                
                <p>Thanks for signing up for AgentForge! To complete your registration and start using all features, please verify your email address by clicking the button below:</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{verification_url}" style="display: inline-block; background-color: #3b82f6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 600;">
                        Verify Email Address
                    </a>
                </div>
                
                <p>If the button doesn't work, copy and paste this link into your browser:</p>
                <p style="background: #f3f4f6; padding: 10px; border-radius: 4px; font-family: monospace; word-break: break-all;">
                    {verification_url}
                </p>
                
                <div style="background: #fef3c7; border: 1px solid #f59e0b; padding: 16px; border-radius: 6px; margin: 20px 0;">
                    <strong>Security Note:</strong> This verification link will expire in 24 hours for your security. If you didn't create an account with AgentForge, please ignore this email.
                </div>
                
                <p>Best regards,<br>The AgentForge Team</p>
            </div>
            
            <div style="text-align: center; font-size: 14px; color: #6b7280;">
                <p>This email was sent to {to_email} because you signed up for AgentForge.</p>
                <p>If you did not request this verification, please ignore this email.</p>
            </div>
        </div>
        """
        
        text_body = f"""
Hi there!

Thanks for signing up for AgentForge! To complete your registration and start using all features, please verify your email address by visiting the following link:

{verification_url}

SECURITY NOTE: This verification link will expire in 24 hours for your security. If you didn't create an account with AgentForge, please ignore this email.

Best regards,
The AgentForge Team

---
This email was sent to {to_email} because you signed up for AgentForge.
If you did not request this verification, please ignore this email.
        """
        
        return await self.backend.send_email(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            from_email=self.default_from_email,
            from_name=self.default_from_name,
        )
    
    async def send_password_reset_email(self, to_email: str, reset_url: str) -> bool:
        """Send password reset email."""
        subject = "Reset your AgentForge password"
        
        html_body = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="text-align: center; margin-bottom: 30px;">
                <h1 style="color: #1e40af; font-size: 28px; margin-bottom: 10px;">AgentForge</h1>
                <h2 style="color: #1f2937; font-size: 24px; margin: 0;">Reset Your Password</h2>
            </div>
            
            <div style="background: white; border-radius: 8px; padding: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px;">
                <p>Hi there!</p>
                
                <p>We received a request to reset the password for your AgentForge account. If you made this request, click the button below to choose a new password:</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_url}" style="display: inline-block; background-color: #dc2626; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 600;">
                        Reset Password
                    </a>
                </div>
                
                <p>If the button doesn't work, copy and paste this link into your browser:</p>
                <p style="background: #f3f4f6; padding: 10px; border-radius: 4px; font-family: monospace; word-break: break-all;">
                    {reset_url}
                </p>
                
                <div style="background: #fee2e2; border: 1px solid #f87171; padding: 16px; border-radius: 6px; margin: 20px 0;">
                    <strong>Security Note:</strong> This password reset link will expire in 1 hour for your security. If you didn't request a password reset, please ignore this email - your password will remain unchanged.
                </div>
                
                <p>Best regards,<br>The AgentForge Team</p>
            </div>
            
            <div style="text-align: center; font-size: 14px; color: #6b7280;">
                <p>This email was sent to {to_email} because a password reset was requested for your AgentForge account.</p>
                <p>If you did not request this reset, please ignore this email.</p>
            </div>
        </div>
        """
        
        text_body = f"""
Hi there!

We received a request to reset the password for your AgentForge account. If you made this request, visit the following link to choose a new password:

{reset_url}

SECURITY NOTE: This password reset link will expire in 1 hour for your security. If you didn't request a password reset, please ignore this email - your password will remain unchanged.

Best regards,
The AgentForge Team

---
This email was sent to {to_email} because a password reset was requested for your AgentForge account.
If you did not request this reset, please ignore this email.
        """
        
        return await self.backend.send_email(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            from_email=self.default_from_email,
            from_name=self.default_from_name,
        )


def create_email_service() -> EmailService:
    """Create email service based on environment configuration."""
    email_backend = os.getenv("EMAIL_BACKEND", "console").lower()
    from_email = os.getenv("EMAIL_FROM_ADDRESS")
    from_name = os.getenv("EMAIL_FROM_NAME", "AgentForge")
    
    if email_backend == "console":
        backend = ConsoleEmailBackend()
    elif email_backend == "file":
        output_dir = os.getenv("EMAIL_FILE_DIR", "tmp/emails")
        backend = FileEmailBackend(output_dir=output_dir)
    elif email_backend == "smtp":
        backend = SMTPEmailBackend(
            smtp_host=os.getenv("SMTP_HOST", "localhost"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_username=os.getenv("SMTP_USERNAME"),
            smtp_password=os.getenv("SMTP_PASSWORD"),
            use_tls=os.getenv("SMTP_USE_TLS", "true").lower() == "true",
        )
    else:
        logger.warning(f"Unknown email backend '{email_backend}', falling back to console")
        backend = ConsoleEmailBackend()
    
    return EmailService(
        backend=backend,
        default_from_email=from_email,
        default_from_name=from_name,
    )