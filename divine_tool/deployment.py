from __future__ import annotations

import json
import os
import shutil
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from . import __version__
from .core import (
    DivineToolError,
    auth_status,
    connect,
    database_status,
    ensure_state,
    list_accounts,
    load_config,
    worker_status,
)


TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def env_bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise DivineToolError(f"Invalid boolean environment value: {value}")


def env_int(value: str | None, default: int, *, name: str, minimum: int = 1) -> int:
    if value is None or value == "":
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise DivineToolError(f"{name} must be an integer.") from exc
    if parsed < minimum:
        raise DivineToolError(f"{name} must be at least {minimum}.")
    return parsed


def normalize_origin(value: str, *, name: str = "origin") -> str:
    candidate = value.strip().rstrip("/")
    try:
        parsed = urllib.parse.urlsplit(candidate)
        port = parsed.port
    except ValueError as exc:
        raise DivineToolError(f"{name} is not a valid HTTP origin.") from exc
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise DivineToolError(f"{name} must be an exact http:// or https:// origin without a path.")
    host = parsed.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    default_port = 80 if parsed.scheme.lower() == "http" else 443
    port_suffix = f":{port}" if port and port != default_port else ""
    return f"{parsed.scheme.lower()}://{host}{port_suffix}"


def allowed_origins(value: str | None, public_origin: str) -> list[str]:
    candidates = [public_origin] if public_origin else []
    candidates.extend(item.strip() for item in (value or "").split(",") if item.strip())
    normalized: list[str] = []
    for index, candidate in enumerate(candidates, start=1):
        origin = normalize_origin(candidate, name=f"allowed origin {index}")
        if origin not in normalized:
            normalized.append(origin)
    return normalized


def deployment_environment(
    environ: Mapping[str, str] | None = None,
    cwd: Path | None = None,
) -> dict[str, Any]:
    env = os.environ if environ is None else environ
    root = cwd or Path.cwd()
    raw_data_dir = env.get("DIVINE_DATA_DIR", str(root / ".divine_tool"))
    data_dir = Path(raw_data_dir).expanduser()
    if not data_dir.is_absolute():
        data_dir = root / data_dir

    backup_dir = Path(env.get("DIVINE_BACKUP_DIR", str(data_dir / "backups"))).expanduser()
    if not backup_dir.is_absolute():
        backup_dir = data_dir / backup_dir

    mode = env.get("DIVINE_DEPLOYMENT_MODE", "local").strip().lower() or "local"
    public_url = env.get("DIVINE_PUBLIC_URL", "").strip().rstrip("/")
    public_origin = normalize_origin(public_url, name="DIVINE_PUBLIC_URL") if public_url else ""
    origin_allowlist = allowed_origins(env.get("DIVINE_ALLOWED_ORIGINS"), public_origin)
    hosted_https = public_origin.startswith("https://")
    hosted_mode = mode not in {"local", "development", "test"}
    secure_by_default = hosted_mode or hosted_https

    return {
        "mode": mode,
        "data_dir": data_dir.resolve(),
        "backup_dir": backup_dir.resolve(),
        "host": env.get("DIVINE_HOST", "127.0.0.1"),
        "port": env_int(env.get("DIVINE_PORT"), 8765, name="DIVINE_PORT"),
        "daemon_interval": env_int(
            env.get("DIVINE_DAEMON_INTERVAL"),
            300,
            name="DIVINE_DAEMON_INTERVAL",
        ),
        "public_url": public_url,
        "public_origin": public_origin,
        "allowed_origins": origin_allowlist,
        "cookie_secure": env_bool(env.get("DIVINE_COOKIE_SECURE"), secure_by_default),
        "csrf_require_origin": env_bool(env.get("DIVINE_CSRF_REQUIRE_ORIGIN"), hosted_mode or bool(public_origin)),
        "trust_proxy": env_bool(env.get("DIVINE_TRUST_PROXY"), False),
        "force_https": env_bool(env.get("DIVINE_FORCE_HTTPS"), secure_by_default),
    }


