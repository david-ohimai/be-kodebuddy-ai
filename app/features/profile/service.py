from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.core.email import send_role_change_email
from app.features.auth.model import User, UserRole
from app.features.courses.repository import CourseRepository
from app.features.profile.schema import (
    CohortSummary,
    CourseSummary,
    ProfilePictureResponse,
    UpdateProfile,
    UpdateUserRole,
    UserDto,
    UserResponse,
)
from app.features.profile.repository import ProfileRepository

#profile 
PROFILE_PICTURE_DIR = Path("uploads/profile_pictures")

PROFILE_PICTURE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

class ProfileService:

    def __init__(self, repository: ProfileRepository, course_repository: CourseRepository):
        self.repository = repository
        self.course_repository = course_repository

    # USER DTO

    def _to_user_dto(
        self,
        user: User,
    ) -> UserDto:

        cohort = None 
        course = None

        cohorts: list[CohortSummary] = []
        courses: list[CourseSummary] = []

        # ---------------- LEARNER ----------------

        if user.role == UserRole.LEARNER: 
            cohort = self.repository.get_learner_cohort( user.id ) 
            course = self.repository.get_learner_course( user.id )

            if cohort:
                cohorts = [
                    CohortSummary(
                        id=cohort.id,
                        name=cohort.name,
                    )
                ]

            if course:
                courses = [
                    CourseSummary(
                        id=course.id,
                        title=course.title,
                    )
                ]

        # ---------------- TRAINER ----------------

        if user.role == UserRole.TRAINER:
            cohort = self.repository.get_trainer_cohort( user.id )
            course = self.repository.get_trainer_course( user.id )

            trainer_cohorts = self.repository.get_trainer_cohorts(
                user.id
            )

            cohorts = [
                CohortSummary(
                    id=item.id,
                    name=item.name,
                )
                for item in trainer_cohorts
            ]

            # New: return all trainer courses
            trainer_courses = self.repository.get_trainer_courses(
                user.id
            )

            courses = [
                CourseSummary(
                    id=item.id,
                    title=item.title,
                )
                for item in trainer_courses
            ]

        # ---------------- MENTOR ----------------

        elif user.role == UserRole.MENTOR:
            trainer_cohorts = self.repository.get_trainer_cohorts(
                user.id
            )

            cohorts = [
                CohortSummary(
                    id=item.id,
                    name=item.name,
                )
                for item in trainer_cohorts
            ]

            # New: return all trainer courses
            trainer_courses = self.repository.get_trainer_courses(
                user.id
            )

            courses = [
                CourseSummary(
                    id=item.id,
                    title=item.title,
                )
                for item in trainer_courses
            ] 

        return UserDto(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            profile_picture=user.profile_picture,

            cohort_id=cohort.id if cohort else None,
            cohort_name=cohort.name if cohort else None,

            course_id=course.id if course else None,
            course_name=course.title if course else None,

            cohorts=cohorts,
            courses=courses,
            
            created_at=user.created_at,
        )

    def get_all_users(self) -> list[UserDto]:

        users = self.repository.get_all()

        return [
            self._to_user_dto(user)
            for user in users
        ]


    def get_user_by_id(
        self,
        user_id: int,
    ) -> UserDto:

        user = self.repository.get_by_id(user_id)

        if user is None:
            raise HTTPException(
                status_code=404,
                detail="User not found",
            )

        return self._to_user_dto(user)

    def update_profile(
        self,
        user: User,
        profile_data: UpdateProfile,
    ) -> UserResponse:

        update_data = profile_data.model_dump(
            exclude_unset=True
        )

        for field, value in update_data.items():
            setattr(user, field, value)

        user.updated_at = datetime.now(timezone.utc)

        updated_user = self.repository.update(user)

        return UserResponse(
            message="Profile updated successfully",
            user=self._to_user_dto(updated_user),
        )

    # ------------ UPLOAD PROFILE PICTURE ------------

    async def upload_profile_picture(
        self,
        user: User,
        file: UploadFile,
    ) -> ProfilePictureResponse:

        # Check MIME type
        if (
            not file.content_type
            or not file.content_type.startswith("image/")
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only image files are allowed",
            )

        # Check extension
        extension = Path(file.filename or "").suffix.lower()

        allowed_extensions = {
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
            ".gif",
        }

        if extension not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported image format",
            )

        # Read file
        contents = await file.read()

        # Maximum size: 5MB
        if len(contents) > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Profile picture must not exceed 5MB",
            )

        # Delete old profile picture
        if user.profile_picture:

            old_path = Path(
                user.profile_picture.lstrip("/")
            )

            if old_path.exists():
                old_path.unlink()

        # Generate unique filename
        filename = (
            f"{uuid4().hex}{extension}"
        )

        file_path = (
            PROFILE_PICTURE_DIR / filename
        )

        # Save file
        file_path.write_bytes(contents)

        # Save URL/path in database
        user.profile_picture = (
            f"/uploads/profile_pictures/{filename}"
        )

        user.updated_at = datetime.now(timezone.utc)

        self.repository.update(user)

        return ProfilePictureResponse(
            message="Profile picture uploaded successfully",
            profile_picture=user.profile_picture,
        )

    # ------------ REMOVE PROFILE PICTURE ------------
    
    def remove_profile_picture(
        self,
        user: User,
    ) -> ProfilePictureResponse:

        if user.profile_picture:

            file_path = Path(
                user.profile_picture.lstrip("/")
            )

            if file_path.exists():
                file_path.unlink()

        user.profile_picture = None

        user.updated_at = datetime.now(timezone.utc)

        self.repository.update(user)

        return ProfilePictureResponse(
            message="Profile picture removed successfully",
            profile_picture=None,
        )

    def update_user_role(
        self,
        user_id: int,
        data: UpdateUserRole,
    ) -> UserResponse:

        user = self.repository.get_by_id(user_id)

        if user is None:
            raise HTTPException(
                status_code=404,
                detail="User not found",
            )
        
        
        old_role = user.role
        new_role = data.role

        # Admin roles cannot be changed
        if old_role == UserRole.ADMIN:
            raise HTTPException(
                status_code=403,
                detail="Admin role cannot be changed",
            )
        
        user.role = new_role
        user.updated_at = datetime.now(timezone.utc)

        updated_user = self.repository.update(user)

        # if old_role != new_role:
        #     await send_role_change_email(
        #         email=updated_user.email,
        #         full_name=updated_user.full_name,
        #         new_role=updated_user.role.value,
        #     )

        return UserResponse(
            message="User role updated successfully",
            user=self._to_user_dto(updated_user),
        )