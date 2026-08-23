from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

from .core import (
    DivineToolError,
    add_exception,
    add_income,
    approval_action_to_dict,
    auth_status,
    create_approval_draft,
    create_account,
    create_temple,
    default_data_dir,
    enqueue_command,
    ensure_state,
    external_connections_snapshot,
    format_money,
    generate_opportunities,
    generate_report,
    generate_upgrades,
    import_income_csv,
    list_approval_actions,
    list_accounts,
    list_exceptions,
    list_income,
    list_temples,
    load_config,
    parse_date,
    parse_money_to_minor,
    process_command_inbox,
    record_heartbeat,
    review_approval_action,
    set_mood,
    set_quota,
    status_report,
    switch_temple,
    strategy_roi_summary,
    temple_summary,
)
from .deployment import create_backup, deployment_environment, deployment_preflight, format_preflight, healthcheck_url
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
    env = deployment_environment()
    parser = argparse.ArgumentParser(
        prog="divine-tool",
        description="Lawful revenue quota tracker and background command daemon.",
    )
    parser.add_argument(
        "--data-dir",
        default=str(env["data_dir"]),
        help="State directory, default: ./.divine_tool or DIVINE_DATA_DIR.",
    )
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

    roi = sub.add_parser("roi", help="Show strategy ROI and pause recommendations.")
    roi.set_defaults(func=cmd_roi)

    report = sub.add_parser("report", help="Generate a weekly or monthly report.")
    report.add_argument("--period", choices=["week", "month"], default="week")
    report.add_argument("--format", choices=["markdown", "json"], default="markdown")
    report.add_argument("--output", help="Optional file path for the generated report.")
    report.set_defaults(func=cmd_report)

    importer = sub.add_parser("import", help="Import income from a CSV file.")
    importer.add_argument("file", help="CSV file path.")
    importer.add_argument("--type", choices=["generic", "payment", "affiliate"], default="generic")
    importer.add_argument("--strategy", default="", help="Default strategy id when the CSV has no strategy column.")
    importer.add_argument("--dry-run", action="store_true", help="Parse and detect duplicates without writing income.")
    importer.set_defaults(func=cmd_import)

    external = sub.add_parser("external", help="Show read-only external connection signals.")
    external.add_argument("--format", choices=["text", "json"], default="text")
    external.set_defaults(func=cmd_external)

    approval = sub.add_parser("approval", help="Create and review human-approved action drafts.")
    approval_sub = approval.add_subparsers(required=True)
    approval_list = approval_sub.add_parser("list", help="List approval queue drafts.")
    approval_list.add_argument("--status", choices=["pending", "approved", "rejected", "completed", "all"], default="pending")
    approval_list.add_argument("--limit", type=int, default=20)
    approval_list.add_argument("--show-body", action="store_true", help="Print each draft body.")
    approval_list.set_defaults(func=cmd_approval_list)
    approval_draft = approval_sub.add_parser("draft", help="Queue a draft for human approval.")
    approval_draft.add_argument("kind", choices=["invoice_reminder", "outreach", "content_prompt"])
    approval_draft.add_argument("--target", default="", help="Client, recipient, or topic target.")
    approval_draft.add_argument("--amount", help="Invoice amount for invoice reminders.")
    approval_draft.add_argument("--due", help="Invoice due date in YYYY-MM-DD format.")
    approval_draft.add_argument("--invoice", default="", help="Invoice reference.")
    approval_draft.add_argument("--offer", default="", help="Offer for outreach.")
    approval_draft.add_argument("--topic", default="", help="Topic for content prompts.")
    approval_draft.add_argument("--goal", default="", help="Goal for outreach or content.")
    approval_draft.add_argument("--channel", default="", help="Content channel.")
    approval_draft.add_argument("--context", default="", help="Background context.")
    approval_draft.add_argument("--strategy", default="", help="Strategy id associated with the draft.")
    approval_draft.add_argument("--tone", default="polite", help="Draft tone.")
    approval_draft.set_defaults(func=cmd_approval_draft)
    approval_approve = approval_sub.add_parser("approve", help="Approve a pending draft for manual use.")
    approval_approve.add_argument("id", type=int)
    approval_approve.add_argument("--note", default="")
    approval_approve.set_defaults(func=cmd_approval_approve)
    approval_reject = approval_sub.add_parser("reject", help="Reject a pending or approved draft.")
    approval_reject.add_argument("id", type=int)
    approval_reject.add_argument("--note", default="")
    approval_reject.set_defaults(func=cmd_approval_reject)
    approval_complete = approval_sub.add_parser("complete", help="Mark an approved draft as manually completed.")
    approval_complete.add_argument("id", type=int)
    approval_complete.add_argument("--note", default="")
    approval_complete.set_defaults(func=cmd_approval_complete)

    upgrade = sub.add_parser("upgrade", help="Show upgrade recommendations.")
    upgrade.set_defaults(func=cmd_upgrade)

    config = sub.add_parser("config", help="Inspect configuration.")
    config_sub = config.add_subparsers(required=True)
    config_show = config_sub.add_parser("show", help="Print config JSON.")
    config_show.set_defaults(func=cmd_config_show)

    temple = sub.add_parser("temple", help="Manage multiple revenue temples.")
    temple_sub = temple.add_subparsers(required=True)
    temple_list = temple_sub.add_parser("list", help="List configured temples.")
    temple_list.set_defaults(func=cmd_temple_list)
    temple_create = temple_sub.add_parser("create", help="Create a new temple profile.")
    temple_create.add_argument("name")
    temple_create.add_argument("--id", dest="temple_id", default="", help="Optional stable temple id.")
    temple_create.add_argument("--description", default="")
    temple_create.add_argument("--template", choices=["balanced", "services", "products"], default="balanced")
    temple_create.set_defaults(func=cmd_temple_create)
    temple_switch = temple_sub.add_parser("switch", help="Switch the active temple.")
    temple_switch.add_argument("temple_id")
    temple_switch.set_defaults(func=cmd_temple_switch)
    temple_summary_cmd = temple_sub.add_parser("summary", help="Show cross-temple quota status.")
    temple_summary_cmd.set_defaults(func=cmd_temple_summary)

    account = sub.add_parser("account", help="Manage local owner account setup.")
    account_sub = account.add_subparsers(required=True)
    account_status = account_sub.add_parser("status", help="Show local authentication status.")
    account_status.set_defaults(func=cmd_account_status)
    account_setup = account_sub.add_parser("setup", help="Create the first local owner account.")
    account_setup.add_argument("username")
    account_setup.add_argument("--display-name", default="")
    account_setup.add_argument("--password", help="Password. If omitted, a hidden prompt is used.")
    account_setup.set_defaults(func=cmd_account_setup)
    account_list = account_sub.add_parser("list", help="List local accounts.")
    account_list.set_defaults(func=cmd_account_list)

    deploy = sub.add_parser("deploy", help="Deployment preflight, health checks, and backups.")
    deploy_sub = deploy.add_subparsers(required=True)
    deploy_preflight = deploy_sub.add_parser("preflight", help="Check whether this state is ready for hosting.")
    deploy_preflight.add_argument("--host", default=env["host"], help="Hosted bind address to validate.")
    deploy_preflight.add_argument("--port", type=int, default=env["port"], help="Hosted port to validate.")
    deploy_preflight.add_argument("--format", choices=["text", "json"], default="text")
    deploy_preflight.add_argument("--strict", action="store_true", help="Exit non-zero unless every check passes.")
    deploy_preflight.set_defaults(func=cmd_deploy_preflight)
    deploy_health = deploy_sub.add_parser("healthcheck", help="Check a running hosted web service.")
    deploy_health.add_argument("--url", help="Health URL, default: local /api/health from deployment env.")
    deploy_health.set_defaults(func=cmd_deploy_healthcheck)
    deploy_backup = deploy_sub.add_parser("backup", help="Create a portable backup of the deployment state.")
    deploy_backup.add_argument("--output", help="Backup output directory.")
    deploy_backup.set_defaults(func=cmd_deploy_backup)

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
    command_income.add_argument("--temple", dest="temple_id", help="Optional temple id for the daemon command.")
    command_income.set_defaults(func=cmd_command_income)
    command_mood = command_sub.add_parser("set-mood", help="Queue a mood change.")
    command_mood.add_argument("mood")
    command_mood.add_argument("--temple", dest="temple_id", help="Optional temple id for the daemon command.")
    command_mood.set_defaults(func=cmd_command_mood)
    command_quota = command_sub.add_parser("set-quota", help="Queue a quota change.")
    command_quota.add_argument("mood")
    command_quota.add_argument("amount")
    command_quota.add_argument("--period", choices=["week", "month"], default="week")
    command_quota.add_argument("--temple", dest="temple_id", help="Optional temple id for the daemon command.")
    command_quota.set_defaults(func=cmd_command_quota)

    daemon = sub.add_parser("daemon", help="Process commands and watch quota state.")
    daemon.add_argument("--once", action="store_true", help="Process one pass and exit.")
    daemon.add_argument("--interval", type=int, help="Override check interval in seconds.")
    daemon.set_defaults(func=cmd_daemon)

    web = sub.add_parser("web", help="Run the local web dashboard and API.")
    web.add_argument("--host", default=env["host"], help="Host interface, default 127.0.0.1 or DIVINE_HOST.")
    web.add_argument("--port", type=int, default=env["port"], help="Port, default 8765 or DIVINE_PORT.")
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


