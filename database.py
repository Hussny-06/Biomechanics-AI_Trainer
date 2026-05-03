"""
Database Layer — SQLAlchemy ORM Models & Session Factory
Provides: User, Session, Set tables + get_db() helper.
DB File: sqlite:///./biomechanics_data.db (auto-created on first run)
"""
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime

DATABASE_URL = "sqlite:///./biomechanics_data.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- ORM MODELS ---

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    goal = Column(String, nullable=False)
    level = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    sessions = relationship("WorkoutSession", back_populates="user")


class WorkoutSession(Base):
    """One per 'Generate AI Plan' click."""
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    protocol_json = Column(Text, nullable=True)  # Raw LLM output
    
    user = relationship("User", back_populates="sessions")
    sets = relationship("WorkoutSet", back_populates="session")


class WorkoutSet(Base):
    """One per 'Next Exercise' click — the core performance data."""
    __tablename__ = "sets"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    exercise = Column(String, nullable=False)       # "Bicep Curls" / "Squats"
    target_reps = Column(Integer, nullable=False)    # What the AI prescribed
    completed_reps = Column(Integer, nullable=False) # What the FSM counted
    completed_at = Column(DateTime, default=datetime.utcnow)
    
    session = relationship("WorkoutSession", back_populates="sets")


# --- Create all tables on import ---
Base.metadata.create_all(bind=engine)


def get_db():
    """Yields a database session. Use in a `with` block or dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
