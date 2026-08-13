import os

from dotenv import load_dotenv
from fastapi_mail import ConnectionConfig
from fastapi_mail import FastMail, MessageSchema, MessageType



load_dotenv()

conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_FROM=os.getenv("MAIL_FROM"),
    MAIL_PORT=int(os.getenv("MAIL_PORT")),
    MAIL_SERVER=os.getenv("MAIL_SERVER"),
    MAIL_FROM_NAME=os.getenv("MAIL_FROM_NAME"),
    MAIL_STARTTLS=os.getenv("MAIL_STARTTLS") == "True",
    MAIL_SSL_TLS=os.getenv("MAIL_SSL_TLS") == "True",
    USE_CREDENTIALS=True,
)



async def send_reset_email(
    email: str,
    token: str,
):
    reset_link = (
        f"{os.getenv('FRONTEND_URL')}"
        f"/reset-password?token={token}"
    )

#     message = MessageSchema(
#         subject="Reset Password",
#         recipients=[email],
#         body=f"""
# Click the link below to reset your password.

# {reset_link}

# If you didn't request this, ignore this email.
# """,
#         subtype=MessageType.plain,
#     )---> if youre using link to send the token
    message = MessageSchema(
        subject="Reset Password",
        recipients=[email],
        body=f"""
Hello,

You requested to reset your password.

Use the token below to reset your password:

{token}

This token expires in 15 minutes.

If you did not request this, please ignore this email.
""",
        subtype=MessageType.plain,
    )
    fm = FastMail(conf)

    await fm.send_message(message)




async def send_order_created_email(
    email: str,
    order_id: int,
    items: list[dict],
    total_cost: float,
    product_name: str,  
):
    item_lines = "\n".join(
        [
            f"- {item['name']} x {item['quantity']} "
            f"@ ₦{item['unit_price']:,.2f} "
            f"= ₦{item['subtotal']:,.2f}"
            for item in items
        ]
    )

    message = MessageSchema(
        subject=f"Order #{order_id} Created Successfully",
        recipients=[email],
        body=f"""
Hello,

Your order #{order_id} ({product_name}) has been created successfully.

Order Summary:

{item_lines}

Total Cost: ₦{total_cost:,.2f}

Order Status: Pending

Thank you for your order.
""",
        subtype=MessageType.plain,
    )

    fm = FastMail(conf)

    await fm.send_message(message)



async def send_order_status_email(
    email: str,
    order_id: int,
    status: str,
    product_names: list[str],  
):
    product_names_text = ", ".join(product_names)

    message = MessageSchema(
        subject=f"Order #{order_id} Status Updated",
        recipients=[email],
        body=f"""
Hello,

Your order #{order_id} ({product_names_text}) has been updated.

New Order Status:

{status.upper()}

Thank you.
""",
        subtype=MessageType.plain,
    )

    fm = FastMail(conf)

    await fm.send_message(message)