def deployment_preflight(
    data_dir: Path,
    *,
    host: str,
    port: int,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    raw_env = os.environ if environ is None else environ
    env = deployment_environment(raw_env)
    env["data_dir"] = data_dir.resolve()
    checks: list[dict[str, str]] = []

    try:
        ensure_state(data_dir)
        checks.append(check("state", "pass", f"State directory is available: {data_dir}"))
    except Exception as exc:
        checks.append(check("state", "fail", f"State directory cannot be initialized: {exc}"))

    try:
        probe = data_dir / ".deploy-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        checks.append(check("writable_state", "pass", "State directory is writable."))
    except Exception as exc:
        checks.append(check("writable_state", "fail", f"State directory is not writable: {exc}"))

    try:
        sqlite_status = database_status(data_dir)
        if not sqlite_status["ready"]:
            raise DivineToolError("SQLite runtime guarantees are incomplete.")
        checks.append(
            check(
                "database",
                "pass",
                "SQLite is ready with WAL, foreign keys, "
                f"a {sqlite_status['busy_timeout_ms']} ms busy timeout, and schema v{sqlite_status['schema_version']}.",
            )
        )
    except Exception as exc:
        checks.append(check("database", "fail", f"SQLite state database is not ready: {exc}"))

    try:
        config = load_config(data_dir)
    except Exception as exc:
        config = {}
        checks.append(check("config", "fail", f"Configuration cannot be loaded: {exc}"))
    else:
        checks.append(check("config", "pass", "Configuration loads successfully."))

    if not raw_env.get("DIVINE_BACKUP_DIR"):
        backup_setting = config.get("deployment", {}).get("backup", {}).get("directory", "backups")
        backup_dir = Path(str(backup_setting)).expanduser()
        if not backup_dir.is_absolute():
            backup_dir = data_dir / backup_dir
        env["backup_dir"] = backup_dir.resolve()

    auth = auth_status(data_dir)
    accounts = list_accounts(data_dir)
    if not auth.get("enabled", True):
        checks.append(check("owner_account", "warn", "Authentication is disabled for this state directory."))
    elif not accounts:
        checks.append(check("owner_account", "fail", "Create the first owner account before exposing the app."))
    else:
        checks.append(check("owner_account", "pass", f"Owner account exists: {accounts[0]['username']}"))

    public_bind = host in {"0.0.0.0", "::", ""}
    if public_bind:
        checks.append(check("network_bind", "pass", f"Web service can bind for container hosting on port {port}."))
    else:
        checks.append(check("network_bind", "warn", f"Host is {host}; use 0.0.0.0 inside most containers."))

    public_url = env["public_url"]
    public_origin = env["public_origin"]
    hosted = env["mode"] not in {"local", "development", "test"} or public_bind or bool(public_url)
    if hosted and not public_origin:
        checks.append(check("hosted_origin", "fail", "Set DIVINE_PUBLIC_URL to the canonical HTTPS origin."))
    elif hosted and not public_origin.startswith("https://"):
        checks.append(check("hosted_origin", "fail", "Hosted deployments require an https:// public origin."))
    elif public_origin:
        checks.append(check("hosted_origin", "pass", f"Canonical hosted origin is {public_origin}."))
    else:
        checks.append(check("hosted_origin", "pass", "Local mode does not require a public origin."))

    if public_origin.startswith("https://") and env["cookie_secure"]:
        checks.append(check("secure_cookies", "pass", "Secure cookies are enabled for HTTPS hosting."))
    elif hosted:
        checks.append(check("secure_cookies", "fail", "Hosted sessions require DIVINE_COOKIE_SECURE=true."))
    else:
        checks.append(check("secure_cookies", "pass", "Local cookie settings are suitable for localhost use."))

    if hosted and not env["force_https"]:
        checks.append(check("secure_transport", "fail", "Set DIVINE_FORCE_HTTPS=true for hosted traffic."))
    elif hosted:
        checks.append(check("secure_transport", "pass", "HTTPS is required for hosted application traffic."))
    else:
        checks.append(check("secure_transport", "pass", "Local HTTP is permitted only for loopback development."))

    if hosted and not env["trust_proxy"]:
        checks.append(
            check(
                "proxy_headers",
                "fail",
                "Set DIVINE_TRUST_PROXY=true behind a trusted reverse proxy that overwrites forwarding headers.",
            )
        )
    elif hosted:
        checks.append(check("proxy_headers", "pass", "Trusted reverse-proxy headers are enabled."))
    else:
        checks.append(check("proxy_headers", "pass", "Forwarded headers are ignored in local mode."))

    if hosted and (
        not env["csrf_require_origin"]
        or not public_origin
        or public_origin not in env["allowed_origins"]
        or any(not origin.startswith("https://") for origin in env["allowed_origins"])
    ):
        checks.append(
            check(
                "csrf_origin",
                "fail",
                "Hosted CSRF protection requires the canonical origin in DIVINE_ALLOWED_ORIGINS.",
            )
        )
    elif hosted:
        checks.append(check("csrf_origin", "pass", "Unsafe requests require an approved Origin or Referer."))
    else:
        checks.append(check("csrf_origin", "pass", "Cross-origin unsafe requests are rejected on localhost."))

    heartbeat = worker_status(data_dir)
    if heartbeat["state"] == "running":
        checks.append(check("daemon", "pass", "Daemon heartbeat is current."))
    elif heartbeat["state"] == "stale":
        checks.append(check("daemon", "warn", "Daemon heartbeat is stale; restart the worker service."))
    else:
        checks.append(check("daemon", "warn", "Daemon has not reported yet; start the worker service after deployment."))

    try:
        backup_dir = env["backup_dir"]
        backup_dir.mkdir(parents=True, exist_ok=True)
        checks.append(check("backups", "pass", f"Backup directory is available: {backup_dir}"))
    except Exception as exc:
        checks.append(check("backups", "fail", f"Backup directory cannot be prepared: {exc}"))

    allowed_env = config.get("auth", {}).get("secret_management", {}).get("allowed_env_vars", [])
    checks.append(
        check(
            "secrets",
            "pass",
            "Runtime secrets are expected through environment variables: " + ", ".join(allowed_env),
        )
    )

    status = preflight_status(checks)
    return {
        "status": status,
        "version": __version__,
        "host": host,
        "port": port,
        "deployment": {
            "mode": env["mode"],
            "public_url": public_url,
            "cookie_secure": env["cookie_secure"],
            "allowed_origins": env["allowed_origins"],
            "csrf_require_origin": env["csrf_require_origin"],
            "trust_proxy": env["trust_proxy"],
            "force_https": env["force_https"],
        },
        "checks": checks,
    }


def check(name: str, severity: str, message: str) -> dict[str, str]:
    return {"name": name, "severity": severity, "message": message}


def preflight_status(checks: list[dict[str, str]]) -> str:
    severities = {item["severity"] for item in checks}
    if "fail" in severities:
        return "blocked"
    if "warn" in severities:
        return "ready_with_warnings"
    return "ready"


def format_preflight(result: dict[str, Any]) -> str:
    lines = [
        f"Deployment preflight: {result['status']}",
        f"Version: {result['version']}",
        f"Web bind: {result['host']}:{result['port']}",
    ]
    for item in result["checks"]:
        marker = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}.get(item["severity"], item["severity"].upper())
        lines.append(f"- {marker} {item['name']}: {item['message']}")
    return "\n".join(lines)


