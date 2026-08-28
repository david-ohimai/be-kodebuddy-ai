from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.features.auth.model import User, UserRole
from app.features.progress.repository import ProgressRepository
from app.features.progress.service import ProgressService
from app.features.submissions.model import Submission

from .repository import MentorRepository
from .schema import AssignedLearnerSummary
from app.features.activity.model import ActivityType
from app.features.activity.repository import ActivityRepository
from app.features.activity.service import ActivityService

from datetime import datetime, timezone

from .model import MentorLearner, MentorCheckIn, CheckInStatus
from .schema import CheckInCreate, CheckInUpdate

def verify_mentor_learner_access(
    session: Session,
    mentor_id: int,
    learner_id: int,
) -> None:
    statement = select(MentorLearner).where(
        MentorLearner.mentor_id == mentor_id,
        MentorLearner.learner_id == learner_id,
    )
    assignment = session.exec(statement).first()

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This learner is not assigned to you",
        )


class MentorService:
    def __init__(self, repository: MentorRepository, session: Session):
        self.repository = repository
        self.session = session
        self.activity_service = ActivityService(ActivityRepository(session))

    def assign_learner(
        self,
        mentor_id: int,
        learner_id: int,
    ) -> MentorLearner:
        mentor = self.session.get(User, mentor_id)

        if mentor is None or mentor.role != UserRole.MENTOR:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mentor not found",
            )

        learner = self.session.get(User, learner_id)

        if learner is None or learner.role != UserRole.LEARNER:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Learner not found",
            )

        existing = self.repository.get_assignment(mentor_id, learner_id)

        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This learner is already assigned to this mentor",
            )

        assignment = MentorLearner(mentor_id=mentor_id, learner_id=learner_id)
        return self.repository.create_assignment(assignment)

    def get_assigned_learners(self, mentor: User) -> list[AssignedLearnerSummary]:
        rows = self.repository.get_assigned_learners(mentor.id)

        return [
            AssignedLearnerSummary(
                learner_id=user.id,
                full_name=user.full_name,
                email=user.email,
                assigned_at=assignment.assigned_at,
            )
            for assignment, user in rows
        ]

    def get_learner_module_progress(
        self,
        mentor: User,
        learner_id: int,
        module_id: int,
        progress_service: ProgressService,
    ):
        verify_mentor_learner_access(self.session, mentor.id, learner_id)
        return progress_service.get_module_progress_for_learner(module_id, learner_id)

    def get_learner_course_progress(
        self,
        mentor: User,
        learner_id: int,
        course_id: int,
        progress_service: ProgressService,
    ):
        verify_mentor_learner_access(self.session, mentor.id, learner_id)
        return progress_service.get_course_progress_for_learner(course_id, learner_id)

    def get_learner_submissions(
        self,
        mentor: User,
        learner_id: int,
    ) -> list[Submission]:
        verify_mentor_learner_access(self.session, mentor.id, learner_id)

        statement = select(Submission).where(Submission.learner_id == learner_id)
        return list(self.session.exec(statement))



    def create_check_in(self, mentor: User, data: CheckInCreate) -> MentorCheckIn:
        verify_mentor_learner_access(self.session, mentor.id, data.learner_id)

        check_in = MentorCheckIn(
            mentor_id=mentor.id,
            learner_id=data.learner_id,
            scheduled_time=data.scheduled_time,
            notes=data.notes,
        )
        return self.repository.create_check_in(check_in)

    def get_my_check_ins(self, mentor: User) -> list[MentorCheckIn]:
        return self.repository.get_check_ins_for_mentor(mentor.id)

    def get_check_ins_for_learner(
        self, mentor: User, learner_id: int
    ) -> list[MentorCheckIn]:
        verify_mentor_learner_access(self.session, mentor.id, learner_id)
        return self.repository.get_check_ins_for_learner(mentor.id, learner_id)

    def update_check_in(
        self, mentor: User, check_in_id: int, data: CheckInUpdate
    ) -> MentorCheckIn:
        check_in = self.repository.get_check_in_by_id(check_in_id)

        if check_in is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Check-in not found",
            )

        if check_in.mentor_id != mentor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This check-in does not belong to you",
            )

        was_already_completed = check_in.status == CheckInStatus.COMPLETED

        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(check_in, field, value)

        check_in.updated_at = datetime.now(timezone.utc)

        updated = self.repository.update_check_in(check_in)

        if updated.status == CheckInStatus.COMPLETED and not was_already_completed:
            self.activity_service.record(
                user_id=mentor.id,
                activity_type=ActivityType.CHECK_IN_COMPLETED,
                title=f"Completed check-in with learner #{updated.learner_id}",
            )

        return updated