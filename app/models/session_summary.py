
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class SessionSummary(Base):
    __tablename__ = "session_summaries"

    __table_args__ = (
        UniqueConstraint(
            "driving_session_id",
            name="uq_session_summaries_driving_session_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    driving_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("driving_sessions.id"),
        nullable=False,
    )
    
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id"),
        nullable=False,
    )

    duration_seconds: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    distance: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    average_speed: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    average_moving_speed: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    maximum_speed: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    total_samples: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    telemetry_summary: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    data_quality: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
