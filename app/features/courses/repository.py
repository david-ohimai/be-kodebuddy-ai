from sqlmodel import Session, select
from app.features.auth.model import User
from .model import Course, CourseTrainer,  CourseLearner


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

    # ----------TRAINER ASSIGNMENT ----------

    def assign_trainer(self, course_id: int, trainer_id: int)-> CourseTrainer:
        assignment = CourseTrainer(
            course_id=course_id,
            trainer_id=trainer_id,
        )

        self.session.add(assignment)
        self.session.commit()
        self.session.refresh(assignment)

        return assignment

    def get_course_trainer(
        self,
        course_id: int,
        trainer_id: int,
    ) -> CourseTrainer | None:

        statement = select(CourseTrainer).where(
            CourseTrainer.course_id == course_id,
            CourseTrainer.trainer_id == trainer_id,
        )

        return self.session.exec(statement).first()

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

    
    # ---------- LEARNER ASSIGNMENT ----------

    def assign_learner(self, course_id: int, learner_id: int) -> CourseLearner:

        assignment = CourseLearner(
            course_id=course_id,
            learner_id=learner_id,
        )

        self.session.add(assignment)
        self.session.commit()
        self.session.refresh(assignment)

        return assignment

    def get_course_learner(
        self,
        course_id: int,
        learner_id: int,
    ) -> CourseLearner | None:

        statement = select(CourseLearner).where(
            CourseLearner.course_id == course_id,
            CourseLearner.learner_id == learner_id,
        )

        return self.session.exec(statement).first()

    def learner_has_access(
        self,
        learner_id: int,
        course_id: int,
    ) -> bool:

        statement = select(CourseLearner).where(
            CourseLearner.course_id == course_id,
            CourseLearner.learner_id == learner_id,
        )

        return self.session.exec(statement).first() is not None

    def get_learner_courses(
        self,
        learner_id: int,
    ) -> list[Course]:

        statement = (
            select(Course)
            .join(
                CourseLearner,
                Course.id == CourseLearner.course_id,
            )
            .where(
                CourseLearner.learner_id == learner_id
            )
        )

        return list(self.session.exec(statement))

    # ---------- USER ----------

    def get_user_by_id(
        self,
        user_id: int,
    ) -> User | None:

        return self.session.get(User, user_id)