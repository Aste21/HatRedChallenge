import smtplib
import ssl
from email.message import EmailMessage

from app.config import Settings


def smtp_configured(settings: Settings) -> bool:
    return bool(settings.smtp_host and settings.smtp_user and settings.owner_email)


def send_email(
    settings: Settings,
    recipient: str,
    subject: str,
    body: str,
    *,
    html: str | None = None,
    bcc: str | None = None,
) -> None:
    message = EmailMessage()
    message["From"] = settings.smtp_user
    message["To"] = recipient
    if bcc and bcc.strip().casefold() != recipient.strip().casefold():
        message["Bcc"] = bcc.strip()
    message["Subject"] = subject
    message.set_content(body)

    if html is not None:
        message.add_alternative(html, subtype="html")

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        server.starttls(context=ssl.create_default_context())
        server.login(settings.smtp_user, settings.smtp_password)
        refused = server.send_message(message)
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)