from sqlmodel import Session

from app.core.database import engine
from app.core.seed_admin import seed_admin


with Session(engine) as session:
    seed_admin(session)