from datetime import datetime, timezone
from sqlmodel import Session, select

from .model import Module


class ModuleRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, module: Module) -> Module:
        self.session.add(module)
        self.session.commit()
        self.session.refresh(module)
        return module


    def get_by_id(self, module_id: int) -> Module | None:
        return self.session.get(Module, module_id)


    def get_active_by_id(self, module_id: int) -> Module | None:
        statement = select(Module).where(
            Module.id == module_id,
            Module.is_active == True,
        )

        return self.session.exec(statement).first()

    def get_by_course_id(
        self,
        course_id: int,
        include_inactive: bool = False,
    ) -> list[Module]:

        statement = select(Module).where(
            Module.course_id == course_id
        )

        if not include_inactive:
            statement = statement.where(Module.is_active == True)

        statement = statement.order_by(Module.order)

        return list(self.session.exec(statement))

        
    def get_by_ids(self, module_ids: list[int]) -> list[Module]:
        if not module_ids:
            return []

        statement = select(Module).where(
            Module.id.in_(module_ids)
        )

        return list(self.session.exec(statement))


    def update(self, module: Module) -> Module:
        self.session.add(module)
        self.session.commit()
        self.session.refresh(module)
        return module


    def deactivate(self, module: Module) -> Module:
        module.is_active = False
        module.updated_at = datetime.now(timezone.utc)

        self.session.add(module)
        self.session.commit()
        self.session.refresh(module)

        return module

    def bulk_update_order(self, modules: list[Module]) -> list[Module]:
        for module in modules:
            self.session.add(module)
        self.session.commit()
        
        for module in modules:
            self.session.refresh(module)
        return modules