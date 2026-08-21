from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlmodel import Session

from app.features.auth.model import User, UserRole
from app.features.modules.model import Module
from app.features.modules.service import (
    verify_trainer_course_access,
    verify_learner_course_access,
)

from .model import Lesson
from .repository import LessonRepository
from .schema import LessonCreate, LessonUpdate, ReorderLessonsRequest


def _get_module_or_404(session: Session, module_id: int) -> Module:
    module = session.get(Module, module_id)

    if module is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Module not found",
        )

    return module


def verify_trainer_lesson_access(
    session: Session,
    current_user: User,
    lesson: Lesson,
) -> None:
    module = _get_module_or_404(session, lesson.module_id)

    verify_trainer_course_access(
        session=session,
        current_user=current_user,
        course_id=module.course_id,
    )


def verify_learner_lesson_access(
    session: Session,
    current_user: User,
    lesson: Lesson,
) -> None:
    module = _get_module_or_404(session, lesson.module_id)

    verify_learner_course_access(
        session=session,
        current_user=current_user,
        course_id=module.course_id,
    )


class LessonService:
    def __init__(self, repository: LessonRepository, session: Session):
        self.repository = repository
        self.session = session

    def create_lesson(self, data: LessonCreate, current_user: User) -> Lesson:
        module = _get_module_or_404(self.session, data.module_id)

        verify_trainer_course_access(
            session=self.session,
            current_user=current_user,
            course_id=module.course_id,
        )

        lesson = Lesson(
            module_id=data.module_id,
            title=data.title,
            content_body=data.content_body,
            order=data.order,
            created_by=current_user.id,
        )
        return self.repository.create(lesson)

    def get_lesson(self, lesson_id: int, current_user: User) -> Lesson:
        lesson = self.repository.get_active_by_id(lesson_id)

        if lesson is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lesson not found",
            )

        if current_user.role == UserRole.ADMIN:
            return lesson

        if current_user.role == UserRole.TRAINER:
            verify_trainer_lesson_access(self.session, current_user, lesson)
            return lesson

        if current_user.role == UserRole.LEARNER:
            verify_learner_lesson_access(self.session, current_user, lesson)
            return lesson

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this lesson",
        )

    def get_lessons_for_module(self, module_id: int, current_user: User) -> list[Lesson]:
        module = _get_module_or_404(self.session, module_id)

        if current_user.role == UserRole.ADMIN:
            return self.repository.get_by_module_id(module_id)

        elif current_user.role == UserRole.TRAINER:
            verify_trainer_course_access(
                session=self.session,
                current_user=current_user,
                course_id=module.course_id,
            )

        elif current_user.role == UserRole.LEARNER:
            verify_learner_course_access(
                session=self.session,
                current_user=current_user,
                course_id=module.course_id,
            )

        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access module lessons",
            )

        return self.repository.get_by_module_id(module_id)

    def update_lesson(self, lesson_id: int, data: LessonUpdate, current_user: User) -> Lesson:
        lesson = self.repository.get_active_by_id(lesson_id)

        if lesson is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lesson not found",
            )

        verify_trainer_lesson_access(self.session, current_user, lesson)

        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(lesson, field, value)

        lesson.updated_at = datetime.now(timezone.utc)

        return self.repository.update(lesson)

    def delete_lesson(self, lesson_id: int, current_user: User) -> Lesson:
        lesson = self.repository.get_active_by_id(lesson_id)

        if lesson is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lesson not found",
            )

        verify_trainer_lesson_access(self.session, current_user, lesson)

        return self.repository.deactivate(lesson)

    def reorder_lessons(self, data: ReorderLessonsRequest, current_user: User) -> list[Lesson]:
        module = _get_module_or_404(self.session, data.module_id)

        verify_trainer_course_access(
            session=self.session,
            current_user=current_user,
            course_id=module.course_id,
        )

        requested_ids = [item.id for item in data.lessons]

        if len(requested_ids) != len(set(requested_ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate lesson IDs are not allowed",
            )

        lessons = self.repository.get_by_ids(requested_ids)

        found_ids = {lesson.id for lesson in lessons}
        missing_ids = set(requested_ids) - found_ids

        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lesson(s) not found: {sorted(missing_ids)}",
            )

        invalid_lessons = [
            lesson.id for lesson in lessons if lesson.module_id != data.module_id
        ]

        if invalid_lessons:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="One or more lessons do not belong to this module",
            )

        order_map = {item.id: item.order for item in data.lessons}

        for lesson in lessons:
            lesson.order = order_map[lesson.id]
            lesson.updated_at = datetime.now(timezone.utc)

        return self.repository.bulk_update_order(lessons)