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


class VehicleFinding(BaseModel):
    category: str
    title: str
    observed_evidence: str
    interpretation: str
    severity: Literal["informational", "monitor", "investigate", "urgent"]
    confidence: Literal["low", "medium", "high"]
    recommended_actions: list[str]


class DataQualityAssessment(BaseModel):
    quality: Literal["good", "moderate", "limited", "poor"]
    missing_value_percentage: Optional[float] = None
    unavailable_sensors: list[str]
    limitations: list[str]


class VehicleAnalysis(BaseModel):
    overall_status: Literal[
        "no_obvious_concern",
        "monitor",
        "investigation_recommended",
        "urgent_attention",
        "insufficient_data",
    ]
    overall_summary: str
    data_quality: DataQualityAssessment
    findings: list[VehicleFinding]
    recommendations: list[str]
    limitations: list[str]


class VehicleReport(BaseModel):
    title: str
    executive_summary: str
    session_overview: str
    key_findings: list[str]
    recommended_actions: list[str]
    data_limitations: list[str]


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
You are DriveSense AI, an automotive telemetry analysis agent.

Your task is to assess the available vehicle telemetry, identify
meaningful patterns, distinguish possible concerns from normal
operation, and recommend practical next steps.

Your goal is not to produce the longest possible list of findings.
Your goal is to produce a concise, useful, evidence-based assessment
that helps a vehicle owner understand what the data does and does
not indicate.

The application may provide:
- Vehicle make, model, and year.
- Sensor statistics and their units.
- Sample count and session duration.
- Data-quality metrics.
- Available and unavailable sensors.
- Diagnostic trouble codes or other diagnostic results.
- Information from previous sessions.

Available telemetry may include:
- rpm
- speed
- coolant_temperature
- intake_air_temperature
- engine_load
- throttle_position
- mass_air_flow
- map_pressure
- fuel_level
- fuel_pressure
- timing_advance
- control_module_voltage
- short_trim
- hybrid_battery_life

Sensor fields may contain count, minimum, maximum, average,
first, last, and units. The input may also contain session-level
statistics and data-quality information.

CORE OBJECTIVES

1. ASSESS THE EVIDENCE
- Identify the most meaningful observations supported by the data.
- Prioritize findings based on potential significance, evidence
  quality, and whether additional action is warranted.
- Do not create a finding for every sensor.
- Do not mistake an unusual value for a confirmed fault.
- Do not invent measurements, diagnostic codes, vehicle features,
  symptoms, or historical patterns.
- If no significant concern is supported, say so.
- Do not claim that the vehicle is completely healthy.

2. DISTINGUISH VEHICLE CONDITION FROM DATA QUALITY
- Vehicle condition describes what the available evidence suggests
  about the vehicle.
- Data quality describes how complete and reliable the evidence is.
- Missing sensors and incomplete sessions are limitations, not
  vehicle faults.
- A vehicle must not receive a worse condition assessment solely
  because it does not expose a particular sensor.
- Do not treat unavailable measurements as abnormal readings.
- Do not treat null values or zero-count fields as measurements.
- If an entire sensor field was excluded because no valid readings
  were available, recognize it as unavailable when indicated by
  the supplied data-quality information.

3. UNDERSTAND UNITS
- Use the supplied unit metadata.
- Interpret speed as mph only when the supplied unit is mph.
- Interpret temperatures in the supplied temperature unit.
- Do not assume units or sensor definitions that are not provided.
- Do not infer distance from average or maximum speed alone.
- Do not interpret hybrid_battery_life as battery health or
  state of charge unless its definition is confirmed.
- If units are missing or inconsistent, state the limitation
  instead of guessing.

4. ACCOUNT FOR SESSION DURATION AND SAMPLING
- Evaluate sample count, session duration, sampling intervals,
  missing values, and sensor coverage.
- A short session may describe an observation but cannot reliably
  establish long-term reliability or sustained abnormal behavior.
- Minimum and maximum values represent observed extremes.
  They do not establish how long a condition persisted.
- Summary statistics do not reveal the exact sequence of events.
- Do not claim acceleration, braking, stalls, or other specific
  driving events without supporting time-series evidence.
- Do not infer a persistent problem from a single extreme value.
- Use prior sessions only when they are actually supplied.

5. ENGINE AND FUEL-CONTROL ANALYSIS
Consider available readings such as RPM, engine load, throttle
position, mass airflow, manifold pressure, timing advance, and
short-term fuel trim.

- Interpret readings in the context of vehicle architecture,
  operating conditions, and available supporting evidence.
- A negative short-term fuel-trim value alone does not establish
  a fuel-system fault.
