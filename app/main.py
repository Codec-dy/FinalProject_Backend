import datetime
import json
import logging
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import APIError
from pydantic import BaseModel, Field
from uuid import UUID
from sqlalchemy.orm import Session

from .services.aiprocess import (
    OPENAI_MODEL,
    analyze_vehicle_data,
    client as openai_client,
)

from .services.summaryCalc import build_session_summary

from .models.driving_session import DrivingSession
from .models.user import User
from .models.vehicle import Vehicle
from .models.diagnostic import Diagnostics
from .models.telemetry import Telemetry
from .models.maintenance import Maintenance
from .models.session_summary import SessionSummary
from .models.vehicle_health_assessment import (
    SystemHealthAssessment,
    VehicleHealthAssessment,
    VehicleHealthFinding,
)
from .database.databaseConnection import engine, get_db
from .routes.vehicle_visualization import router as vehicle_visualization_router

logger = logging.getLogger(__name__)


class Signup(BaseModel):
    first_name: str
    last_name: str
    email: str
    password_hash: str
    phone: str  
    make: str
    model: str
    year: int
    engine: str
    vin: str
    mileage: int
    fuel_type: str

class Login(BaseModel):
    email: str
    password: str

class ChangePassword(BaseModel):
    email: str
    current_password: str
    new_password: str

class MaintenanceCreate(BaseModel):
    vehicle_id: UUID
    title: str
    scheduled_date: datetime.date
    notes: str | None = None

class VehicleUpdate(BaseModel):
    mileage: int = Field(ge=0)
    fuel_type: str

class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)

class VehicleChatRequest(BaseModel):
    vehicle_id: UUID
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatHistoryMessage] = Field(default_factory=list, max_length=12)

class DiagnosticsInfo(BaseModel):
    vehicle_id: str
    title: str
    code: str
    description: str
    severity: str
    causes: list[str]
    recommended: str
    cost_to_repair: str

class TelemetryInfo(BaseModel):
    vehicle_id: UUID | None = None
    driving_session_id: UUID | None = None
    rpm: float | None = None
    speed: float | None = None
    coolant_temperature: float | None = None
    intake_air_temperature: float | None = None
    engine_load: float | None = None
    throttle_position: float | None = None
    mass_air_flow: float | None = None
    map_pressure: float | None = None
    fuel_level: float | None = None
    fuel_pressure: float | None = None
    timing_advance: float | None = None
    control_module_voltage: float | None = None
    short_trim: float | None = None
    hybrid_battery_life: float | None = None
    timestamp: datetime.datetime | None = None


def _maintenance_payload(record: Maintenance) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "vehicle_id": str(record.vehicle_id),
        "title": record.title,
        "notes": record.notes,
        "scheduled_date": record.scheduled_date.isoformat(),
        "completed": record.completed,
        "completed_at": record.completed_at.isoformat()
        if record.completed_at
        else None,
    }


try:
    connection = engine.connect()
    print("✅ PostgreSQL Connected Successfully!")

    connection.close()

except Exception as e:
    print("❌ Connection Failed")
    print(e)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vehicle_visualization_router)


@app.on_event("startup")
def create_additional_tables() -> None:
    Maintenance.__table__.create(bind=engine, checkfirst=True)
    VehicleHealthAssessment.__table__.create(bind=engine, checkfirst=True)
    SystemHealthAssessment.__table__.create(bind=engine, checkfirst=True)
    VehicleHealthFinding.__table__.create(bind=engine, checkfirst=True)


@app.get("/api/raspberrypitest")
async def raspberry_pi_test():
    print("✅ Raspberry Pi test received")
    return {"message": f"Raspberry Pi test successful for device with message"}


#login endpoint
@app.post("/api/login")
def login(login: Login, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.email == login.email).first()
        if not user or user.password_hash != login.password:
            return {"message": "Invalid email or password", "success": False}

        userInfo = get_user_info(user_id=str(user.id), db=db)
        vehicleInfo = get_vehicle_info(user_id=str(user.id), db=db)
        print(vehicleInfo,"Here")
        diagnosticsInfo = get_diagnostics_info(vehicle_id=str(vehicleInfo["vehicle"]["id"]), db=db)
        print(diagnosticsInfo,"Here")
        return {"message": "Login successful", "user_id": str(user.id), "userInfo": userInfo, "vehicleInfo": vehicleInfo, "diagnosticsInfo":diagnosticsInfo, "success": True}
    except Exception as e:
        raise e

