"""Server-Sent Events — 'new prediction available' pushes (§3 realtime row)."""
from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse

from app.services.events import event_stream

router = APIRouter(prefix="/api", tags=["events"])


@router.get("/events")
async def sse_events():
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
