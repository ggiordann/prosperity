from __future__ import annotations

from pydantic import BaseModel, Field


class IdeaNode(BaseModel):
    strategy_id: str
    parent_ids: list[str] = Field(default_factory=list)
    family: str
    created_by_role: str
