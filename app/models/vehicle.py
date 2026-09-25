import uuid

from sqlalchemy import String, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID

from ..database.base import Base


class Vehicle(Base):

    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id")
    )

    vin: Mapped[str] = mapped_column(
        String(17),
        unique=True
    )

    make: Mapped[str] = mapped_column(String(50))

    model: Mapped[str] = mapped_column(String(50))

    year: Mapped[int] = mapped_column(Integer)

    engine: Mapped[str] = mapped_column(String(50))

    fuel_type: Mapped[str] = mapped_column(String(30))

    mileage: Mapped[int] = mapped_column(Integer)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    owner = relationship(
        "User",
        back_populates="vehicles"
    )

    telemetry = relationship(
        "Telemetry",
        back_populates="vehicle"
    )

    diagnostics = relationship(
        "Diagnostics",
        back_populates="vehicle"
    )

    # maintenance_records = relationship(
    #     "Maintenance",
    #     back_populates="vehicle"
    # )

    # health_reports = relationship(
    #     "HealthReport",
    #     back_populates="vehicle"
    # )

    # ai_reports = relationship(
    #     "AIReport",
    #     back_populates="vehicle"
    # )

    # alerts = relationship(
    #     "Alert",
    #     back_populates="vehicle"
    # )

    # sessions = relationship(
    #     "DrivingSession",
    #     back_populates="vehicle"
    # )