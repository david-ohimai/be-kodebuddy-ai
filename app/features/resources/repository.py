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
        created_by: int,
    ) -> Resource:

        resource = Resource(
            module_id=resource_data.module_id,
            title=resource_data.title,
            description=resource_data.description,
            type=resource_data.type,
            url=resource_data.url,
            created_by=created_by,
            is_active=True,
        )

        self.db.add(resource)
        self.db.commit()
        self.db.refresh(resource)

        return resource

    def get_all(
        self,
        module_id: int | None = None,
    ) -> list[Resource]:

        statement = select(Resource).where(
            Resource.is_active == True
        )

        if module_id is not None:
            statement = statement.where(
                Resource.module_id == module_id
            )

        return list(self.db.exec(statement).all())

    def get_by_id(
        self,
        resource_id: int,
    ) -> Resource | None:

        statement = select(Resource).where(
            Resource.id == resource_id,
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