from sqlmodel import Session, select

from app.features.auth.model import User
from app.features.cohorts.models.cohort_learners import ( CohortLearner, CohortTrainer, ) 
from app.features.cohorts.models.model import Cohort 
from app.features.courses.model import ( 
    Course, 
    CourseLearner, 
    CourseTrainer, 
) 
from app.features.mentors.model import MentorLearner

class ProfileRepository:

    def __init__(self, session: Session):
        self.session = session


    def get_by_id(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def get_all(self) -> list[User]:
        return list(
            self.session.exec(
                select(User)
            ).all()
        )


    def update(self, user: User) -> User:
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)

        return user

    # ---------------- LEARNER ----------------

    def get_learner_cohort(
        self,
        learner_id: int,
    ) -> Cohort | None:

        statement = (
            select(Cohort)
            .join(
                CohortLearner,
                Cohort.id == CohortLearner.cohort_id,
            )
            .where(
                CohortLearner.learner_id == learner_id,
                CohortLearner.is_active == True,
            )
        )

        return self.session.exec(statement).first()

    def get_learner_course(
        self,
        learner_id: int,
    ) -> Course | None:

        statement = (
            select(Course)
            .join(
                CourseLearner,
                Course.id == CourseLearner.course_id,
            )
            .where(
                CourseLearner.learner_id == learner_id,
                Course.is_active == True,
            )
        )

        return self.session.exec(statement).first()

    # ---------------- TRAINER ----------------

    def get_trainer_cohort(
        self,
        trainer_id: int,
    ) -> Cohort | None:

        statement = (
            select(Cohort)
            .join(
                CohortTrainer,
                Cohort.id == CohortTrainer.cohort_id,
            )
            .where(
                CohortTrainer.trainer_id == trainer_id,
                CohortTrainer.removed_at.is_(None),
            )
        )

        return self.session.exec(statement).first()

    def get_trainer_course(
        self,
        trainer_id: int,
    ) -> Course | None:

        statement = (
            select(Course)
            .join(
                CourseTrainer,
                Course.id == CourseTrainer.course_id,
            )
            .where(
                CourseTrainer.trainer_id == trainer_id,
                Course.is_active == True,
            )
        )

        return self.session.exec(statement).first()

    # ---------------- MENTOR ----------------

    def get_mentor_learners(
        self,
        mentor_id: int,
    ) -> list[User]:

        statement = (
            select(User)
            .join(
                MentorLearner,
                User.id == MentorLearner.learner_id,
            )
            .where(
                MentorLearner.mentor_id == mentor_id,
                User.is_active == True,
            )
        )

        return list(self.session.exec(statement).all())
    