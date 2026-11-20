import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from ..database.base import Base


class VehicleHealthAssessment(Base):
    __tablename__ = "vehicle_health_assessments"
    __table_args__ = (
        CheckConstraint(
            "overall_status IN "
            "('good', 'monitor', 'investigation_recommended', "
            "'urgent_attention', 'insufficient_data')",
            name="ck_vehicle_health_assessments_overall_status",
        ),
        CheckConstraint(
            "data_quality IN ('good', 'moderate', 'limited', 'poor')",
            name="ck_vehicle_health_assessments_data_quality",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id"),
        nullable=False,
        index=True,
    )
    driving_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("driving_sessions.id"),
        nullable=False,
        index=True,
    )
    overall_status: Mapped[str] = mapped_column(String(30), nullable=False)
    overall_summary: Mapped[str] = mapped_column(Text, nullable=False)
    data_quality: Mapped[str | None] = mapped_column(String(20), nullable=True)
    missing_value_percentage: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    analysis_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    analysis_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    vehicle: Mapped["Vehicle"] = relationship(
        back_populates="health_assessments",
    )
    driving_session: Mapped["DrivingSession"] = relationship(
        back_populates="health_assessments",
    )
    system_assessments: Mapped[list["SystemHealthAssessment"]] = relationship(
        back_populates="assessment",
        cascade="all, delete-orphan",
    )


class SystemHealthAssessment(Base):
    __tablename__ = "system_health_assessments"
    __table_args__ = (
        CheckConstraint(
            "system IN "
            "('engine', 'transmission', 'brake_system', '12v_battery', "
            "'coolant_system')",
            name="ck_system_health_assessments_system",
        ),
        CheckConstraint(
            "status IN "
            "('good', 'monitor', 'investigation_recommended', "
            "'urgent_attention', 'insufficient_data')",
            name="ck_system_health_assessments_status",
        ),
        CheckConstraint(
            "jsonb_typeof(supporting_evidence) = 'array'",
            name="ck_system_health_assessments_evidence_array",
        ),
        CheckConstraint(
            "jsonb_typeof(limitations) = 'array'",
            name="ck_system_health_assessments_limitations_array",
        ),
        UniqueConstraint(
            "assessment_id",
            "system",
            name="uq_system_health_assessments_assessment_system",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicle_health_assessments.id"),
        nullable=False,
        index=True,
    )
    system: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_evidence: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        server_default=text("'[]'::jsonb"),
        nullable=False,
    )
    limitations: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        server_default=text("'[]'::jsonb"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    assessment: Mapped[VehicleHealthAssessment] = relationship(
        back_populates="system_assessments",
    )
    findings: Mapped[list["VehicleHealthFinding"]] = relationship(
        back_populates="system_assessment",
        cascade="all, delete-orphan",
    )


class VehicleHealthFinding(Base):
    __tablename__ = "vehicle_health_findings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    system_assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("system_health_assessments.id"),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    observed_evidence: Mapped[str] = mapped_column(Text, nullable=False)
    interpretation: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    recommended_actions: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        server_default=text("'[]'::jsonb"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    system_assessment: Mapped[SystemHealthAssessment] = relationship(
        back_populates="findings",
    )
