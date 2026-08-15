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

    def get_by_ids(self, module_ids: list[int]) -> list[Module]:
        return self.session.exec(
            select(Module).where(Module.id.in_(module_ids))
        ).all()

    def update(self, module: Module) -> Module:
        self.session.add(module)
        self.session.commit()
        self.session.refresh(module)
        return module

    def delete(self, module: Module) -> None:
        self.session.delete(module)
        self.session.commit()

    def bulk_update_order(self, modules: list[Module]) -> list[Module]:
        for module in modules:
            self.session.add(module)
        self.session.commit()
        for module in modules:
            self.session.refresh(module)
        return modules