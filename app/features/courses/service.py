from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.features.auth.model import User, UserRole
from app.features.cohorts.repository.repository import CohortRepository
from .model import Course, CourseLearner
from .repository import CourseRepository
from .schema import AssignTrainer,AssignLearner, CourseCreate, CourseUpdate


class CourseService:

    def __init__(
        self, 
        repository: CourseRepository,
        cohort_repository: CohortRepository,
        ):
        self.repository = repository
        self.cohort_repository = cohort_repository

    # ---------- ADMIN ----------

    def create_course(
        self,
        data: CourseCreate,
        admin_id: int,
    ) -> Course:

        cohort = self.cohort_repository.get_by_id(data.cohort_id)

        if not cohort:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cohort not found.",
            )

        course = Course(
            title=data.title,
            description=data.description,
            cohort_id=data.cohort_id,
            created_by=admin_id,
        )

        return self.repository.create(course)

    def update_course(
        self,
        course_id: int,
        data: CourseUpdate,
    ) -> Course:

        course = self.get_course_for_admin(course_id)

        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(course, key, value)

        course.updated_at = datetime.now(timezone.utc)

        return self.repository.update(course)

    def delete_course(self, course_id: int):
        course = self.get_course_for_admin(course_id)
        self.repository.delete(course)

    # ---------- TRAINER ASSIGNMENT ----------
    def assign_trainer(
        self,
        course_id: int,
        trainer_id: int,
    ):
        # Check if the course exists and is accessible by the admin
        course = self.get_course_for_admin(course_id)

        # Check if the trainer exists and has the correct role
        trainer = self.repository.get_user_by_id(trainer_id)

        if trainer is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trainer not found.",
            )

        # Check if the user is a trainer
        if trainer.role != UserRole.TRAINER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only trainers can be assigned to a course.",
            )

        # Check if the trainer is already assigned to the course
        existing = self.repository.get_course_trainer(
            course_id,
            trainer_id,
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Trainer is already assigned to this course.",
            )

        # Assign the trainer to the course
        self.repository.assign_trainer(
            course.id,
            trainer_id,
        )

        return {"message": "Trainer assigned successfully"}

    # ---------- LEARNER ASSIGNMENT ----------
    
    def assign_learner(
        self,
        course_id: int,
        learner_id: int,
    ) -> CourseLearner:
        
        course = self.repository.get_by_id(course_id)

        if course is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found.",
            )

        learner = self.repository.get_user_by_id(learner_id)

        if learner is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Learner not found.",
            )

        if learner.role != UserRole.LEARNER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only learners can be assigned to a course.",
            )

        existing = self.repository.get_course_learner(
            course_id,
            learner_id,
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Learner is already assigned to this course.",
            )

        assigned_learner = self.repository.assign_learner(
            course_id,
            learner_id,
        )

        if assigned_learner is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to assign learner to the course.",
            )

        return assigned_learner

    # ---------- VIEW COURSES ----------

    def get_courses(self, current_user: User):

        if current_user.role == UserRole.ADMIN:
            return self.repository.get_all()

        if current_user.role == UserRole.TRAINER:
            return self.repository.get_trainer_courses(current_user.id)

        # Learner integration comes later with Cohort assignment
        return []

    def get_course(
        self,
        course_id: int,
        current_user: User,
    ) -> Course:

        course = self.repository.get_by_id(course_id)

        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found",
            )

        if current_user.role == UserRole.ADMIN:
            return course

        if current_user.role == UserRole.TRAINER:

            has_access = self.repository.trainer_has_access(
                trainer_id=current_user.id,
                course_id=course.id,
            )

            if not has_access:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You cannot access another trainer's course.",
                )

            return course

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # ---------- INTERNAL ----------

    def get_course_for_admin(self, course_id: int) -> Course:
        course = self.repository.get_by_id(course_id)

        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found",
            )

        return course