from policy import engine as policy


def evaluate(tool: str, params: dict) -> str:
    """실행 위험도 반환: low | medium | high"""
    if tool == "shell":
        command = params.get("command", "").strip().split()
        safe_commands = {"ls", "pwd", "echo"}
        if command and command[0] in safe_commands:
            return "low"
        return policy.get_risk_level("shell_execution")
    if tool == "file":
        op = params.get("operation", "read")
        if op == "read":
            return policy.get_risk_level("file_read")
        if op == "delete":
            return policy.get_risk_level("file_delete")
        return policy.get_risk_level("file_write")
    if tool == "crawler":
        return "low"
    if tool == "shopping_helper":
        if params.get("purchase_intent"):
            return "high"
        return "low"
    if tool == "browser":
        return "low"
    if tool in {"time", "system_info"}:
        return "low"
    if tool == "message":
        return policy.get_risk_level("external_message")
    return "low"