def cmd_roi(_args: argparse.Namespace, data_dir: Path) -> int:
    summary = strategy_roi_summary(data_dir)
    period = summary["period"]
    previous = summary["previous_period"]
    print(f"Strategy ROI: {period['start']} to {period['end']} (previous: {previous['start']} to {previous['end']})")
    for row in summary["rows"]:
        print(
            f"- #{row['roi_rank']} {row['name']}: {row['current_period']} now, "
            f"{row['previous_period']} previous, {row['delta']} delta, "
            f"{row['roi_per_effort']} per effort unit, {row['trend']}; "
            f"recommendation: {row['recommendation']} - {row['recommendation_reason']}"
        )
    return 0


def cmd_report(args: argparse.Namespace, data_dir: Path) -> int:
    report = generate_report(data_dir, period_name=args.period)
    if args.format == "json":
        content = json.dumps(report, indent=2, sort_keys=True)
    else:
        content = report["markdown"]

    if args.output:
        output = Path(args.output)
        output.write_text(content, encoding="utf-8")
        print(f"Report written to {output}")
    else:
        print(content)
    return 0


def cmd_import(args: argparse.Namespace, data_dir: Path) -> int:
    path = Path(args.file)
    csv_text = path.read_text(encoding="utf-8-sig")
    result = import_income_csv(
        data_dir,
        csv_text,
        source_type=args.type,
        default_strategy=args.strategy,
        dry_run=args.dry_run,
        filename=path.name,
    )
    if args.dry_run:
        print(
            f"CSV import dry run: {result['ready_count']} ready, "
            f"{result['duplicate_count']} duplicate, {result['skipped_count']} skipped."
        )
    else:
        print(
            f"CSV import complete: {result['imported_count']} imported, "
            f"{result['duplicate_count']} duplicate, {result['skipped_count']} skipped."
        )
    for row in result["rows"]:
        if row["status"] in {"skipped", "duplicate"}:
            detail = row.get("reason") or f"existing income #{row.get('existing_id')}"
            print(f"- row {row.get('row_number', '?')}: {row['status']} - {detail}")
    return 0


