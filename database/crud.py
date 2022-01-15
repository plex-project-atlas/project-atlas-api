from sqlalchemy.orm import Session
from .              import models, schemas


def get_users(db: Session, skip: int = 0, limit: int = 1000):
    return db.query(models.User).offset(skip).limit(limit).all()


def get_user_by_google_id(db: Session, google_id: int):
    return db.query(models.User).filter(models.User.google_id == google_id).first()


def create_user(db: Session, user: schemas.User):
    db_user = models.User( **user.dict() )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def get_requestss(db: Session, skip: int = 0, limit: int = 1000):
    return db.query(models.Request).offset(skip).limit(limit).all()


def create_request(db: Session, request: schemas.Request, user_id: int):
    db_item = models.Request(**request.dict(), owner_id = user_id)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item