def create_backup(data_dir: Path, output_dir: Path | None = None) -> dict[str, Any]:
    if not data_dir.exists():
        raise DivineToolError(f"State directory does not exist: {data_dir}")
    state_names = (
        "config.json",
        "divine_tool.sqlite3",
        "commands.jsonl",
        "commands.processed.jsonl",
        "commands.failed.jsonl",
    )
    if not any((data_dir / name).exists() for name in state_names):
        raise DivineToolError(f"No Divine Tool state was found in: {data_dir}")
    backup_dir = output_dir or data_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    staging = backup_dir / f".divine-backup-{timestamp}"
    staging.mkdir(parents=True, exist_ok=False)
    files: list[str] = []

    try:
        config_path = data_dir / "config.json"
        if config_path.exists():
            shutil.copy2(config_path, staging / "config.json")
            files.append("config.json")

        db_path = data_dir / "divine_tool.sqlite3"
        if db_path.exists():
            source = connect(data_dir)
            target = sqlite3.connect(staging / "divine_tool.sqlite3")
            try:
                source.backup(target)
            finally:
                target.close()
                source.close()
            files.append("divine_tool.sqlite3")

        for name in ("commands.jsonl", "commands.processed.jsonl", "commands.failed.jsonl"):
            path = data_dir / name
            if path.exists():
                shutil.copy2(path, staging / name)
                files.append(name)

        manifest = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "version": __version__,
            "files": files,
        }
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        files.append("manifest.json")

        archive = backup_dir / f"divine-tool-backup-{timestamp}.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_name in files:
                zf.write(staging / file_name, arcname=file_name)
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    return {
        "archive": archive,
        "created_at": timestamp,
        "files": files,
        "size_bytes": archive.stat().st_size,
    }


def healthcheck_url(url: str, timeout: float = 5.0) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
            ok = response.status == 200 and bool(payload.get("ok"))
            return {"ok": ok, "status_code": response.status, "payload": payload}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status_code": exc.code, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "status_code": None, "error": str(exc)}
