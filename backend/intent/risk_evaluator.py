import shlex

from policy import engine as policy


def evaluate(tool: str, params: dict) -> str:
    """실행 위험도 반환: low | medium | high"""
    if tool == "shell":
        try:
            command = shlex.split(params.get("command", ""))
        except ValueError:
            return policy.get_risk_level("shell_execution")

        if not command:
            return policy.get_risk_level("shell_execution")

        low_risk_commands = {
            "ls",
            "pwd",
            "echo",
            "cat",
            "grep",
            "find",
            "head",
            "tail",
            "wc",
            "sort",
            "uniq",
            "diff",
            "git",
        }
        if command[0] in low_risk_commands:
            return "low"
        if command[0] in {"curl", "wget"}:
            return "medium"
        if command[0] == "pip" and len(command) > 1 and command[1] == "install":
            return "medium"
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
