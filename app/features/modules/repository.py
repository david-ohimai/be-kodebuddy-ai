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