def cmd_external(args: argparse.Namespace, data_dir: Path) -> int:
    snapshot = external_connections_snapshot(data_dir)
    if args.format == "json":
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 0

    print("External connections:")
    for connection in snapshot["connections"]:
        print(f"- {connection['name']}: {connection['state']} - {connection['summary']}")
        for item in connection.get("items", [])[:4]:
            print(f"  - {format_external_item(item)}")
        if connection.get("next_action"):
            print(f"  next: {connection['next_action']}")
    return 0


def format_external_item(item: dict[str, object]) -> str:
    if "one_unit" in item:
        return f"{item['currency']} = {item['one_unit']}"
    if "net" in item:
        return f"{item['currency']} net {item['net']} across {item.get('transaction_count', '0')} transaction(s)"
    if "label" in item:
        return f"{item['label']}: {item['value']}"
    return json.dumps(item, sort_keys=True)


def cmd_approval_list(args: argparse.Namespace, data_dir: Path) -> int:
    rows = list_approval_actions(data_dir, status=args.status, limit=args.limit)
    if not rows:
        print("No approval drafts found.")
        return 0
    for row in rows:
        item = approval_action_to_dict(row)
        print(
            f"#{item['id']} {item['status']} {item['kind_label']}: "
            f"{item['title']} [{item.get('strategy') or 'unassigned'}]"
        )
        if args.show_body:
            print(item["body"])
    return 0


