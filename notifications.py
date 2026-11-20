import os
import ssl
from email.message import EmailMessage
import smtplib

def send_email(recipient, subject, body):
    msg = EmailMessage()
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)

    # Retrieve SMTP settings from environment variables
    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ["SMTP_PORT"])
    smtp_user = os.environ["SMTP_USER"]
    smtp_password = os.environ["SMTP_PASSWORD"]
    smtp_from = os.environ["SMTP_FROM"]

    # Create a secure SSL context
    context = ssl.create_default_context()

    # Connect to the SMTP server and send the email
    with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
        server.starttls(context=context)
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
