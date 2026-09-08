from datetime import datetime, timezone

from sqlmodel import Session, select

from app.features.resources.model import Resource
from app.features.resources.schema import (
    ResourceCreate,
    ResourceUpdate,
)


class ResourceRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        resource_data: ResourceCreate,
        module_id: int,
        created_by: int,
        lesson_id: int | None = None,
    ) -> Resource:

        resource = Resource(
            **resource_data.model_dump(),
            module_id=module_id,
            created_by=created_by,
            lesson_id=lesson_id,
            is_active=True,
        )

        self.db.add(resource)
        self.db.commit()
        self.db.refresh(resource)

        return resource

    def get_all(
        self,
        module_id: int,
    ) -> list[Resource]:

        statement = select(Resource).where(
            Resource.module_id == module_id,
            Resource.lesson_id.is_(None),
            Resource.is_active == True,
        )

        return list(self.db.exec(statement).all())

    def get_by_id(
        self,
        resource_id: int,
        module_id: int,
    ) -> Resource | None:

        statement = select(Resource).where(
            Resource.id == resource_id,
            Resource.module_id == module_id,
            Resource.is_active == True,
        )

        return self.db.exec(statement).first()

    # LESSON RESOURCES

    def get_all_for_lesson(
        self,
        lesson_id: int,
    ) -> list[Resource]:

        statement = select(Resource).where(
            Resource.lesson_id == lesson_id,
            Resource.is_active == True,
        )

        return list(
            self.db.exec(statement).all()
        )

    def get_by_id_for_lesson(
        self,
        resource_id: int,
        lesson_id: int,
    ) -> Resource | None:

        statement = select(Resource).where(
            Resource.id == resource_id,
            Resource.lesson_id == lesson_id,
            Resource.is_active == True,
        )

        return self.db.exec(statement).first()

    def update(
        self,
        resource: Resource,
        resource_data: ResourceUpdate,
    ) -> Resource:

        update_data = resource_data.model_dump(
            exclude_unset=True
        )

        for key, value in update_data.items():
            setattr(resource, key, value)

        resource.updated_at = datetime.now(timezone.utc)

        self.db.add(resource)
        self.db.commit()
        self.db.refresh(resource)

        return resource

    def delete(
        self,
        resource: Resource,
    ) -> Resource:

        resource.is_active = False
        resource.updated_at = datetime.now(timezone.utc)

        self.db.add(resource)
        self.db.commit()
        self.db.refresh(resource)

        return resource