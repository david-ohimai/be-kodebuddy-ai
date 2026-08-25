from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.auth import (
    get_current_admin,
    get_current_learner,
    get_current_mentor,
    get_current_trainer,
)
from app.core.session import get_session
from app.features.auth.model import User

from .repository import DashboardRepository
from .service import DashboardService


router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


def get_dashboard_service(
    session: Session = Depends(get_session),
) -> DashboardService:
    repository = DashboardRepository(session)
    return DashboardService(repository)


# ---------- LEARNER DASHBOARD ----------

@router.get("/learner")
def get_learner_dashboard(
    current_user: User = Depends(get_current_learner),
    service: DashboardService = Depends(get_dashboard_service)
):
    return service.get_learner_dashboard(current_user.id)


# ---------- TRAINER DASHBOARD ----------

@router.get("/trainer")
def get_trainer_dashboard(
    current_user: User = Depends(get_current_trainer),
    service: DashboardService = Depends(get_dashboard_service)
):
    return service.get_trainer_dashboard(current_user.id)


# ---------- MENTOR DASHBOARD ----------

@router.get("/mentor")
def get_mentor_dashboard(
    current_user: User = Depends(get_current_mentor),
    service: DashboardService = Depends(get_dashboard_service)
):
    return service.get_mentor_dashboard(current_user.id)


# =========================
# ADMIN DASHBOARD
# =========================

@router.get("/admin")
def get_admin_dashboard(
    current_user: User = Depends(get_current_admin),
    service: DashboardService = Depends(get_dashboard_service),
):
    return service.get_admin_dashboard()