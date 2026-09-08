from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from app.features.resources.model import ResourceType


class ResourceCreate(BaseModel):
    title: str = Field(
        min_length=2,
        max_length=255,
    )

    description: str | None = None

    type: ResourceType

    url: str | None = None

    content: str | None = None

    # --- File upload fields ---
    # Must be declared here (not just set via model_copy) so that
    # model_dump() in ResourceRepository.create() actually includes them
    # when building the Resource row. Without these, file_path/file_name/
    # mime_type set in BaseResourceService.prepare_create_data() are
    # silently dropped, and content_extraction.py never finds the file
    # to parse for embeddings.
    file_path: str | None = None
    file_name: str | None = None
    mime_type: str | None = None


class ResourceUpdate(BaseModel):
    title: str | None = Field(
        default=None,
        min_length=2,
        max_length=255,
    )

    description: str | None = None
    type: ResourceType | None = Field(default=None)
    url: str | None = None
    content: str | None = None
    is_active: bool | None = None

    # --- File upload fields ---
    # Same reasoning as ResourceCreate above: must be declared so
    # ResourceRepository.update()'s model_dump(exclude_unset=True) picks
    # them up when BaseResourceService.update_resource() sets them via
    # model_copy(update={...}).
    file_path: str | None = None
    file_name: str | None = None
    mime_type: str | None = None


class ResourceResponse(BaseModel):
    id: int
    module_id: int
    lesson_id: int | None
    title: str
    description: str | None
    type: ResourceType
    url: str | None
    content: str | None

    # --- File upload fields (from Version B) ---
    file_name: str | None = None
    mime_type: str | None = None

    # --- Extraction status fields (from Version B) ---
    content_extract_status: str | None = None
    content_extract_error: str | None = None

    created_by: int
    created_at: datetime
    updated_at: datetime
    is_active: bool

    model_config = ConfigDict(
        from_attributes=True
    )