from fastapi import FastAPI
from app.features.auth.router import router as user_router
from app.features.profile.router import router as profile_router
from app.features.cohorts.router.router import router as cohorts_router
from app.features.cohorts.router.assign_cohort_router import router as assign_cohorts_router
from app.features.courses.router import router as course_router
from app.features.modules.router import router as module_router
from app.features.assignments.router import router as assignment_router
from app.features.resources.router import router as resource_router
from app.features.submissions.router import router as submission_router

app = FastAPI(
    title="KodeBuddy Backend API",
    version="1.0.0",
)

app.include_router(user_router)
app.include_router(profile_router)
app.include_router(cohorts_router)
app.include_router(assign_cohorts_router)
app.include_router(course_router)
app.include_router(module_router)
app.include_router(resource_router)
app.include_router(assignment_router)
app.include_router(submission_router)

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