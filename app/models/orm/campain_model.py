from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class Campaign(BaseModel):
    id: UUID
    name: str
    description: str
    start_date: datetime
    end_date: datetime
    created_at: datetime