from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import FRONTEND_URL
from app.features.auth.router import router as user_router
from app.features.profile.router import router as profile_router
from app.features.cohorts.router.router import router as cohorts_router
from app.features.cohorts.router.assign_cohort_router import router as assign_cohorts_router
from app.features.courses.router import router as course_router
from app.features.modules.router import router as module_router
from app.features.lessons.router import router as lesson_router
from app.features.resources.router.module_resource_router import router as module_resource_router
from app.features.resources.router.lesson_resource_router import router as lesson_resource_router
from app.features.assignments.router import router as assignment_router
from app.features.submissions.router import router as submission_router
from app.features.progress.router import router as progress_router
from app.agent.router import router as agent_router
from app.features.mentors.router import router as mentor_router
from app.features.activity.router import router as activity_router
from app.features.dashboard.router import router as dashboard_router
from app.features.escalations.router import router as escalation_router
from app.features.notifications.router import router as notification_router
from fastapi.staticfiles import StaticFiles


app = FastAPI(
    title="KodeBuddy Backend API",
    version="1.0.0",
)



app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_origin_regex=r"^http://localhost(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(
    "/uploads",
    StaticFiles(directory="uploads"),
    name="uploads",
)

app.include_router(user_router)
app.include_router(profile_router)
app.include_router(cohorts_router)
app.include_router(assign_cohorts_router)

app.include_router(course_router)
app.include_router(module_router)
app.include_router(lesson_router)
app.include_router(module_resource_router)
app.include_router(lesson_resource_router)
app.include_router(assignment_router)
app.include_router(submission_router)
app.include_router(progress_router)
app.include_router(agent_router)
app.include_router(mentor_router)
app.include_router(activity_router)
app.include_router(dashboard_router)
app.include_router(escalation_router)
app.include_router(notification_router)

@app.get("/")
def home():
    return {
        "message": "Welcome to KODEBUDDY AI API"
    }


@app.get("/health")
def health_check():
    return {
        "status": "UP"
    }