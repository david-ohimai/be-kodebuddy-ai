from fastapi import FastAPI
from app.features.auth.router import router as user_router
from app.features.profile.router import router as profile_router

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     create_db_and_tables()
#     yield


app = FastAPI(
    title="KodeBuddy Backend API",
    version="1.0.0",
)

app.include_router(user_router)
app.include_router(profile_router)


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


