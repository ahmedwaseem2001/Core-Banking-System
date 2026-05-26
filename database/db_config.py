
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite:///core_banking.db"

# For SQLite, 'connect_args' is required to avoid thread errors
engine = create_engine(
    DATABASE_URL,
    echo=False, 
    connect_args={"check_same_thread": False}
)

# Base class for ORM models
Base = declarative_base()

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Dependency for getting DB session in routes
def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Creates all tables from models
def create_tables():
    Base.metadata.create_all(bind=engine)
