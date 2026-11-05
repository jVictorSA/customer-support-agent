from dataclasses import dataclass

from app.modules.complaints.domain.complaint import Complaint


@dataclass(frozen=True, slots=True)
class RegisterComplaintResult:
    complaint: Complaint
    already_open: bool
