import argparse
import asyncio
import json
from typing import Sequence
from sqlalchemy.exc import SQLAlchemyError

from ai.runtime import has_api_key
from config.secret_store import secret_store
from config.store import config_store
from db.session import init_db
from intent import router as intent_router
from orchestrator import engine as orchestrator
from plugins import describe_plugins, load_plugins, scaffold_plugin
from permissions import list_permissions, set_permission
from tunnel import manager as tunnel_manager
from tunnel.pairing import get_pairing_data, rotate_token
from tools.registry import list_tools, load_default_tools

_runtime_ready = False


async def run_command(command: str, *, output_json: bool = False) -> int:
    await _init_runtime()

    task = await intent_router.route(command)
    if not task.steps:
        result = {
            "task_id": task.id,
            "status": "failed",
            "summary": "실행 가능한 작업을 찾지 못했습니다.",
            "results": [],
        }
        _print_result(result, output_json)
        return 1

    persist = True
    try:
        await orchestrator.save_pending(task)
    except SQLAlchemyError:
        persist = False

    task = await orchestrator.run(task, persist=persist)
    result = {
        "task_id": task.id,
        "status": task.status,
        "summary": task.summary,
        "results": task.results,
        "error": task.error or None,
        "persisted": persist,
    }
    _print_result(result, output_json)
    return 0 if task.status == "done" else 1


async def repl(*, output_json: bool = False) -> int:
    await _init_runtime()
    print("Agent CLI REPL")
    print("종료하려면 exit 또는 quit 를 입력하세요.")

    while True:
        try:
            command = input("> ").strip()
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print()
            return 0

        if not command:
            continue
        if command.lower() in {"exit", "quit"}:
            return 0

        exit_code = await run_command(command, output_json=output_json)
        if exit_code != 0 and output_json:
            continue


async def print_tools(*, output_json: bool = False) -> int:
    await _init_runtime()
    tools = {"tools": list_tools()}
    if output_json:
        print(json.dumps(tools, ensure_ascii=False, indent=2))
    else:
        print("Available tools:")
        for tool in tools["tools"]:
            print(f"- {tool['name']}: {tool['description']}")
    return 0


async def print_status(*, output_json: bool = False) -> int:
    await _init_runtime()
    tunnel_url = tunnel_manager.get_url()
    result = {
        "tunnel": {
            "mode": config_store.get("tunnel_mode", "none"),
            "active": bool(tunnel_url),
            "url": tunnel_url or None,
            "cloudflared_installed": tunnel_manager.is_installed(),
            "error": tunnel_manager.get_last_error(),
        },
        "ai": {
            "configured": has_api_key(),
            "storage_backend": secret_store.backend("anthropic_api_key"),
        },
    }
    _print_result(result, output_json)
    return 0


async def configure_ai_key(api_key: str, *, output_json: bool = False) -> int:
    success, error = secret_store.set("anthropic_api_key", api_key.strip())
    result = {
        "success": success,
        "configured": success,
        "storage_backend": secret_store.backend("anthropic_api_key"),
        "error": error,
    }
    _print_result(result, output_json)
    return 0 if success else 1


async def remove_ai_key(*, output_json: bool = False) -> int:
    success, error = secret_store.delete("anthropic_api_key")
    result = {"success": success, "configured": False, "error": error}
    _print_result(result, output_json)
    return 0 if success else 1


async def configure_quick_tunnel(*, output_json: bool = False) -> int:
    await _init_runtime()
    config_store.set("tunnel_mode", "quick")
    config_store.delete("cloudflare_tunnel_token")
    await tunnel_manager.stop()
    url = await tunnel_manager.start()
    success = bool(url)
    result = {"success": success, "mode": "quick", "url": url or None, "error": tunnel_manager.get_last_error()}
    _print_result(result, output_json)
    return 0 if success else 1


async def configure_cloudflare_tunnel(token: str, *, output_json: bool = False) -> int:
    await _init_runtime()
    config_store.set("tunnel_mode", "cloudflare")
    config_store.set("cloudflare_tunnel_token", token.strip())
    await tunnel_manager.stop()
    url = await tunnel_manager.start()
    success = bool(url)
    result = {
        "success": success,
        "mode": "cloudflare",
        "url": url or None,
        "error": tunnel_manager.get_last_error(),
    }
    _print_result(result, output_json)
    return 0 if success else 1


