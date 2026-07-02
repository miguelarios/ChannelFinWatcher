"""Database configuration and session management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import get_settings

settings = get_settings()

# Create SQLAlchemy engine
# timeout: how long a connection waits on a locked database before raising
# "database is locked". Matters now that request handlers run blocking work
# in threadpool threads and can genuinely overlap as concurrent writers.
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False, "timeout": 15} if "sqlite" in settings.database_url else {}
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)