"""Per-recipient validation.

Each recipient is validated independently so one bad row never rejects the
whole job: invalid recipients are stored as FAILED with a clear error message.
"""
from datetime import date

from pydantic import BaseModel, ValidationError, field_validator


class RecipientData(BaseModel):
    name: str
    email: str
    course_name: str
    issue_date: date

    @field_validator("name", "course_name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        if len(v) > 100:
            raise ValueError("must be at most 100 characters")
        return v

    @field_validator("email")
    @classmethod
    def simple_email(cls, v: str) -> str:
        v = v.strip()
        local, sep, domain = v.partition("@")
        if not sep or not local or "." not in domain or " " in v:
            raise ValueError("must be a valid email address")
        return v


def validate_recipient(raw) -> tuple[RecipientData | None, str | None]:
    """Return (data, None) if valid, otherwise (None, human-readable error)."""
    if not isinstance(raw, dict):
        return None, "recipient must be a JSON object"
    try:
        return RecipientData(**raw), None
    except ValidationError as exc:
        msgs = []
        for err in exc.errors():
            field = ".".join(str(p) for p in err["loc"]) or "recipient"
            msgs.append(f"{field}: {err['msg']}")
        return None, "; ".join(msgs)
