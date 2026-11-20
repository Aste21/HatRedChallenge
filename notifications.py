from email.message import EmailMessage


def send_email(recipient, subject, body):
    message = EmailMessage()
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    print(message.as_string())