from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.features.auth.model import User, UserRole
from app.features.assignments.model import Assignment
from app.features.courses.model import CourseTrainer, CourseLearner
from app.features.modules.model import Module

from app.features.activity.model import ActivityType
from app.features.activity.repository import ActivityRepository
from app.features.activity.service import ActivityService

from .model import Submission
from .repository import SubmissionRepository
from .schema import GradeSubmission, SubmissionCreate, SubmissionUpdate

class SubmissionService:
    def __init__(self, repository: SubmissionRepository, session: Session, activity_service: ActivityService):
        self.repository = repository
        self.session = session
        self.activity_service = activity_service

    # ---------- AUTHORIZATION HELPERS ----------
    def _get_assignment(
        self,
        assignment_id: int,
    ) -> Assignment:
        assignment = self.session.get(
            Assignment,
            assignment_id,
        )

        if assignment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found."
            )

        return assignment

    def _get_assignment_module(
        self,
        assignment: Assignment
    ) -> Module:
        module = self.session.get(
            Module,
            assignment.module_id
        )

        if module is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module associated with this assignment was not found.",
            )

        return module

    def _trainer_can_access_course(
        self,
        trainer_id: int,
        course_id: int
    ) -> bool:
        statement = select(CourseTrainer).where(
            CourseTrainer.course_id == course_id,
            CourseTrainer.trainer_id == trainer_id
        )

        relationship = self.session.exec(statement).first()

        return relationship is not None

    def _verify_trainer_assignment_access(
        self,
        trainer_id: int,
        assignment_id: int
    ) -> Assignment:
        assignment = self._get_assignment(
            assignment_id
        )

        module = self._get_assignment_module(
            assignment
        )

        if not self._trainer_can_access_course(
            trainer_id=trainer_id,
            course_id=module.course_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "You are not authorized to access submissions "
                    "for this course."
                )
            )

        return assignment

