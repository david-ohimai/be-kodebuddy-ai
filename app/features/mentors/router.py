from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.auth import get_current_admin, get_current_mentor
from app.core.session import get_session
from app.features.auth.model import User
from app.features.progress.repository import ProgressRepository
from app.features.progress.service import ProgressService
from app.features.submissions.schema import SubmissionResponse

from .repository import MentorRepository
from .schema import AssignedLearnerSummary, AssignLearnerToMentor, MentorLearnerResponse
from .service import MentorService


router = APIRouter(
    prefix="/mentors",
    tags=["Mentors"],
)


def get_mentor_service(
    session: Session = Depends(get_session),
) -> MentorService:
    repository = MentorRepository(session)
    return MentorService(repository=repository, session=session)


def get_progress_service(
    session: Session = Depends(get_session),
) -> ProgressService:
    repository = ProgressRepository(session)
    return ProgressService(repository=repository, session=session)


@router.post(
    "/{mentor_id}/learners",
    response_model=MentorLearnerResponse,
)
def assign_learner_to_mentor(
    mentor_id: int,
    data: AssignLearnerToMentor,
    current_admin: User = Depends(get_current_admin),
    service: MentorService = Depends(get_mentor_service),
):
    return service.assign_learner(mentor_id, data.learner_id)


@router.get(
    "/learners",
    response_model=list[AssignedLearnerSummary],
)
def get_my_assigned_learners(
    current_mentor: User = Depends(get_current_mentor),
    service: MentorService = Depends(get_mentor_service),
):
    return service.get_assigned_learners(current_mentor)


@router.get(
    "/learners/{learner_id}/modules/{module_id}/progress",
)
def get_assigned_learner_module_progress(
    learner_id: int,
    module_id: int,
    current_mentor: User = Depends(get_current_mentor),
    mentor_service: MentorService = Depends(get_mentor_service),
    progress_service: ProgressService = Depends(get_progress_service),
):
    return mentor_service.get_learner_module_progress(
        current_mentor, learner_id, module_id, progress_service
    )


@router.get(
    "/learners/{learner_id}/courses/{course_id}/progress",
)
def get_assigned_learner_course_progress(
    learner_id: int,
    course_id: int,
    current_mentor: User = Depends(get_current_mentor),
    mentor_service: MentorService = Depends(get_mentor_service),
    progress_service: ProgressService = Depends(get_progress_service),
):
    return mentor_service.get_learner_course_progress(
        current_mentor, learner_id, course_id, progress_service
    )


@router.get(
    "/learners/{learner_id}/submissions",
    response_model=list[SubmissionResponse],
)
def get_assigned_learner_submissions(
    learner_id: int,
    current_mentor: User = Depends(get_current_mentor),
    service: MentorService = Depends(get_mentor_service),
):
    return service.get_learner_submissions(current_mentor, learner_id)