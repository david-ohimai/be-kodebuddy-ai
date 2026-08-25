from datetime import datetime, timezone

from app.features.dashboard.repository import DashboardRepository
from app.features.dashboard.schema import (
    AdminDashboardResponse,
    LearnerAssignmentStatus,
    LearnerCourseProgress,
    LearnerDashboardResponse,
    MentorDashboardResponse,
    TrainerCourseSummary,
    TrainerDashboardResponse,
)


class DashboardService:

    def __init__(self, repository: DashboardRepository):
        self.repository = repository

    # ============================================================
    # ADMIN DASHBOARD
    # ============================================================

    def get_admin_dashboard(self) -> AdminDashboardResponse:

        return AdminDashboardResponse(
            total_users=self.repository.get_total_users(),
            total_learners=self.repository.get_total_learners(),
            total_trainers=self.repository.get_total_trainers(),
            total_mentors=self.repository.get_total_mentors(),
            total_admins=self.repository.get_total_admins(),
            active_users=self.repository.get_active_users(),
            total_cohorts=self.repository.get_total_cohorts(),
            active_cohorts=self.repository.get_active_cohorts(),
            total_courses=self.repository.get_total_courses(),
            active_courses=self.repository.get_active_courses(),
            total_submissions=self.repository.get_total_submissions(),
            pending_grades=self.repository.get_pending_grades(),
        )

    # ============================================================
    # LEARNER DASHBOARD
    # ============================================================

    def get_learner_dashboard(
        self,
        learner_id: int,
    ) -> LearnerDashboardResponse:

        courses = self.repository.get_learner_courses(
            learner_id
        )

        course_progress = []

        total_modules = 0
        total_lessons = 0
        completed_lessons = 0

        for course in courses:

            if course.id is None:
                continue

            modules = self.repository.get_course_modules(
                course.id
            )

            course_total_lessons = 0
            course_completed_lessons = 0

            for module in modules:

                if module.id is None:
                    continue

                lessons = self.repository.get_module_lessons(
                    module.id
                )

                lesson_ids = [
                    lesson.id
                    for lesson in lessons
                    if lesson.id is not None
                ]

                progress_records = (
                    self.repository.get_learner_progress(
                        learner_id,
                        lesson_ids,
                    )
                )

                completed = sum(
                    1
                    for progress in progress_records
                    if progress.is_completed
                )

                course_total_lessons += len(lessons)
                course_completed_lessons += completed

            total_modules += len(modules)
            total_lessons += course_total_lessons
            completed_lessons += course_completed_lessons

            percentage = (
                (
                    course_completed_lessons
                    / course_total_lessons
                )
                * 100
                if course_total_lessons
                else 0
            )

            course_progress.append(
                LearnerCourseProgress(
                    course_id=course.id,
                    course_title=course.title,
                    total_modules=len(modules),
                    total_lessons=course_total_lessons,
                    completed_lessons=course_completed_lessons,
                    completion_percentage=round(
                        percentage,
                        2,
                    ),
                )
            )

        assignments = (
            self.repository.get_learner_assignments(
                learner_id
            )
        )

        assignment_status = []

        now = datetime.now(timezone.utc)

        for assignment in assignments:

            if assignment.id is None:
                continue

            submission = (
                self.repository.get_learner_submission(
                    learner_id,
                    assignment.id,
                )
            )

            submitted = submission is not None

            graded = (
                submission is not None
                and submission.score is not None
            )

            score = (
                submission.score
                if submission is not None
                else None
            )

            is_overdue = (
                assignment.due_date < now
                and not submitted
            )

            assignment_status.append(
                LearnerAssignmentStatus(
                    assignment_id=assignment.id,
                    title=assignment.title,
                    due_date=assignment.due_date,
                    submitted=submitted,
                    graded=graded,
                    score=score,
                    is_overdue=is_overdue,
                )
            )

        overall_percentage = (
            (
                completed_lessons
                / total_lessons
            )
            * 100
            if total_lessons
            else 0
        )

        return LearnerDashboardResponse(
            total_courses=len(courses),
            total_modules=total_modules,
            total_lessons=total_lessons,
            completed_lessons=completed_lessons,
            overall_completion_percentage=round(
                overall_percentage,
                2,
            ),
            courses=course_progress,
            assignments=assignment_status,
        )

    # ============================================================
    # TRAINER DASHBOARD
    # ============================================================

    def get_trainer_dashboard(
        self,
        trainer_id: int,
    ) -> TrainerDashboardResponse:

        courses = self.repository.get_trainer_courses(
            trainer_id
        )

        course_summaries = []

        for course in courses:

            if course.id is None:
                continue

            learners = self.repository.get_course_learners(
                course.id
            )

            modules = self.repository.get_course_modules(
                course.id
            )

            assignments = (
                self.repository.get_course_assignments(
                    course.id
                )
            )

            submissions = (
                self.repository.get_course_submissions(
                    course.id
                )
            )

            pending_grades = sum(
                1
                for submission in submissions
                if submission.score is None
            )

            total_lessons = 0

            for module in modules:

                if module.id is None:
                    continue

                lessons = self.repository.get_module_lessons(
                    module.id
                )

                total_lessons += len(lessons)

            course_summaries.append(
                TrainerCourseSummary(
                    course_id=course.id,
                    course_title=course.title,
                    cohort_id=course.cohort_id,
                    learner_count=len(learners),
                    total_modules=len(modules),
                    total_lessons=total_lessons,
                    total_assignments=len(assignments),
                    total_submissions=len(submissions),
                    pending_grades=pending_grades,
                )
            )

        return TrainerDashboardResponse(
            total_courses=len(courses),
            courses=course_summaries,
        )

    # ============================================================
    # MENTOR DASHBOARD
    # ============================================================

    def get_mentor_dashboard(
        self,
        mentor_id: int,
    ) -> MentorDashboardResponse:

        learners = (
            self.repository.get_mentor_assigned_learners(
                mentor_id
            )
        )

        # The Mentor -> Learner relationship is being
        # implemented separately. Once that model is available,
        # the repository method above will provide the assigned
        # learners and this method can calculate their progress.

        learner_progress = []

        for learner in learners:

            if learner.id is None:
                continue

            courses = (
                self.repository.get_learner_courses(
                    learner.id
                )
            )

            total_lessons = 0
            completed_lessons = 0

            for course in courses:

                if course.id is None:
                    continue

                modules = (
                    self.repository.get_course_modules(
                        course.id
                    )
                )

                for module in modules:

                    if module.id is None:
                        continue

                    lessons = (
                        self.repository.get_module_lessons(
                            module.id
                        )
                    )

                    lesson_ids = [
                        lesson.id
                        for lesson in lessons
                        if lesson.id is not None
                    ]

                    progress_records = (
                        self.repository.get_learner_progress(
                            learner.id,
                            lesson_ids,
                        )
                    )

                    total_lessons += len(lessons)

                    completed_lessons += sum(
                        1
                        for progress in progress_records
                        if progress.is_completed
                    )

            percentage = (
                (
                    completed_lessons
                    / total_lessons
                )
                * 100
                if total_lessons
                else 0
            )

            learner_progress.append(
                {
                    "learner_id": learner.id,
                    "learner_name": learner.full_name
                    or learner.email,
                    "total_courses": len(courses),
                    "total_lessons": total_lessons,
                    "completed_lessons": completed_lessons,
                    "completion_percentage": round(
                        percentage,
                        2,
                    ),
                }
            )

        return MentorDashboardResponse(
            total_learners=len(learners),
            learners=learner_progress,
        )
