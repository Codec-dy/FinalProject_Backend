import math
import uuid
from datetime import datetime
from statistics import median

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.databaseConnection import get_db
from app.models.telemetry import Telemetry
from app.models.driving_session import DrivingSession
from app.models.session_summary import SessionSummary


# These are the numeric sensor fields in your Telemetry model.
SENSOR_FIELDS = [
    "rpm",
    "speed",
    "coolant_temperature",
    "intake_air_temperature",
    "engine_load",
    "throttle_position",
    "mass_air_flow",
    "map_pressure",
    "fuel_level",
    "fuel_pressure",
    "timing_advance",
    "control_module_voltage",
    "short_trim",
    "hybrid_battery_life",
]

SENSOR_UNITS = {
    "rpm": "rpm",
    "speed": "mph",
    "coolant_temperature": "°C",
    "intake_air_temperature": "°C",
    "engine_load": "%",
    "throttle_position": "%",
    "mass_air_flow": "g/s",
    "map_pressure": "kPa",
    "fuel_level": "%",
    "fuel_pressure": "kPa",
    "timing_advance": "degrees",
    "control_module_voltage": "V",
    "short_trim": "%",
    "hybrid_battery_life": "%",
}

def is_valid_number(value):
    """Return True for finite numeric values."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def calculate_sensor_statistics(readings):
    """
    Calculate descriptive statistics for a list of sensor readings.
    Ignore null, non-numeric, and non-finite values.
    """
    values = [value for value in readings if is_valid_number(value)]

    if not values:
        return {
            "count": 0,
            "minimum": None,
            "maximum": None,
            "average": None,
            "first": None,
            "last": None,
        }

    return {
        "count": len(values),
        "minimum": round(min(values), 2),
        "maximum": round(max(values), 2),
        "average": round(sum(values) / len(values), 2),
        "first": round(values[0], 2),
        "last": round(values[-1], 2),
    }


from typing import Any

def sample_telemetry(
    telemetry_records: list[Telemetry],
    max_samples: int = 30,
    event_samples_per_sensor: int = 2,
) -> list[dict[str, Any]]:
    """
    Select representative telemetry samples and readings associated
    with unusually high or low sensor values.

    Args:
        telemetry_records: Telemetry records ordered by timestamp.
        max_samples: Target maximum number of samples.
        event_samples_per_sensor: Number of lowest and highest readings
            to consider for each numeric sensor.

    Returns:
        A chronological list of serialized telemetry samples.
    """

    if not telemetry_records:
        return []

    # Exclude database identifiers and relationship objects.
    sensor_fields = [
        "rpm",
        "speed",
        "coolant_temperature",
        "intake_air_temperature",
        "engine_load",
        "throttle_position",
        "mass_air_flow",
        "map_pressure",
        "fuel_level",
        "fuel_pressure",
        "timing_advance",
        "control_module_voltage",
        "short_trim",
        "hybrid_battery_life",
    ]

    total_records = len(telemetry_records)

    # Keep all readings if the session is already small enough.
    if total_records <= max_samples:
        selected_indices = set(range(total_records))
    else:
        selected_indices = set()

        # 1. Select evenly distributed samples across the session.
        evenly_spaced_count = max_samples

        for i in range(evenly_spaced_count):
            index = round(
                i * (total_records - 1) / (evenly_spaced_count - 1)
            )
            selected_indices.add(index)

    # 2. Select potentially important low/high readings.
    # These are candidates for review, not automatic fault indicators.
    for field in sensor_fields:
        valid_records = []

        for index, record in enumerate(telemetry_records):
            value = getattr(record, field, None)

            if isinstance(value, (int, float)) and not isinstance(value, bool):
                # Exclude NaN and infinity.
                import math

                if math.isfinite(value):
                    valid_records.append((index, value))

        if not valid_records:
            continue

        lowest = sorted(valid_records, key=lambda item: item[1])
        highest = sorted(valid_records, key=lambda item: item[1], reverse=True)

        for index, _ in lowest[:event_samples_per_sensor]:
            selected_indices.add(index)

        for index, _ in highest[:event_samples_per_sensor]:
            selected_indices.add(index)

    # 3. Serialize selected records chronologically.
    sampled_records = []

    for index in sorted(selected_indices):
        record = telemetry_records[index]

        sample = {
            "timestamp": (
                record.timestamp.isoformat()
                if record.timestamp is not None
                else None
            ),
        }

        for field in sensor_fields:
            value = getattr(record, field, None)

            # Convert database numeric values to ordinary Python numbers.
            # Preserve missing readings as null.
            if value is None:
                sample[field] = None
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                import math

                sample[field] = (
                    value if math.isfinite(value) else None
                )
            else:
                sample[field] = value

        sampled_records.append(sample)

    return sampled_records



def build_session_summary(
    db: Session,
    driving_session_id: uuid.UUID,
):
    """
    Calculate and save a summary for one driving session.

    Sensors with no valid readings across the entire session are excluded
    from telemetry_summary and the data-quality percentage denominator.

    Args:
        db: An active SQLAlchemy database session.
        driving_session_id: UUID of the driving session.

    Returns:
        The SessionSummary object. The caller is responsible for committing.

    Raises:
        ValueError: If the driving session or its telemetry does not exist.
    """

    # 1. Retrieve the driving session.
    driving_session = db.get(DrivingSession, driving_session_id)

    if driving_session is None:
        raise ValueError(
            f"Driving session {driving_session_id} was not found."
        )

    # 2. Retrieve telemetry in timestamp order.
    statement = (
        select(Telemetry)
        .where(Telemetry.driving_session_id == driving_session_id)
        .order_by(Telemetry.timestamp.asc(), Telemetry.id.asc())
    )

    telemetry_records = list(db.scalars(statement).all())

    if not telemetry_records:
        raise ValueError(
            "Cannot create a session summary because no telemetry "
            "records were found for this session."
        )

    telemetry_samples = sample_telemetry(
    telemetry_records=telemetry_records,
    max_samples=30,
    event_samples_per_sensor=2,
    )
    # 3. Calculate the session's time range.
    timestamps = [
        record.timestamp
        for record in telemetry_records
        if record.timestamp is not None
    ]

    timestamps.sort()

    first_timestamp = timestamps[0] if timestamps else None
    last_timestamp = timestamps[-1] if timestamps else None

    # Prefer the session's recorded start and end times when available.
    start_time = driving_session.start_time or first_timestamp
    end_time = driving_session.end_time or last_timestamp

    duration_seconds = None

    if start_time is not None and end_time is not None:
        duration_seconds = max(
            0.0,
            (end_time - start_time).total_seconds(),
        )

    # 4. Calculate sensor statistics.
    # Exclude sensors with zero valid readings across the entire session.
    telemetry_summary = {}
    available_sensor_fields = []

    for field in SENSOR_FIELDS:
        readings = [
            getattr(record, field)
            for record in telemetry_records
            if is_valid_number(getattr(record, field))
        ]

        # If every sample is missing or invalid, omit this sensor.
        if not readings:
            continue

        field_summary = calculate_sensor_statistics(readings)

    # Attach the corresponding unit to each sensor summary.
        field_summary["units"] = SENSOR_UNITS.get(field, "unknown")

        telemetry_summary[field] = field_summary
        available_sensor_fields.append(field)

    # 5. Calculate speed metrics.
    # Values remain in the units stored in your database.
    valid_speeds = [
        record.speed
        for record in telemetry_records
        if is_valid_number(record.speed)
        and record.speed >= 0
    ]

    moving_speeds = [
        speed for speed in valid_speeds if speed > 0
    ]

    average_speed = (
        sum(valid_speeds) / len(valid_speeds)
        if valid_speeds
        else None
    )

    average_moving_speed = (
        sum(moving_speeds) / len(moving_speeds)
        if moving_speeds
        else None
    )

    maximum_speed = (
        max(valid_speeds)
        if valid_speeds
        else None
    )

    # 6. Measure missing sensor values.
    missing_values_by_field = {}
    available_sensor_value_count = 0
    total_missing_values = 0

    for field in SENSOR_FIELDS:
        valid_count = sum(
            1
            for record in telemetry_records
            if is_valid_number(getattr(record, field))
        )

        missing_count = len(telemetry_records) - valid_count

        missing_values_by_field[field] = missing_count

        # Only include sensors that provided at least one valid reading
        # in the data-quality percentage denominator.
        if valid_count > 0:
            available_sensor_value_count += len(telemetry_records)
            total_missing_values += missing_count

    # Count expected values only for sensors that provided data.
    total_sensor_values = available_sensor_value_count

    # 7. Examine timestamp intervals.
    intervals = []

    for previous, current in zip(timestamps, timestamps[1:]):
        interval_seconds = (
            current - previous
        ).total_seconds()

        if interval_seconds >= 0:
            intervals.append(interval_seconds)

    data_quality = {
        "total_samples": len(telemetry_records),
        "samples_with_timestamp": len(timestamps),
        "samples_without_timestamp": (
            len(telemetry_records) - len(timestamps)
        ),
        "available_sensors": available_sensor_fields,
        "unavailable_sensors": [
            field
            for field in SENSOR_FIELDS
            if field not in available_sensor_fields
        ],
        "total_expected_sensor_values": total_sensor_values,
        "total_missing_sensor_values": total_missing_values,
        "missing_values_by_field": missing_values_by_field,
        "missing_value_percentage": (
            round(
                total_missing_values / total_sensor_values * 100,
                2,
            )
            if total_sensor_values
            else 0
        ),
        "median_sample_interval_seconds": (
            round(median(intervals), 2)
            if intervals
            else None
        ),
        "maximum_sample_interval_seconds": (
            round(max(intervals), 2)
            if intervals
            else None
        ),
    }

    # 8. Add session-level context to the summary JSON.
    telemetry_summary["session"] = {
        "start_time": (
            start_time.isoformat()
            if start_time is not None
            else None
        ),
        "end_time": (
            end_time.isoformat()
            if end_time is not None
            else None
        ),
        "duration_seconds": (
            round(duration_seconds, 2)
            if duration_seconds is not None
            else None
        ),
        "speed_unit": "mph",
    }

    # 9. Create or update the existing summary.
    existing_summary_statement = select(SessionSummary).where(
        SessionSummary.driving_session_id == driving_session_id
    )


    summary = db.scalars(
        existing_summary_statement
    ).first()

    if summary is None:
        summary = SessionSummary(
            driving_session_id=driving_session_id,
        )
        db.add(summary)

    summary.duration_seconds = duration_seconds
    summary.distance = None  # Calculate after confirming speed units.

    summary.average_speed = (
        round(average_speed, 2)
        if average_speed is not None
        else None
    )

    summary.average_moving_speed = (
        round(average_moving_speed, 2)
        if average_moving_speed is not None
        else None
    )

    summary.maximum_speed = (
        round(maximum_speed, 2)
        if maximum_speed is not None
        else None
    )

    summary.total_samples = len(telemetry_records)
    summary.telemetry_summary = telemetry_summary
    summary.data_quality = data_quality
    summary.vehicle_id = telemetry_records[0].vehicle_id
    summary.samples = telemetry_samples
    # The caller is responsible for committing the transaction.
    return summary
