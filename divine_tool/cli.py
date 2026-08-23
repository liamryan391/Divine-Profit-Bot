from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

from .core import (
    DivineToolError,
    add_exception,
    add_income,
    default_data_dir,
    enqueue_command,
    ensure_state,
    format_money,
    generate_opportunities,
    generate_upgrades,
    list_exceptions,
    list_income,
    load_config,
    parse_date,
    parse_money_to_minor,
    process_command_inbox,
    record_heartbeat,
    set_mood,
    set_quota,
    status_report,
)
from .web import run_web


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    data_dir = Path(args.data_dir).resolve()
    try:
        return args.func(args, data_dir)
    except DivineToolError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nDaemon stopped.")
        return 130


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="divine-tool",
        description="Lawful revenue quota tracker and background command daemon.",
    )
    parser.add_argument("--data-dir", default=str(default_data_dir()), help="State directory, default: ./.divine_tool")
    sub = parser.add_subparsers(required=True)

    init = sub.add_parser("init", help="Create config and database state.")
    init.set_defaults(func=cmd_init)

    status = sub.add_parser("status", help="Show quota progress and judgement.")
    status.set_defaults(func=cmd_status)

    income = sub.add_parser("income", help="Record or list income.")
    income_sub = income.add_subparsers(required=True)
    income_add = income_sub.add_parser("add", help="Record income.")
    income_add.add_argument("amount", help="Amount in the original currency.")
    income_add.add_argument("--currency", default="GBP", help="Currency code, default GBP.")
    income_add.add_argument("--gbp-equivalent", help="Required for non-GBP income.")
    income_add.add_argument("--source", required=True, help="Lawful source of the income.")
    income_add.add_argument("--note", default="", help="Optional note.")
    income_add.add_argument("--strategy", default="", help="Strategy id from the configured channels.")
    income_add.add_argument("--date", help="Income date in YYYY-MM-DD format.")
    income_add.set_defaults(func=cmd_income_add)

    income_list = income_sub.add_parser("list", help="List recent income.")
    income_list.add_argument("--limit", type=int, default=20)
    income_list.set_defaults(func=cmd_income_list)

    mood = sub.add_parser("mood", help="Manage the Creator's mood.")
    mood_sub = mood.add_subparsers(required=True)
    mood_set = mood_sub.add_parser("set", help="Set active mood.")
    mood_set.add_argument("mood")
    mood_set.set_defaults(func=cmd_mood_set)

    quota = sub.add_parser("quota", help="Set mood quota.")
    quota_sub = quota.add_subparsers(required=True)
    quota_set = quota_sub.add_parser("set", help="Set the quota for a mood.")
    quota_set.add_argument("mood")
    quota_set.add_argument("amount")
    quota_set.add_argument("--period", choices=["week", "month"], default="week")
    quota_set.set_defaults(func=cmd_quota_set)

    exception = sub.add_parser("exception", help="Manage quota exceptions.")
    exception_sub = exception.add_subparsers(required=True)
    exception_add = exception_sub.add_parser("add", help="Add a mercy exception.")
    exception_add.add_argument("--reason", required=True)
    exception_add.add_argument("--from", dest="starts_on")
    exception_add.add_argument("--until", required=True)
    exception_add.set_defaults(func=cmd_exception_add)
    exception_list = exception_sub.add_parser("list", help="List exceptions.")
    exception_list.set_defaults(func=cmd_exception_list)

    opportunities = sub.add_parser("opportunities", help="Suggest lawful revenue actions.")
    opportunities.set_defaults(func=cmd_opportunities)

    upgrade = sub.add_parser("upgrade", help="Show upgrade recommendations.")
    upgrade.set_defaults(func=cmd_upgrade)

    config = sub.add_parser("config", help="Inspect configuration.")
    config_sub = config.add_subparsers(required=True)
    config_show = config_sub.add_parser("show", help="Print config JSON.")
    config_show.set_defaults(func=cmd_config_show)

    command = sub.add_parser("command", help="Queue commands for the daemon.")
    command_sub = command.add_subparsers(required=True)
    command_income = command_sub.add_parser("add-income", help="Queue an income entry.")
    command_income.add_argument("amount")
    command_income.add_argument("--currency", default="GBP")
    command_income.add_argument("--gbp-equivalent")
    command_income.add_argument("--source", required=True)
    command_income.add_argument("--note", default="")
    command_income.add_argument("--strategy", default="")
    command_income.add_argument("--date")
    command_income.set_defaults(func=cmd_command_income)
    command_mood = command_sub.add_parser("set-mood", help="Queue a mood change.")
    command_mood.add_argument("mood")
    command_mood.set_defaults(func=cmd_command_mood)
    command_quota = command_sub.add_parser("set-quota", help="Queue a quota change.")
    command_quota.add_argument("mood")
    command_quota.add_argument("amount")
    command_quota.add_argument("--period", choices=["week", "month"], default="week")
    command_quota.set_defaults(func=cmd_command_quota)

    daemon = sub.add_parser("daemon", help="Process commands and watch quota state.")
    daemon.add_argument("--once", action="store_true", help="Process one pass and exit.")
    daemon.add_argument("--interval", type=int, help="Override check interval in seconds.")
    daemon.set_defaults(func=cmd_daemon)

    web = sub.add_parser("web", help="Run the local web dashboard and API.")
    web.add_argument("--host", default="127.0.0.1", help="Host interface, default 127.0.0.1.")
    web.add_argument("--port", type=int, default=8765, help="Port, default 8765.")
    web.set_defaults(func=cmd_web)

    return parser


