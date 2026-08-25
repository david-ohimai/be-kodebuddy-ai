from datetime import datetime, timezone
from sqlmodel import Session, select

from .model import Lesson


class LessonRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, lesson: Lesson) -> Lesson:
        self.session.add(lesson)
        self.session.commit()
        self.session.refresh(lesson)
        return lesson

    def get_by_id(self, lesson_id: int) -> Lesson | None:
        return self.session.get(Lesson, lesson_id)

    def get_active_by_id(self, lesson_id: int) -> Lesson | None:
        statement = select(Lesson).where(
            Lesson.id == lesson_id,
            Lesson.is_active == True,
        )
        return self.session.exec(statement).first()

    def get_by_module_id(
        self,
        module_id: int,
        include_inactive: bool = False,
    ) -> list[Lesson]:
        statement = select(Lesson).where(Lesson.module_id == module_id)

        if not include_inactive:
            statement = statement.where(Lesson.is_active == True)

        statement = statement.order_by(Lesson.order)

        return list(self.session.exec(statement))

    def get_by_ids(self, lesson_ids: list[int]) -> list[Lesson]:
        if not lesson_ids:
            return []

        statement = select(Lesson).where(Lesson.id.in_(lesson_ids))
        return list(self.session.exec(statement))

    def update(self, lesson: Lesson) -> Lesson:
        self.session.add(lesson)
        self.session.commit()
        self.session.refresh(lesson)
        return lesson

    def deactivate(self, lesson: Lesson) -> Lesson:
        lesson.is_active = False
        lesson.updated_at = datetime.now(timezone.utc)

        self.session.add(lesson)
        self.session.commit()
        self.session.refresh(lesson)

        return lesson

    def bulk_update_order(self, lessons: list[Lesson]) -> list[Lesson]:
        for lesson in lessons:
            self.session.add(lesson)
        self.session.commit()

        for lesson in lessons:
            self.session.refresh(lesson)
        return lessons