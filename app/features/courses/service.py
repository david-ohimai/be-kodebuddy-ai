from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.features.auth.model import User, UserRole

from .model import Course
from .repository import CourseRepository
from .schema import AssignTrainer, CourseCreate, CourseUpdate


class CourseService:

    def __init__(self, repository: CourseRepository):
        self.repository = repository

    # ---------- ADMIN ----------

    def create_course(
        self,
        data: CourseCreate,
        admin_id: int,
    ) -> Course:

        course = Course(
            title=data.title,
            description=data.description,
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

    def assign_trainer(
        self,
        course_id: int,
        trainer_id: int,
    ):
        course = self.get_course_for_admin(course_id)

        self.repository.assign_trainer(
            course.id,
            trainer_id,
        )

        return {"message": "Trainer assigned successfully"}

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