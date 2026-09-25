import uuid

from sqlalchemy import Float, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID

from .telemetry import Telemetry

from ..database.base import Base


class DrivingSession(Base):
    
    __tablename__ = "driving_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id")
    )

    start_time: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    end_time: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    telemetry: Mapped[list["Telemetry"]] = relationship(
        "Telemetry", back_populates="driving_session"
    )