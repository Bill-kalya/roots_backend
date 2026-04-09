from app.workers.celery_app import celery_app
from typing import Dict, Any, List
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from jinja2 import Environment, FileSystemLoader
import logging
from app.core.config import settings
from app.core.retry import with_retry, RETRY_CONFIGS

logger = logging.getLogger(__name__)

# Setup email templates
template_env = Environment(loader=FileSystemLoader('templates/email'))

class EmailService:
    """Enterprise email service with templates and tracking"""
    
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_FROM
    
    @with_retry("email")
    async def send_email(
        self,
        to_email: str,
        subject: str,
        template_name: str,
        context: Dict[str, Any],
        attachments: List[str] = None
    ) -> bool:
        """Send email with template"""
        try:
            # Render template
            template = template_env.get_template(f"{template_name}.html")
            html_content = template.render(**context)
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = to_email
            msg['X-Priority'] = '3'  # Normal priority
            
            # Attach HTML content
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Attach plain text version
            text_template = template_env.get_template(f"{template_name}.txt")
            text_content = text_template.render(**context)
            text_part = MIMEText(text_content, 'plain')
            msg.attach(text_part)
            
            # Add attachments
            if attachments:
                for attachment_path in attachments:
                    with open(attachment_path, 'rb') as f:
                        img = MIMEImage(f.read())
                        img.add_header('Content-Disposition', 'attachment', filename=attachment_path.split('/')[-1])
                        msg.attach(img)
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email sent to {to_email}: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            raise

email_service = EmailService()

@celery_app.task(bind=True, max_retries=3, name="send_welcome_email")
def send_welcome_email(self, user_id: str, email: str, name: str):
    """Send welcome email to new user"""
    try:
        context = {
            "name": name,
            "login_url": "https://roots.com/login",
            "support_email": settings.SMTP_FROM
        }
        
        import asyncio
        asyncio.run(email_service.send_email(
            to_email=email,
            subject="Welcome to Roots!",
            template_name="welcome",
            context=context
        ))
        
        return {"success": True, "user_id": user_id}
        
    except Exception as e:
        logger.error(f"Welcome email failed: {e}")
        raise self.retry(exc=e, countdown=60 * 2 ** self.request.retries)

@celery_app.task(bind=True, name="send_order_confirmation")
def send_order_confirmation(self, order_id: str, user_email: str, order_data: Dict):
    """Send order confirmation email"""
    try:
        context = {
            "order_id": order_id,
            "items": order_data.get("items", []),
            "total": order_data.get("total"),
            "order_url": f"https://roots.com/orders/{order_id}"
        }
        
        import asyncio
        asyncio.run(email_service.send_email(
            to_email=user_email,
            subject=f"Order Confirmation #{order_id[:8]}",
            template_name="order_confirmation",
            context=context
        ))
        
        return {"success": True, "order_id": order_id}
        
    except Exception as e:
        logger.error(f"Order confirmation email failed: {e}")
        raise self.retry(exc=e, countdown=300)

@celery_app.task(name="send_password_reset")
def send_password_reset(self, email: str, reset_token: str):
    """Send password reset email"""
    try:
        context = {
            "reset_link": f"https://roots.com/reset-password?token={reset_token}",
            "expiry_hours": 24
        }
        
        import asyncio
        asyncio.run(email_service.send_email(
            to_email=email,
            subject="Password Reset Request",
            template_name="password_reset",
            context=context
        ))
        
        return {"success": True, "email": email}
        
    except Exception as e:
        logger.error(f"Password reset email failed: {e}")
        raise

@celery_app.task(name="send_newsletter")
def send_newsletter(self, recipients: List[str], subject: str, content: str):
    """Send newsletter to subscribers (batched)"""
    batch_size = 50
    results = []
    
    for i in range(0, len(recipients), batch_size):
        batch = recipients[i:i+batch_size]
        for email in batch:
            try:
                context = {"content": content, "unsubscribe_link": f"https://roots.com/unsubscribe?email={email}"}
                
                import asyncio
                asyncio.run(email_service.send_email(
                    to_email=email,
                    subject=subject,
                    template_name="newsletter",
                    context=context
                ))
                results.append({"email": email, "status": "sent"})
                
            except Exception as e:
                logger.error(f"Newsletter failed for {email}: {e}")
                results.append({"email": email, "status": "failed", "error": str(e)})
    
    return {"total": len(recipients), "results": results}