@app.put("/api/change-password")
def change_password(change: ChangePassword, db: Session = Depends(get_db)):
    if len(change.new_password) < 8:
        return {"message": "New password must be at least 8 characters", "success": False}

    user = db.query(User).filter(User.email == change.email).first()
    if not user or user.password_hash != change.current_password:
        return {"message": "Current password is incorrect", "success": False}

    try:
        user.password_hash = change.new_password
        db.commit()
        return {"message": "Password updated successfully", "success": True}
    except Exception:
        db.rollback()
        raise

@app.get('/api/userInfo')
def get_user_info(user_id: str, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"message": "User not found", "success": False}
        return {
            "message": "User found",
            "success": True,
            "user": {
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "phone": user.phone
            }
        }
    except Exception as e:
        raise e




@app.get("/api/vehicleInfo")
def get_vehicle_info(user_id: str, db: Session = Depends(get_db)):
    try:
        vehicle = db.query(Vehicle).filter(Vehicle.user_id == user_id).first()
        if not vehicle:
            return {"message": "Vehicle not found", "success": False}
        return {
            "message": "Vehicle found",
            "success": True,
            "vehicle": {

                "id": vehicle.id,
                "make": vehicle.make,
                "model": vehicle.model,
                "year": vehicle.year,
                "engine": vehicle.engine,
                "vin": vehicle.vin,
                "mileage": vehicle.mileage,
                "fuel_type": vehicle.fuel_type
            }
        }
    except Exception as e:
        raise e


@app.put("/api/vehicleInfo/{vehicle_id}")
def update_vehicle_info(
    vehicle_id: UUID,
    update: VehicleUpdate,
    db: Session = Depends(get_db),
):
    fuel_type = update.fuel_type.strip()
    if not fuel_type:
        raise HTTPException(status_code=400, detail="Fuel type is required")

    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    try:
        vehicle.mileage = update.mileage
        vehicle.fuel_type = fuel_type
        db.commit()
        db.refresh(vehicle)
    except Exception:
        db.rollback()
        raise

    return {
        "success": True,
        "message": "Vehicle details updated",
        "vehicle": {
            "id": str(vehicle.id),
            "make": vehicle.make,
            "model": vehicle.model,
            "year": vehicle.year,
            "engine": vehicle.engine,
            "vin": vehicle.vin,
            "mileage": vehicle.mileage,
            "fuel_type": vehicle.fuel_type,
        },
    }


@app.get("/api/maintenance")
def get_maintenance(vehicle_id: UUID, db: Session = Depends(get_db)):
    records = (
        db.query(Maintenance)
        .filter(Maintenance.vehicle_id == vehicle_id)
        .order_by(Maintenance.scheduled_date.desc(), Maintenance.created_at.desc())
        .all()
    )
    return {
        "success": True,
        "maintenance": [_maintenance_payload(record) for record in records],
    }


