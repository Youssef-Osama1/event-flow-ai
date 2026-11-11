from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, EmailStr, Field


class SupportTicketEventSchema(BaseModel):
    ticket_id: UUID = Field(default_factory=uuid4, description="Server-side ticket identifier")
    received_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC time the ticket arrived",
    )
    customer_email: EmailStr = Field(description="Address the ticket was sent from")
    customer_name: str = Field(min_length=1, max_length=200, description="Customer display name")
    subject: str = Field(min_length=1, max_length=300, description="Ticket subject line")
    message: str = Field(min_length=1, max_length=8000, description="Ticket body text")