# ---------- SERVICE METHODS ----------
    def create_submission(
        self,
        learner: User,
        data: SubmissionCreate
    ) -> Submission:

        if learner.role != UserRole.LEARNER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only learners can submit assignments."
            )

        if learner.id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Learner identity is required to submit assignments."
            )

        assignment = self._get_assignment(
            data.assignment_id
        )

        if not assignment.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This assignment is not active."
            )

        # An assignment with a future start_date has not opened yet. The client
        # greys the card out, but that lock is only cosmetic unless the
        # state-changing endpoint enforces it too -- a learner can POST here
        # directly. start_date NULL means "already open".
        if assignment.start_date is not None:
            start_date = assignment.start_date

            if start_date.tzinfo is None:
                start_date = start_date.replace(tzinfo=timezone.utc)

            if datetime.now(timezone.utc) < start_date:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "This assignment has not opened yet. It becomes "
                        f"available on {start_date.date().isoformat()}."
                    ),
                )

        module = self._get_assignment_module(
            assignment
        )

        if not module.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The module containing this assignment is not active."
            )

        # Verify learner is assigned to the course.
        statement = select(CourseLearner).where(
            CourseLearner.course_id == module.course_id,
            CourseLearner.learner_id == learner.id,
        )

        course_learner = self.session.exec(statement).first()

        if course_learner is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "You are not authorized to submit an assignment "
                    "for this course."
                ),
            )

        # Prevent duplicate submissions for the same assignment by the same learner.
        existing_submission = self.repository.get_submissions_by_assignment_learner(
            assignment_id=data.assignment_id,
            learner_id=learner.id
        )

        if existing_submission is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already submitted this assignment.",
            )
        
        submission_data = {
            "assignment_id": data.assignment_id,
            "learner_id": learner.id,
            "content": data.content,
        }

        submission = self.repository.create_submission(submission_data)

        self.activity_service.record(
            user_id=learner.id,
            activity_type=ActivityType.ASSIGNMENT_SUBMITTED,
            title="Assignment submitted",
            description=f"Assignment {assignment.title} was submitted.",
        )

        return submission

    def get_submission_by_id(self, submission_id: int,current_user: User) -> Submission:
       
        submission = self.repository.get_submission_by_id(
            submission_id
        )

        if not submission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Submission not found."
            )

        # Admin can view everything
        if current_user.role == UserRole.ADMIN:
            return submission

        # Trainer can view submissions only for assigned courses
        if current_user.role == UserRole.TRAINER:
            self._verify_trainer_assignment_access(
                trainer_id=current_user.id,
                assignment_id=submission.assignment_id
            )
            return submission

         # Mentor access is not implemented yet
        if current_user.role == UserRole.MENTOR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    
                    "Mentor submission access is not "
                    "available until mentor-learner relationships "
                    "are implemented."
                ), 
            )

        # Learner can only view own submission
        if current_user.role == UserRole.LEARNER:
            if submission.learner_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not authorized to view this submission.",
                )
            return submission
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view this submission.",
        )

   
    def get_my_submissions(
        self,
        learner: User,
    ) -> list[Submission]:
        if learner.role != UserRole.LEARNER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only learners can view their own submissions.",
            )

        if learner.id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Learner identity is required to view submissions.",
            )

        return self.repository.get_by_learner_id(
            learner.id
        )

 
    def get_assignment_submissions(
        self,
        assignment_id: int,
        current_user: User,
    ) -> list[Submission]:

        self._get_assignment(
            assignment_id,
        )

        if current_user.role == UserRole.ADMIN:
            return self.repository.get_by_assignment_id(
                assignment_id
            )

        if current_user.role == UserRole.TRAINER:
            self._verify_trainer_assignment_access(
                trainer_id=current_user.id,
                assignment_id=assignment_id,
            )

            return self.repository.get_by_assignment_id(
                assignment_id,
            )

        if current_user.role == UserRole.MENTOR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Mentor Mentor submission access is not available until mentor-learner relationships are implemented"
                ),
            )
        
        raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Learners cannot view other learners' submissions.",
        )


    def update_submission(
        self,
        submission_id: int,
        learner: User,
        data: SubmissionUpdate,
    ) -> Submission:

        if learner.role != UserRole.LEARNER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only learners can update submissions.",
            )
      
        submission = self.repository.get_submission_by_id(
            submission_id
        )

        if submission is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Submission not found."
            )

        if submission.learner_id != learner.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your own submission."
            )

        # Do not allow modification after grading.
        if submission.graded_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A graded submission cannot be modified.",
            )

        update_data = {
            "content": data.content,
        }

        updated_submission = self.repository.update_submission(
            submission_id,
            update_data
        )

        if updated_submission is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Submission not found."
            )

        return updated_submission

  
    def grade_submission(
        self,
        submission_id: int,
        grader: User,
        data: GradeSubmission,
    ) -> Submission:

        submission = self.repository.get_submission_by_id(
            submission_id
        )

        if submission is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Submission not found.",
            )

        # Learners cannot grade
        if grader.role == UserRole.LEARNER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Learners cannot grade submissions.",
            )

        if grader.role == UserRole.ADMIN:
            pass

        elif grader.role == UserRole.TRAINER:
            self._verify_trainer_assignment_access(
                trainer_id=grader.id,
                assignment_id=submission.assignment_id,
            )

        elif grader.role == UserRole.MENTOR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Mentors cannot grade submissions.",
            )
        
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to grade submissions.",
            )

        assignment = self._get_assignment(
            submission.assignment_id
        )

        if data.score > assignment.maximum_score:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Score must be between 0 and {assignment.maximum_score}.",
            )

        if grader.id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Grader identity is required to grade submissions.",
            )
        
        update_data = {
            "score": data.score,
            "feedback": data.feedback,
            "graded_by": grader.id,
            "graded_at": datetime.now(timezone.utc),
        }

        graded_submission = self.repository.update_submission(
            submission_id,
            update_data,
        )

        if graded_submission is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Submission not found.",
            )

        self.activity_service.record(
            user_id=submission.learner_id,
            activity_type=ActivityType.ASSIGNMENT_GRADED,
            title="Assignment graded",
            description=f"Assignment {assignment.title} has been graded.",
        )

        return graded_submission

  
    def delete_submission(
        self,
        submission_id: int,
        current_user: User,
    ) -> bool:
      
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can delete submissions.",
            )

        deleted = self.repository.delete_submission(
            submission_id
        )

        if deleted is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Submission not found.",
            )

        return True