def cmd_init(_args: argparse.Namespace, data_dir: Path) -> int:
    ensure_state(data_dir)
    print(f"Divine Tool initialized at {data_dir}")
    print("Use `python -m divine_tool status` to view the quota.")
    return 0


def cmd_status(_args: argparse.Namespace, data_dir: Path) -> int:
    print_status(status_report(data_dir))
    return 0


def cmd_income_add(args: argparse.Namespace, data_dir: Path) -> int:
    currency = args.currency.upper()
    amount_minor = parse_money_to_minor(args.amount)
    gbp_minor = parse_money_to_minor(args.gbp_equivalent) if args.gbp_equivalent else None
    income_id = add_income(
        data_dir,
        amount_minor=amount_minor,
        currency=currency,
        gbp_minor=gbp_minor,
        source=args.source,
        note=args.note,
        strategy=args.strategy,
        occurred_on=parse_date(args.date) if args.date else None,
    )
    print(f"Recorded income #{income_id}: {format_money(gbp_minor if gbp_minor is not None else amount_minor)} counted toward quota.")
    return 0


def cmd_income_list(args: argparse.Namespace, data_dir: Path) -> int:
    rows = list_income(data_dir, limit=args.limit)
    if not rows:
        print("No income recorded yet.")
        return 0
    for row in rows:
        original = format_money(row["amount_minor"], row["currency"])
        counted = format_money(row["gbp_minor"])
        suffix = f" ({original})" if row["currency"] != "GBP" else ""
        strategy = f" [{row['strategy']}]" if row["strategy"] else ""
        print(f"#{row['id']} {row['occurred_at']} {counted}{suffix}{strategy} - {row['source']} {row['note']}".rstrip())
    return 0


def cmd_mood_set(args: argparse.Namespace, data_dir: Path) -> int:
    set_mood(data_dir, args.mood)
    print(f"Mood set to {args.mood}.")
    return 0


def cmd_quota_set(args: argparse.Namespace, data_dir: Path) -> int:
    set_quota(data_dir, args.mood, parse_money_to_minor(args.amount), args.period)
    print(f"{args.mood} quota set to {format_money(parse_money_to_minor(args.amount))} per {args.period}.")
    return 0


def cmd_exception_add(args: argparse.Namespace, data_dir: Path) -> int:
    exception_id = add_exception(
        data_dir,
        reason=args.reason,
        starts_on=parse_date(args.starts_on) if args.starts_on else None,
        ends_on=parse_date(args.until),
    )
    print(f"Added exception #{exception_id}.")
    return 0


def cmd_exception_list(_args: argparse.Namespace, data_dir: Path) -> int:
    rows = list_exceptions(data_dir)
    if not rows:
        print("No exceptions recorded.")
        return 0
    for row in rows:
        print(f"#{row['id']} {row['starts_on']} to {row['ends_on']} - {row['reason']}")
    return 0