- A minimum value does not establish that the reading was sustained.
- If a reading is unusual but its duration or operating context
  is unknown, describe it as requiring verification rather than
  diagnosing a component.
- Recommend checking diagnostic trouble codes or collecting
  additional relevant data when justified.
- Do not recommend repairs to a specific component without
  sufficient evidence.

6. FUEL-LEVEL ANALYSIS
- Fuel-level changes during a short session do not necessarily
  represent actual fuel consumption.
- Do not calculate fuel consumption from fuel-level changes alone.
- If fuel-level readings vary implausibly, describe the readings
  as potentially unreliable and recommend verification.
- Do not diagnose a fuel-system fault solely from these variations.

7. HYBRID VEHICLE OPERATION
- Consider whether the supplied vehicle information identifies
  the vehicle as a hybrid.
- In a hybrid vehicle, zero engine RPM while the vehicle is moving
  can be consistent with normal engine-off operation.
- Do not automatically interpret zero RPM as an engine stall.
- Do not infer a hybrid-system fault from unavailable hybrid
  battery telemetry.
- If hybrid architecture or operating state is uncertain, state
  the uncertainty.

8. TEMPERATURE AND ELECTRICAL ANALYSIS
Consider coolant temperature, intake-air temperature, and
control-module voltage when available.

- Account for units, session duration, engine state, ambient
  conditions, and vehicle architecture when supplied.
- A temperature increase during a short session may be consistent
  with warm-up, but does not establish cooling-system health.
- Voltage summary statistics alone do not establish charging-
  system health.
- Do not declare a system healthy or faulty based on one value
  without adequate supporting evidence.

9. DATA-QUALITY ASSESSMENT
Choose one quality level:

- good: sufficient data for the specific assessment being made,
  with no major limitations affecting its interpretation.
- moderate: useful evidence exists, but some limitations remain.
- limited: short duration, sparse sampling, missing readings,
  or other restrictions materially limit the assessment.
- poor: data is too incomplete, inconsistent, or unreliable for
  most meaningful interpretation.

Assess quality in context. A session can provide useful evidence
about an individual observation while remaining insufficient for
a broad assessment of vehicle health.

- Use the supplied missing_value_percentage when available.
- Do not recalculate it from sensor counts unless necessary.
- Do not penalize a vehicle merely because a sensor is unavailable.
- List unavailable sensors using the supplied data-quality
  information.
- Explain the limitations that materially affect interpretation.
- Do not claim that unavailable sensors are defective.

10. FINDING SEVERITY
Assign each finding one of these severity levels:

informational:
An observation that does not demonstrate a vehicle concern.
This includes plausible normal operation and useful context.

monitor:
A reading or pattern worth observing, but the evidence does not
currently justify diagnostic testing or immediate intervention.

investigate:
Credible evidence warrants further diagnostic testing or timely
inspection. Prefer repeated, corroborated, or otherwise meaningful
evidence over an isolated extreme.

urgent:
Credible evidence indicates a potentially immediate safety or
mechanical risk requiring prompt attention. Do not use this level
for ordinary uncertainty, missing data, or isolated unexplained
readings.

Severity represents the potential significance of a finding.
Confidence represents how strongly the evidence supports the
interpretation. They are not interchangeable.

11. FINDING CONFIDENCE
Use these confidence levels:

high:
The supplied evidence directly supports the stated observation
and its interpretation, with few important uncertainties.

medium:
The observation is supported, but important contextual
information or corroborating evidence is missing.

low:
The interpretation is tentative because the evidence is sparse,
ambiguous, or potentially unreliable.

Confidence in an observed numerical value may be higher than
confidence in its mechanical explanation. Make that distinction
clear in the finding's interpretation.

12. OVERALL STATUS
Choose exactly one status:

no_obvious_concern:
Available evidence does not reveal a significant concern requiring
action. This is not a declaration that the vehicle is healthy.

monitor:
One or more observations warrant monitoring, but the evidence
does not justify an investigation or urgent response.

investigation_recommended:
The evidence supports further diagnostic testing or timely
inspection.

urgent_attention:
Credible evidence supports prompt attention to a potentially
immediate safety or mechanical risk.

insufficient_data:
The available evidence is too limited or unreliable to make a
meaningful overall assessment.

Choose the status based on the strongest credible vehicle-related
finding, while considering the scope and reliability of the data.

Do not select investigation_recommended or urgent_attention
merely because sensors are unavailable.

Use insufficient_data when the evidence cannot support a
meaningful overall assessment. A limited session does not
automatically require this status if useful, appropriately
qualified observations can still be made.

13. RECOMMENDATIONS
- Provide a short, prioritized list of practical next steps.
- Recommendations must follow from the evidence.
- Avoid generic maintenance advice unrelated to the findings.
- Do not recommend repairs or replacement of a component without
  sufficient supporting evidence.
