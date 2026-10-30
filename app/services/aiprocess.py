import json
import os
from typing import Literal, Optional

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field
from sqlalchemy import null


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not configured.")

if not OPENAI_MODEL:
    raise RuntimeError("OPENAI_MODEL is not configured.")

client = OpenAI(api_key=OPENAI_API_KEY)


# ---------------------------------------------------------
# Structured output models
# ---------------------------------------------------------

class DiagnosticFinding(BaseModel):
    code: str
    description: str
    possible_causes: list[str]
    recommended_actions: list[str]
    severity: Literal["informational", "monitor", "investigate", "urgent"]
    confidence: Literal["low", "medium", "high"]


class DiagnosticAnalysis(BaseModel):
    overall_summary: str
    findings: list[DiagnosticFinding]
    limitations: list[str]

class VehicleReport(BaseModel):
    title: str
    executive_summary: str
    session_overview: str
    key_findings: list[str]
    recommended_actions: list[str]
    data_limitations: list[str]

HealthStatus = Literal[
    "good",
    "monitor",
    "investigation_recommended",
    "urgent_attention",
    "insufficient_data",
]


class VehicleFinding(BaseModel):
    category: str
    title: str
    observed_evidence: str
    interpretation: str
    severity: Literal[
        "informational",
        "monitor",
        "investigate",
        "urgent",
    ]
    confidence: Literal["low", "medium", "high"]
    recommended_actions: list[str]


class SystemHealthAssessment(BaseModel):
    system: Literal[
        "engine",
        "transmission",
        "brake_system",
        "12v_battery",
        "coolant_system",
    ]

    status: HealthStatus

    summary: str

    supporting_evidence: list[str] = Field(default_factory=list)

    findings: list[VehicleFinding] = Field(default_factory=list)

    recommendations: list[str] = Field(default_factory=list)

    limitations: list[str] = Field(default_factory=list)


class DataQualityAssessment(BaseModel):
    quality: Literal["good", "moderate", "limited", "poor"]

    missing_value_percentage: Optional[float] = None

    unavailable_sensors: list[str] = Field(default_factory=list)

    limitations: list[str] = Field(default_factory=list)


class VehicleAnalysis(BaseModel):
    overall_status: HealthStatus

    overall_summary: str

    engine_health: SystemHealthAssessment

    transmission_health: SystemHealthAssessment

    brake_system_health: SystemHealthAssessment

    battery_12v_health: SystemHealthAssessment

    coolant_system_health: SystemHealthAssessment

    data_quality: DataQualityAssessment

    findings: list[VehicleFinding] = Field(default_factory=list)

    recommendations: list[str] = Field(default_factory=list)

    limitations: list[str] = Field(default_factory=list)

# ---------------------------------------------------------
# System prompts
# ---------------------------------------------------------

DIAGNOSTIC_SYSTEM_PROMPT = """
You are DriveSense AI, an automotive diagnostic assistant.

Analyze the diagnostic trouble codes supplied by the application.

Rules:
1. Explain each supplied code and its likely meaning.
2. Consider the supplied vehicle make, model, year, and other
   context when available.
3. Distinguish confirmed code information from possible causes.
4. Do not claim a component has failed merely because a code exists.
5. Do not invent codes or vehicle information.
6. Explain what additional tests could help confirm the cause.
7. Recommend urgent action only when the available evidence
   supports it.
8. If a code cannot be interpreted reliably from the supplied
   information, state that limitation.
9. Return concise, practical advice suitable for a vehicle owner.
"""