@app.post("/api/maintenance")
def create_maintenance(
    maintenance: MaintenanceCreate,
    db: Session = Depends(get_db),
):
    title = maintenance.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Maintenance title is required")
    if not db.query(Vehicle).filter(Vehicle.id == maintenance.vehicle_id).first():
        raise HTTPException(status_code=404, detail="Vehicle not found")

    record = Maintenance(
        vehicle_id=maintenance.vehicle_id,
        title=title,
        notes=maintenance.notes.strip() if maintenance.notes else None,
        scheduled_date=maintenance.scheduled_date,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {
        "success": True,
        "message": "Maintenance scheduled",
        "maintenance": _maintenance_payload(record),
    }


@app.put("/api/maintenance/{maintenance_id}/complete")
def complete_maintenance(
    maintenance_id: UUID,
    vehicle_id: UUID,
    db: Session = Depends(get_db),
):
    record = (
        db.query(Maintenance)
        .filter(
            Maintenance.id == maintenance_id,
            Maintenance.vehicle_id == vehicle_id,
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Maintenance schedule not found")
    if not record.completed:
        record.completed = True
        record.completed_at = datetime.datetime.now(datetime.timezone.utc)
        db.commit()
        db.refresh(record)
    return {
        "success": True,
        "message": "Maintenance marked as complete",
        "maintenance": _maintenance_payload(record),
    }


@app.delete("/api/maintenance/{maintenance_id}")
def delete_maintenance(
    maintenance_id: UUID,
    vehicle_id: UUID,
    db: Session = Depends(get_db),
):
    record = (
        db.query(Maintenance)
        .filter(
            Maintenance.id == maintenance_id,
            Maintenance.vehicle_id == vehicle_id,
            Maintenance.completed.is_(False),
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Scheduled maintenance not found")
    db.delete(record)
    db.commit()
    return {"success": True, "message": "Maintenance schedule deleted"}


@app.post("/api/vehicle-chat")
def vehicle_chat(
    request: VehicleChatRequest,
    db: Session = Depends(get_db),
):
    vehicle = db.query(Vehicle).filter(Vehicle.id == request.vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    maintenance_records = (
        db.query(Maintenance)
        .filter(Maintenance.vehicle_id == request.vehicle_id)
        .order_by(Maintenance.scheduled_date.asc())
        .limit(50)
        .all()
    )
    diagnostic_records = (
        db.query(Diagnostics)
        .filter(Diagnostics.vehicle_id == request.vehicle_id)
        .order_by(Diagnostics.detected_at.desc())
        .limit(50)
        .all()
    )
    completed_sessions = (
        db.query(DrivingSession)
        .filter(
            DrivingSession.vehicle_id == request.vehicle_id,
            DrivingSession.end_time.is_not(None),
        )
        .order_by(DrivingSession.end_time.desc())
        .limit(10)
        .all()
    )
    session_ids = [session.id for session in completed_sessions]
    summaries = (
        db.query(SessionSummary)
        .filter(SessionSummary.driving_session_id.in_(session_ids))
        .all()
        if session_ids
        else []
    )
    summary_by_session = {
        str(summary.driving_session_id): summary for summary in summaries
    }
    latest_telemetry = (
        db.query(Telemetry)
        .filter(Telemetry.vehicle_id == request.vehicle_id)
        .order_by(Telemetry.timestamp.desc())
        .first()
    )

    vehicle_context = {
        "vehicle": {
            "year": vehicle.year,
            "make": vehicle.make,
            "model": vehicle.model,
            "engine": vehicle.engine,
            "fuel_type": vehicle.fuel_type,
            "mileage": vehicle.mileage,
        },
        "maintenance": [
            {
                "title": item.title,
                "notes": item.notes,
                "scheduled_date": item.scheduled_date.isoformat(),
                "completed": item.completed,
                "completed_at": item.completed_at.isoformat()
                if item.completed_at
                else None,
            }
            for item in maintenance_records
        ],
        "diagnostic_codes": [
            {
                "code": item.code,
                "title": item.title,
                "description": item.description,
                "severity": item.severity,
                "causes": item.causes,
                "recommended": item.recommended,
                "detected_at": item.detected_at.isoformat()
                if item.detected_at
                else None,
                "cleared_at": item.cleared_at.isoformat()
                if item.cleared_at
                else None,
            }
            for item in diagnostic_records
        ],
        "completed_trips": [
            {
                "start_time": session.start_time.isoformat()
                if session.start_time
                else None,
                "end_time": session.end_time.isoformat()
                if session.end_time
                else None,
                "summary": (
                    {
                        "duration_seconds": summary_by_session[
                            str(session.id)
                        ].duration_seconds,
                        "distance": summary_by_session[str(session.id)].distance,
                        "average_speed": summary_by_session[
                            str(session.id)
                        ].average_speed,
                        "maximum_speed": summary_by_session[
                            str(session.id)
                        ].maximum_speed,
                        "total_samples": summary_by_session[
                            str(session.id)
                        ].total_samples,
                        "telemetry_summary": summary_by_session[
                            str(session.id)
                        ].telemetry_summary,
                    }
                    if str(session.id) in summary_by_session
                    else None
                ),
            }
            for session in completed_sessions
        ],
        "latest_telemetry": (
            {
                "timestamp": latest_telemetry.timestamp.isoformat()
                if latest_telemetry.timestamp
                else None,
                "rpm": latest_telemetry.rpm,
                "speed": latest_telemetry.speed,
                "coolant_temperature": latest_telemetry.coolant_temperature,
                "control_module_voltage": latest_telemetry.control_module_voltage,
                "fuel_level": latest_telemetry.fuel_level,
            }
            if latest_telemetry
            else None
        ),
    }

    try:
        response = openai_client.responses.create(
            model=OPENAI_MODEL,
            instructions=(
                "You are DriveSense AI, a helpful vehicle information assistant. "
                "Answer questions using the supplied vehicle data. Address "
                "predictive maintenance, upcoming or completed maintenance, "
                "completed trips, diagnostic trouble codes, and latest "
                "telemetry when relevant. Treat diagnostic codes as recorded "
                "evidence, not a definitive diagnosis. Never invent readings, "
                "trips, codes, or maintenance records; state when data is "
                "missing. For safety-critical or urgent symptoms, advise the "
                "user to stop driving when appropriate and consult a qualified "
                "mechanic. Keep answers clear and concise."
            ),
            input=json.dumps(
                {
                    "vehicle_data": vehicle_context,
                    "recent_conversation": [
                        message.model_dump() for message in request.history[-12:]
                    ],
                    "question": request.message.strip(),
                },
                default=str,
            ),
        )
    except APIError as error:
        logger.exception("Vehicle chat request to OpenAI failed")
        raise HTTPException(
            status_code=502,
            detail="The vehicle assistant is temporarily unavailable.",
        ) from error

    output_text = response.output_text
    answer = output_text.strip() if isinstance(output_text, str) else ""
    if not answer:
        logger.error("OpenAI returned an empty vehicle chat response")
        raise HTTPException(
            status_code=502,
            detail="The vehicle assistant returned an empty response.",
        )
    return {"success": True, "answer": answer}


@app.get("/api/diagnostics")
def get_diagnostics_info(vehicle_id: str, db: Session = Depends(get_db)):
    try:
        diagnostics = db.query(Diagnostics).filter(Diagnostics.vehicle_id == vehicle_id).all()
        if not diagnostics:
            return {"message": "No data found", "success": False}
        return {
            "message": "Vehicle found",
            "success": True,
                "diagnostics": [
                    {
                        "id": str(d.id),
                        "vehicle_id": str(d.vehicle_id),
                        "title": d.title,
                        "code": d.code,
                        "description": d.description,
                        "severity": d.severity,
                        "causes": d.causes,
                        "recommended": d.recommended,
                        "cost_to_repair": d.cost_to_repair,
                        "detected_at": d.detected_at.isoformat(),
                        "cleared_at": d.cleared_at.isoformat() if d.cleared_at else None
                    } for d in diagnostics
                ]
            
        }
    except Exception as e:
        raise e

@app.post("/api/telemetry")
def add_telemetry_data(telemetry: list[TelemetryInfo], db: Session = Depends(get_db)):
    try:
        telemetry_records = []
        for data in telemetry:
            telemetry_data = Telemetry(
                vehicle_id=data.vehicle_id,
                driving_session_id=data.driving_session_id,
                rpm=data.rpm,
                speed=data.speed,
                coolant_temperature=data.coolant_temperature,
                intake_air_temperature=data.intake_air_temperature,
                engine_load=data.engine_load,
                throttle_position=data.throttle_position,
                mass_air_flow=data.mass_air_flow,
                map_pressure=data.map_pressure,
                fuel_level=data.fuel_level,
                fuel_pressure=data.fuel_pressure,
                timing_advance=data.timing_advance,
                control_module_voltage=data.control_module_voltage,
                short_trim=data.short_trim,
                hybrid_battery_life=data.hybrid_battery_life,
                timestamp=data.timestamp
            )
            db.add(telemetry_data)
            telemetry_records.append(telemetry_data)

        if not telemetry_records:
            return {"message": "Telemetry list cannot be empty", "success": False}

        db.commit()
        db.refresh(telemetry_records[-1])
        return {
            "message": "Telemetry data added successfully",
            "success": True,
            "telemetry_id": str(telemetry_records[-1].id)
        }
    except Exception as e:
        db.rollback()
        raise e

@app.get("/api/telemetry")
def get_telemetry_data(vehicle_id: str, db: Session = Depends(get_db)):
    try:
        telemetry_data = db.query(Telemetry).filter(Telemetry.vehicle_id == vehicle_id).all()
        if not telemetry_data:
            return {"message": "No telemetry data found", "success": False}
        return {
            "message": "Telemetry data found",
            "success": True,
            "telemetry": [
                {
                    "id": str(t.id),
                    "vehicle_id": str(t.vehicle_id),
                    "timestamp": t.timestamp.isoformat(),
                    "rpm": t.rpm,
                    "speed": t.speed,
                    "coolant_temperature": t.coolant_temperature,
                    "intake_air_temperature": t.intake_air_temperature,
                    "engine_load": t.engine_load,
                    "throttle_position": t.throttle_position,
                    "mass_air_flow": t.mass_air_flow,
                    "map_pressure": t.map_pressure,
                    "fuel_level": t.fuel_level,
                    "fuel_pressure": t.fuel_pressure,
                    "timing_advance": t.timing_advance,
                    "control_module_voltage": t.control_module_voltage,
                    "short_trim": t.short_trim,
                    "hybrid_battery_life": t.hybrid_battery_life
                } for t in telemetry_data
            ]
        }
    except Exception as e:
        raise e

@app.post("/api/driving_sessions/start")
def start_driving_session(vehicle_id: str, start_time: datetime.datetime = None, db: Session = Depends(get_db)):
    try:
        driving_session = DrivingSession(
            vehicle_id=UUID(vehicle_id),
            start_time=start_time
        )
        db.add(driving_session)
        db.flush()
        db.commit()
        db.refresh(driving_session)
        return {
            "message": "Driving session started successfully",
            "success": True,
            "driving_session_id": str(driving_session.id)
        }
    except Exception as e:
        db.rollback()
        raise e

@app.put("/api/driving_sessions/end")
def end_driving_session(driving_session_id: str, end_time: datetime.datetime = None, db: Session = Depends(get_db)):
    try:
        driving_session = db.query(DrivingSession).filter(DrivingSession.id == UUID(driving_session_id)).first()
        if not driving_session:
            return {"message": "Driving session not found", "success": False}
        
        driving_session.end_time = end_time or datetime.datetime.now(
            datetime.timezone.utc
        )
        db.commit()
        db.refresh(driving_session)
        return {
            "message": "Driving session ended successfully",
            "success": True,
            "driving_session_id": str(driving_session.id)
        }
    except Exception as e:
        db.rollback()
        raise e

@app.get("/api/driving_sessions")
def get_driving_sessions(vehicle_id:str, db:Session=Depends(get_db)):
    try:
        driving_sessions = db.query(DrivingSession).filter(
            DrivingSession.vehicle_id == UUID(vehicle_id)
        ).all()
        if not driving_sessions:
            return {"message":"No driving sessions found", "success": True}

        session_list = [
            {
                "id": str(session.id),
                "vehicle_id": str(session.vehicle_id),
                "start_time": session.start_time.isoformat() if session.start_time else None,
                "end_time": session.end_time.isoformat() if session.end_time else None,
                "telemetry":session.telemetry
            }
            for session in driving_sessions
        ]

        return {
            "message":"Driving sessions found",
            "success":True,
            "session_list": session_list
        }
    except Exception as e:
        raise e

@app.post("/api/diagnostics")
def add_diagnostics_info(info: DiagnosticsInfo, db: Session = Depends(get_db)):
    print(info)
    try:
        data = Diagnostics(
            vehicle_id = UUID(info.vehicle_id),
            title = info.title,
            code = info.code,
            description = info.description,
            severity = info.severity,
            causes = info.causes,
            recommended = info.recommended,
            cost_to_repair = info.cost_to_repair
        )
        db.add(data)
        db.flush()
        db.commit()
        db.refresh(data)
        return {
            "message": "Diagnostics info added successfully",
            "success": True,
            "diagnostics_id": str(data.id)
        }
    except Exception as e:
        db.rollback()
        raise e



#SummaryRoute
@app.get('/api/summary')
def create_session_summary(drivingSession, db: Session = Depends(get_db)):
    try:
        summary = build_session_summary(
            db=db,
            driving_session_id=drivingSession
        )


        summary_data = {
            "id": str(summary.id),
            "driving_session_id": str(summary.driving_session_id),
            "vehicle_id":str(summary.vehicle_id),
            "duration_seconds": summary.duration_seconds,
            "distance": summary.distance,
            "average_speed": summary.average_speed,
            "average_moving_speed": summary.average_moving_speed,
            "maximum_speed": summary.maximum_speed,
            "total_samples": summary.total_samples,
            "telemetry_summary": summary.telemetry_summary,
            "data_quality": summary.data_quality,
            "samples":summary.samples
        }
        existing_summary = db.query(SessionSummary).filter(
        SessionSummary.driving_session_id == summary_data["driving_session_id"]
    ).first()

        if existing_summary:
            # Update existing summary
            existing_summary.vehicle_id = summary_data["vehicle_id"]
            existing_summary.duration_seconds = summary_data["duration_seconds"]
            existing_summary.distance = summary_data["distance"]
            existing_summary.average_speed = summary_data["average_speed"]
            existing_summary.average_moving_speed = summary_data["average_moving_speed"]
            existing_summary.maximum_speed = summary_data["maximum_speed"]
            existing_summary.total_samples = summary_data["total_samples"]
            existing_summary.telemetry_summary = summary_data["telemetry_summary"]
            existing_summary.data_quality = summary_data["data_quality"]

            summary = existing_summary

        else:
            # Create a new summary
            summary = SessionSummary(
                driving_session_id=summary_data["driving_session_id"],
                vehicle_id=summary_data["vehicle_id"],
                duration_seconds=summary_data["duration_seconds"],
                distance=summary_data["distance"],
                average_speed=summary_data["average_speed"],
                average_moving_speed=summary_data["average_moving_speed"],
                maximum_speed=summary_data["maximum_speed"],
                total_samples=summary_data["total_samples"],
                telemetry_summary=summary_data["telemetry_summary"],
                data_quality=summary_data["data_quality"],
            )

            db.add(summary)

        db.commit()
        db.refresh(summary)
        return summary_data


    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc)
        )

#AIProcess
@app.get('/api/analyze_session')
def analyze_session(drivingSession=None, db: Session = Depends(get_db)):
    if drivingSession is not None:
        
        session = create_session_summary(drivingSession,db)
    else:
        #get the last driving session
        last_session = db.query(DrivingSession).filter(DrivingSession.end_time.is_not(None)).order_by(DrivingSession.end_time.desc()).first()
        if not last_session:
            raise HTTPException(status_code=404, detail="No completed driving session found")
        
        session = create_session_summary(last_session.id,db)

    vehicle = db.query(Vehicle).filter(Vehicle.id ==session["vehicle_id"]).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    analysis = analyze_vehicle_data({
    "make": vehicle.make,
    "model": vehicle.model,
    "year": vehicle.year,
},session)
    try:
        # 4. Save overall health assessment
        assessment = VehicleHealthAssessment(
            vehicle_id=vehicle.id,
            driving_session_id=drivingSession,
            overall_status=analysis.overall_status,
            overall_summary=analysis.overall_summary,
            data_quality=analysis.data_quality.quality,
            missing_value_percentage=(
                analysis.data_quality.missing_value_percentage
            ),
            analysis_model="OpenAI",
            analysis_version="1.0",
        )

        db.add(assessment)
        db.flush()

        # 5. Save the five system assessments
        system_results = [
            analysis.engine_health,
            analysis.transmission_health,
            analysis.brake_system_health,
            analysis.battery_12v_health,
            analysis.coolant_system_health,
        ]

        for system in system_results:

            system_record = SystemHealthAssessment(
                assessment_id=assessment.id,
                system=system.system,
                status=system.status,
                summary=system.summary,
                supporting_evidence=system.supporting_evidence,
                limitations=system.limitations,
            )

            db.add(system_record)
            db.flush()

            # 6. Save findings for this system
            for finding in system.findings:

                finding_record = VehicleHealthFinding(
                    system_assessment_id=system_record.id,
                    category=finding.category,
                    title=finding.title,
                    observed_evidence=finding.observed_evidence,
                    interpretation=finding.interpretation,
                    severity=finding.severity,
                    confidence=finding.confidence,
                    recommended_actions=finding.recommended_actions,
                )

                db.add(finding_record)

        # 7. Commit all records
        db.commit()

        # 8. Return the original AI analysis
        return analysis

    except Exception:
        db.rollback()
        raise

# Signup endpoint
@app.post("/api/signup")
def signup(signup: Signup, db: Session = Depends(get_db)):
    try:
        user = User(
            first_name=signup.first_name,
            last_name=signup.last_name,
            email=signup.email,
            password_hash=signup.password_hash,
            phone=signup.phone,
        )
        db.add(user)
        db.flush()

        vehicle = Vehicle(
            make=signup.make,
            model=signup.model,
            year=signup.year,
            user_id=user.id,
            engine=signup.engine,
            vin=signup.vin,
            mileage=signup.mileage,
            fuel_type=signup.fuel_type
        )
        db.add(vehicle)
        db.commit()
        db.refresh(vehicle)

        return {
            "message": "Signup successful",
            "user_id": str(user.id),
            "vehicle_id": str(vehicle.id),
        }
    except Exception as e:
        db.rollback()
        raise e
        # raise e
