import os

from sqlmodel import Session, select

from app.core.security import hash_password
from app.features.auth.model import User, UserRole


def seed_admin(session: Session):

    admin_email = "admin@kodebuddyai.com"

    existing_admin = session.exec(
        select(User).where(
            User.email == admin_email
        )
    ).first()

    if existing_admin:
        print("Admin already exists")
        return

    admin_password = os.getenv(
        "INITIAL_ADMIN_PASSWORD"
    )

    if not admin_password:
        raise RuntimeError(
            "INITIAL_ADMIN_PASSWORD is not configured"
        )

    admin = User(
        email=admin_email,
        hashed_password=hash_password(
            admin_password
        ),
        role=UserRole.ADMIN,
        is_active=True,
    )

    session.add(admin)
    session.commit()

    print("Admin created successfully")