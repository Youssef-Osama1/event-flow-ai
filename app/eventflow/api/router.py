from fastapi import APIRouter

from eventflow.api import events

router = APIRouter()
router.include_router(events.router, prefix="/events", tags=["events"])
