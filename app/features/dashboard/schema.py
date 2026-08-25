from pydantic import BaseModel
from datetime import datetime

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


# ---------- MENTOR DASHBOARD ----------

class MentorLearnerProgress(BaseModel):
    learner_id: int
    learner_name: str
    total_courses: int
    total_lessons: int
    completed_lessons: int
    completion_percentage: float


class MentorDashboardResponse(BaseModel):
    total_learners: int
    learners: list[MentorLearnerProgress]


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