def cmd_opportunities(_args: argparse.Namespace, data_dir: Path) -> int:
    print("Lawful revenue opportunities:")
    for item in generate_opportunities(data_dir):
        print(
            f"- #{item['rank']} {item['name']} ({item['score']}/100, {item['score_label']}): "
            f"{item['next_action']} Expected: {item['expected']}; fit: {item['fit']}; "
            f"risk: {item['risk']}; effort: {item['effort']}; evidence: {item['period_income']} this period."
        )
    return 0


def cmd_upgrade(_args: argparse.Namespace, data_dir: Path) -> int:
    print("Upgrade path:")
    for item in generate_upgrades(data_dir):
        print(f"- {item}")
    return 0


def cmd_config_show(_args: argparse.Namespace, data_dir: Path) -> int:
    print(json.dumps(load_config(data_dir), indent=2, sort_keys=True))
    return 0


def cmd_command_income(args: argparse.Namespace, data_dir: Path) -> int:
    command = {
        "action": "add_income",
        "amount": args.amount,
        "currency": args.currency.upper(),
        "source": args.source,
        "note": args.note,
        "strategy": args.strategy,
    }
    if args.gbp_equivalent:
        command["gbp_equivalent"] = args.gbp_equivalent
    if args.date:
        command["date"] = args.date
    enqueue_command(data_dir, command)
    print("Queued income command.")
    return 0


def cmd_command_mood(args: argparse.Namespace, data_dir: Path) -> int:
    enqueue_command(data_dir, {"action": "set_mood", "mood": args.mood})
    print("Queued mood command.")
    return 0


def cmd_command_quota(args: argparse.Namespace, data_dir: Path) -> int:
    enqueue_command(data_dir, {"action": "set_quota", "mood": args.mood, "amount": args.amount, "period": args.period})
    print("Queued quota command.")
    return 0


def cmd_daemon(args: argparse.Namespace, data_dir: Path) -> int:
    ensure_state(data_dir)
    interval = args.interval
    if interval is None:
        interval = int(load_config(data_dir).get("automation", {}).get("check_interval_seconds", 300))
    while True:
        outcomes = process_command_inbox(data_dir)
        record_heartbeat(data_dir, detail=f"processed {len(outcomes)} command(s)")
        for outcome in outcomes:
            print(f"command: {outcome}", flush=True)
        print_status(status_report(data_dir), compact=True)
        if args.once:
            return 0
        time.sleep(max(interval, 1))


def cmd_web(args: argparse.Namespace, data_dir: Path) -> int:
    run_web(data_dir, host=args.host, port=args.port)
    return 0


def print_status(report: dict[str, object], compact: bool = False) -> None:
    period = report["period"]
    progress_pct = float(report["progress"]) * 100
    exception = report["exception"]
    if compact:
        print(
            f"[{date.today().isoformat()}] {report['judgement']}: "
            f"{format_money(int(report['earned_minor']))}/{format_money(int(report['quota_minor']))} "
            f"({progress_pct:.1f}%)",
            flush=True,
        )
        return

    print("Divine Tool status")
    print(f"Creator: {report['god_name']}")
    print(f"Mood: {report['mood']}")
    print(f"Period: {period.name} ({period.start.isoformat()} to {period.end.isoformat()})")
    print(f"Quota: {format_money(int(report['quota_minor']))}")
    print(f"Earned: {format_money(int(report['earned_minor']))}")
    print(f"Remaining: {format_money(int(report['remaining_minor']))}")
    print(f"Progress: {progress_pct:.1f}%")
    print(f"Days left: {report['days_left']}")
    print(f"Judgement: {report['judgement']}")
    if report["remaining_minor"] and not exception:
        print(f"Consequence if missed: {report['punishment']}")
    if exception:
        print(f"Exception active: #{exception['id']} until {exception['ends_on']} - {exception['reason']}")
    print("Boundary: lawful income only; no fraud, spam, theft, unauthorized access, or autonomous real-money trading.")


if __name__ == "__main__":
    raise SystemExit(main())
