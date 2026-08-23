from datetime import datetime

from pydantic import BaseModel

from .model import ChatRole


class ConversationTurnResponse(BaseModel):
    id: int
    role: ChatRole
    message: str
    course_id: int
    module_id: int | None
    created_at: datetime

    class Config:
        from_attributes = True


class HistoryResponse(BaseModel):
    turns: list[ConversationTurnResponse]
    total: int
    limit: int
    offset: int
