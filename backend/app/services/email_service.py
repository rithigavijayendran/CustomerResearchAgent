"""
Email service for sending emails (password reset, notifications, etc.)
Supports multiple email providers: SMTP, SendGrid, AWS SES
"""

import os
import logging
from typing import Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

logger = logging.getLogger(__name__)

class EmailService:
    """Email service with multiple provider support"""
    
    def __init__(self):
        self.provider = os.getenv("EMAIL_PROVIDER", "smtp").lower()
        self.from_email = os.getenv("EMAIL_FROM", "noreply@eightfoldai.com")
        self.from_name = os.getenv("EMAIL_FROM_NAME", "Eightfold AI")
        
        # SMTP Configuration
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        
        # SendGrid Configuration
        self.sendgrid_api_key = os.getenv("SENDGRID_API_KEY", "")
        
        # AWS SES Configuration
        self.aws_region = os.getenv("AWS_REGION", "us-east-1")
        self.aws_access_key = os.getenv("AWS_ACCESS_KEY_ID", "")
        self.aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "")
        
        # Frontend URL for reset links
        self.frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        
        logger.info(f"Email service initialized with provider: {self.provider}")
    
    async def send_password_reset_email(
        self,
        to_email: str,
        reset_token: str,
        user_name: Optional[str] = None
    ) -> bool:
        """
        Send password reset email
        
        Args:
            to_email: Recipient email address
            reset_token: Password reset token
            user_name: Optional user name for personalization
            
        Returns:
            True if email sent successfully, False otherwise
        """
        reset_link = f"{self.frontend_url}/reset-password?token={reset_token}"
        
        subject = "Reset Your Password - Eightfold AI"
        
        # HTML email template
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Password Reset</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0;">Password Reset Request</h1>
            </div>
            <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px;">
                <p style="font-size: 16px;">Hello{(' ' + user_name) if user_name else ''},</p>
                <p style="font-size: 16px;">You requested to reset your password for your Eightfold AI account.</p>
                <p style="font-size: 16px;">Click the button below to reset your password:</p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_link}" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold; font-size: 16px;">Reset Password</a>
                </div>
                <p style="font-size: 14px; color: #666;">Or copy and paste this link into your browser:</p>
                <p style="font-size: 12px; color: #999; word-break: break-all; background: #fff; padding: 10px; border-radius: 5px; border: 1px solid #ddd;">{reset_link}</p>
                <p style="font-size: 14px; color: #666;">This link will expire in 1 hour.</p>
                <p style="font-size: 14px; color: #666;">If you didn't request this password reset, please ignore this email.</p>
                <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                <p style="font-size: 12px; color: #999; text-align: center;">© {os.getenv('CURRENT_YEAR', '2025')} Eightfold AI. All rights reserved.</p>
            </div>
        </body>
        </html>
        """
        
        # Plain text version
        text_body = f"""
        Password Reset Request
        
        Hello{(' ' + user_name) if user_name else ''},
        
        You requested to reset your password for your Eightfold AI account.
        
        Click this link to reset your password:
        {reset_link}
        
        This link will expire in 1 hour.
        
        If you didn't request this password reset, please ignore this email.
        
        © {os.getenv('CURRENT_YEAR', '2025')} Eightfold AI. All rights reserved.
        """
        
        return await self._send_email(to_email, subject, text_body, html_body)
    
    async def _send_email(
        self,
        to_email: str,
        subject: str,
        text_body: str,
        html_body: Optional[str] = None
    ) -> bool:
        """
        Send email using configured provider
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            text_body: Plain text email body
            html_body: Optional HTML email body
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            if self.provider == "smtp":
                return await self._send_via_smtp(to_email, subject, text_body, html_body)
            elif self.provider == "sendgrid":
                return await self._send_via_sendgrid(to_email, subject, text_body, html_body)
            elif self.provider == "ses":
                return await self._send_via_ses(to_email, subject, text_body, html_body)
            elif self.provider == "console":
                # Development mode - just log the email
                logger.info(f"📧 [CONSOLE MODE] Email would be sent to {to_email}")
                logger.info(f"Subject: {subject}")
                logger.info(f"Body: {text_body}")
                if html_body:
                    logger.info(f"HTML Body: {html_body[:200]}...")
                return True
            else:
                logger.error(f"Unknown email provider: {self.provider}")
                return False
        except Exception as e:
            logger.error(f"Error sending email: {e}", exc_info=True)
            return False
    
    async def _send_via_smtp(
        self,
        to_email: str,
        subject: str,
        text_body: str,
        html_body: Optional[str] = None
    ) -> bool:
        """Send email via SMTP"""
        try:
            if not self.smtp_user or not self.smtp_password:
                logger.error("SMTP credentials not configured. Set SMTP_USER and SMTP_PASSWORD environment variables.")
                return False
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add text and HTML parts
            part1 = MIMEText(text_body, 'plain')
            msg.attach(part1)
            
            if html_body:
                part2 = MIMEText(html_body, 'html')
                msg.attach(part2)
            
            # Send email
            import asyncio
            await asyncio.to_thread(self._send_smtp_sync, msg, to_email)
            
            logger.info(f"✅ Password reset email sent to {to_email} via SMTP")
            return True
        except Exception as e:
            logger.error(f"SMTP email send error: {e}", exc_info=True)
            return False
    
    def _send_smtp_sync(self, msg: MIMEMultipart, to_email: str):
        """Synchronous SMTP send (runs in thread)"""
        server = smtplib.SMTP(self.smtp_host, self.smtp_port)
        if self.smtp_use_tls:
            server.starttls()
        server.login(self.smtp_user, self.smtp_password)
        server.send_message(msg)
        server.quit()
    
    async def _send_via_sendgrid(
        self,
        to_email: str,
        subject: str,
        text_body: str,
        html_body: Optional[str] = None
    ) -> bool:
        """Send email via SendGrid"""
        try:
            if not self.sendgrid_api_key:
                logger.error("SendGrid API key not configured. Set SENDGRID_API_KEY environment variable.")
                return False
            
            try:
                import sendgrid
                from sendgrid.helpers.mail import Mail, Email, Content
            except ImportError:
                logger.error("SendGrid library not installed. Install with: pip install sendgrid")
                return False
            
            sg = sendgrid.SendGridAPIClient(api_key=self.sendgrid_api_key)
            
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=to_email,
                subject=subject,
                plain_text_content=text_body
            )
            
            if html_body:
                message.content = Content("text/html", html_body)
            
            response = sg.send(message)
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"✅ Password reset email sent to {to_email} via SendGrid")
                return True
            else:
                logger.error(f"SendGrid error: {response.status_code} - {response.body}")
                return False
        except Exception as e:
            logger.error(f"SendGrid email send error: {e}", exc_info=True)
            return False
    
    async def _send_via_ses(
        self,
        to_email: str,
        subject: str,
        text_body: str,
        html_body: Optional[str] = None
    ) -> bool:
        """Send email via AWS SES"""
        try:
            if not self.aws_access_key or not self.aws_secret_key:
                logger.error("AWS credentials not configured. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables.")
                return False
            
            try:
                import boto3
            except ImportError:
                logger.error("boto3 library not installed. Install with: pip install boto3")
                return False
            
            ses_client = boto3.client(
                'ses',
                region_name=self.aws_region,
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key
            )
            
            message = {
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body': {
                    'Text': {'Data': text_body, 'Charset': 'UTF-8'},
                }
            }
            
            if html_body:
                message['Body']['Html'] = {'Data': html_body, 'Charset': 'UTF-8'}
            
            response = ses_client.send_email(
                Source=f"{self.from_name} <{self.from_email}>",
                Destination={'ToAddresses': [to_email]},
                Message=message
            )
            
            logger.info(f"✅ Password reset email sent to {to_email} via AWS SES. MessageId: {response['MessageId']}")
            return True
        except Exception as e:
            logger.error(f"AWS SES email send error: {e}", exc_info=True)
            return False

# Global email service instance
_email_service: Optional[EmailService] = None

def get_email_service() -> EmailService:
    """Get or create email service instance"""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service

