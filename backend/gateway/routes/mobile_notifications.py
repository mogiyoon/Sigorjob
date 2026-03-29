from fastapi import APIRouter
from pydantic import BaseModel

from notifications.store import acknowledge, enqueue_notification, list_unread

router = APIRouter()


class AcknowledgeRequest(BaseModel):
    ids: list[str]


class TestNotificationRequest(BaseModel):
    title: str | None = None
    body: str | None = None


@router.get("/mobile/notifications")
async def get_mobile_notifications(limit: int = 20):
    notifications = list_unread(limit=limit)
    return {"notifications": notifications}


@router.post("/mobile/notifications/ack")
async def acknowledge_mobile_notifications(req: AcknowledgeRequest):
    count = acknowledge(req.ids)
    return {"success": True, "acknowledged": count}


@router.post("/mobile/notifications/test")
async def create_test_mobile_notification(req: TestNotificationRequest | None = None):
    title = req.title if req and req.title is not None else "Sigorjob test"
    body = req.body if req and req.body is not None else "This is a test notification from your desktop."
    item = enqueue_notification(title=title, body=body)
    return {"success": True, "notification": item}
