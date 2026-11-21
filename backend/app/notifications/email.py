import smtplib
import ssl
from email.message import EmailMessage

from app.config import Settings


def smtp_configured(settings: Settings) -> bool:
    """Check whether real e-mail delivery is set up.

    Args:
        settings: Application settings.

    Returns:
        `True` if SMTP host, login and recipient are configured.
    """
    return bool(settings.smtp_host and settings.smtp_user and settings.owner_email)


def send_email(settings: Settings, recipient: str, subject: str, body: str) -> None:
    """Send a plain-text e-mail over SMTP with STARTTLS.

    Args:
        settings: Application settings with the SMTP server and login.
        recipient: Recipient address.
        subject: Subject line.
        body: Plain-text body.
    """
    message = EmailMessage()
    message["From"] = settings.smtp_user
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        server.starttls(context=ssl.create_default_context())
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(message)
