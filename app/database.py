from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine, String, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DATA = Path(__file__).resolve().parents[1] / "data"
DATA.mkdir(exist_ok=True)
engine = create_engine(f"sqlite:///{DATA / 'visiontime.db'}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    camera_id: Mapped[str] = mapped_column(String(80), index=True)
    track_id: Mapped[str] = mapped_column(String(80), index=True)
    direction: Mapped[str] = mapped_column(String(3))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

def init_db():
    Base.metadata.create_all(engine)