def cmd_approval_draft(args: argparse.Namespace, data_dir: Path) -> int:
    amount_minor = parse_money_to_minor(args.amount) if args.amount else None
    due_on = parse_date(args.due) if args.due else None
    action_id = create_approval_draft(
        data_dir,
        kind=args.kind,
        target=args.target,
        strategy=args.strategy,
        amount_minor=amount_minor,
        due_on=due_on,
        invoice=args.invoice,
        offer=args.offer,
        topic=args.topic,
        goal=args.goal,
        channel=args.channel,
        context=args.context,
        tone=args.tone,
    )
    print(f"Queued approval draft #{action_id}.")
    return 0


def cmd_approval_approve(args: argparse.Namespace, data_dir: Path) -> int:
    item = review_approval_action(data_dir, args.id, "approve", args.note)
    print(f"Approved draft #{item['id']} for manual use.")
    return 0


def cmd_approval_reject(args: argparse.Namespace, data_dir: Path) -> int:
    item = review_approval_action(data_dir, args.id, "reject", args.note)
    print(f"Rejected draft #{item['id']}.")
    return 0


def cmd_approval_complete(args: argparse.Namespace, data_dir: Path) -> int:
    item = review_approval_action(data_dir, args.id, "complete", args.note)
    print(f"Completed draft #{item['id']} manually.")
    return 0


def cmd_upgrade(_args: argparse.Namespace, data_dir: Path) -> int:
    print("Upgrade path:")
    for item in generate_upgrades(data_dir):
        print(f"- {item}")
    return 0


def cmd_config_show(_args: argparse.Namespace, data_dir: Path) -> int:
    print(json.dumps(load_config(data_dir), indent=2, sort_keys=True))
    return 0


def cmd_temple_list(_args: argparse.Namespace, data_dir: Path) -> int:
    temples = list_temples(data_dir)
    if not temples:
        print("No temples configured.")
        return 0
    for temple in temples:
        marker = "*" if temple["active"] else " "
        description = f" - {temple['description']}" if temple["description"] else ""
        print(
            f"{marker} {temple['id']}: {temple['name']} "
            f"({temple['active_mood']}, {temple['channel_count']} strategies){description}"
        )
    return 0


def cmd_temple_create(args: argparse.Namespace, data_dir: Path) -> int:
    temple = create_temple(
        data_dir,
        name=args.name,
        temple_id=args.temple_id,
        description=args.description,
        template=args.template,
    )
    print(f"Created temple {temple['id']}: {temple['name']}")
    return 0


def cmd_temple_switch(args: argparse.Namespace, data_dir: Path) -> int:
    temple = switch_temple(data_dir, args.temple_id)
    print(f"Active temple: {temple['id']} - {temple['name']}")
    return 0


def cmd_temple_summary(_args: argparse.Namespace, data_dir: Path) -> int:
    summary = temple_summary(data_dir)
    print(
        f"Temple summary: {summary['total_earned']} earned of {summary['total_quota']} "
        f"({summary['overall_progress_pct']}%) across {summary['temple_count']} temple(s)."
    )
    for row in summary["rows"]:
        marker = "*" if row["active"] else " "
        print(
            f"{marker} {row['id']}: {row['earned']}/{row['quota']} "
            f"({row['progress_pct']}%) - {row['judgement']}; top: {row['top_strategy']}"
        )
    return 0