async def reset_tunnel(*, output_json: bool = False) -> int:
    config_store.set("tunnel_mode", "none")
    config_store.delete("cloudflare_tunnel_token")
    await tunnel_manager.stop()
    result = {"success": True, "mode": "none", "url": None}
    _print_result(result, output_json)
    return 0


async def print_pair_data(*, rotate: bool = False, output_json: bool = False) -> int:
    await _init_runtime()
    if rotate:
        rotate_token()
    url = tunnel_manager.get_url()
    if not url:
        result = {
            "success": False,
            "status": "tunnel_not_ready",
            "error": tunnel_manager.get_last_error() or "tunnel is not active",
        }
        _print_result(result, output_json)
        return 1
    result = {"success": True, "status": "ready", **get_pairing_data(url)}
    _print_result(result, output_json)
    return 0


async def print_plugins(*, output_json: bool = False) -> int:
    await _init_runtime()
    result = {"plugins": describe_plugins()}
    _print_result(result, output_json)
    return 0


async def create_plugin_scaffold(name: str, plugin_type: str, *, output_json: bool = False) -> int:
    path = scaffold_plugin(name, plugin_type=plugin_type)
    result = {
        "success": True,
        "name": path.name,
        "path": str(path),
        "type": plugin_type,
    }
    _print_result(result, output_json)
    return 0


async def print_permissions(*, output_json: bool = False) -> int:
    await _init_runtime()
    result = {
        "permissions": list_permissions(
            ai_configured=has_api_key(),
            tunnel_configured=config_store.get("tunnel_mode", "none") in {"quick", "cloudflare"},
        )
    }
    _print_result(result, output_json)
    return 0


