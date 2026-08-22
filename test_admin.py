from sqlmodel import Session, select

from app.core.database import engine
from app.features.auth.model import User


with Session(engine) as session:
    admin = session.exec(
        select(User).where(
            User.email == "admin@kodebuddyai.com"
        )
    ).first()

    print("ADMIN:", admin)

    if admin:
        print("EMAIL:", admin.email)
        print("ROLE:", admin.role)
        print("ACTIVE:", admin.is_active)