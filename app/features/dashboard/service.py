from datetime import datetime, timezone

from app.features.dashboard.repository import DashboardRepository
from app.features.dashboard.schema import (
    AdminDashboardResponse,
    LearnerAssignmentStatus,
    LearnerCourseProgress,
    LearnerDashboardResponse,
    MentorCheckInSummary,
    MentorDashboardResponse,
    MentorLearnerProgress,
    TrainerCourseSummary,
    TrainerDashboardResponse,
)


class DashboardService:

    def __init__(self, repository: DashboardRepository):
        self.repository = repository


    # ---------- ADMIN DASHBOARD ----------

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


    # ---------- LEARNER DASHBOARD ----------

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


# ---------- TRAINER DASHBOARD ----------
    
    def get_trainer_dashboard(
        self,
        trainer_id: int,
    ) -> TrainerDashboardResponse:

        courses = self.repository.get_trainer_courses(
            trainer_id
        )

        course_summaries = []

        total_learners = 0
        total_submissions = 0
        total_pending_grades = 0


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

            # Aggregate trainer-level totals
            total_learners += len(learners)
            total_submissions += len(submissions)
            total_pending_grades += pending_grades


        return TrainerDashboardResponse(
            total_courses=len(courses),
            courses=course_summaries,
            total_learners=total_learners,
            total_submissions=total_submissions,
            pending_grades=total_pending_grades,
        )


    # ---------- MENTOR DASHBOARD ----------
    
    def get_mentor_dashboard(
        self,
        mentor_id: int,
    ) -> MentorDashboardResponse:

        learners = (
            self.repository.get_mentor_assigned_learners(
                mentor_id
            )
        )

        check_ins = (
            self.repository.get_mentor_check_ins(
                mentor_id
            )
        )

        total_check_ins = len(check_ins)
        upcoming_check_ins = sum(
            1
            for check_in in check_ins
            if check_in.status.value == "upcoming"
        )

        completed_check_ins = sum(
            1
            for check_in in check_ins
            if check_in.status.value == "completed"
        )


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

            learner_check_ins = [
                check_in
                for check_in in check_ins
                if check_in.learner_id == learner.id
            ]

            check_in_summaries = [
                MentorCheckInSummary(
                    id=check_in.id,
                    scheduled_time=check_in.scheduled_time,
                    status=check_in.status.value,
                    notes=check_in.notes,
                )
                for check_in in learner_check_ins
                if check_in.id is not None
            ]


            learner_progress.append(
                MentorLearnerProgress(
                    learner_id=learner.id,
                    learner_name=learner.full_name or learner.email,
                    total_courses=len(courses),
                    total_lessons=total_lessons,
                    completed_lessons=completed_lessons,
                    completion_percentage=round(
                        percentage,
                        2,
                    ),
                    check_ins=check_in_summaries,
                )
            )

        return MentorDashboardResponse(
            total_learners=len(learners),
            total_check_ins=total_check_ins,
            upcoming_check_ins=upcoming_check_ins,
            completed_check_ins=completed_check_ins,
            learners=learner_progress,
        )