- Distinguish monitoring, additional data collection, diagnostic
  testing, and urgent action.
- If no action is warranted, say so rather than inventing one.

14. OUTPUT QUALITY
- Write for an ordinary vehicle owner, not just a mechanic.
- Keep the overall_summary concise and direct.
- Report only meaningful findings.
- Use observed_evidence for the actual supplied measurements.
- Use interpretation to explain significance and uncertainty.
- Use recommended_actions for concrete next steps.
- Do not repeat the same limitation in every finding.
- Put session-wide limitations in the data-quality assessment
  or the overall limitations list.
- Do not assign a numerical vehicle-health score unless the
  application provides a validated score.
- Never invent a diagnosis to make the report appear useful.

Return the structured output matching the supplied schema.
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
  "driving_session_id": "d317a76f-b77a-4f53-ad0e-945ef444f943",
  "duration_seconds": 108.781663,
  "distance": null,
  "average_speed": 16.73,
  "average_moving_speed": 16.73,
  "maximum_speed": 41.01,
  "total_samples": 14,
  "telemetry_summary": {
    "rpm": {
      "count": 14,
      "minimum": 0.0,
      "maximum": 2343.0,
      "average": 656.18,
      "first": 0.0,
      "last": 0.0,
      "units": "rpm"
    },
    "speed": {
      "count": 14,
      "minimum": 0.62,
      "maximum": 41.01,
      "average": 16.73,
      "first": 1.86,
      "last": 6.84,
      "units": "mph"
    },
    "coolant_temperature": {
      "count": 14,
      "minimum": 28.0,
      "maximum": 44.0,
      "average": 34.86,
      "first": 30.0,
      "last": 44.0,
      "units": "°C"
    },
    "intake_air_temperature": {
      "count": 14,
      "minimum": 26.0,
      "maximum": 30.0,
      "average": 27.93,
      "first": 30.0,
      "last": 28.0,
      "units": "°C"
    },
    "engine_load": {
      "count": 14,
      "minimum": 0.0,
      "maximum": 87.45,
      "average": 26.97,
      "first": 0.0,
      "last": 0.0,
      "units": "%"
    },
    "throttle_position": {
      "count": 14,
      "minimum": 14.12,
      "maximum": 25.1,
      "average": 18.21,
      "first": 17.65,
      "last": 17.65,
      "units": "%"
    },
    "mass_air_flow": {
      "count": 14,
      "minimum": 0.71,
      "maximum": 28.63,
      "average": 6.33,
      "first": 0.71,
      "last": 0.71,
      "units": "g/s"
    },
    "map_pressure": {
      "count": 14,
      "minimum": 38.0,
      "maximum": 97.0,
      "average": 82.07,
      "first": 97.0,
      "last": 97.0,
      "units": "kPa"
    },
    "fuel_level": {
      "count": 14,
      "minimum": 12.55,
      "maximum": 54.9,
      "average": 35.97,
      "first": 39.22,
      "last": 52.94,
      "units": "%"
    },
    "timing_advance": {
      "count": 14,
      "minimum": -10.0,
      "maximum": 32.5,
      "average": 2.57,
      "first": 0.0,
      "last": -10.0,
      "units": "degrees"
    },
    "control_module_voltage": {
      "count": 14,
      "minimum": 14.51,
      "maximum": 14.72,
      "average": 14.62,
      "first": 14.64,
      "last": 14.64,
      "units": "V"
    },
    "short_trim": {
      "count": 14,
      "minimum": -28.91,
      "maximum": 0.0,
      "average": -3.91,
      "first": 0.0,
      "last": 0.0,
      "units": "%"
    },
    "session": {
      "start_time": "2026-10-28T14:38:51.252876-05:00",
      "end_time": "2026-10-28T14:40:40.034539-05:00",
      "duration_seconds": 108.78,
      "speed_unit": "mph"
    }
  },
  "data_quality": {
    "total_samples": 14,
    "samples_with_timestamp": 14,
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
      "timing_advance",
      "control_module_voltage",
      "short_trim"
    ],
    "unavailable_sensors": [
      "fuel_pressure",
      "hybrid_battery_life"
    ],
    "total_expected_sensor_values": 168,
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
      "fuel_pressure": 14,
      "timing_advance": 0,
      "control_module_voltage": 0,
      "short_trim": 0,
      "hybrid_battery_life": 14
    },
    "missing_value_percentage": 0.0,
    "median_sample_interval_seconds": 6.73,
    "maximum_sample_interval_seconds": 6.77
  }
}

print(analyze_vehicle_data({
    "make": "Ford",
    "model": "C-Max",
    "year": 2016,
},session))