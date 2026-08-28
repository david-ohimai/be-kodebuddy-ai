from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlmodel import Session

from app.features.activity.model import ActivityType
from app.features.activity.repository import ActivityRepository
from app.features.activity.service import ActivityService

from app.features.auth.model import User
from app.features.lessons.model import Lesson
from app.features.lessons.repository import LessonRepository
from app.features.modules.model import Module
from app.features.modules.repository import ModuleRepository
from app.features.modules.service import verify_learner_course_access

from .model import UserProgress
from .repository import ProgressRepository
from .schema import (
    CourseProgressResponse,
    LessonProgressResponse,
    ModuleProgressResponse,
)


class ProgressService:
    def __init__(self, repository: ProgressRepository, session: Session):
        self.repository = repository
        self.session = session

    def toggle_lesson_completion(
        self,
        lesson_id: int,
        current_user: User,
    ) -> LessonProgressResponse:
        lesson = self.session.get(Lesson, lesson_id)

        if lesson is None or not lesson.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lesson not found",
            )

        module = self.session.get(Module, lesson.module_id)

        if module is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module not found",
            )

        verify_learner_course_access(
            session=self.session,
            current_user=current_user,
            course_id=module.course_id,
        )

        progress = self.repository.get_by_learner_and_lesson(
            learner_id=current_user.id,
            lesson_id=lesson_id,
        )

        if progress is None:
            progress = UserProgress(
                learner_id=current_user.id,
                lesson_id=lesson_id,
                is_completed=True,
                completed_at=datetime.now(timezone.utc),
            )
            progress = self.repository.create(progress)
        else:
            progress.is_completed = not progress.is_completed
            progress.completed_at = (
                datetime.now(timezone.utc) if progress.is_completed else None
            )
            progress = self.repository.update(progress)

        # Activity triggers
        if progress.is_completed:
            self.activity_service.record(
                user_id=current_user.id,
                activity_type=ActivityType.LESSON_COMPLETED,
                title=f"Completed lesson: {lesson.title}",
            )

        self.activity_service.record(
            user_id=current_user.id,
            activity_type=ActivityType.PROGRESS_UPDATED,
            title=f"Progress updated for lesson: {lesson.title}",
        )

        return LessonProgressResponse(
            lesson_id=progress.lesson_id,
            is_completed=progress.is_completed,
            completed_at=progress.completed_at,
        )

    def get_module_progress(
        self,
        module_id: int,
        current_user: User,
    ) -> ModuleProgressResponse:
        module = self.session.get(Module, module_id)

        if module is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module not found",
            )

        verify_learner_course_access(
            session=self.session,
            current_user=current_user,
            course_id=module.course_id,
        )

        lesson_repository = LessonRepository(self.session)
        lessons = lesson_repository.get_by_module_id(module_id)

        progress_records = self.repository.get_by_learner_and_lessons(
            learner_id=current_user.id,
            lesson_ids=[lesson.id for lesson in lessons],
        )
        progress_map = {record.lesson_id: record for record in progress_records}

        lesson_progress = [
            LessonProgressResponse(
                lesson_id=lesson.id,
                is_completed=progress_map[lesson.id].is_completed
                if lesson.id in progress_map
                else False,
                completed_at=progress_map[lesson.id].completed_at
                if lesson.id in progress_map
                else None,
            )
            for lesson in lessons
        ]

        total_lessons = len(lesson_progress)
        completed_lessons = sum(1 for lp in lesson_progress if lp.is_completed)
        percentage = (
            round((completed_lessons / total_lessons) * 100, 2)
            if total_lessons
            else 0.0
        )

        return ModuleProgressResponse(
            module_id=module_id,
            total_lessons=total_lessons,
            completed_lessons=completed_lessons,
            completion_percentage=percentage,
            lessons=lesson_progress,
        )

    def get_course_progress(
        self,
        course_id: int,
        current_user: User,
    ) -> CourseProgressResponse:
        verify_learner_course_access(
            session=self.session,
            current_user=current_user,
            course_id=course_id,
        )

        module_repository = ModuleRepository(self.session)
        lesson_repository = LessonRepository(self.session)

        modules = module_repository.get_by_course_id(course_id)

        all_lesson_ids: list[int] = []
        for module in modules:
            lessons = lesson_repository.get_by_module_id(module.id)
            all_lesson_ids.extend(lesson.id for lesson in lessons)

        progress_records = self.repository.get_by_learner_and_lessons(
            learner_id=current_user.id,
            lesson_ids=all_lesson_ids,
        )

        completed_lessons = sum(1 for record in progress_records if record.is_completed)
        total_lessons = len(all_lesson_ids)
        percentage = (
            round((completed_lessons / total_lessons) * 100, 2)
            if total_lessons
            else 0.0
        )

        return CourseProgressResponse(
            course_id=course_id,
            total_modules=len(modules),
            total_lessons=total_lessons,
            completed_lessons=completed_lessons,
            completion_percentage=percentage,
        )

    def get_module_progress_for_learner(
        self,
        module_id: int,
        learner_id: int,
    ) -> ModuleProgressResponse:
        module = self.session.get(Module, module_id)

        if module is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module not found",
            )

        lesson_repository = LessonRepository(self.session)
        lessons = lesson_repository.get_by_module_id(module_id)

        progress_records = self.repository.get_by_learner_and_lessons(
            learner_id=learner_id,
            lesson_ids=[lesson.id for lesson in lessons],
        )
        progress_map = {record.lesson_id: record for record in progress_records}

        lesson_progress = [
            LessonProgressResponse(
                lesson_id=lesson.id,
                is_completed=progress_map[lesson.id].is_completed
                if lesson.id in progress_map
                else False,
                completed_at=progress_map[lesson.id].completed_at
                if lesson.id in progress_map
                else None,
            )
            for lesson in lessons
        ]

        total_lessons = len(lesson_progress)
        completed_lessons = sum(1 for lp in lesson_progress if lp.is_completed)
        percentage = (
            round((completed_lessons / total_lessons) * 100, 2)
            if total_lessons
            else 0.0
        )

        return ModuleProgressResponse(
            module_id=module_id,
            total_lessons=total_lessons,
            completed_lessons=completed_lessons,
            completion_percentage=percentage,
            lessons=lesson_progress,
        )

    def get_course_progress_for_learner(
        self,
        course_id: int,
        learner_id: int,
    ) -> CourseProgressResponse:
        module_repository = ModuleRepository(self.session)
        lesson_repository = LessonRepository(self.session)

        modules = module_repository.get_by_course_id(course_id)

        all_lesson_ids: list[int] = []
        for module in modules:
            lessons = lesson_repository.get_by_module_id(module.id)
            all_lesson_ids.extend(lesson.id for lesson in lessons)

        progress_records = self.repository.get_by_learner_and_lessons(
            learner_id=learner_id,
            lesson_ids=all_lesson_ids,
        )

        completed_lessons = sum(1 for record in progress_records if record.is_completed)
        total_lessons = len(all_lesson_ids)
        percentage = (
            round((completed_lessons / total_lessons) * 100, 2)
            if total_lessons
            else 0.0
        )

        return CourseProgressResponse(
            course_id=course_id,
            total_modules=len(modules),
            total_lessons=total_lessons,
            completed_lessons=completed_lessons,
            completion_percentage=percentage,
        )