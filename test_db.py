from sqlmodel import Session, text

from app.core.database import engine


with Session(engine) as session:
    result = session.exec(text("SELECT 1"))
    print(result.one())