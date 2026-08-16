from sqlmodel import Session, select
from .model import Course, CourseTrainer


class CourseRepository:

    def __init__(self, session: Session):
        self.session = session

    # ---------- COURSE ----------

    def create(self, course: Course) -> Course:
        self.session.add(course)
        self.session.commit()
        self.session.refresh(course)
        return course

    def get_by_id(self, course_id: int) -> Course | None:
        return self.session.get(Course, course_id)

    def get_all(self) -> list[Course]:
        statement = select(Course).order_by(Course.created_at.desc())
        return list(self.session.exec(statement))

    def update(self, course: Course) -> Course:
        self.session.add(course)
        self.session.commit()
        self.session.refresh(course)
        return course

    def delete(self, course: Course):
        self.session.delete(course)
        self.session.commit()

    # ---------- ASSIGNMENT ----------

    def assign_trainer(self, course_id: int, trainer_id: int):
        assignment = CourseTrainer(
            course_id=course_id,
            trainer_id=trainer_id,
        )

        self.session.add(assignment)
        self.session.commit()

    def trainer_has_access(
        self,
        trainer_id: int,
        course_id: int,
    ) -> bool:
        statement = select(CourseTrainer).where(
            CourseTrainer.course_id == course_id,
            CourseTrainer.trainer_id == trainer_id,
        )

        return self.session.exec(statement).first() is not None

    def get_trainer_courses(self, trainer_id: int) -> list[Course]:
        statement = (
            select(Course)
            .join(
                CourseTrainer,
                Course.id == CourseTrainer.course_id,
            )
            .where(CourseTrainer.trainer_id == trainer_id)
        )

        return list(self.session.exec(statement))