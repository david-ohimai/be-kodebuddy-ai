from sqlmodel import Session
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

    def update(self, module: Module) -> Module:
        self.session.add(module)
        self.session.commit()
        self.session.refresh(module)
        return module

    def delete(self, module: Module) -> None:
        self.session.delete(module)
        self.session.commit()