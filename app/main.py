from datetime import datetime, date, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4
from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from .database import Event, SessionLocal, init_db

app = FastAPI(title="VisionTime AI", version="0.1.0")

class EventIn(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    camera_id: str
    track_id: str
    direction: Literal["IN", "OUT"]
    occurred_at: datetime

def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
def startup():
    init_db()

@app.get("/")
def dashboard():
    return FileResponse(Path(__file__).parent / "static" / "index.html")

@app.post("/api/events", status_code=201)
def add_event(payload: EventIn, db: Session = Depends(db_session)):
    if db.scalar(select(Event).where(Event.event_id == payload.event_id)):
        return {"ok": True, "duplicate": True, "event_id": payload.event_id}
    when = payload.occurred_at if payload.occurred_at.tzinfo else payload.occurred_at.replace(tzinfo=timezone.utc)
    db.add(Event(event_id=payload.event_id, camera_id=payload.camera_id, track_id=payload.track_id,
                 direction=payload.direction, occurred_at=when))
    db.commit()
    return {"ok": True, "event_id": payload.event_id}

@app.get("/api/attendance")
def attendance(day: date | None = None, db: Session = Depends(db_session)):
    target = day or datetime.now().date()
    rows = [r for r in db.scalars(select(Event).order_by(Event.occurred_at)).all()
            if r.occurred_at.date() == target]
    active, records = {}, []
    for r in rows:
        key = (r.camera_id, r.track_id)
        if r.direction == "IN":
            active.setdefault(key, r)
        elif key in active:
            start = active.pop(key)
            seconds = max(0, int((r.occurred_at - start.occurred_at).total_seconds()))
            records.append({"camera_id": r.camera_id, "track_id": r.track_id,
                            "arrived_at": start.occurred_at.isoformat(), "left_at": r.occurred_at.isoformat(),
                            "duration_seconds": seconds})
    for start in active.values():
        records.append({"camera_id": start.camera_id, "track_id": start.track_id,
                        "arrived_at": start.occurred_at.isoformat(), "left_at": None, "duration_seconds": None})
    return {"date": target.isoformat(), "records": records}
