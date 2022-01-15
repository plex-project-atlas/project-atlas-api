from typing   import List, Optional
from pydantic import BaseModel
from datetime import datetime


class Request(BaseModel):
    id:           int
    request_date: datetime
    media_id:     int
    owner_id:     int
    owner_notes:  str
    admin_notes:  str = ""
    status:       str = "WIP"

    class Config:
        orm_mode = True


class User(BaseModel):
    id:        int
    google_id: int
    email:     str
    name:      str  = ""
    surname:   str  = ""
    is_active: bool = True
    requests:  List[Request] = []

    class Config:
        orm_mode = True
