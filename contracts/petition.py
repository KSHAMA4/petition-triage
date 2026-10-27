import json, pathlib, time
from enum import Enum
from typing import Optional, Literal
from pydantic import BaseModel, Field, ValidationError, model_validator


class PetitionType(str, Enum):
    attendance = "attendance"
    re_evaluation = "re_evaluation"
    re_registration = "re_registration"
    medical_leave = "medical_leave"
    grade_grievance = "grade_grievance"


class Petition(BaseModel):
    petition_id: str = Field(min_length=3, max_length=40)
    student_ref: str = Field(pattern=r"^SYN\d{4}$")
    petition_type: PetitionType
    semester: int = Field(ge=1, le=8)
    regulation_doc: Literal["r24ug_academic_regulations_version_3.0.pdf", "regulations_3.1.pdf"] = "r24ug_academic_regulations_version_3.0.pdf"
    course_code: Optional[str] = Field(default=None, max_length=15)
    attendance_percentage: Optional[float] = Field(default=None, ge=0, le=100)
    has_medical_documentation: bool = False
    description: str = Field(min_length=10, max_length=1000)

    @model_validator(mode="after")
    def cross_field(self):
        if self.petition_type == PetitionType.attendance and self.attendance_percentage is None:
            raise ValueError("attendance petitions require attendance_percentage")
        if self.petition_type == PetitionType.medical_leave and not self.has_medical_documentation:
            raise ValueError("medical_leave petitions require has_medical_documentation=true")
        return self


def quarantine(raw: dict, err: ValidationError):
    pathlib.Path("quarantine").mkdir(exist_ok=True)
    rec = {"received_at": time.time(), "raw": raw,
           "errors": [{"field": ".".join(map(str, e["loc"])), "msg": e["msg"]} for e in err.errors()]}
    with open("quarantine/rejected.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")