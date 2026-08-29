from pydantic import BaseModel
from datetime import datetime
from app.features.activity.model import ActivityType

# ---------- COHORT BREAKDOWN ----------

class AdminCohortBreakdown(BaseModel):
    cohort_id: int
    cohort_name: str
    learner_count: int
    course_count: int
    active: bool

# ---------- ACTIVITY ----------

class DashboardActivity(BaseModel):
    id: int
    activity_type: ActivityType
    title: str
    description: str | None
    created_at: datetime

# ---------- LEARNER DASHBOARD ----------

class LearnerCourseProgress(BaseModel):
    course_id: int
    course_title: str
    total_modules: int
    total_lessons: int
    completed_lessons: int
    completion_percentage: float


class LearnerAssignmentStatus(BaseModel):
    assignment_id: int
    title: str
    due_date: datetime
    submitted: bool
    graded: bool
    score: float | None
    is_overdue: bool


class LearnerDashboardResponse(BaseModel):
    total_courses: int
    total_modules: int
    total_lessons: int
    completed_lessons: int
    overall_completion_percentage: float
    courses: list[LearnerCourseProgress]
    assignments: list[LearnerAssignmentStatus]
    activities: list[DashboardActivity]


# ---------- TRAINER DASHBOARD ----------

class TrainerCourseSummary(BaseModel):
    course_id: int
    course_title: str
    cohort_id: int
    learner_count: int
    total_modules: int
    total_lessons: int
    total_assignments: int
    total_submissions: int
    pending_grades: int


class TrainerDashboardResponse(BaseModel):
    total_courses: int
    total_learners: int
    total_submissions: int
    pending_grades: int
    courses: list[TrainerCourseSummary]
    activities: list[DashboardActivity]


# ---------- MENTOR DASHBOARD ----------

class MentorCheckInSummary(BaseModel):
    id: int
    scheduled_time: datetime
    status: str
    notes: str | None


class MentorLearnerProgress(BaseModel):
    learner_id: int
    learner_name: str
    total_courses: int
    total_lessons: int
    completed_lessons: int
    completion_percentage: float
    check_ins: list[MentorCheckInSummary]


class MentorDashboardResponse(BaseModel):
    total_learners: int
    total_check_ins: int
    upcoming_check_ins: int
    completed_check_ins: int
    learners: list[MentorLearnerProgress]
    activities: list[DashboardActivity]


# ---------- ADMIN DASHBOARD ----------

class AdminDashboardResponse(BaseModel):
    total_users: int
    total_learners: int
    total_trainers: int
    total_mentors: int
    total_admins: int
    active_users: int
    total_cohorts: int
    active_cohorts: int
    total_courses: int
    active_courses: int
    total_submissions: int
    pending_grades: int
    activities: list[DashboardActivity]
    cohort_breakdown: list[AdminCohortBreakdown]
