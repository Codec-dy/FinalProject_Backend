import uuid
from typing import Optional

from sqlalchemy import Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID

from ..database.base import Base


class Telemetry(Base):

    __tablename__ = "telemetry"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    vehicle_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id"),
    )

    timestamp: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    driving_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("driving_sessions.id"),
        nullable=True
    )

    rpm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    speed: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    coolant_temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    intake_air_temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    engine_load: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    throttle_position: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    mass_air_flow: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    map_pressure: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    fuel_level: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    fuel_pressure: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    timing_advance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    control_module_voltage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    short_trim: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    hybrid_battery_life: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    vehicle = relationship(
        "Vehicle",
        back_populates="telemetry"
    )

    driving_session = relationship(
        "DrivingSession",
        back_populates="telemetry"
    )