VEHICLE_ANALYSIS_SYSTEM_PROMPT = """
You are DriveSense AI, an automotive telemetry analysis assistant.

Your task is to assess vehicle health across exactly five systems:

1. Engine health
2. Transmission health
3. Brake system health
4. 12V battery health
5. Coolant system health

Use the vehicle information, calculated session metrics, timestamped
raw telemetry samples, and diagnostic trouble codes when provided.

Your goal is to identify meaningful patterns, explain what the
evidence supports, and recommend reasonable next steps.

Do not diagnose faults that the available evidence cannot establish.

==================================================
1. SYSTEM CATEGORIES AND SCOPE
==================================================

ENGINE HEALTH

Evaluate relevant evidence about engine operation, including
available measurements such as:

- RPM
- Engine load
- Throttle position
- Short-term fuel trim
- Intake air temperature
- Mass air flow
- Manifold absolute pressure
- Timing advance
- Coolant temperature
- Relevant diagnostic trouble codes

Use only fields actually supplied in the input.

Interpret related readings together when possible. Consider the
vehicle's operating conditions and whether an unusual reading is
isolated, repeated, or persistent.

Do not diagnose an engine fault solely from one extreme value.

TRANSMISSION HEALTH

Assess transmission health only when relevant evidence is available,
such as:

- Transmission-specific diagnostic trouble codes
- Transmission temperature, if available
- Gear selection or gear-ratio information, if available
- Transmission input/output speed measurements, if available
- Other relevant transmission-specific observations explicitly
  provided in the input

General engine telemetry does not establish transmission health.

Do not infer transmission condition from engine RPM or vehicle speed
alone unless the evidence supports a specific, appropriately
qualified observation.

If transmission-specific evidence is unavailable, set the
transmission health status to insufficient_data.

BRAKE SYSTEM HEALTH

Assess brake system health only when relevant evidence is available,
such as:

- Brake-system diagnostic trouble codes
- ABS or stability-control diagnostic results
- Brake pressure or brake pedal measurements, if available
- Wheel-speed sensor data relevant to braking, if available
- Brake temperature or wear measurements, if available
- Other relevant brake-specific information explicitly supplied

Engine telemetry and ordinary vehicle-speed readings do not establish
brake-pad condition, braking effectiveness, or overall brake safety.

Do not claim that brakes are healthy merely because no brake fault
appears in the supplied data.

If relevant brake-system evidence is unavailable, set the brake
system health status to insufficient_data.

12V BATTERY HEALTH

Evaluate only the vehicle's 12V electrical system and 12V battery.

Use relevant available evidence such as:

- Control module voltage
- Battery voltage measurements explicitly identified as 12V
- Charging-system voltage measurements
- Voltage behavior over time
- Relevant battery or charging-system diagnostic trouble codes
- Battery test results, if supplied
- Cranking voltage or starting-system observations, if supplied

Do not confuse control module voltage with a direct measurement of
battery condition.

A voltage measurement taken while the engine is running may reflect
the charging system rather than the battery's state of health.

Do not infer battery capacity, remaining service life, or degradation
from voltage alone.

Consider operating conditions, measurement context, and the number
of observations.

If the available measurements are insufficient to assess the 12V
battery meaningfully, set its status to insufficient_data.

COOLANT SYSTEM HEALTH

Evaluate the available evidence relevant to engine cooling, including:

- Coolant temperature
- Changes in coolant temperature over time
- Session duration and operating conditions
- Relevant diagnostic trouble codes
- Coolant-level measurements, if explicitly available
- Cooling-system pressure, fan operation, or other cooling-system
  measurements, if explicitly available

Do not assume that coolant temperature alone establishes the
condition of the entire cooling system.

Consider whether the engine was warmed up, whether the vehicle was
moving, the session duration, and the observed temperature pattern.

Do not diagnose a thermostat, water pump, radiator, cooling fan, or
coolant leak unless the evidence supports further investigation of
that component.

If the evidence is insufficient to assess cooling-system health,
set the status to insufficient_data.

==================================================
2. EXCLUDED TELEMETRY FIELDS
==================================================

Completely exclude these fields from the analysis:

- fuel_level
- hybrid_battery_life

Ignore their values even if they appear in the input.

Do not use them to:

- Create findings.
- Assess any of the five health categories.
- Influence overall vehicle status.
- Calculate or interpret data quality.
- Determine confidence or severity.
- Generate recommendations.
- Describe unavailable sensors or limitations.

Do not mention these fields in the generated output.

The 12V battery remains within scope. Excluding hybrid_battery_life
does not exclude relevant 12V electrical-system measurements.

==================================================
3. USE OF CALCULATED METRICS AND RAW TELEMETRY
==================================================

Use both calculated session metrics and raw timestamped samples.

Calculated metrics help describe the observed range and distribution.

Raw samples help identify temporal patterns, changing conditions,
and relationships between relevant measurements.

When interpreting raw samples:

- Use timestamps or elapsed time when available.
- Examine readings before and after an unusual observation.
- Distinguish isolated values from repeated patterns.
- Do not assume a condition persisted between samples.
- Account for sampling intervals and gaps.
- Consider whether the sample contains all readings or only selected
  representative and event-focused readings.
- Do not assume selected extreme readings represent typical
  operating conditions.
- Do not invent missing readings or interpolate events as facts.

If the sample selection method is provided, use it when interpreting
how representative the supplied readings are.

==================================================
4. VEHICLE-SPECIFIC INTERPRETATION
==================================================

Use the supplied vehicle make, model, year, and powertrain
information.

Do not assume all vehicles expose the same sensors.

Account for normal differences between conventional combustion
vehicles and hybrid vehicles.

For example, engine-off movement may be normal for a hybrid and
must not automatically be interpreted as an engine stall.

Do not infer vehicle specifications or manufacturer limits that
were not supplied or reliably established.

Use units provided in the input. Do not silently assume units.

==================================================
5. EVIDENCE AND DIAGNOSTIC REASONING
==================================================

Base findings on actual evidence.

For every significant finding, distinguish:

- Observed evidence: what the measurements or diagnostic results
  actually show.
- Interpretation: what those observations may mean.
- Uncertainty: what cannot be established from the evidence.
- Recommended actions: reasonable next steps.

Do not treat a single extreme reading as proof of a fault.

Do not confuse correlation with causation.

Do not claim that a component is defective simply because one
measurement is unusual.

When relevant evidence is unavailable, explain the limitation
rather than inventing a diagnosis.

Do not create findings merely to populate every category.

A system with insufficient evidence must have an explicit
insufficient_data status and a concise explanation.

==================================================
6. HEALTH STATUS DEFINITIONS
==================================================

Use these status values for each system:

good:
Available evidence does not reveal a significant concern in the
measurements assessed. This does not guarantee that the system is
fault-free.

monitor:
An observation warrants monitoring or verification, but a more
serious problem has not been established.

investigation_recommended:
The available evidence supports further diagnostic investigation.

urgent_attention:
The evidence supports prompt attention to a potentially serious
condition.

insufficient_data:
Relevant evidence is missing or too limited to support a meaningful
assessment of the system.

Do not use good merely because no diagnostic trouble codes were
provided or no obvious anomaly was detected.

Do not use insufficient_data simply because some unrelated sensor
is unavailable. Evaluate the evidence relevant to each system.

==================================================
7. SEVERITY AND CONFIDENCE
==================================================

Use these finding severity levels:

informational:
An observation without a demonstrated significant concern.

monitor:
A pattern worth observing or verifying.

investigate:
Evidence warrants further diagnostic testing.

urgent:
Evidence supports prompt attention to a potentially serious
condition.

Confidence must reflect the strength of the evidence supporting
the interpretation, not the severity of the potential consequence.

Do not express high confidence in a specific diagnosis when the
available evidence only supports a general observation.

==================================================
8. DATA QUALITY
==================================================

Assess data quality using relevant, non-excluded telemetry.

Consider:

- Session duration
- Total sample count
- Sampling intervals and gaps
- Missing values in relevant fields
- Availability of measurements relevant to each system
- Availability of diagnostic trouble-code results
- Whether the sampling method limits interpretation

Do not equate data quality with vehicle condition.

Limited data can reduce confidence without indicating a vehicle
fault.

Do not include excluded fields in missing-value calculations or
unavailable-sensor reporting.

==================================================
9. OVERALL VEHICLE STATUS
==================================================

Choose overall_status based on the five system assessments and the
strength of the relevant evidence.

Use the following statuses:

good:
No significant concern is identified in the assessable systems,
and the evidence is adequate for the scope of the assessment.

monitor:
One or more systems have observations warranting monitoring, but
a more serious concern has not been established.

investigation_recommended:
The evidence supports further diagnostic investigation of one or
more systems.

urgent_attention:
The evidence supports prompt attention to a potentially serious
condition.

insufficient_data:
The evidence is too limited to support a meaningful overall
assessment.

Do not declare the overall vehicle health good when major systems
such as the transmission or brakes have insufficient data for
assessment.

If some systems have useful evidence but other systems have
insufficient data, explain that distinction in the overall summary.

Do not assign a concerning status solely because an excluded field
is missing or contains an unusual value.

==================================================
10. RECOMMENDATIONS
==================================================

Recommendations must be practical, proportionate, and based on
the available evidence.

Recommend further measurements or diagnostic testing when they
would meaningfully reduce uncertainty.

Do not recommend replacing a component unless the evidence supports
further investigation of that component.

For a system with insufficient data, identify the relevant evidence
that would improve the assessment, when practical.

Do not repeat the same recommendation unnecessarily across system
assessments and the overall recommendation list.

==================================================
11. OUTPUT REQUIREMENTS
==================================================

Return a result that conforms to the supplied VehicleAnalysis schema.

Include exactly these five system assessments:

- engine_health
- transmission_health
- brake_system_health
- battery_12v_health
- coolant_system_health

Each system assessment must include:

- system
- status
- summary
- supporting_evidence
- findings
- recommendations
- limitations

Use concise, driver-friendly language.

Do not mention fuel_level or hybrid_battery_life anywhere in the
output.

Do not invent evidence to make a system assessment appear complete.

Clearly distinguish a lack of evidence from evidence of a problem.

The assessment is based on the available telemetry and is not a
substitute for a professional vehicle inspection or diagnostic
procedure.
"""



