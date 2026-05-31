import logging
import asyncio
from pathlib import Path
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from ..celery import celery
from ..config import Config

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent

mail_config = ConnectionConfig(
    MAIL_USERNAME=Config.MAIL_USERNAME,
    MAIL_PASSWORD=Config.MAIL_PASSWORD,
    MAIL_FROM=Config.MAIL_FROM,
    MAIL_PORT=587,
    MAIL_SERVER=Config.MAIL_SERVER,
    MAIL_FROM_NAME=Config.MAIL_FROM_NAME,
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
)

def send_email_sync(subject: str, recipients: list, body: str):
    async def _send():
        message = MessageSchema(
            subject=subject,
            recipients=recipients,
            body=body,
            subtype=MessageType.html
        )
        fm = FastMail(mail_config)
        await fm.send_message(message)

    asyncio.run(_send())


@celery.task(name="send_confirmation_email")
def send_confirmation_email(email: str, username: str, token: str):
    link = f"http://localhost:8000/api/v1/verify-email?token={token}"
    body = f"""
    <h2>Hi {username}!</h2>
    <p>Please confirm your email by clicking the link below:</p>
    <a href="{link}">Verify Email</a>
    <p>Link expires in 24 hours.</p>
    """
    send_email_sync("Confirm your MessaGe account", [email], body)
    logger.info(f"[Email] Confirmation sent to {email}")
    return {"status": "sent", "email": email}


@celery.task(name="send_password_reset_email")
def send_password_reset_email(email: str, token: str):
    link = f"http://localhost:8000/api/v1/reset-password?token={token}"
    body = f"""
    <h2>Password Reset</h2>
    <p>Click the link below to reset your password:</p>
    <a href="{link}">Reset Password</a>
    <p>If you didn't request this, ignore this email.</p>
    """
    send_email_sync("Reset your MessaGe password", [email], body)
    logger.info(f"[Email] Password reset sent to {email}")
    return {"status": "sent", "email": email}