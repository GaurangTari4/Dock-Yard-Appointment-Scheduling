from datetime import datetime
from pydantic import BaseModel, Field
class AppointmentCreate(BaseModel):
    facility_id: str; vehicle_id: str; shipment_id: str; appointment_type: str
    requested_start_ts: datetime
class ScheduleRequest(BaseModel):
    start_ts: datetime | None = None
    candidate_intervals: int = Field(default=1, ge=1, le=48)
    interval_minutes: int = Field(default=15, ge=5, le=120)
    approved_override: bool = False
    override_reason: str | None = None
class ArrivalRequest(BaseModel): event_ts: datetime | None = None; source: str='API'; actor: str='system'
class ExceptionOut(BaseModel): exception_id:str; appointment_id:str|None=None; issue_type:str; cause_code:str; severity:str; status:str
