import os
import uuid
from fastapi import HTTPException, UploadFile, status
from app.features.auth.model import User, UserRole
from app.features.resources.model import (
    Resource,
    ResourceType,
)
from app.features.resources.repository import ResourceRepository
from app.features.resources.schema import (
    ResourceCreate,
    ResourceUpdate,
)


class BaseResourceService:

    def __init__(
        self,
        repository: ResourceRepository,
    ):
        self.repository = repository

     # ============ PERMISSIONS ============ 

    def check_can_create(
        self,
        current_user: User,
    ) -> None:

        if current_user.role not in {
            UserRole.ADMIN,
            UserRole.TRAINER,
        }:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins and trainers can create resources",
            )

    def check_can_manage(
        self,
        resource: Resource,
        current_user: User,
    ) -> None:

        if current_user.role == UserRole.ADMIN:
            return

        if (
            current_user.role == UserRole.TRAINER
            and resource.created_by == current_user.id
        ):
            return

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this resource",
        )

    # ============ VALIDATION ============ 

    def validate_resource_data(
        self,
        resource_type: ResourceType,
        url: str | None,
        content: str | None,
        file: UploadFile | None,
    ) -> None:

        if resource_type == ResourceType.FILE:

            if file is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A file is required for file resources",
                )

            return

        if resource_type == ResourceType.LINK:

            if not url:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A URL is required for link resources",
                )
            
            return

        if resource_type == ResourceType.ARTICLE:

            if not content:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Content is required for article resources",
                )

            return

    # ============  CREATE DATA  ============ 

    def prepare_create_data(
        self,
        data: ResourceCreate,
        file: UploadFile | None,
    ) -> ResourceCreate:

        if data.type == ResourceType.FILE:

            file_url = self.save_file(file)

            return data.model_copy(
                update={
                    "url": file_url,
                    "content": None,
                }
            )

        if data.type == ResourceType.LINK:
            return data.model_copy(update={"content": None,})

        if data.type == ResourceType.ARTICLE:
            return data.model_copy(update={"url": None,})

        return data

    # ============  UPDATE ============ 

    def update_resource(
        self,
        resource: Resource,
        data: ResourceUpdate,
        current_user: User,
        file: UploadFile | None = None,
    ) -> Resource:

        self.check_can_manage(
            resource,
            current_user,
        )

        resource_type = (
            data.type
            if data.type is not None
            else resource.type
        )

        # FILE
        if resource_type == ResourceType.FILE:

            # Converting another type to FILE requires an actual uploaded file.
            if (
                resource.type != ResourceType.FILE
                and file is None
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail= "A new file is required when changing a resource to file type"
                )

            if file is not None:

                old_file_url = resource.url
                new_file_url = self.save_file(file)

                data = data.model_copy(
                    update={
                        "type": ResourceType.FILE,
                        "url": new_file_url,
                        "content": None,
                    }
                )

                updated_resource = self.repository.update(
                    resource,
                    data,
                )

                self.delete_file(old_file_url)

                return updated_resource

            if not resource.url:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A file is required for this file resource"
                )

            data = data.model_copy(
                update={
                    "type": ResourceType.FILE,
                    "url": resource.url,
                    "content": None,
                }
            )

        # LINK
        elif resource_type == ResourceType.LINK:

            url = (
                data.url
                if data.url is not None
                else resource.url
            )

            if not url:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A URL is required for link resources",
                )

            old_file_url = None

            if (
                resource.type == ResourceType.FILE
                and resource.url
            ):
                old_file_url = resource.url

            data = data.model_copy(
                update={
                    "type": ResourceType.LINK,
                    "url": url,
                    "content": None,
                }
            )

            updated_resource = self.repository.update(
                resource,
                data,
            )

            self.delete_file(old_file_url)

            return updated_resource

        # ARTICLE
        elif resource_type == ResourceType.ARTICLE:

            content = (
                data.content
                if data.content is not None
                else resource.content
            )

            if not content:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Content is required for article resources",
                )

            old_file_url = None

            if (
                resource.type == ResourceType.FILE
                and resource.url
            ):
                old_file_url = resource.url

            data = data.model_copy(
                update={
                    "type": ResourceType.ARTICLE,
                    "url": None,
                    "content": content,
                }
            )

            updated_resource = self.repository.update(
                resource,
                data,
            )

            self.delete_file(old_file_url)

            return updated_resource

        return self.repository.update(
            resource,
            data,
        )

    # FILE STORAGE
    def save_file(
        self,
        file: UploadFile | None,
    ) -> str:

        if file is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided",
            )

        upload_directory = "uploads/resources"
        os.makedirs(upload_directory, exist_ok=True,)

        extension = ""

        if file.filename and "." in file.filename:
            extension = (
                "."
                + file.filename.rsplit(
                    ".",
                    1,
                )[1]
            )

        filename = (
            f"{uuid.uuid4()}{extension}"
        )

        file_path = os.path.join(upload_directory, filename,)

        try:
            with open(file_path, "wb",) as buffer:
                while True:
                    chunk = file.file.read(
                        1024 * 1024
                    )

                    if not chunk:
                        break

                    buffer.write(chunk)

        except Exception:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save uploaded file",
            )

        return f"/uploads/resources/{filename}"

    def delete_file(
        self,
        file_url: str | None,
    ) -> None:

        if not file_url:
            return

        file_path = os.path.join(
            os.getcwd(),
            file_url.lstrip("/"),
        )

        if os.path.exists(file_path):
            try:
                os.remove(file_path)

            except OSError:
                pass