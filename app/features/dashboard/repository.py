from sqlmodel import Session, select

from app.features.auth.model import User, UserRole
from app.features.activity.model import UserActivity
from app.features.cohorts.models.model import Cohort
from app.features.courses.model import Course, CourseTrainer, CourseLearner
from app.features.modules.model import Module
from app.features.lessons.model import Lesson
from app.features.assignments.model import Assignment
from app.features.submissions.model import Submission
from app.features.progress.model import UserProgress
from app.features.mentors.model import MentorLearner, MentorCheckIn


class DashboardRepository:

    def __init__(self, session: Session):
        self.session = session

    # ---------- USER / ADMIN STATISTICS ----------
    def get_total_users(self) -> int:
        statement = select(User)
        return len(list(self.session.exec(statement)))

    def get_total_learners(self) -> int:
        statement = select(User).where(
            User.role == UserRole.LEARNER
        )
        return len(list(self.session.exec(statement)))

    def get_total_trainers(self) -> int:
        statement = select(User).where(
            User.role == UserRole.TRAINER
        )
        return len(list(self.session.exec(statement)))

    def get_total_mentors(self) -> int:
        statement = select(User).where(
            User.role == UserRole.MENTOR
        )
        return len(list(self.session.exec(statement)))

    def get_total_admins(self) -> int:
        statement = select(User).where(
            User.role == UserRole.ADMIN
        )
        return len(list(self.session.exec(statement)))

    def get_active_users(self) -> int:
        statement = select(User).where(
            User.is_active == True
        )
        return len(list(self.session.exec(statement)))

    # ---------- COHORT STATISTICS ----------
    def get_total_cohorts(self) -> int:
        statement = select(Cohort)
        return len(list(self.session.exec(statement)))

    def get_active_cohorts(self) -> int:
        statement = select(Cohort).where(
            Cohort.is_open == True
        )
        return len(list(self.session.exec(statement)))

    def get_cohort_breakdown(self) -> list[dict]:
       cohorts = list(
           self.session.exec(
               select(Cohort)
           )
       )
   
       breakdown = []
   
       for cohort in cohorts:
           if cohort.id is None:
               continue
   
           learner_statement = (
               select(CourseLearner.learner_id)
               .join(
                   Course,
                   Course.id == CourseLearner.course_id,
               )
               .where(
                   Course.cohort_id == cohort.id,
                   Course.is_active == True,
               )
               .distinct()
           )
   
           learner_ids = list(
               self.session.exec(learner_statement)
           )
   
           course_statement = (
               select(Course.id)
               .where(
                   Course.cohort_id == cohort.id,
                   Course.is_active == True,
               )
           )
   
           course_ids = list(
               self.session.exec(course_statement)
           )
   
           breakdown.append(
               {
                   "cohort_id": cohort.id,
                   "cohort_name": cohort.name,
                   "learner_count": len(learner_ids),
                   "course_count": len(course_ids),
                   "active": cohort.is_open,
               }
           )
   
       return breakdown

    # ---------- COURSE STATISTICS ----------
    def get_total_courses(self) -> int:
        statement = select(Course)
        return len(list(self.session.exec(statement)))

    def get_active_courses(self) -> int:
        statement = select(Course).where(
            Course.is_active == True
        )
        return len(list(self.session.exec(statement)))

    # ---------- SUBMISSION STATISTICS ----------
    def get_total_submissions(self) -> int:
        statement = select(Submission)
        return len(list(self.session.exec(statement)))

    def get_pending_grades(self) -> int:
        statement = select(Submission).where(
            Submission.score.is_(None)
        )
        return len(list(self.session.exec(statement)))

    # ---------- LEARNER DASHBOARD ----------
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
                CourseLearner.learner_id == learner_id,
                Course.is_active == True,
            )
        )

        return list(self.session.exec(statement))

    def get_course_modules(
        self,
        course_id: int,
    ) -> list[Module]:

        statement = select(Module).where(
            Module.course_id == course_id,
            Module.is_active == True,
        )

        return list(self.session.exec(statement))

    def get_module_lessons(
        self,
        module_id: int,
    ) -> list[Lesson]:

        statement = select(Lesson).where(
            Lesson.module_id == module_id,
            Lesson.is_active == True,
        )

        return list(self.session.exec(statement))

    def get_learner_progress(
        self,
        learner_id: int,
        lesson_ids: list[int],
    ) -> list[UserProgress]:

        if not lesson_ids:
            return []

        statement = select(UserProgress).where(
            UserProgress.learner_id == learner_id,
            UserProgress.lesson_id.in_(lesson_ids),
        )

        return list(self.session.exec(statement))

    def get_learner_assignments(
        self,
        learner_id: int,
    ) -> list[Assignment]:

        courses = self.get_learner_courses(learner_id)

        if not courses:
            return []

        course_ids = [course.id for course in courses if course.id is not None]

        if not course_ids:
            return []

        module_statement = select(Module.id).where(
            Module.course_id.in_(course_ids),
            Module.is_active == True,
        )

        module_ids = list(self.session.exec(module_statement))

        if not module_ids:
            return []

        assignment_statement = select(Assignment).where(
            Assignment.module_id.in_(module_ids),
            Assignment.is_active == True,
        )

        return list(self.session.exec(assignment_statement))

    def get_learner_submission(
        self,
        learner_id: int,
        assignment_id: int,
    ) -> Submission | None:

        statement = select(Submission).where(
            Submission.learner_id == learner_id,
            Submission.assignment_id == assignment_id,
        )

        return self.session.exec(statement).first()

    # ---------- TRAINER DASHBOARD ----------
    def get_trainer_courses(
        self,
        trainer_id: int,
    ) -> list[Course]:

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

        return list(self.session.exec(statement))

    def get_course_learners(
        self,
        course_id: int,
    ) -> list[User]:

        statement = (
            select(User)
            .join(
                CourseLearner,
                User.id == CourseLearner.learner_id,
            )
            .where(
                CourseLearner.course_id == course_id,
                User.role == UserRole.LEARNER,
                User.is_active == True,
            )
        )

        return list(self.session.exec(statement))

    def get_course_assignments(
        self,
        course_id: int,
    ) -> list[Assignment]:

        module_statement = select(Module.id).where(
            Module.course_id == course_id,
            Module.is_active == True,
        )

        module_ids = list(self.session.exec(module_statement))

        if not module_ids:
            return []

        statement = select(Assignment).where(
            Assignment.module_id.in_(module_ids),
            Assignment.is_active == True,
        )

        return list(self.session.exec(statement))

    def get_course_submissions(
        self,
        course_id: int,
    ) -> list[Submission]:

        assignments = self.get_course_assignments(course_id)

        assignment_ids = [
            assignment.id
            for assignment in assignments
            if assignment.id is not None
        ]

        if not assignment_ids:
            return []

        statement = select(Submission).where(
            Submission.assignment_id.in_(assignment_ids)
        )

        return list(self.session.exec(statement))

    # ---------- MENTOR DASHBOARD ----------
    def get_mentor_assigned_learners(
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
                User.role == UserRole.LEARNER,
                User.is_active == True,
            )
        )

        return list(self.session.exec(statement))

    def get_mentor_check_ins(
        self,
        mentor_id: int,
    ) -> list[MentorCheckIn]:

        statement = select(MentorCheckIn).where(
            MentorCheckIn.mentor_id == mentor_id
        )

        return list(self.session.exec(statement))

    # ---------- ACTIVITY ----------
    def get_learner_activities(
        self,
        learner_id: int,
        limit: int = 20,
    ) -> list[UserActivity]:

        statement = (
            select(UserActivity)
            .where(
                UserActivity.user_id == learner_id
            )
            .order_by(
                UserActivity.created_at.desc()
            )
            .limit(limit)
        )

        return list(
            self.session.exec(statement)
        )

    def get_trainer_activities(
        self,
        trainer_id: int,
        limit: int = 20,
    ) -> list[UserActivity]:

        statement = (
            select(UserActivity)
            .join(
                CourseLearner,
                CourseLearner.learner_id == UserActivity.user_id,
            )
            .join(
                CourseTrainer,
                CourseTrainer.course_id == CourseLearner.course_id,
            )
            .where(
                CourseTrainer.trainer_id == trainer_id,
            )
            .order_by(
                UserActivity.created_at.desc()
            )
            .limit(limit)
        )

        return list(
            self.session.exec(statement)
        )

    def get_mentor_activities(
        self,
        mentor_id: int,
        limit: int = 20,
    ) -> list[UserActivity]:

        statement = (
            select(UserActivity)
            .join(
                MentorLearner,
                MentorLearner.learner_id == UserActivity.user_id,
            )
            .where(
                MentorLearner.mentor_id == mentor_id,
            )
            .order_by(
                UserActivity.created_at.desc()
            )
            .limit(limit)
        )

        return list(
            self.session.exec(statement)
        )

    def get_admin_activities(
        self,
        limit: int = 20,
    ) -> list[UserActivity]:

        statement = (
            select(UserActivity)
            .order_by(
                UserActivity.created_at.desc()
            )
            .limit(limit)
        )

        return list(
            self.session.exec(statement)
        )