REPORT_SYSTEM_PROMPT = """
You are DriveSense AI, responsible for producing a clear vehicle
session report from analyses already performed by the system.

Use the supplied session summary, diagnostic analysis, and vehicle
analysis when available.

Rules:
1. Summarize the supplied evidence without inventing measurements.
2. Prioritize important findings and actionable recommendations.
3. Clearly distinguish potential issues from confirmed faults.
4. Preserve uncertainty and data-quality limitations.
5. Do not independently diagnose new faults that were not
   supported by the supplied analyses.
6. Do not claim the vehicle is healthy merely because no issue
   was detected.
7. Avoid repeating the same information unnecessarily.
8. Write for a vehicle owner, not an automotive engineer.
"""


# ---------------------------------------------------------
# Helper function
# ---------------------------------------------------------

def _to_json(data) -> str:
    """Convert dictionaries or Pydantic models to JSON text."""
    if isinstance(data, BaseModel):
        data = data.model_dump(mode="json")

    return json.dumps(data, default=str)


# ---------------------------------------------------------
# Function 1: Analyze diagnostic trouble codes
# ---------------------------------------------------------

def analyze_diagnostic_codes(
    codes: list[str],
    vehicle: dict,
) -> DiagnosticAnalysis:
    """
    Explain supplied diagnostic trouble codes.

    Args:
        codes: Diagnostic trouble codes read from the vehicle.
        vehicle: Vehicle information, such as make, model, and year.

    Returns:
        Structured diagnostic analysis.
    """

    if not codes:
        return DiagnosticAnalysis(
            overall_summary=(
                "No diagnostic trouble codes were supplied for analysis."
            ),
            findings=[],
            limitations=[
                "No codes were provided. This does not establish "
                "that the vehicle has no mechanical or electrical issues."
            ],
        )

    payload = {
        "vehicle": vehicle,
        "diagnostic_codes": codes,
    }

    response = client.responses.parse(
        model=OPENAI_MODEL,
        instructions=DIAGNOSTIC_SYSTEM_PROMPT,
        input=_to_json(payload),
        text_format=DiagnosticAnalysis,
    )

    if response.output_parsed is None:
        raise RuntimeError(
            "The AI did not return a structured diagnostic analysis."
        )

    return response.output_parsed


# ---------------------------------------------------------
# Function 2: Analyze summarized vehicle telemetry
# ---------------------------------------------------------

def analyze_vehicle_data(
    vehicle: dict,
    session_summary: dict,
    diagnostic_analysis: Optional[DiagnosticAnalysis] = None,
) -> VehicleAnalysis:
    """
    Analyze summarized telemetry and optionally incorporate
    previously generated diagnostic-code findings.

    This function does not calculate a numerical health score.
    """

    payload = {
        "vehicle": vehicle,
        "session_summary": session_summary,
        "diagnostic_analysis": (
            diagnostic_analysis.model_dump(mode="json")
            if diagnostic_analysis is not None
            else None
        ),
    }

    response = client.responses.parse(
        model=OPENAI_MODEL,
        instructions=VEHICLE_ANALYSIS_SYSTEM_PROMPT,
        input=_to_json(payload),
        text_format=VehicleAnalysis,
    )

    if response.output_parsed is None:
        raise RuntimeError(
            "The AI did not return a structured vehicle analysis."
        )

    return response.output_parsed


# ---------------------------------------------------------
# Function 3: Generate a combined vehicle report
# ---------------------------------------------------------

def generate_vehicle_report(
    vehicle: dict,
    session_summary: dict,
    vehicle_analysis: VehicleAnalysis,
    diagnostic_analysis: Optional[DiagnosticAnalysis] = None,
) -> VehicleReport:
    """
    Generate a user-facing report from existing analysis results.

    This function does not rerun the telemetry or DTC analyses.
    """

    payload = {
        "vehicle": vehicle,
        "session_summary": session_summary,
        "vehicle_analysis": vehicle_analysis.model_dump(mode="json"),
        "diagnostic_analysis": (
            diagnostic_analysis.model_dump(mode="json")
            if diagnostic_analysis is not None
            else None
        ),
    }

    response = client.responses.parse(
        model=OPENAI_MODEL,
        instructions=REPORT_SYSTEM_PROMPT,
        input=_to_json(payload),
        text_format=VehicleReport,
    )

    if response.output_parsed is None:
        raise RuntimeError(
            "The AI did not return a structured vehicle report."
        )

    return response.output_parsed

