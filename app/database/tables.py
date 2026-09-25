from .databaseConnection import engine
from .base import Base

# Import every model
from ..models.user import User
from ..models.vehicle import Vehicle
from ..models.driving_session import DrivingSession
from ..models.telemetry import Telemetry
from ..models.diagnostic import Diagnostics
# from ..models.maintenance import Maintenance
# from ..models.ai_report import AIReport
# from ..models.health_report import HealthReport
# from ..models.alert import Alert


Base.metadata.create_all(bind=engine)

print("✅ All DriveSense AI tables created successfully.")