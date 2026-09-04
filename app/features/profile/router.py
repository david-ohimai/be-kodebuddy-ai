from app.core.auth import get_current_admin, get_current_user
from fastapi import APIRouter, Depends, File, UploadFile
from sqlmodel import Session

from app.core.session import get_session
from app.features.auth.model import User
from app.features.profile.schema import ProfilePictureResponse, UpdateProfile, UpdateUserRole, UserDto, UserResponse
from app.features.profile.service import ProfileService

from app.features.profile.repository  import ProfileRepository
from app.features.courses.repository import CourseRepository


router = APIRouter(
    prefix="/profile",
    tags=["Profile"],
)


def get_profile_service(
    session: Session = Depends(get_session),
) -> ProfileService:
   profile_repository = ProfileRepository(session)
   course_repository = CourseRepository(session)

   return ProfileService(repository=profile_repository, course_repository=course_repository)


@router.get(
    "/users",
    response_model=list[UserDto],
    dependencies=[Depends(get_current_admin)],
)
def get_users(
   service: ProfileService = Depends(get_profile_service),
):
    return service.get_all_users()




@router.get(
    "/profile-me",
    response_model=UserDto,
)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    return service.get_user_by_id(current_user.id)



@router.patch(
    "/update-profile",
    response_model=UserResponse,
)
def update_profile(
    data: UpdateProfile,
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    return service.update_profile(
        current_user,
        data,
    )

@router.post(
    "/profile-picture",
    response_model=ProfilePictureResponse,
)
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    return await service.upload_profile_picture(
        current_user,
        file,
    )


@router.delete(
    "/profile-picture",
    response_model=ProfilePictureResponse,
)
def remove_profile_picture(
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    return service.remove_profile_picture(current_user)

@router.patch(
    "/users/{user_id}/role",
    response_model=UserResponse,
    dependencies=[Depends(get_current_admin)],
)
def update_user_role(
    user_id: int,
    data: UpdateUserRole,
    service:ProfileService = Depends(get_profile_service),
):
    return service.update_user_role(
        user_id,
        data,
    )

@router.get(
    "/users/{user_id}",
    response_model=UserDto,
    dependencies=[Depends(get_current_admin)],
)
def get_user_by_id(
    user_id: int,
    service: ProfileService = Depends(get_profile_service),
):
    return service.get_user_by_id(user_id)