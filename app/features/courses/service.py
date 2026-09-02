from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.features.auth.model import User, UserRole
from app.features.cohorts.repository.repository import CohortRepository
from .model import Course, CourseLearner
from .repository import CourseRepository
from .schema import CourseCreate, CourseUpdate


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

        if cohort is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cohort not found.",
            )

        course_title = data.title.strip()

        existing_course = self.repository.get_by_cohort_and_title(
            cohort_id=data.cohort_id,
            title=course_title
        )

        if existing_course is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A course with this title already exists in the cohort.",
            )

        course = Course(
            title=course_title,
            description=data.description,
            level=data.level,
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

        if "title" in update_data and update_data["title"] is not None:
            new_title = update_data["title"].strip()

            existing_course = self.repository.get_by_cohort_and_title(
                cohort_id=course.cohort_id,
                title=new_title,
            )

            if (
                existing_course is not None
                and existing_course.id != course.id
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail= "A course with this title already exists in this cohort."
                )

            update_data["title"] = new_title

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
        course = self.get_course_for_admin(course_id)

        trainer = self.repository.get_user_by_id(trainer_id)

        if trainer is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trainer not found.",
            )

        if trainer.role != UserRole.TRAINER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only trainers can be assigned to a course.",
            )

        existing = self.repository.get_course_trainer(
            course_id,
            trainer_id,
        )

        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Trainer is already assigned to this course.",
            )

        self.repository.assign_trainer(
            course.id,
            trainer_id,
        )

        return {"message": "Trainer assigned successfully"}

# ---------- LEARNER SELF COURSE SELECTION ----------
    
    def select_course(
        self,
        course_id: int,
        learner: User,
    ) -> CourseLearner:

        if learner.role != UserRole.LEARNER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only learners can select a course.",
            )

        course = self.repository.get_by_id(course_id)

        if course is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found.",
            )

        if not course.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This course is not available.",
            )

        learner_cohort = self.repository.get_learner_cohort(learner.id)

        if learner_cohort is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You are not assigned to a cohort.",
            )

        if course.cohort_id != learner_cohort.cohort_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only select a course from your cohort.",
            )

        existing_assignment = self.repository.get_learner_assignment(
            learner_id=learner.id
        )

        if existing_assignment is not None:
            if existing_assignment.course_id == course_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="You have already selected this course.",
                )

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "You already have a course assigned. "
                    "Please contact an administrator if "
                    "you want to change your course."
                ),
            )

        return self.repository.assign_learner(
            course_id=course_id,
            learner_id=learner.id,
        )

    # ---------- ADMIN ASSIGN OR CHANGE LEARNER COURSE ----------
    
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

        if not course.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This course is not available.",
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

        learner_cohort = self.repository.get_learner_cohort(learner_id=learner_id)

        if learner_cohort is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Learner is not assigned to a cohort.",
            )

        if course.cohort_id != learner_cohort.cohort_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "The course does not belong to the learner's cohort."
                ),
            )

        existing_assignment = self.repository.get_learner_assignment(
            learner_id=learner_id
        )

        if existing_assignment is not None:
            if existing_assignment.course_id == course_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Learner is already assigned to this course.",
                )
            
            return self.repository.replace_learner_assignment(
                existing_assignment=existing_assignment,
                course_id=course_id,
                learner_id=learner_id,
            )
       
        # Learner has no course yet.
        return self.repository.assign_learner(
            course_id=course_id,
            learner_id=learner_id,
        )

    # ---------- VIEW COURSES ----------

    def get_courses(self, current_user: User):

        if current_user.role == UserRole.ADMIN:
            return self.repository.get_all()

        if current_user.role == UserRole.TRAINER:
            return self.repository.get_trainer_courses(current_user.id)

        if current_user.role == UserRole.LEARNER:
            assigned_course = self.repository.get_learner_course(
                    current_user.id
                )

            if assigned_course is not None:
                return [assigned_course]

            learner_cohort = self.repository.get_learner_cohort(
                current_user.id
            )

            if learner_cohort is None:
                return []

            return self.repository.get_active_courses_by_cohort(
                learner_cohort.cohort_id
            )
        return []

    def get_course(
        self,
        course_id: int,
        current_user: User,
    ) -> Course:

        course = self.repository.get_by_id(course_id)

        if course is None:
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

        if current_user.role == UserRole.LEARNER:

            has_access = self.repository.learner_has_access(
                    learner_id=current_user.id,
                    course_id=course.id,
            )

            if not has_access:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "You can only access your assigned course."
                    ),
                )

            return course

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # ---------- INTERNAL ----------

    def get_course_for_admin(self, course_id: int) -> Course:
        course = self.repository.get_by_id(course_id)

        if course is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found",
            )

        return course