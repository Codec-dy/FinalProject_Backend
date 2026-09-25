import datetime

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from uuid import UUID
from sqlalchemy.orm import Session

from .models.driving_session import DrivingSession
from .models.user import User
from .models.vehicle import Vehicle
from .models.diagnostic import Diagnostics
from .models.telemetry import Telemetry
from .database.databaseConnection import engine, get_db
from .routes.vehicle_visualization import router as vehicle_visualization_router


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
                hybrid_battery_life=data.hybrid_battery_life
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
def start_driving_session(vehicle_id: str, db: Session = Depends(get_db)):
    try:
        driving_session = DrivingSession(
            vehicle_id=UUID(vehicle_id),
            start_time=datetime.datetime.utcnow()
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
def end_driving_session(driving_session_id: str, db: Session = Depends(get_db)):
    try:
        driving_session = db.query(DrivingSession).filter(DrivingSession.id == UUID(driving_session_id)).first()
        if not driving_session:
            return {"message": "Driving session not found", "success": False}
        
        driving_session.end_time = datetime.datetime.utcnow()
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



# @app.get("/")
# async def root():
#     return {"message": "Hello World"}

# @app.get("/items/{item_id}")
# async def read_item(item_id: int, q: str = None):
#     return {"item_id": item_id, "q": q}

# @app.post("/item/")
# async def create_item(item: Item):
#     return [item.name, item.description, item.price, item.tax]