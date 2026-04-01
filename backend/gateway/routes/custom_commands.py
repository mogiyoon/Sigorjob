from fastapi import APIRouter
from pydantic import BaseModel

from custom_commands import create_custom_command, delete_custom_command, list_custom_commands

router = APIRouter()


class CustomCommandRequest(BaseModel):
    trigger: str
    action_text: str
    match_type: str = "contains"


@router.get("/custom-commands")
async def get_custom_commands():
    return {"custom_commands": list_custom_commands()}


@router.post("/custom-commands")
async def add_custom_command(req: CustomCommandRequest):
    trigger = req.trigger.strip()
    action_text = req.action_text.strip()
    if not trigger or not action_text:
        return {"success": False, "error": "trigger and action_text are required"}
    item = create_custom_command(trigger, action_text, match_type=req.match_type)
    return {"success": True, "custom_command": item}


@router.delete("/custom-commands/{rule_id}")
async def remove_custom_command(rule_id: str):
    deleted = delete_custom_command(rule_id)
    if not deleted:
        return {"success": False, "error": "custom command not found"}
    return {"success": True, "status": "deleted"}
