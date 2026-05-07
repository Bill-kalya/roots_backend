from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

from app.core.config import settings


class EmailService:
    @staticmethod
    async def send_verification_email(email: str, full_name: str, token: str):
        print(f"📧 Sending verification email to {email}")
        verify_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"

        html = f"""
        <h2>Welcome to Roots, {full_name}!</h2>
        <p>Please verify your email by clicking the link below:</p>
        <a href="{verify_url}" style="
            background: #c4861a;
            color: white;
            padding: 12px 24px;
            border-radius: 8px;
            text-decoration: none;
        ">Verify Email</a>
        <p>This link expires in 24 hours.</p>
        <p>If you didn't create this account, ignore this email.</p>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Verify your Roots account"
        msg["From"] = settings.EMAIL_FROM
        msg["To"] = email
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAIL_FROM, email, msg.as_string())


email_service = EmailService()

