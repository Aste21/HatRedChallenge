from email.message import EmailMessage
import smtplib

def send_email(recipient, subject, body):
    msg = EmailMessage()
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)

    # SMTP settings
    smtp_host = "SMTP_HOST"  # Replace with your SMTP server host
    smtp_port = SMTP_PORT  # Replace with your SMTP server port
    smtp_user = SMTP_USER  # Replace with your SMTP username
    smtp_password = SMTP_PASSWORD  # Replace with your SMTP password
    smtp_from = SMTP_FROM  # Replace with your email address

    # Create a secure SSL context
    context = smtplib.SSLContext(smtplib.protocol.STARTTLS)

    # Connect to the SMTP server and send the email
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls(context=context)
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
