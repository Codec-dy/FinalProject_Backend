import uuid

from sqlalchemy import String, Text, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID

from ..database.base import Base


class Diagnostics(Base):

    __tablename__ = "diagnostic_codes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id")
    )
    title: Mapped[str] = mapped_column(Text)

    code: Mapped[str] = mapped_column(String(10))

    description: Mapped[str] = mapped_column(Text)

    severity: Mapped[str] = mapped_column(String(20))

    causes: Mapped[list[str]] = mapped_column(JSON, default=list)

    recommended: Mapped[str] = mapped_column(Text)

    cost_to_repair: Mapped[str] = mapped_column(Text)

    detected_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    cleared_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    vehicle = relationship(
        "Vehicle",
        back_populates="diagnostics"
    )