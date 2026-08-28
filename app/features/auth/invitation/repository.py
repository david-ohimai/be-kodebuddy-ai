from sqlmodel import Session, select

from .model import UserInvitation, InvitationStatus


class InvitationRepository:

    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        invitation: UserInvitation,
    ) -> UserInvitation:
        self.session.add(invitation)
        self.session.commit()
        self.session.refresh(invitation)

        return invitation

    def get_by_token(
        self,
        token: str,
    ) -> UserInvitation | None:
        statement = select(UserInvitation).where(
            UserInvitation.token == token
        )

        return self.session.exec(statement).first()

    def get_pending_by_email(
        self,
        email: str,
    ) -> UserInvitation | None:
        statement = select(UserInvitation).where(
            UserInvitation.email == email,
            UserInvitation.status == InvitationStatus.PENDING
        )

        return self.session.exec(statement).first()

    def update(
        self,
        invitation: UserInvitation,
    ) -> UserInvitation:
        self.session.add(invitation)
        self.session.commit()
        self.session.refresh(invitation)

        return invitation