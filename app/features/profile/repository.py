from sqlmodel import Session, select

from app.features.auth.model import User



class ProfileRepository:

    def __init__(self, session: Session):
        self.session = session


    def get_by_id(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def get_all(self) -> list[User]:
        return list(
            self.session.exec(
                select(User)
            ).all()
        )


    def update(self, user: User) -> User:
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)

        return user