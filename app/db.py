import os
from sqlmodel import SQLModel, create_engine, Session

# Support both local SQLite and Railway PostgreSQL
database_url = os.getenv("DATABASE_URL", "sqlite:///./jewelry.db")

# Railway provides postgres://, but SQLAlchemy 2.0+ requires postgresql://
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(database_url, echo=False)

def init_db() -> None:
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
