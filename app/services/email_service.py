from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

from app.core.config import settings


class EmailService:
    @staticmethod
    async def _send_resend(to: str, subject: str, html: str):
        """Send email via Resend API."""
        import requests

        from_email = settings.RESEND_FROM_EMAIL or settings.EMAIL_FROM
        if not settings.RESEND_API_KEY:
            raise RuntimeError("RESEND_API_KEY not configured")
        if not from_email:
            raise RuntimeError("EMAIL_FROM/RESEND_FROM_EMAIL not configured")

        if "<" in from_email and ">" in from_email:
            resend_from = from_email
        else:
            resend_from = f"{settings.RESEND_VERIFY_EMAIL_FROM_NAME} <{from_email}>"

        payload = {
            "from": resend_from,
            "to": [to],
            "subject": subject,
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
    async def _send_smtp(to: str, subject: str, html: str):
        """Send email via SMTP."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.EMAIL_FROM
        msg["To"] = to
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAIL_FROM, to, msg.as_string())

    @staticmethod
    async def send_email(to: str, subject: str, html: str):
        """Send email using Resend (preferred) with SMTP fallback."""
        try:
            if settings.RESEND_API_KEY:
                return await EmailService._send_resend(to=to, subject=subject, html=html)
        except Exception as e:
            print(f"⚠️ Resend email failed, falling back to SMTP: {e}")

        return await EmailService._send_smtp(to=to, subject=subject, html=html)

    @staticmethod
    async def send_verification_email(email: str, full_name: str, token: str):
        """Send verification email using Resend (preferred) with SMTP fallback."""
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

        try:
            if settings.RESEND_API_KEY:
                return await EmailService._send_resend(to=email, subject="Verify your Roots account", html=html)
        except Exception as e:
            print(f"⚠️ Resend verification email failed, falling back to SMTP: {e}")

        return await EmailService._send_smtp(to=email, subject="Verify your Roots account", html=html)



email_service = EmailService()