def cmd_account_status(_args: argparse.Namespace, data_dir: Path) -> int:
    status = auth_status(data_dir)
    print("Authentication")
    print(f"Enabled: {status['enabled']}")
    print(f"Setup required: {status['setup_required']}")
    print(f"Accounts: {len(list_accounts(data_dir))}")
    policy = status.get("secret_management", {}).get("policy")
    if policy:
        print(f"Secret policy: {policy}")
    return 0


def cmd_account_setup(args: argparse.Namespace, data_dir: Path) -> int:
    password = args.password
    if not password:
        password = getpass.getpass("Owner password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            raise DivineToolError("Passwords do not match.")
    account = create_account(data_dir, args.username, password, display_name=args.display_name)
    print(f"Created owner account: {account['username']}")
    return 0


def cmd_account_list(_args: argparse.Namespace, data_dir: Path) -> int:
    accounts = list_accounts(data_dir)
    if not accounts:
        print("No accounts configured.")
        return 0
    for account in accounts:
        disabled = " disabled" if account["disabled"] else ""
        print(f"#{account['id']} {account['username']} ({account['role']}){disabled}")
    return 0


def cmd_deploy_preflight(args: argparse.Namespace, data_dir: Path) -> int:
    result = deployment_preflight(data_dir, host=args.host, port=args.port)
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    else:
        print(format_preflight(result))
    if args.strict and result["status"] != "ready":
        return 2
    return 0


def cmd_deploy_healthcheck(args: argparse.Namespace, _data_dir: Path) -> int:
    env = deployment_environment()
    url = args.url or f"http://127.0.0.1:{env['port']}/api/health"
    result = healthcheck_url(url)
    if result["ok"]:
        payload = result.get("payload", {})
        version = payload.get("version", "unknown")
        worker = payload.get("worker", {}).get("state", "unknown")
        print(f"Healthcheck OK: version {version}, worker {worker}")
        return 0
    print(f"Healthcheck failed: {result.get('error') or result.get('status_code')}", file=sys.stderr)
    return 2


def cmd_deploy_backup(args: argparse.Namespace, data_dir: Path) -> int:
    output_dir = Path(args.output).resolve() if args.output else None
    backup = create_backup(data_dir, output_dir)
    print(f"Backup written: {backup['archive']}")
    print(f"Files: {', '.join(backup['files'])}")
    print(f"Size: {backup['size_bytes']} bytes")
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
    if args.temple_id:
        command["temple_id"] = args.temple_id
    enqueue_command(data_dir, command)
    print("Queued income command.")
    return 0


def cmd_command_mood(args: argparse.Namespace, data_dir: Path) -> int:
    command = {"action": "set_mood", "mood": args.mood}
    if args.temple_id:
        command["temple_id"] = args.temple_id
    enqueue_command(data_dir, command)
    print("Queued mood command.")
    return 0


def cmd_command_quota(args: argparse.Namespace, data_dir: Path) -> int:
    command = {"action": "set_quota", "mood": args.mood, "amount": args.amount, "period": args.period}
    if args.temple_id:
        command["temple_id"] = args.temple_id
    enqueue_command(data_dir, command)
    print("Queued quota command.")
    return 0


def cmd_daemon(args: argparse.Namespace, data_dir: Path) -> int:
    ensure_state(data_dir)
    interval = args.interval
    if interval is None:
        env = deployment_environment()
        interval = env["daemon_interval"]
        if "DIVINE_DAEMON_INTERVAL" not in os.environ:
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
            f"[{date.today().isoformat()}] {report['temple']['id']} {report['judgement']}: "
            f"{format_money(int(report['earned_minor']))}/{format_money(int(report['quota_minor']))} "
            f"({progress_pct:.1f}%)",
            flush=True,
        )
        return

    print("Divine Tool status")
    print(f"Creator: {report['god_name']}")
    print(f"Temple: {report['temple']['name']} ({report['temple']['id']})")
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
