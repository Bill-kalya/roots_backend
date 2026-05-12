from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

from app.core.config import settings


class EmailService:
    @staticmethod
    async def _send_verification_email_smtp(email: str, full_name: str, token: str):
        print(f"📧 Sending verification email (SMTP) to {email}")
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

    @staticmethod
    async def _send_verification_email_resend(email: str, full_name: str, token: str):
        # Resend API (https://resend.com/docs)
        # Uses JSON over HTTPS; we keep it optional and fall back to SMTP.
        import requests

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

        from_email = settings.RESEND_FROM_EMAIL or settings.EMAIL_FROM
        if not settings.RESEND_API_KEY:
            raise RuntimeError("RESEND_API_KEY not configured")
        if not from_email:
            raise RuntimeError("EMAIL_FROM/RESEND_FROM_EMAIL not configured")

        payload = {
            "from": f"{settings.RESEND_VERIFY_EMAIL_FROM_NAME} <{from_email}>",
            "to": [email],
            "subject": "Verify your Roots account",
            "html": html,
        }

        headers = {
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
        }

        resp = requests.post("https://api.resend.com/emails", headers=headers, json=payload, timeout=15)
        if resp.status_code >= 400:
            raise RuntimeError(f"Resend error {resp.status_code}: {resp.text}")

    @staticmethod
    async def send_verification_email(email: str, full_name: str, token: str):
        """Send verification email using Resend (preferred) with SMTP fallback."""
        # If Resend is misconfigured/provider fails, we don't block registration.
        try:
            if settings.RESEND_API_KEY:
                return await EmailService._send_verification_email_resend(email=email, full_name=full_name, token=token)
        except Exception as e:
            print(f"⚠️ Resend verification email failed, falling back to SMTP: {e}")

        return await EmailService._send_verification_email_smtp(email=email, full_name=full_name, token=token)



email_service = EmailService()