async def set_permission_state(permission_id: str, granted: bool, *, output_json: bool = False) -> int:
    set_permission(permission_id, granted)
    result = {"success": True, "permission_id": permission_id, "granted": granted}
    _print_result(result, output_json)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-cli",
        description="Sigorjob CLI for headless environments",
    )
    subparsers = parser.add_subparsers(dest="subcommand")

    serve = subparsers.add_parser("serve", help="Run the FastAPI backend server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    run = subparsers.add_parser("run", help="Run a single command")
    run.add_argument("command", nargs="+", help="Natural language command to execute")
    run.add_argument("--json", action="store_true", help="Print machine-readable JSON output")

    repl_parser = subparsers.add_parser("repl", help="Start an interactive CLI session")
    repl_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output")

    tools = subparsers.add_parser("tools", help="List available tools")
    tools.add_argument("--json", action="store_true", help="Print machine-readable JSON output")

    status = subparsers.add_parser("status", help="Show tunnel and AI configuration status")
    status.add_argument("--json", action="store_true", help="Print machine-readable JSON output")

    ai = subparsers.add_parser("ai", help="Manage AI key configuration")
    ai_subparsers = ai.add_subparsers(dest="ai_command", required=True)
    ai_set = ai_subparsers.add_parser("set", help="Store Anthropic API key")
    ai_set.add_argument("api_key")
    ai_set.add_argument("--json", action="store_true", help="Print machine-readable JSON output")
    ai_remove = ai_subparsers.add_parser("remove", help="Remove stored Anthropic API key")
    ai_remove.add_argument("--json", action="store_true", help="Print machine-readable JSON output")

    tunnel = subparsers.add_parser("tunnel", help="Manage remote tunnel mode")
    tunnel_subparsers = tunnel.add_subparsers(dest="tunnel_command", required=True)
    tunnel_quick = tunnel_subparsers.add_parser("quick", help="Start quick tunnel")
    tunnel_quick.add_argument("--json", action="store_true", help="Print machine-readable JSON output")
    tunnel_cf = tunnel_subparsers.add_parser("cloudflare", help="Start Cloudflare token tunnel")
    tunnel_cf.add_argument("token")
    tunnel_cf.add_argument("--json", action="store_true", help="Print machine-readable JSON output")
    tunnel_reset = tunnel_subparsers.add_parser("reset", help="Stop and clear tunnel configuration")
    tunnel_reset.add_argument("--json", action="store_true", help="Print machine-readable JSON output")

    pair = subparsers.add_parser("pair", help="Show pairing information")
    pair.add_argument("--rotate-token", action="store_true", help="Rotate pairing token before printing")
    pair.add_argument("--json", action="store_true", help="Print machine-readable JSON output")

    plugins = subparsers.add_parser("plugins", help="Manage local Sigorjob plugins")
    plugins_subparsers = plugins.add_subparsers(dest="plugins_command", required=True)
    plugins_list = plugins_subparsers.add_parser("list", help="List installed plugins")
    plugins_list.add_argument("--json", action="store_true", help="Print machine-readable JSON output")
    plugins_scaffold = plugins_subparsers.add_parser("scaffold", help="Create a plugin scaffold")
    plugins_scaffold.add_argument("name")
    plugins_scaffold.add_argument(
        "--type",
        choices=["tool", "rules", "hybrid"],
        default="hybrid",
        help="What kind of plugin scaffold to create",
    )
    plugins_scaffold.add_argument("--json", action="store_true", help="Print machine-readable JSON output")

    permissions = subparsers.add_parser("permissions", help="Manage permission states for integrations and plugins")
    permissions_subparsers = permissions.add_subparsers(dest="permissions_command", required=True)
    permissions_list = permissions_subparsers.add_parser("list", help="List current permissions")
    permissions_list.add_argument("--json", action="store_true", help="Print machine-readable JSON output")
    permissions_grant = permissions_subparsers.add_parser("grant", help="Mark a permission as allowed")
    permissions_grant.add_argument("permission_id")
    permissions_grant.add_argument("--json", action="store_true", help="Print machine-readable JSON output")
    permissions_revoke = permissions_subparsers.add_parser("revoke", help="Mark a permission as not allowed")
    permissions_revoke.add_argument("permission_id")
    permissions_revoke.add_argument("--json", action="store_true", help="Print machine-readable JSON output")

    return parser


async def dispatch(args: argparse.Namespace) -> int:
    subcommand = args.subcommand or "serve"

    if subcommand == "run":
        return await run_command(" ".join(args.command), output_json=args.json)
    if subcommand == "repl":
        return await repl(output_json=args.json)
    if subcommand == "tools":
        return await print_tools(output_json=args.json)
    if subcommand == "status":
        return await print_status(output_json=args.json)
    if subcommand == "ai":
        if args.ai_command == "set":
            return await configure_ai_key(args.api_key, output_json=args.json)
        if args.ai_command == "remove":
            return await remove_ai_key(output_json=args.json)
    if subcommand == "tunnel":
        if args.tunnel_command == "quick":
            return await configure_quick_tunnel(output_json=args.json)
        if args.tunnel_command == "cloudflare":
            return await configure_cloudflare_tunnel(args.token, output_json=args.json)
        if args.tunnel_command == "reset":
            return await reset_tunnel(output_json=args.json)
    if subcommand == "pair":
        return await print_pair_data(rotate=args.rotate_token, output_json=args.json)
    if subcommand == "plugins":
        if args.plugins_command == "list":
            return await print_plugins(output_json=args.json)
        if args.plugins_command == "scaffold":
            return await create_plugin_scaffold(args.name, args.type, output_json=args.json)
    if subcommand == "permissions":
        if args.permissions_command == "list":
            return await print_permissions(output_json=args.json)
        if args.permissions_command == "grant":
            return await set_permission_state(args.permission_id, True, output_json=args.json)
        if args.permissions_command == "revoke":
            return await set_permission_state(args.permission_id, False, output_json=args.json)

    raise ValueError(f"unknown subcommand: {subcommand}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if (args.subcommand or "serve") == "serve":
        import uvicorn

        uvicorn.run(
            "gateway.app:app",
            host=args.host,
            port=args.port,
            reload=False,
        )
        return 0

    return asyncio.run(dispatch(args))


async def _init_runtime() -> None:
    global _runtime_ready
    if _runtime_ready:
        return
    try:
        await init_db()
    except SQLAlchemyError:
        pass
    load_default_tools()
    load_plugins()
    _runtime_ready = True


def _print_result(result: dict, output_json: bool) -> None:
    if output_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if "tunnel" in result or "ai" in result:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if "plugins" in result:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if "success" in result and "task_id" not in result:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(f"[{result['status']}] {result['task_id']}")
    if result.get("persisted") is False:
        print("warning: task history could not be persisted; running in ephemeral mode")
    if result.get("summary"):
        print(result["summary"])
    if result.get("error"):
        print(f"error: {result['error']}")
    for index, step_result in enumerate(result.get("results", []), start=1):
        status = "ok" if step_result.get("success") else "failed"
        payload = step_result.get("data") if step_result.get("success") else step_result.get("error")
        print(f"{index}. {status}: {payload}")
