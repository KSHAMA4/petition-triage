from contracts.petition import Petition, quarantine
from pydantic import ValidationError

good = {"petition_id": "P001", "student_ref": "SYN0001", "petition_type": "attendance",
        "semester": 3, "attendance_percentage": 68.0, "has_medical_documentation": True,
        "description": "Attendance 68 percent due to documented medical emergency."}
print("valid:", Petition(**good).petition_id)

bad = {"petition_id": "P2", "student_ref": "bad", "petition_type": "attendance",
       "semester": 12, "description": "short"}
try:
    Petition(**bad)
except ValidationError as e:
    quarantine(bad, e)
    print("quarantined; see quarantine/rejected.jsonl")