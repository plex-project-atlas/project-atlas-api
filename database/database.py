import os

from sqlalchemy                 import create_engine
from sqlalchemy.orm             import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

DATABASE_URL = f"sqlite:///./data/{os.environ.get('DB_FILE', 'project-atlas.db')}"

db_engine = create_engine(
    DATABASE_URL,
    echo         = True,
    echo_pool    = True,
    encoding     = 'latin1',
    connect_args = {'check_same_thread': False}
)
SessionLocal = sessionmaker(autocommit = False, autoflush = False, bind = db_engine)
BaseModel    = declarative_base()
