from .database      import BaseModel
from sqlalchemy     import Column, Boolean, DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship


class Request(BaseModel):
    __tablename__ = "requests"

    id            = Column(Integer,  primary_key = True, index = True)
    request_date  = Column(DateTime, nullable = False)
    media_id      = Column(String,   nullable = False)
    owner_id      = Column(Integer,  ForeignKey("users.id"))
    owner_notes   = Column(Text,     nullable = True)
    admin_notes   = Column(Text,     nullable = True)
    status        = Column(String,   nullable = False, default = 'WIP')

    owner         = relationship("Users", back_populates = "requests")


class User(BaseModel):
    __tablename__ = "users"

    id            = Column(Integer, primary_key = True, index = True)
    google_id     = Column(Integer, nullable = False)
    email         = Column(String,  nullable = False)
    name          = Column(String,  nullable = True)
    surname       = Column(String,  nullable = True)
    is_active     = Column(Boolean, nullable = False, default = True)

    requests      = relationship("Requests", back_populates = "owner")
