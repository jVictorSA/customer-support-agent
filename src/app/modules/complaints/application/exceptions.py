from app.core.exceptions import NotFoundError


class ComplaintNotFoundError(NotFoundError):
    code = "complaint_not_found"
    message = "Complaint not found"
