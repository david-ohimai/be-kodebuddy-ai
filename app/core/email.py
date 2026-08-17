import os

from dotenv import load_dotenv
from fastapi_mail import (
    ConnectionConfig,
    FastMail,
    MessageSchema,
    MessageType,
)

load_dotenv()


conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_FROM=os.getenv("MAIL_FROM"),
    MAIL_PORT=int(os.getenv("MAIL_PORT", "587")),
    MAIL_SERVER=os.getenv("MAIL_SERVER"),
    MAIL_FROM_NAME=os.getenv("MAIL_FROM_NAME", "KodeBuddyAi"),
    MAIL_STARTTLS=os.getenv("MAIL_STARTTLS") == "True",
    MAIL_SSL_TLS=os.getenv("MAIL_SSL_TLS") == "True",
    USE_CREDENTIALS=True,
)


async def send_reset_email(
    email: str,
    token: str,
):
    frontend_url = os.getenv("FRONTEND_URL")

    reset_link = (
        f"{frontend_url}/reset-password"
        f"?token={token}"
    )

    message = MessageSchema(
        subject="Reset Your KodeBuddy Password",
        recipients=[email],
        body=f"""
Hello,

You requested to reset your KodeBuddy password.

Click the link below to create a new password:

{reset_link}

This link expires in 15 minutes.

If you did not request a password reset, please ignore this email.

Regards,
KodeBuddy Team
""",
        subtype=MessageType.plain,
    )

    fm = FastMail(conf)

    await fm.send_message(message)


async def send_role_change_email(
    email: str,
    full_name: str | None,
    new_role: str,
):
    name = full_name or "there"

    message = MessageSchema(
        subject="Your KodeBuddy Role Has Been Updated",
        recipients=[email],
        body=f"""
Hello {name},

Your KodeBuddy account role has been updated.

Your new role is:

{new_role.upper()}

You can now access the features and permissions available to your new role.

If you believe this change was made in error, please contact the KodeBuddy administrator.

Regards,
KodeBuddy Team
""",
        subtype=MessageType.plain,
    )

    fm = FastMail(conf)

    await fm.send_message(message)