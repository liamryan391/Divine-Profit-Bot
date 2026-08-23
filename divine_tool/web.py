from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import __version__
from .core import (
    DivineToolError,
    add_exception,
    add_income,
    enqueue_command,
    ensure_state,
    format_money,
    generate_opportunities,
    generate_upgrades,
    list_events,
    list_exceptions,
    list_income,
    load_config,
    parse_date,
    parse_money_to_minor,
    process_command_inbox,
    record_heartbeat,
    row_to_dict,
    set_mood,
    set_quota,
    status_report,
    worker_status,
)


STATIC_DIR = Path(__file__).with_name("static")


def run_web(data_dir: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    ensure_state(data_dir)
    handler = make_handler(data_dir)
    server = ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{server.server_port}"
    print(f"Divine Tool web app running at {url}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


def make_handler(data_dir: Path) -> type[BaseHTTPRequestHandler]:
    class DivineRequestHandler(BaseHTTPRequestHandler):
        server_version = "DivineToolHTTP/0.1"

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/api/status":
                    self.send_json(dashboard_payload(data_dir))
                    return
                if parsed.path == "/api/health":
                    self.send_json({"ok": True, "version": __version__, "worker": worker_status(data_dir)})
                    return
                if parsed.path == "/api/logs":
                    query = parse_qs(parsed.query)
                    limit = int(query.get("limit", ["50"])[0])
                    self.send_json({"events": serialize_rows(list_events(data_dir, limit=limit))})
                    return
                if parsed.path == "/api/income":
                    query = parse_qs(parsed.query)
                    limit = int(query.get("limit", ["20"])[0])
                    self.send_json({"income": serialize_income(list_income(data_dir, limit=limit))})
                    return
                self.serve_static(parsed.path)
            except DivineToolError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                self.send_json({"error": f"Unexpected server error: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            try:
                payload = self.read_json()
                if parsed.path == "/api/income":
                    income_id = add_income(
                        data_dir,
                        amount_minor=parse_money_to_minor(payload["amount"]),
                        currency=str(payload.get("currency", "GBP")),
                        gbp_minor=parse_money_to_minor(payload["gbp_equivalent"])
                        if payload.get("gbp_equivalent")
                        else None,
                        source=str(payload["source"]),
                        note=str(payload.get("note", "")),
                        occurred_on=parse_date(payload["date"]) if payload.get("date") else None,
                    )
                    self.send_json({"ok": True, "id": income_id, "state": dashboard_payload(data_dir)})
                    return
                if parsed.path == "/api/quota":
                    set_quota(
                        data_dir,
                        mood_name=str(payload["mood"]),
                        amount_minor=parse_money_to_minor(payload["amount"]),
                        period=str(payload.get("period", "week")),
                    )
                    self.send_json({"ok": True, "state": dashboard_payload(data_dir)})
                    return
                if parsed.path == "/api/mood":
                    set_mood(data_dir, str(payload["mood"]))
                    self.send_json({"ok": True, "state": dashboard_payload(data_dir)})
                    return
                if parsed.path == "/api/exception":
                    exception_id = add_exception(
                        data_dir,
                        reason=str(payload["reason"]),
                        starts_on=parse_date(payload["starts_on"]) if payload.get("starts_on") else None,
                        ends_on=parse_date(payload["until"]),
                    )
                    self.send_json({"ok": True, "id": exception_id, "state": dashboard_payload(data_dir)})
                    return
                if parsed.path == "/api/command/income":
                    command = {
                        "action": "add_income",
                        "amount": payload["amount"],
                        "currency": str(payload.get("currency", "GBP")),
                        "source": str(payload["source"]),
                        "note": str(payload.get("note", "")),
                    }
                    if payload.get("gbp_equivalent"):
                        command["gbp_equivalent"] = payload["gbp_equivalent"]
                    if payload.get("date"):
                        command["date"] = payload["date"]
                    enqueue_command(data_dir, command)
                    self.send_json({"ok": True, "state": dashboard_payload(data_dir)})
                    return
                if parsed.path == "/api/daemon/run-once":
                    outcomes = process_command_inbox(data_dir)
                    record_heartbeat(data_dir, detail=f"processed {len(outcomes)} command(s)")
                    self.send_json({"ok": True, "outcomes": outcomes, "state": dashboard_payload(data_dir)})
                    return
                self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            except KeyError as exc:
                self.send_json({"error": f"Missing required field: {exc.args[0]}"}, HTTPStatus.BAD_REQUEST)
            except DivineToolError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except json.JSONDecodeError:
                self.send_json({"error": "Request body must be valid JSON."}, HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                self.send_json({"error": f"Unexpected server error: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

        def read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length == 0:
                return {}
            raw = self.rfile.read(length).decode("utf-8")
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise DivineToolError("Request body must be a JSON object.")
            return value

        def serve_static(self, path: str) -> None:
            if path == "/":
                path = "/index.html"
            parts = [part for part in path.removeprefix("/").split("/") if part not in {"", ".", ".."}]
            target = (STATIC_DIR / Path(*parts)).resolve()
            root = STATIC_DIR.resolve()
            try:
                target.relative_to(root)
            except ValueError:
                self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
                return
            if not target.exists() or not target.is_file():
                self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
                return
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            data = target.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, _format: str, *_args: Any) -> None:
            return

    return DivineRequestHandler


def dashboard_payload(data_dir: Path) -> dict[str, Any]:
    config = load_config(data_dir)
    return {
        "version": __version__,
        "status": serialize_status(status_report(data_dir)),
        "income": serialize_income(list_income(data_dir, limit=10)),
        "exceptions": serialize_rows(list_exceptions(data_dir, limit=10)),
        "events": serialize_rows(list_events(data_dir, limit=50)),
        "opportunities": generate_opportunities(data_dir),
        "upgrades": generate_upgrades(data_dir),
        "worker": worker_status(data_dir),
        "config": {
            "god_name": config.get("god_name", "Creator"),
            "active_mood": config.get("active_mood", "watchful"),
            "base_currency": config.get("base_currency", "GBP"),
            "moods": config.get("moods", {}),
            "channels": config.get("channels", []),
        },
    }


def serialize_status(report: dict[str, Any]) -> dict[str, Any]:
    period = report["period"]
    return {
        "god_name": report["god_name"],
        "mood": report["mood"],
        "period": {
            "name": period.name,
            "start": period.start.isoformat(),
            "end": period.end.isoformat(),
        },
        "quota_minor": report["quota_minor"],
        "earned_minor": report["earned_minor"],
        "remaining_minor": report["remaining_minor"],
        "quota": format_money(int(report["quota_minor"])),
        "earned": format_money(int(report["earned_minor"])),
        "remaining": format_money(int(report["remaining_minor"])),
        "progress": report["progress"],
        "progress_pct": round(float(report["progress"]) * 100, 1),
        "days_left": report["days_left"],
        "judgement": report["judgement"],
        "punishment": report["punishment"],
        "exception": report["exception"],
    }


def serialize_income(rows: list[Any]) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        item = row_to_dict(row)
        item["amount"] = format_money(int(item["amount_minor"]), str(item["currency"]))
        item["counted"] = format_money(int(item["gbp_minor"]))
        output.append(item)
    return output


def serialize_rows(rows: list[Any]) -> list[dict[str, Any]]:
    return [row_to_dict(row) for row in rows]