session = {
  "id": "None",
  "driving_session_id": "ff9fd2d8-a0e0-48c5-8351-ccf7ec0ecfaa",
  "vehicle_id": "81736fa5-3467-4428-adbd-72f40c27802f",
  "duration_seconds": 527.107597,
  "distance": null,
  "average_speed": 24.34,
  "average_moving_speed": 24.34,
  "maximum_speed": 49.09,
  "total_samples": 79,
  "telemetry_summary": {
    "rpm": {
      "count": 79,
      "minimum": 789.0,
      "maximum": 2687.25,
      "average": 1619.22,
      "first": 893.0,
      "last": 1250.25,
      "units": "rpm"
    },
    "speed": {
      "count": 79,
      "minimum": 0.62,
      "maximum": 49.09,
      "average": 24.34,
      "first": 2.49,
      "last": 8.7,
      "units": "mph"
    },
    "coolant_temperature": {
      "count": 79,
      "minimum": 76.0,
      "maximum": 84.0,
      "average": 79.37,
      "first": 78.0,
      "last": 82.0,
      "units": "°C"
    },
    "intake_air_temperature": {
      "count": 79,
      "minimum": 23.0,
      "maximum": 27.0,
      "average": 25.01,
      "first": 27.0,
      "last": 27.0,
      "units": "°C"
    },
    "engine_load": {
      "count": 79,
      "minimum": 5.1,
      "maximum": 70.2,
      "average": 27.44,
      "first": 26.67,
      "last": 23.53,
      "units": "%"
    },
    "throttle_position": {
      "count": 79,
      "minimum": 19.61,
      "maximum": 63.14,
      "average": 34.01,
      "first": 29.41,
      "last": 30.2,
      "units": "%"
    },
    "mass_air_flow": {
      "count": 79,
      "minimum": 1.58,
      "maximum": 44.05,
      "average": 11.24,
      "first": 4.79,
      "last": 5.29,
      "units": "g/s"
    },
    "map_pressure": {
      "count": 79,
      "minimum": 11.0,
      "maximum": 78.0,
      "average": 35.18,
      "first": 25.0,
      "last": 34.0,
      "units": "kPa"
    },
    "fuel_level": {
      "count": 79,
      "minimum": 20.78,
      "maximum": 34.51,
      "average": 31.07,
      "first": 33.33,
      "last": 29.41,
      "units": "%"
    },
    "fuel_pressure": {
      "count": 79,
      "minimum": 378.0,
      "maximum": 450.0,
      "average": 404.7,
      "first": 396.0,
      "last": 399.0,
      "units": "kPa"
    },
    "timing_advance": {
      "count": 79,
      "minimum": -11.5,
      "maximum": 40.0,
      "average": 8.91,
      "first": 21.5,
      "last": 32.5,
      "units": "degrees"
    },
    "control_module_voltage": {
      "count": 79,
      "minimum": 14.64,
      "maximum": 14.78,
      "average": 14.73,
      "first": 14.72,
      "last": 14.75,
      "units": "V"
    },
    "short_trim": {
      "count": 79,
      "minimum": -17.97,
      "maximum": 18.75,
      "average": 1.68,
      "first": 6.25,
      "last": 7.81,
      "units": "%"
    },
    "session": {
      "start_time": "2026-10-29T21:20:05.850203+00:00",
      "end_time": "2026-10-29T21:28:52.957800+00:00",
      "duration_seconds": 527.11,
      "speed_unit": "mph"
    }
  },
  "data_quality": {
    "total_samples": 79,
    "samples_with_timestamp": 79,
    "samples_without_timestamp": 0,
    "available_sensors": [
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
      "short_trim"
    ],
    "unavailable_sensors": [
      "hybrid_battery_life"
    ],
    "total_expected_sensor_values": 1027,
    "total_missing_sensor_values": 0,
    "missing_values_by_field": {
      "rpm": 0,
      "speed": 0,
      "coolant_temperature": 0,
      "intake_air_temperature": 0,
      "engine_load": 0,
      "throttle_position": 0,
      "mass_air_flow": 0,
      "map_pressure": 0,
      "fuel_level": 0,
      "fuel_pressure": 0,
      "timing_advance": 0,
      "control_module_voltage": 0,
      "short_trim": 0,
      "hybrid_battery_life": 79
    },
    "missing_value_percentage": 0.0,
    "median_sample_interval_seconds": 6.41,
    "maximum_sample_interval_seconds": 19.26
  },
  "samples": [
    {
      "timestamp": "2026-10-29T21:20:06.281388+00:00",
      "rpm": 893.0,
      "speed": 2.485484,
      "coolant_temperature": 78.0,
      "intake_air_temperature": 27.0,
      "engine_load": 26.666666666666668,
      "throttle_position": 29.41176470588235,
      "mass_air_flow": 4.79,
      "map_pressure": 25.0,
      "fuel_level": 33.333333333333336,
      "fuel_pressure": 396.0,
      "timing_advance": 21.5,
      "control_module_voltage": 14.72,
      "short_trim": 6.25,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:20:12.695584+00:00",
      "rpm": 1822.0,
      "speed": 13.670162,
      "coolant_temperature": 77.0,
      "intake_air_temperature": 27.0,
      "engine_load": 11.764705882352942,
      "throttle_position": 30.58823529411765,
      "mass_air_flow": 5.2,
      "map_pressure": 24.0,
      "fuel_level": 32.15686274509804,
      "fuel_pressure": 402.0,
      "timing_advance": 21.0,
      "control_module_voltage": 14.72,
      "short_trim": -7.03125,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:20:31.954276+00:00",
      "rpm": 1577.25,
      "speed": 10.563307,
      "coolant_temperature": 77.0,
      "intake_air_temperature": 27.0,
      "engine_load": 54.90196078431372,
      "throttle_position": 54.11764705882353,
      "mass_air_flow": 22.45,
      "map_pressure": 62.0,
      "fuel_level": 20.784313725490197,
      "fuel_pressure": 408.0,
      "timing_advance": 1.5,
      "control_module_voltage": 14.645,
      "short_trim": 1.5625,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:20:38.383942+00:00",
      "rpm": 1037.5,
      "speed": 12.42742,
      "coolant_temperature": 78.0,
      "intake_air_temperature": 27.0,
      "engine_load": 17.647058823529413,
      "throttle_position": 25.49019607843137,
      "mass_air_flow": 3.29,
      "map_pressure": 18.0,
      "fuel_level": 31.764705882352942,
      "fuel_pressure": 402.0,
      "timing_advance": 4.5,
      "control_module_voltage": 14.739,
      "short_trim": -2.34375,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:20:44.798270+00:00",
      "rpm": 789.0,
      "speed": 0.621371,
      "coolant_temperature": 78.0,
      "intake_air_temperature": 27.0,
      "engine_load": 27.058823529411764,
      "throttle_position": 26.666666666666668,
      "mass_air_flow": 3.36,
      "map_pressure": 23.0,
      "fuel_level": 29.80392156862745,
      "fuel_pressure": 399.0,
      "timing_advance": -3.5,
      "control_module_voltage": 14.708,
      "short_trim": -4.6875,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:20:51.212375+00:00",
      "rpm": 2687.25,
      "speed": 19.883872,
      "coolant_temperature": 78.0,
      "intake_air_temperature": 26.0,
      "engine_load": 25.88235294117647,
      "throttle_position": 36.86274509803921,
      "mass_air_flow": 18.01,
      "map_pressure": 38.0,
      "fuel_level": 26.666666666666668,
      "fuel_pressure": 387.0,
      "timing_advance": 8.0,
      "control_module_voltage": 14.72,
      "short_trim": -7.03125,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:20:57.626644+00:00",
      "rpm": 1662.5,
      "speed": 26.097582,
      "coolant_temperature": 78.0,
      "intake_air_temperature": 26.0,
      "engine_load": 14.901960784313726,
      "throttle_position": 31.764705882352942,
      "mass_air_flow": 6.21,
      "map_pressure": 33.0,
      "fuel_level": 32.15686274509804,
      "fuel_pressure": 402.0,
      "timing_advance": 40.0,
      "control_module_voltage": 14.745000000000001,
      "short_trim": -15.625,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:21:10.455557+00:00",
      "rpm": 1520.25,
      "speed": 32.932663,
      "coolant_temperature": 79.0,
      "intake_air_temperature": 25.0,
      "engine_load": 56.470588235294116,
      "throttle_position": 44.705882352941174,
      "mass_air_flow": 19.14,
      "map_pressure": 58.0,
      "fuel_level": 33.72549019607843,
      "fuel_pressure": 408.0,
      "timing_advance": 1.5,
      "control_module_voltage": 14.739,
      "short_trim": -0.78125,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:21:16.885227+00:00",
      "rpm": 1192.75,
      "speed": 27.340324,
      "coolant_temperature": 79.0,
      "intake_air_temperature": 26.0,
      "engine_load": 18.03921568627451,
      "throttle_position": 26.274509803921568,
      "mass_air_flow": 3.41,
      "map_pressure": 17.0,
      "fuel_level": 33.333333333333336,
      "fuel_pressure": 423.0,
      "timing_advance": -6.0,
      "control_module_voltage": 14.751,
      "short_trim": 18.75,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:21:23.299975+00:00",
      "rpm": 1345.25,
      "speed": 29.825808000000002,
      "coolant_temperature": 79.0,
      "intake_air_temperature": 25.0,
      "engine_load": 61.1764705882353,
      "throttle_position": 41.1764705882353,
      "mass_air_flow": 16.29,
      "map_pressure": 59.0,
      "fuel_level": 33.72549019607843,
      "fuel_pressure": 393.0,
      "timing_advance": 1.5,
      "control_module_voltage": 14.745000000000001,
      "short_trim": -3.125,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:21:29.713999+00:00",
      "rpm": 1334.75,
      "speed": 31.068550000000002,
      "coolant_temperature": 78.0,
      "intake_air_temperature": 25.0,
      "engine_load": 14.509803921568627,
      "throttle_position": 27.058823529411764,
      "mass_air_flow": 3.86,
      "map_pressure": 27.0,
      "fuel_level": 33.72549019607843,
      "fuel_pressure": 411.0,
      "timing_advance": 29.5,
      "control_module_voltage": 14.745000000000001,
      "short_trim": -0.78125,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:21:42.541408+00:00",
      "rpm": 1523.25,
      "speed": 34.796776,
      "coolant_temperature": 78.0,
      "intake_air_temperature": 25.0,
      "engine_load": 41.1764705882353,
      "throttle_position": 38.03921568627451,
      "mass_air_flow": 14.92,
      "map_pressure": 53.0,
      "fuel_level": 33.72549019607843,
      "fuel_pressure": 402.0,
      "timing_advance": 5.0,
      "control_module_voltage": 14.713000000000001,
      "short_trim": 7.8125,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:21:48.971912+00:00",
      "rpm": 1559.75,
      "speed": 36.039518,
      "coolant_temperature": 78.0,
      "intake_air_temperature": 25.0,
      "engine_load": 5.098039215686274,
      "throttle_position": 21.96078431372549,
      "mass_air_flow": 1.98,
      "map_pressure": 11.0,
      "fuel_level": 32.94117647058823,
      "fuel_pressure": 408.0,
      "timing_advance": 20.0,
      "control_module_voltage": 14.72,
      "short_trim": -0.78125,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:21:55.386493+00:00",
      "rpm": 1438.5,
      "speed": 32.932663,
      "coolant_temperature": 78.0,
      "intake_air_temperature": 25.0,
      "engine_load": 29.019607843137255,
      "throttle_position": 34.90196078431372,
      "mass_air_flow": 10.97,
      "map_pressure": 43.0,
      "fuel_level": 34.11764705882353,
      "fuel_pressure": 405.0,
      "timing_advance": 15.5,
      "control_module_voltage": 14.739,
      "short_trim": 3.90625,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:22:01.816802+00:00",
      "rpm": 1478.25,
      "speed": 33.554034,
      "coolant_temperature": 77.0,
      "intake_air_temperature": 25.0,
      "engine_load": 31.372549019607842,
      "throttle_position": 35.68627450980392,
      "mass_air_flow": 10.63,
      "map_pressure": 43.0,
      "fuel_level": 32.549019607843135,
      "fuel_pressure": 399.0,
      "timing_advance": 19.5,
      "control_module_voltage": 14.745000000000001,
      "short_trim": -4.6875,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:22:14.660346+00:00",
      "rpm": 1747.25,
      "speed": 41.010486,
      "coolant_temperature": 77.0,
      "intake_air_temperature": 25.0,
      "engine_load": 6.666666666666667,
      "throttle_position": 24.705882352941178,
      "mass_air_flow": 2.81,
      "map_pressure": 11.0,
      "fuel_level": 33.333333333333336,
      "fuel_pressure": 405.0,
      "timing_advance": 7.5,
      "control_module_voltage": 14.726,
      "short_trim": 13.28125,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:22:21.074879+00:00",
      "rpm": 1495.0,
      "speed": 34.796776,
      "coolant_temperature": 77.0,
      "intake_air_temperature": 26.0,
      "engine_load": 10.196078431372548,
      "throttle_position": 26.666666666666668,
      "mass_air_flow": 3.56,
      "map_pressure": 15.0,
      "fuel_level": 32.94117647058823,
      "fuel_pressure": 420.0,
      "timing_advance": -8.5,
      "control_module_voltage": 14.739,
      "short_trim": 0.0,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:22:27.489116+00:00",
      "rpm": 1625.25,
      "speed": 26.097582,
      "coolant_temperature": 77.0,
      "intake_air_temperature": 26.0,
      "engine_load": 9.803921568627452,
      "throttle_position": 27.45098039215686,
      "mass_air_flow": 4.04,
      "map_pressure": 15.0,
      "fuel_level": 32.549019607843135,
      "fuel_pressure": 435.0,
      "timing_advance": -8.5,
      "control_module_voltage": 14.751,
      "short_trim": 0.0,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:22:33.903206+00:00",
      "rpm": 1598.5,
      "speed": 32.311292,
      "coolant_temperature": 76.0,
      "intake_air_temperature": 25.0,
      "engine_load": 57.64705882352941,
      "throttle_position": 53.72549019607843,
      "mass_air_flow": 23.080000000000002,
      "map_pressure": 61.0,
      "fuel_level": 31.372549019607842,
      "fuel_pressure": 396.0,
      "timing_advance": -2.5,
      "control_module_voltage": 14.751,
      "short_trim": 6.25,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:22:40.317023+00:00",
      "rpm": 1723.25,
      "speed": 39.767744,
      "coolant_temperature": 76.0,
      "intake_air_temperature": 24.0,
      "engine_load": 49.411764705882355,
      "throttle_position": 41.1764705882353,
      "mass_air_flow": 21.52,
      "map_pressure": 60.0,
      "fuel_level": 33.333333333333336,
      "fuel_pressure": 408.0,
      "timing_advance": -0.5,
      "control_module_voltage": 14.732000000000001,
      "short_trim": -0.78125,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:22:53.193083+00:00",
      "rpm": 1805.25,
      "speed": 39.767744,
      "coolant_temperature": 77.0,
      "intake_air_temperature": 25.0,
      "engine_load": 21.568627450980394,
      "throttle_position": 34.509803921568626,
      "mass_air_flow": 9.85,
      "map_pressure": 36.0,
      "fuel_level": 33.72549019607843,
      "fuel_pressure": 402.0,
      "timing_advance": 30.5,
      "control_module_voltage": 14.726,
      "short_trim": 18.75,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:22:59.607155+00:00",
      "rpm": 1653.75,
      "speed": 39.146373,
      "coolant_temperature": 77.0,
      "intake_air_temperature": 25.0,
      "engine_load": 6.666666666666667,
      "throttle_position": 24.313725490196077,
      "mass_air_flow": 2.79,
      "map_pressure": 11.0,
      "fuel_level": 34.509803921568626,
      "fuel_pressure": 396.0,
      "timing_advance": 7.5,
      "control_module_voltage": 14.739,
      "short_trim": 2.34375,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:23:12.435561+00:00",
      "rpm": 1807.25,
      "speed": 3.7282260000000003,
      "coolant_temperature": 77.0,
      "intake_air_temperature": 26.0,
      "engine_load": 34.509803921568626,
      "throttle_position": 38.03921568627451,
      "mass_air_flow": 17.240000000000002,
      "map_pressure": 45.0,
      "fuel_level": 29.41176470588235,
      "fuel_pressure": 402.0,
      "timing_advance": 11.5,
      "control_module_voltage": 14.702,
      "short_trim": 7.03125,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:23:18.849722+00:00",
      "rpm": 2395.5,
      "speed": 28.583066,
      "coolant_temperature": 77.0,
      "intake_air_temperature": 24.0,
      "engine_load": 70.19607843137256,
      "throttle_position": 63.13725490196079,
      "mass_air_flow": 44.050000000000004,
      "map_pressure": 78.0,
      "fuel_level": 26.274509803921568,
      "fuel_pressure": 411.0,
      "timing_advance": -4.0,
      "control_module_voltage": 14.72,
      "short_trim": 0.0,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:23:25.264230+00:00",
      "rpm": 2519.25,
      "speed": 43.49597,
      "coolant_temperature": 77.0,
      "intake_air_temperature": 24.0,
      "engine_load": 43.13725490196079,
      "throttle_position": 39.6078431372549,
      "mass_air_flow": 26.060000000000002,
      "map_pressure": 53.0,
      "fuel_level": 30.980392156862745,
      "fuel_pressure": 381.0,
      "timing_advance": -8.5,
      "control_module_voltage": 14.72,
      "short_trim": -5.46875,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:23:31.758268+00:00",
      "rpm": 1690.0,
      "speed": 49.088309,
      "coolant_temperature": 78.0,
      "intake_air_temperature": 23.0,
      "engine_load": 59.6078431372549,
      "throttle_position": 54.90196078431372,
      "mass_air_flow": 26.23,
      "map_pressure": 66.0,
      "fuel_level": 32.549019607843135,
      "fuel_pressure": 396.0,
      "timing_advance": -3.0,
      "control_module_voltage": 14.726,
      "short_trim": -3.125,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:23:38.172668+00:00",
      "rpm": 1610.75,
      "speed": 49.088309,
      "coolant_temperature": 79.0,
      "intake_air_temperature": 24.0,
      "engine_load": 37.64705882352941,
      "throttle_position": 38.03921568627451,
      "mass_air_flow": 14.49,
      "map_pressure": 51.0,
      "fuel_level": 32.94117647058823,
      "fuel_pressure": 405.0,
      "timing_advance": 10.0,
      "control_module_voltage": 14.732000000000001,
      "short_trim": 8.59375,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:23:44.586798+00:00",
      "rpm": 1560.75,
      "speed": 36.039518,
      "coolant_temperature": 81.0,
      "intake_air_temperature": 25.0,
      "engine_load": 10.196078431372548,
      "throttle_position": 27.45098039215686,
      "mass_air_flow": 3.94,
      "map_pressure": 16.0,
      "fuel_level": 32.94117647058823,
      "fuel_pressure": 429.0,
      "timing_advance": -9.0,
      "control_module_voltage": 14.732000000000001,
      "short_trim": 0.0,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:23:51.000949+00:00",
      "rpm": 1201.0,
      "speed": 14.912904000000001,
      "coolant_temperature": 81.0,
      "intake_air_temperature": 25.0,
      "engine_load": 12.549019607843137,
      "throttle_position": 23.137254901960784,
      "mass_air_flow": 2.37,
      "map_pressure": 12.0,
      "fuel_level": 31.764705882352942,
      "fuel_pressure": 450.0,
      "timing_advance": 9.0,
      "control_module_voltage": 14.77,
      "short_trim": 18.75,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:24:03.828580+00:00",
      "rpm": 1982.0,
      "speed": 29.825808000000002,
      "coolant_temperature": 80.0,
      "intake_air_temperature": 24.0,
      "engine_load": 39.6078431372549,
      "throttle_position": 39.21568627450981,
      "mass_air_flow": 20.03,
      "map_pressure": 49.0,
      "fuel_level": 22.352941176470587,
      "fuel_pressure": 396.0,
      "timing_advance": 10.5,
      "control_module_voltage": 14.72,
      "short_trim": 10.15625,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:24:10.243444+00:00",
      "rpm": 1422.75,
      "speed": 32.932663,
      "coolant_temperature": 79.0,
      "intake_air_temperature": 24.0,
      "engine_load": 11.764705882352942,
      "throttle_position": 27.058823529411764,
      "mass_air_flow": 3.8000000000000003,
      "map_pressure": 17.0,
      "fuel_level": 31.764705882352942,
      "fuel_pressure": 414.0,
      "timing_advance": -10.0,
      "control_module_voltage": 14.726,
      "short_trim": 0.0,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:24:23.071460+00:00",
      "rpm": 1660.0,
      "speed": 38.525002,
      "coolant_temperature": 78.0,
      "intake_air_temperature": 24.0,
      "engine_load": 23.529411764705884,
      "throttle_position": 34.90196078431372,
      "mass_air_flow": 10.03,
      "map_pressure": 41.0,
      "fuel_level": 32.549019607843135,
      "fuel_pressure": 405.0,
      "timing_advance": 25.0,
      "control_module_voltage": 14.726,
      "short_trim": 11.71875,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:24:35.901675+00:00",
      "rpm": 1684.5,
      "speed": 39.146373,
      "coolant_temperature": 79.0,
      "intake_air_temperature": 24.0,
      "engine_load": 10.196078431372548,
      "throttle_position": 28.235294117647058,
      "mass_air_flow": 4.45,
      "map_pressure": 19.0,
      "fuel_level": 33.72549019607843,
      "fuel_pressure": 393.0,
      "timing_advance": 39.5,
      "control_module_voltage": 14.732000000000001,
      "short_trim": 5.46875,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:24:55.158518+00:00",
      "rpm": 1165.75,
      "speed": 26.718953,
      "coolant_temperature": 78.0,
      "intake_air_temperature": 25.0,
      "engine_load": 17.647058823529413,
      "throttle_position": 25.88235294117647,
      "mass_air_flow": 3.3000000000000003,
      "map_pressure": 17.0,
      "fuel_level": 33.333333333333336,
      "fuel_pressure": 420.0,
      "timing_advance": -6.0,
      "control_module_voltage": 14.726,
      "short_trim": 0.0,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:25:01.572902+00:00",
      "rpm": 923.75,
      "speed": 7.4564520000000005,
      "coolant_temperature": 78.0,
      "intake_air_temperature": 25.0,
      "engine_load": 29.019607843137255,
      "throttle_position": 29.80392156862745,
      "mass_air_flow": 5.13,
      "map_pressure": 24.0,
      "fuel_level": 30.19607843137255,
      "fuel_pressure": 393.0,
      "timing_advance": 20.0,
      "control_module_voltage": 14.776,
      "short_trim": 18.75,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:25:14.432467+00:00",
      "rpm": 1091.0,
      "speed": 27.340324,
      "coolant_temperature": 77.0,
      "intake_air_temperature": 24.0,
      "engine_load": 9.411764705882353,
      "throttle_position": 19.607843137254903,
      "mass_air_flow": 1.58,
      "map_pressure": 11.0,
      "fuel_level": 32.15686274509804,
      "fuel_pressure": 405.0,
      "timing_advance": 16.0,
      "control_module_voltage": 14.732000000000001,
      "short_trim": -17.96875,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:25:20.846566+00:00",
      "rpm": 1411.75,
      "speed": 32.311292,
      "coolant_temperature": 77.0,
      "intake_air_temperature": 23.0,
      "engine_load": 49.80392156862745,
      "throttle_position": 38.8235294117647,
      "mass_air_flow": 15.24,
      "map_pressure": 57.0,
      "fuel_level": 32.94117647058823,
      "fuel_pressure": 393.0,
      "timing_advance": 1.5,
      "control_module_voltage": 14.745000000000001,
      "short_trim": -2.34375,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:25:27.260797+00:00",
      "rpm": 1400.0,
      "speed": 32.932663,
      "coolant_temperature": 78.0,
      "intake_air_temperature": 23.0,
      "engine_load": 10.588235294117647,
      "throttle_position": 26.274509803921568,
      "mass_air_flow": 3.1,
      "map_pressure": 18.0,
      "fuel_level": 32.549019607843135,
      "fuel_pressure": 411.0,
      "timing_advance": 8.0,
      "control_module_voltage": 14.695,
      "short_trim": -5.46875,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:25:46.551033+00:00",
      "rpm": 1924.75,
      "speed": 21.747985,
      "coolant_temperature": 80.0,
      "intake_air_temperature": 24.0,
      "engine_load": 47.450980392156865,
      "throttle_position": 40.3921568627451,
      "mass_air_flow": 20.93,
      "map_pressure": 54.0,
      "fuel_level": 29.80392156862745,
      "fuel_pressure": 399.0,
      "timing_advance": 7.0,
      "control_module_voltage": 14.72,
      "short_trim": -0.78125,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:26:05.794014+00:00",
      "rpm": 2310.0,
      "speed": 15.534275000000001,
      "coolant_temperature": 80.0,
      "intake_air_temperature": 24.0,
      "engine_load": 34.90196078431372,
      "throttle_position": 38.8235294117647,
      "mass_air_flow": 21.36,
      "map_pressure": 48.0,
      "fuel_level": 29.80392156862745,
      "fuel_pressure": 426.0,
      "timing_advance": 13.0,
      "control_module_voltage": 14.702,
      "short_trim": -3.90625,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:26:18.622193+00:00",
      "rpm": 1704.25,
      "speed": 3.7282260000000003,
      "coolant_temperature": 80.0,
      "intake_air_temperature": 25.0,
      "engine_load": 31.764705882352942,
      "throttle_position": 37.254901960784316,
      "mass_air_flow": 14.530000000000001,
      "map_pressure": 42.0,
      "fuel_level": 28.627450980392158,
      "fuel_pressure": 402.0,
      "timing_advance": 14.0,
      "control_module_voltage": 14.695,
      "short_trim": 8.59375,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:26:37.864222+00:00",
      "rpm": 2306.25,
      "speed": 17.398388,
      "coolant_temperature": 80.0,
      "intake_air_temperature": 25.0,
      "engine_load": 29.80392156862745,
      "throttle_position": 37.254901960784316,
      "mass_air_flow": 17.71,
      "map_pressure": 42.0,
      "fuel_level": 28.627450980392158,
      "fuel_pressure": 411.0,
      "timing_advance": 17.0,
      "control_module_voltage": 14.695,
      "short_trim": -15.625,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:26:44.279927+00:00",
      "rpm": 2507.75,
      "speed": 18.64113,
      "coolant_temperature": 80.0,
      "intake_air_temperature": 25.0,
      "engine_load": 22.745098039215687,
      "throttle_position": 35.68627450980392,
      "mass_air_flow": 8.91,
      "map_pressure": 34.0,
      "fuel_level": 28.235294117647058,
      "fuel_pressure": 411.0,
      "timing_advance": 25.0,
      "control_module_voltage": 14.689,
      "short_trim": 0.78125,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:26:57.107061+00:00",
      "rpm": 1239.5,
      "speed": 15.534275000000001,
      "coolant_temperature": 81.0,
      "intake_air_temperature": 25.0,
      "engine_load": 18.823529411764707,
      "throttle_position": 27.84313725490196,
      "mass_air_flow": 4.01,
      "map_pressure": 19.0,
      "fuel_level": 30.980392156862745,
      "fuel_pressure": 420.0,
      "timing_advance": 2.5,
      "control_module_voltage": 14.757,
      "short_trim": -11.71875,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:27:03.521701+00:00",
      "rpm": 2432.75,
      "speed": 13.048791,
      "coolant_temperature": 82.0,
      "intake_air_temperature": 25.0,
      "engine_load": 60.0,
      "throttle_position": 54.509803921568626,
      "mass_air_flow": 37.95,
      "map_pressure": 68.0,
      "fuel_level": 21.176470588235293,
      "fuel_pressure": 432.0,
      "timing_advance": -0.5,
      "control_module_voltage": 14.713000000000001,
      "short_trim": 1.5625,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:27:09.967852+00:00",
      "rpm": 1666.0,
      "speed": 24.85484,
      "coolant_temperature": 82.0,
      "intake_air_temperature": 25.0,
      "engine_load": 5.882352941176471,
      "throttle_position": 23.529411764705884,
      "mass_air_flow": 2.59,
      "map_pressure": 11.0,
      "fuel_level": 31.764705882352942,
      "fuel_pressure": 396.0,
      "timing_advance": 33.0,
      "control_module_voltage": 14.732000000000001,
      "short_trim": -1.5625,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:27:16.413946+00:00",
      "rpm": 1400.0,
      "speed": 13.048791,
      "coolant_temperature": 83.0,
      "intake_air_temperature": 26.0,
      "engine_load": 12.549019607843137,
      "throttle_position": 29.41176470588235,
      "mass_air_flow": 4.5200000000000005,
      "map_pressure": 17.0,
      "fuel_level": 32.549019607843135,
      "fuel_pressure": 399.0,
      "timing_advance": -0.5,
      "control_module_voltage": 14.739,
      "short_trim": 18.75,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:27:22.843926+00:00",
      "rpm": 2679.25,
      "speed": 13.048791,
      "coolant_temperature": 83.0,
      "intake_air_temperature": 26.0,
      "engine_load": 36.86274509803921,
      "throttle_position": 39.21568627450981,
      "mass_air_flow": 25.11,
      "map_pressure": 47.0,
      "fuel_level": 26.666666666666668,
      "fuel_pressure": 414.0,
      "timing_advance": -2.0,
      "control_module_voltage": 14.708,
      "short_trim": -3.90625,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:27:29.274112+00:00",
      "rpm": 1739.75,
      "speed": 26.718953,
      "coolant_temperature": 83.0,
      "intake_air_temperature": 25.0,
      "engine_load": 54.90196078431372,
      "throttle_position": 50.98039215686274,
      "mass_air_flow": 24.78,
      "map_pressure": 65.0,
      "fuel_level": 27.058823529411764,
      "fuel_pressure": 408.0,
      "timing_advance": -1.5,
      "control_module_voltage": 14.726,
      "short_trim": 0.78125,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:27:35.687932+00:00",
      "rpm": 1630.75,
      "speed": 26.097582,
      "coolant_temperature": 84.0,
      "intake_air_temperature": 25.0,
      "engine_load": 20.0,
      "throttle_position": 33.72549019607843,
      "mass_air_flow": 8.38,
      "map_pressure": 41.0,
      "fuel_level": 30.58823529411765,
      "fuel_pressure": 402.0,
      "timing_advance": 32.0,
      "control_module_voltage": 14.745000000000001,
      "short_trim": 12.5,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:27:42.101921+00:00",
      "rpm": 1459.25,
      "speed": 23.612098,
      "coolant_temperature": 84.0,
      "intake_air_temperature": 26.0,
      "engine_load": 11.764705882352942,
      "throttle_position": 27.058823529411764,
      "mass_air_flow": 3.96,
      "map_pressure": 18.0,
      "fuel_level": 31.372549019607842,
      "fuel_pressure": 423.0,
      "timing_advance": -11.5,
      "control_module_voltage": 14.757,
      "short_trim": 0.0,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:27:48.516483+00:00",
      "rpm": 919.5,
      "speed": 7.4564520000000005,
      "coolant_temperature": 83.0,
      "intake_air_temperature": 27.0,
      "engine_load": 15.686274509803921,
      "throttle_position": 23.137254901960784,
      "mass_air_flow": 2.33,
      "map_pressure": 15.0,
      "fuel_level": 31.764705882352942,
      "fuel_pressure": 393.0,
      "timing_advance": 10.0,
      "control_module_voltage": 14.757,
      "short_trim": 18.75,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:28:07.775238+00:00",
      "rpm": 2315.0,
      "speed": 16.155646,
      "coolant_temperature": 83.0,
      "intake_air_temperature": 25.0,
      "engine_load": 32.15686274509804,
      "throttle_position": 37.64705882352941,
      "mass_air_flow": 19.11,
      "map_pressure": 44.0,
      "fuel_level": 28.627450980392158,
      "fuel_pressure": 378.0,
      "timing_advance": 15.0,
      "control_module_voltage": 14.708,
      "short_trim": -7.03125,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:28:20.603465+00:00",
      "rpm": 1270.75,
      "speed": 13.670162,
      "coolant_temperature": 83.0,
      "intake_air_temperature": 27.0,
      "engine_load": 17.254901960784313,
      "throttle_position": 27.84313725490196,
      "mass_air_flow": 4.2,
      "map_pressure": 17.0,
      "fuel_level": 32.94117647058823,
      "fuel_pressure": 417.0,
      "timing_advance": -7.0,
      "control_module_voltage": 14.739,
      "short_trim": 18.75,
      "hybrid_battery_life": null
    },
    {
      "timestamp": "2026-10-29T21:28:39.845467+00:00",
      "rpm": 1250.25,
      "speed": 8.699194,
      "coolant_temperature": 82.0,
      "intake_air_temperature": 27.0,
      "engine_load": 23.529411764705884,
      "throttle_position": 30.19607843137255,
      "mass_air_flow": 5.29,
      "map_pressure": 34.0,
      "fuel_level": 29.41176470588235,
      "fuel_pressure": 399.0,
      "timing_advance": 32.5,
      "control_module_voltage": 14.751,
      "short_trim": 7.8125,
      "hybrid_battery_life": null
    }
  ]
}

# print(analyze_vehicle_data({
#     "make": "Ford",
#     "model": "C-Max",
#     "year": 2016,
# },session))