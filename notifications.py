import os
import smtplib
import ssl
from email.message import EmailMessage


def send_email(recipient, subject, body):
    host = os.environ["SMTP_HOST"]
    port = int(os.environ["SMTP_PORT"])
    username = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]

    message = EmailMessage()
    message["From"] = username
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(host, port, timeout=15) as server:
        server.starttls(context=ssl.create_default_context())
        server.login(username, password)
        server.send_message(message)