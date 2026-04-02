"""
AWS SES Integration Example for AgentForge Backend

This module demonstrates how to integrate the Terraform-provisioned SES
configuration with the FastAPI backend for sending transactional emails.
"""

import json
import logging
from typing import Dict, Optional
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)


class SESEmailService:
    """
    AWS SES email service for sending transactional emails.
    
    This service automatically loads configuration from AWS Secrets Manager
    and provides methods for sending templated emails.
    """
    
    def __init__(self, aws_region: str = "us-east-1", secret_name: str = None):
        """
        Initialize the SES email service.
        
        Args:
            aws_region: AWS region for SES and Secrets Manager
            secret_name: Name of the secret containing SES configuration
                        Defaults to {project_name}-{environment}-ses-config
        """
        self.aws_region = aws_region
        self.secret_name = secret_name
        self._ses_config: Optional[Dict] = None
        self._ses_client = None
        self._secrets_client = None
    
    @property
    def ses_client(self):
        """Lazy-loaded SES client."""
        if self._ses_client is None:
            self._ses_client = boto3.client('ses', region_name=self.aws_region)
        return self._ses_client
    
    @property
    def secrets_client(self):
        """Lazy-loaded Secrets Manager client."""
        if self._secrets_client is None:
            self._secrets_client = boto3.client('secretsmanager', region_name=self.aws_region)
        return self._secrets_client
    
    def _load_ses_config(self) -> Dict:
        """Load SES configuration from AWS Secrets Manager."""
        if self._ses_config is not None:
            return self._ses_config
            
        try:
            # Use provided secret name or construct default
            secret_id = self.secret_name or f"agentforge-prod-ses-config"
            
            response = self.secrets_client.get_secret_value(SecretId=secret_id)
            self._ses_config = json.loads(response['SecretString'])
            
            logger.info(f"Loaded SES configuration from secret: {secret_id}")
            return self._ses_config
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ResourceNotFoundException':
                logger.error(f"SES configuration secret not found: {secret_id}")
            elif error_code == 'InvalidRequestException':
                logger.error(f"Invalid request to Secrets Manager: {str(e)}")
            else:
                logger.error(f"Error loading SES configuration: {str(e)}")
            raise
        except NoCredentialsError:
            logger.error("AWS credentials not found. Ensure ECS task role has proper permissions.")
            raise
    
    def send_verification_email(self, to_email: str, verification_url: str) -> bool:
        """
        Send email verification email using SES template.
        
        Args:
            to_email: Recipient email address
            verification_url: URL containing verification token
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        config = self._load_ses_config()
        
        try:
            response = self.ses_client.send_templated_email(
                Source=config['ses_from_email'],
                Destination={'ToAddresses': [to_email]},
                Template=config['templates']['email_verification'],
                TemplateData=json.dumps({
                    'verification_url': verification_url,
                    'email_address': to_email
                }),
                ConfigurationSetName=config['ses_configuration_set']
            )
            
            message_id = response['MessageId']
            logger.info(f"Verification email sent to {to_email}, MessageId: {message_id}")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'MessageRejected':
                logger.error(f"SES rejected verification email to {to_email}: {str(e)}")
            elif error_code == 'SendingPausedException':
                logger.error(f"SES sending paused for account: {str(e)}")
            else:
                logger.error(f"Error sending verification email to {to_email}: {str(e)}")
            return False
    
    def send_password_reset_email(self, to_email: str, reset_url: str) -> bool:
        """
        Send password reset email using SES template.
        
        Args:
            to_email: Recipient email address  
            reset_url: URL containing password reset token
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        config = self._load_ses_config()
        
        try:
            response = self.ses_client.send_templated_email(
                Source=config['ses_from_email'],
                Destination={'ToAddresses': [to_email]},
                Template=config['templates']['password_reset'],
                TemplateData=json.dumps({
                    'reset_url': reset_url,
                    'email_address': to_email
                }),
                ConfigurationSetName=config['ses_configuration_set']
            )
            
            message_id = response['MessageId']
            logger.info(f"Password reset email sent to {to_email}, MessageId: {message_id}")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'MessageRejected':
                logger.error(f"SES rejected password reset email to {to_email}: {str(e)}")
            elif error_code == 'SendingPausedException':
                logger.error(f"SES sending paused for account: {str(e)}")
            else:
                logger.error(f"Error sending password reset email to {to_email}: {str(e)}")
            return False
    
    def send_custom_email(self, to_email: str, subject: str, html_body: str, text_body: str = None) -> bool:
        """
        Send a custom email (not using templates).
        
        Args:
            to_email: Recipient email address
            subject: Email subject  
            html_body: HTML email body
            text_body: Plain text email body (optional)
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        config = self._load_ses_config()
        
        # Prepare message body
        body = {'Html': {'Data': html_body, 'Charset': 'UTF-8'}}
        if text_body:
            body['Text'] = {'Data': text_body, 'Charset': 'UTF-8'}
        
        try:
            response = self.ses_client.send_email(
                Source=config['ses_from_email'],
                Destination={'ToAddresses': [to_email]},
                Message={
                    'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                    'Body': body
                },
                ConfigurationSetName=config['ses_configuration_set']
            )
            
            message_id = response['MessageId']
            logger.info(f"Custom email sent to {to_email}, Subject: '{subject}', MessageId: {message_id}")
            return True
            
        except ClientError as e:
            logger.error(f"Error sending custom email to {to_email}: {str(e)}")
            return False
    
    def get_send_statistics(self) -> Optional[Dict]:
        """
        Get sending statistics from SES.
        
        Returns:
            dict: SES sending statistics or None if error
        """
        try:
            response = self.ses_client.get_send_statistics()
            return response.get('SendDataPoints', [])
        except ClientError as e:
            logger.error(f"Error getting SES statistics: {str(e)}")
            return None


# Example integration with existing auth service
"""
Add this to your auth service (app/services/auth.py):

from .email_service import SESEmailService

class AuthService:
    def __init__(self):
        # ... existing initialization
        self.email_service = SESEmailService()
    
    async def create_user(self, user_create: UserCreate) -> User:
        # ... existing user creation logic
        
        # After creating verification token
        verification_token = self.create_verification_token(user)
        verification_url = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"
        
        # Send verification email
        email_sent = self.email_service.send_verification_email(
            to_email=user.email,
            verification_url=verification_url
        )
        
        if not email_sent:
            logger.warning(f"Failed to send verification email to {user.email}")
            # Optionally handle the error (retry, notify admin, etc.)
        
        return user
    
    async def request_password_reset(self, email: str) -> bool:
        # ... existing password reset logic
        
        # After creating reset token
        reset_token = self.create_password_reset_token(user)
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
        
        # Send password reset email
        return self.email_service.send_password_reset_email(
            to_email=email,
            reset_url=reset_url
        )
"""

# Example usage in FastAPI endpoint
"""
Add this to your auth routes (app/api/routes/auth.py):

@router.post("/auth/verify/send", response_model=dict)
async def send_verification_email(
    request: EmailVerificationRequest,
    current_user: User = Depends(get_current_user)
):
    # Create verification token
    token = auth_service.create_verification_token(current_user)
    verification_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    
    # Send email using SES
    email_service = SESEmailService()
    success = email_service.send_verification_email(
        to_email=current_user.email,
        verification_url=verification_url
    )
    
    if success:
        return {"success": True, "message": "Verification email sent successfully"}
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to send verification email. Please try again later."
        )
"""