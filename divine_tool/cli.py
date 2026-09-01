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
    WorkerCycleBusyError,
    add_exception,
    add_income,
    approval_action_to_dict,
    auth_status,
    create_approval_draft,
    create_account,
    create_receivable,
    create_recurring_revenue_template,
    create_temple,
    default_data_dir,
    enqueue_command,
    ensure_state,
    external_connections_snapshot,
    follow_up_summary,
    format_money,
    confirm_reconciliation_match,
    generate_opportunities,
    generate_report,
    generate_upgrades,
    import_income_csv,
    import_reconciliation_csv,
    ignore_reconciliation_transaction,
    list_approval_actions,
    list_accounts,
    list_exceptions,
    list_income,
    list_temples,
    load_config,
    parse_date,
    parse_money_to_minor,
    process_follow_up_cadences,
    process_recurring_revenue,
    queue_receivable_reminder,
    receivables_summary,
    recurring_revenue_summary,
    reconciliation_summary,
    record_follow_up_outcome,
    record_receivable_payment,
    reset_account_password,
    run_worker_cycle,
    review_approval_action,
    set_mood,
    set_quota,
    status_report,
    switch_temple,
    strategy_roi_summary,
    temple_summary,
    update_client_contact_state,
    update_follow_up_cadence,
    update_receivable_status,
    update_recurring_revenue_template_status,
)
from .deployment import (
    create_backup,
    deployment_environment,
    deployment_preflight,
    format_integrity,
    format_preflight,
    format_recovery_drills,
    healthcheck_url,
    restore_backup,
    run_recovery_drills,
    state_integrity,
    verify_backup,
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

    receivable = sub.add_parser("receivable", help="Manage invoices and other money owed.")
    receivable_sub = receivable.add_subparsers(required=True)
    receivable_list = receivable_sub.add_parser("list", help="List receivables and collection totals.")
    receivable_list.add_argument(
        "--status",
        choices=["all", "open", "overdue", "due_soon", "partial", "paid", "void"],
        default="all",
    )
    receivable_list.add_argument("--limit", type=int, default=60)
    receivable_list.set_defaults(func=cmd_receivable_list)
    receivable_add = receivable_sub.add_parser("add", help="Create a receivable.")
    receivable_add.add_argument("client")
    receivable_add.add_argument("reference")
    receivable_add.add_argument("amount")
    receivable_add.add_argument("--due", required=True, help="Due date in YYYY-MM-DD format.")
    receivable_add.add_argument("--currency", default="GBP")
    receivable_add.add_argument("--gbp-equivalent")
    receivable_add.add_argument("--issued", help="Issue date in YYYY-MM-DD format.")
    receivable_add.add_argument("--description", default="")
    receivable_add.add_argument("--lead-id", type=int)
    receivable_add.add_argument("--notes", default="")
    receivable_add.set_defaults(func=cmd_receivable_add)
    receivable_pay = receivable_sub.add_parser("pay", help="Record a receivable payment.")
    receivable_pay.add_argument("id", type=int)
    receivable_pay.add_argument("amount")
    receivable_pay.add_argument("--currency", default="GBP")
    receivable_pay.add_argument("--gbp-equivalent")
    receivable_pay.add_argument("--date", help="Payment date in YYYY-MM-DD format.")
    receivable_pay.add_argument("--reference", default="")
    receivable_pay.add_argument("--note", default="")
    receivable_pay.add_argument("--count-as-income", action="store_true")
    receivable_pay.set_defaults(func=cmd_receivable_pay)
    receivable_remind = receivable_sub.add_parser("remind", help="Queue a human-approved payment reminder.")
    receivable_remind.add_argument("id", type=int)
    receivable_remind.set_defaults(func=cmd_receivable_remind)
    receivable_status = receivable_sub.add_parser("status", help="Void or reopen an unpaid receivable.")
    receivable_status.add_argument("id", type=int)
    receivable_status.add_argument("status", choices=["open", "void"])
    receivable_status.set_defaults(func=cmd_receivable_status)

    follow_up = sub.add_parser("follow-up", help="Configure and review human-approved collection cadences.")
    follow_up_sub = follow_up.add_subparsers(required=True)
    follow_up_status = follow_up_sub.add_parser("status", help="Show cadence, queue, and outcome metrics.")
    follow_up_status.add_argument("--limit", type=int, default=30)
    follow_up_status.add_argument("--format", choices=["text", "json"], default="text")
    follow_up_status.set_defaults(func=cmd_follow_up_status)
    follow_up_configure = follow_up_sub.add_parser("configure", help="Update the active temple cadence.")
    follow_up_configure.add_argument("--due-soon", default="3,0", help="Days before due, comma separated.")
    follow_up_configure.add_argument("--overdue", default="3,7,14,30", help="Days after due, comma separated.")
    follow_up_configure.add_argument("--minimum-gap", type=int, default=2)
    follow_up_configure.add_argument("--max-reminders", type=int, default=6)
    follow_up_configure.add_argument("--stop-after", type=int, default=60, help="Stop after this many overdue days.")
    follow_up_configure.add_argument("--disable", action="store_true", help="Disable background cadence drafting.")
    follow_up_configure.set_defaults(func=cmd_follow_up_configure)
    follow_up_run = follow_up_sub.add_parser("run", help="Draft any currently due reminders for approval.")
    follow_up_run.add_argument("--date", help="Optional review date in YYYY-MM-DD format.")
    follow_up_run.set_defaults(func=cmd_follow_up_run)
    follow_up_client = follow_up_sub.add_parser("client", help="Set a client contact state.")
    follow_up_client.add_argument("client")
    follow_up_client.add_argument("status", choices=["active", "paused", "do_not_contact"])
    follow_up_client.add_argument("--until", help="Optional suppression end date in YYYY-MM-DD format.")
    follow_up_client.add_argument("--reason", default="")
    follow_up_client.set_defaults(func=cmd_follow_up_client)
    follow_up_outcome = follow_up_sub.add_parser("outcome", help="Record the outcome of a completed reminder.")
    follow_up_outcome.add_argument("event_id", type=int)
    follow_up_outcome.add_argument(
        "outcome",
        choices=["no_response", "payment_promised", "partial_payment", "paid", "disputed", "wrong_contact", "other"],
    )
    follow_up_outcome.add_argument("--note", default="")
    follow_up_outcome.set_defaults(func=cmd_follow_up_outcome)

    recurring = sub.add_parser("recurring", help="Manage retainers and recurring receivable templates.")
    recurring_sub = recurring.add_subparsers(required=True)
    recurring_status = recurring_sub.add_parser("status", help="Show recurring value, generation, and renewal risk.")
    recurring_status.add_argument("--limit", type=int, default=60)
    recurring_status.add_argument("--format", choices=["text", "json"], default="text")
    recurring_status.set_defaults(func=cmd_recurring_status)
    recurring_create = recurring_sub.add_parser("create", help="Create a recurring receivable template.")
    recurring_create.add_argument("name")
    recurring_create.add_argument("client")
    recurring_create.add_argument("reference_prefix")
    recurring_create.add_argument("amount")
    recurring_create.add_argument("--kind", choices=["retainer", "subscription", "instalment"], required=True)
    recurring_create.add_argument("--cadence", choices=["weekly", "monthly", "quarterly", "yearly"], default="monthly")
    recurring_create.add_argument("--start", required=True, help="First issue date in YYYY-MM-DD format.")
    recurring_create.add_argument("--currency", default="GBP")
    recurring_create.add_argument("--gbp-equivalent")
    recurring_create.add_argument("--description", default="")
    recurring_create.add_argument("--payment-terms", type=int, default=14)
    recurring_create.add_argument("--generate-ahead", type=int, default=7)
    recurring_create.add_argument("--end", help="Optional last schedule date in YYYY-MM-DD format.")
    recurring_create.add_argument("--renewal", help="Optional renewal date in YYYY-MM-DD format.")
    recurring_create.add_argument("--renewal-notice", type=int, default=30)
    recurring_create.add_argument("--occurrences", type=int, help="Optional cap; required for instalments.")
    recurring_create.add_argument("--notes", default="")
    recurring_create.set_defaults(func=cmd_recurring_create)
    recurring_run = recurring_sub.add_parser("run", help="Generate receivables inside configured windows.")
    recurring_run.add_argument("--date", help="Optional generation date in YYYY-MM-DD format.")
    recurring_run.add_argument("--template-id", type=int)
    recurring_run.set_defaults(func=cmd_recurring_run)
    recurring_template = recurring_sub.add_parser("template", help="Pause, resume, or permanently end a template.")
    recurring_template.add_argument("id", type=int)
    recurring_template.add_argument("status", choices=["active", "paused", "ended"])
    recurring_template.set_defaults(func=cmd_recurring_template_status)

    reconcile = sub.add_parser("reconcile", help="Import and review payment evidence.")
    reconcile_sub = reconcile.add_subparsers(required=True)
    reconcile_list = reconcile_sub.add_parser("list", help="List reconciliation transactions and totals.")
    reconcile_list.add_argument(
        "--status",
        choices=["all", "review", "unmatched", "suggested", "matched", "ignored"],
        default="review",
    )
    reconcile_list.add_argument("--limit", type=int, default=60)
    reconcile_list.set_defaults(func=cmd_reconcile_list)
    reconcile_import = reconcile_sub.add_parser("import", help="Import a bank or provider CSV as payment evidence.")
    reconcile_import.add_argument("file", help="CSV file path.")
    reconcile_import.add_argument(
        "--provider",
        choices=["bank", "generic", "paypal", "square", "stripe"],
        default="generic",
    )
    reconcile_import.add_argument("--dry-run", action="store_true", help="Preview matches without writing evidence.")
    reconcile_import.set_defaults(func=cmd_reconcile_import)
    reconcile_confirm = reconcile_sub.add_parser("confirm", help="Confirm a transaction-to-receivable match.")
    reconcile_confirm.add_argument("transaction_id", type=int)
    reconcile_confirm.add_argument("receivable_id", type=int)
    reconcile_confirm.add_argument("--count-as-income", action="store_true")
    reconcile_confirm.add_argument("--note", default="")
    reconcile_confirm.set_defaults(func=cmd_reconcile_confirm)
    reconcile_ignore = reconcile_sub.add_parser("ignore", help="Ignore non-receivable payment evidence.")
    reconcile_ignore.add_argument("transaction_id", type=int)
    reconcile_ignore.add_argument("--reason", required=True)
    reconcile_ignore.set_defaults(func=cmd_reconcile_ignore)

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
    account_setup.add_argument("--recovery-email", default="", help="Optional email label for account recovery reference.")
    account_setup.add_argument("--password", help="Password. If omitted, a hidden prompt is used.")
    account_setup.set_defaults(func=cmd_account_setup)
    account_list = account_sub.add_parser("list", help="List local accounts.")
    account_list.set_defaults(func=cmd_account_list)
    account_reset = account_sub.add_parser("reset-password", help="Reset a local owner account password.")
    account_reset.add_argument("username")
    account_reset.add_argument("--password", help="New password. If omitted, a hidden prompt is used.")
    account_reset.set_defaults(func=cmd_account_reset_password)

    deploy = sub.add_parser("deploy", help="Deployment checks, backups, restores, and recovery drills.")
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
    deploy_verify = deploy_sub.add_parser("verify-backup", help="Verify a portable backup without changing state.")
    deploy_verify.add_argument("archive", help="Backup ZIP archive to verify.")
    deploy_verify.add_argument("--format", choices=["text", "json"], default="text")
    deploy_verify.set_defaults(func=cmd_deploy_verify_backup)
    deploy_restore = deploy_sub.add_parser("restore", help="Restore a verified backup into an offline state directory.")
    deploy_restore.add_argument("archive", help="Backup ZIP archive to restore.")
    deploy_restore.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm replacement of existing state after stopping web and daemon services.",
    )
    deploy_restore.add_argument("--safety-output", help="Directory for the automatic pre-restore safety backup.")
    deploy_restore.add_argument(
        "--skip-safety-backup",
        action="store_true",
        help="Emergency recovery only: replace damaged state without first backing it up.",
    )
    deploy_restore.add_argument("--format", choices=["text", "json"], default="text")
    deploy_restore.set_defaults(func=cmd_deploy_restore)
    deploy_integrity = deploy_sub.add_parser("integrity", help="Check live state without modifying it.")
    deploy_integrity.add_argument("--format", choices=["text", "json"], default="text")
    deploy_integrity.set_defaults(func=cmd_deploy_integrity)
    deploy_drill = deploy_sub.add_parser("drill", help="Run isolated backup and failure-recovery drills.")
    deploy_drill.add_argument("--output", help="Directory for the verified drill backup.")
    deploy_drill.add_argument("--format", choices=["text", "json"], default="text")
    deploy_drill.set_defaults(func=cmd_deploy_drill)

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


def cmd_receivable_list(args: argparse.Namespace, data_dir: Path) -> int:
    summary = receivables_summary(data_dir, status=args.status, limit=args.limit)
    print(
        f"Receivables: {summary['outstanding']} outstanding; {summary['overdue']} overdue; "
        f"{summary['collected']} collected."
    )
    if not summary["rows"]:
        print("No receivables found.")
        return 0
    for item in summary["rows"]:
        print(
            f"#{item['id']} {item['state_label']}: {item['reference']} - {item['client']} - "
            f"{item['outstanding']} outstanding (due {item['due_on']})"
        )
    return 0


def cmd_receivable_add(args: argparse.Namespace, data_dir: Path) -> int:
    receivable_id = create_receivable(
        data_dir,
        client=args.client,
        reference=args.reference,
        amount_minor=parse_money_to_minor(args.amount),
        due_on=parse_date(args.due),
        currency=args.currency,
        gbp_minor=parse_money_to_minor(args.gbp_equivalent) if args.gbp_equivalent else None,
        description=args.description,
        issued_on=parse_date(args.issued) if args.issued else None,
        lead_id=args.lead_id,
        notes=args.notes,
    )
    print(f"Created receivable #{receivable_id}.")
    return 0


def cmd_receivable_pay(args: argparse.Namespace, data_dir: Path) -> int:
    result = record_receivable_payment(
        data_dir,
        receivable_id=args.id,
        amount_minor=parse_money_to_minor(args.amount),
        currency=args.currency,
        gbp_minor=parse_money_to_minor(args.gbp_equivalent) if args.gbp_equivalent else None,
        occurred_on=parse_date(args.date) if args.date else None,
        payment_reference=args.reference,
        note=args.note,
        count_as_income=args.count_as_income,
    )
    payment = result["payment"]
    receivable = result["receivable"]
    counted = f" and counted as income #{payment['counted_income_id']}" if payment["counted_income_id"] else ""
    print(f"Recorded {payment['counted']} on receivable #{args.id}{counted}.")
    print(f"Outstanding: {receivable['outstanding']} ({receivable['state_label']}).")
    return 0


def cmd_receivable_remind(args: argparse.Namespace, data_dir: Path) -> int:
    result = queue_receivable_reminder(data_dir, args.id)
    print(f"Queued reminder approval draft #{result['approval_id']} for receivable #{args.id}.")
    return 0


def cmd_receivable_status(args: argparse.Namespace, data_dir: Path) -> int:
    receivable = update_receivable_status(data_dir, args.id, args.status)
    print(f"Receivable #{receivable['id']} marked {receivable['state_label']}.")
    return 0


def cmd_follow_up_status(args: argparse.Namespace, data_dir: Path) -> int:
    summary = follow_up_summary(data_dir, limit=args.limit)
    if args.format == "json":
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    cadence = summary["cadence"]
    metrics = summary["metrics"]
    print(
        f"Follow-up cadence: {'enabled' if cadence['enabled'] else 'disabled'}; "
        f"{summary['due_count']} due; {summary['counts']['drafted']} drafted; "
        f"{summary['counts']['suppressed']} suppressed."
    )
    print(
        f"Schedule: {cadence['due_soon_display']} day(s) before due; "
        f"{cadence['overdue_display']} day(s) overdue; minimum gap {cadence['minimum_gap_days']} day(s)."
    )
    print(
        f"Outcomes: {metrics['completed_reminders']} completed, {metrics['response_rate_pct']}% response rate, "
        f"{metrics['collected_after_reminder']} collected after a completed reminder."
    )
    for item in summary["upcoming"]:
        suppression = f" - suppressed: {item['suppression_reason']}" if item["suppression_reason"] else ""
        print(
            f"#{item['receivable_id']} {item['reference']} - {item['client']}: "
            f"{item['status_label']} on {item['scheduled_for']}{suppression}"
        )
    return 0


def cmd_follow_up_configure(args: argparse.Namespace, data_dir: Path) -> int:
    cadence = update_follow_up_cadence(
        data_dir,
        due_soon_days=args.due_soon,
        overdue_days=args.overdue,
        minimum_gap_days=args.minimum_gap,
        max_reminders=args.max_reminders,
        stop_after_overdue_days=args.stop_after,
        enabled=not args.disable,
    )
    print(
        f"Follow-up cadence {'enabled' if cadence['enabled'] else 'disabled'}: "
        f"due-soon {cadence['due_soon_display']}; overdue {cadence['overdue_display']}."
    )
    return 0


def cmd_follow_up_run(args: argparse.Namespace, data_dir: Path) -> int:
    result = process_follow_up_cadences(data_dir, today=parse_date(args.date) if args.date else None)
    print(
        f"Follow-up review: {result['evaluated']} due, {result['drafted']} drafted for approval, "
        f"{result['suppressed']} suppressed, {result['existing']} already handled."
    )
    return 0


def cmd_follow_up_client(args: argparse.Namespace, data_dir: Path) -> int:
    state = update_client_contact_state(
        data_dir,
        client=args.client,
        status=args.status,
        suppress_until=parse_date(args.until) if args.until else None,
        reason=args.reason,
    )
    until = f" until {state['suppress_until']}" if state["suppress_until"] else ""
    print(f"{state['client']} contact state: {state['status_label']}{until}.")
    return 0


def cmd_follow_up_outcome(args: argparse.Namespace, data_dir: Path) -> int:
    result = record_follow_up_outcome(data_dir, args.event_id, args.outcome, args.note)
    event = result["event"]
    print(f"Follow-up event #{event['id']} outcome: {event['outcome_label']}.")
    return 0


def cmd_recurring_status(args: argparse.Namespace, data_dir: Path) -> int:
    summary = recurring_revenue_summary(data_dir, limit=args.limit)
    if args.format == "json":
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    print(
        f"Recurring revenue: {summary['monthly_recurring_revenue']} normalized monthly; "
        f"{summary['expected_30_days']} expected in 30 days; {summary['renewal_risk_count']} renewal risk(s)."
    )
    print(
        f"Templates: {summary['active_count']} active, {summary['paused_count']} paused, "
        f"{summary['ended_count']} ended; {summary['generation_due_count']} ready to generate."
    )
    for item in summary["rows"]:
        next_issue = f" next {item['next_issue_on']}" if item["next_issue_on"] else " schedule complete"
        renewal = f"; renewal {item['renewal_state_label']}" if item["renewal_on"] else ""
        print(
            f"#{item['id']} {item['status_label']} {item['kind_label']}: {item['name']} - "
            f"{item['client']} - {item['gbp_value']} {item['cadence_label'].lower()};{next_issue}{renewal}"
        )
    return 0


def cmd_recurring_create(args: argparse.Namespace, data_dir: Path) -> int:
    template_id = create_recurring_revenue_template(
        data_dir,
        name=args.name,
        kind=args.kind,
        client=args.client,
        reference_prefix=args.reference_prefix,
        amount_minor=parse_money_to_minor(args.amount),
        cadence=args.cadence,
        start_on=parse_date(args.start),
        currency=args.currency,
        gbp_minor=parse_money_to_minor(args.gbp_equivalent) if args.gbp_equivalent else None,
        description=args.description,
        payment_terms_days=args.payment_terms,
        generate_ahead_days=args.generate_ahead,
        end_on=parse_date(args.end) if args.end else None,
        renewal_on=parse_date(args.renewal) if args.renewal else None,
        renewal_notice_days=args.renewal_notice,
        total_occurrences=args.occurrences,
        notes=args.notes,
    )
    print(f"Created recurring template #{template_id}.")
    return 0


def cmd_recurring_run(args: argparse.Namespace, data_dir: Path) -> int:
    result = process_recurring_revenue(
        data_dir,
        today=parse_date(args.date) if args.date else None,
        template_id=args.template_id,
    )
    print(
        f"Recurring generation: {result['evaluated']} template(s) reviewed, "
        f"{result['generated']} receivable(s) generated, {result['blocked']} blocked."
    )
    for item in result["results"]:
        detail = f" - {item['reason']}" if item["reason"] else ""
        print(f"- #{item['template_id']} {item['name']}: {item['status']}, {item['generated']} generated{detail}")
    return 0


def cmd_recurring_template_status(args: argparse.Namespace, data_dir: Path) -> int:
    template = update_recurring_revenue_template_status(data_dir, args.id, args.status)
    print(f"Recurring template #{template['id']} marked {template['status_label']}.")
    return 0


def cmd_reconcile_list(args: argparse.Namespace, data_dir: Path) -> int:
    summary = reconciliation_summary(data_dir, status=args.status, limit=args.limit)
    print(
        f"Reconciliation: {summary['review_count']} awaiting review ({summary['awaiting_review']}); "
        f"{summary['matched_count']} matched ({summary['matched']})."
    )
    if not summary["rows"]:
        print("No reconciliation transactions found.")
        return 0
    for item in summary["rows"]:
        reference = item["external_reference"] or f"transaction-{item['id']}"
        suggestion = (
            f" -> receivable #{item['suggested_receivable_id']} at {item['match_confidence']}/100"
            if item.get("suggested_receivable_id")
            else ""
        )
        print(
            f"#{item['id']} {item['status_label']}: {reference} - {item['gbp_value']} - "
            f"{item['payer'] or 'unknown payer'}{suggestion}"
        )
    return 0


def cmd_reconcile_import(args: argparse.Namespace, data_dir: Path) -> int:
    path = Path(args.file).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise DivineToolError(f"CSV file was not found: {path}")
    result = import_reconciliation_csv(
        data_dir,
        csv_text=path.read_text(encoding="utf-8-sig"),
        provider=args.provider,
        dry_run=args.dry_run,
        filename=path.name,
    )
    mode = "ready" if args.dry_run else "imported"
    count = result["ready_count"] if args.dry_run else result["imported_count"]
    print(
        f"Reconciliation import: {count} {mode}, {result['duplicate_count']} duplicate, "
        f"{result['skipped_count']} skipped."
    )
    if result.get("batch_id"):
        print(f"Audit batch: #{result['batch_id']}.")
    return 0


def cmd_reconcile_confirm(args: argparse.Namespace, data_dir: Path) -> int:
    result = confirm_reconciliation_match(
        data_dir,
        transaction_id=args.transaction_id,
        receivable_id=args.receivable_id,
        count_as_income=args.count_as_income,
        note=args.note,
    )
    transaction = result["transaction"]
    receivable = result["receivable"]
    print(
        f"Matched evidence #{transaction['id']} to receivable #{receivable['id']} "
        f"as payment #{result['payment']['id']}."
    )
    print(f"Income treatment: {transaction['income_treatment'].replace('_', ' ')}.")
    return 0


def cmd_reconcile_ignore(args: argparse.Namespace, data_dir: Path) -> int:
    result = ignore_reconciliation_transaction(
        data_dir,
        transaction_id=args.transaction_id,
        reason=args.reason,
    )
    print(f"Ignored reconciliation evidence #{result['transaction']['id']}; decision #{result['decision_id']} recorded.")
    return 0


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
    account = create_account(data_dir, args.username, password, display_name=args.display_name, recovery_email=args.recovery_email)
    print(f"Created owner account: {account['username']}")
    return 0


def cmd_account_list(_args: argparse.Namespace, data_dir: Path) -> int:
    accounts = list_accounts(data_dir)
    if not accounts:
        print("No accounts configured.")
        return 0
    for account in accounts:
        disabled = " disabled" if account["disabled"] else ""
        recovery = f" recovery:{account['recovery_email']}" if account.get("recovery_email") else ""
        print(f"#{account['id']} {account['username']} ({account['role']}){disabled}{recovery}")
    return 0


def cmd_account_reset_password(args: argparse.Namespace, data_dir: Path) -> int:
    password = args.password
    if not password:
        password = getpass.getpass("New owner password: ")
        confirm = getpass.getpass("Confirm new password: ")
        if password != confirm:
            raise DivineToolError("Passwords do not match.")
    account = reset_account_password(data_dir, args.username, password)
    print(f"Password reset for account: {account['username']}")
    print("Existing sessions were signed out.")
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
    print(f"Verification: {backup['verification']['status']}")
    return 0


def cmd_deploy_verify_backup(args: argparse.Namespace, _data_dir: Path) -> int:
    result = verify_backup(Path(args.archive))
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    else:
        print(format_integrity(result, title="Backup verification"))
    return 0


def cmd_deploy_restore(args: argparse.Namespace, data_dir: Path) -> int:
    safety_output = Path(args.safety_output).resolve() if args.safety_output else None
    result = restore_backup(
        Path(args.archive),
        data_dir,
        replace=args.confirm,
        safety_output_dir=safety_output,
        create_safety_backup=not args.skip_safety_backup,
    )
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    else:
        print(f"Restore complete: {result['target']}")
        print(f"Source schema: v{result['source_schema_version']}")
        print(f"Active schema: v{result['schema_version']}")
        if result["safety_backup"]:
            print(f"Safety backup: {result['safety_backup']}")
        print(f"Files: {', '.join(result['restored_files'])}")
    return 0


def cmd_deploy_integrity(args: argparse.Namespace, data_dir: Path) -> int:
    result = state_integrity(data_dir)
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    else:
        print(format_integrity(result))
    return 0 if result["ok"] else 2


def cmd_deploy_drill(args: argparse.Namespace, data_dir: Path) -> int:
    output_dir = Path(args.output).resolve() if args.output else None
    result = run_recovery_drills(data_dir, output_dir)
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    else:
        print(format_recovery_drills(result))
    return 0 if result["ok"] else 2


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
        trigger = "cli" if args.once else "daemon"
        try:
            cycle = run_worker_cycle(data_dir, trigger=trigger, worker_name=trigger)
        except WorkerCycleBusyError as exc:
            print(f"worker busy: {exc}", file=sys.stderr, flush=True)
            if args.once:
                return 2
            time.sleep(max(interval, 1))
            continue
        except Exception as exc:
            if args.once:
                raise
            print(f"worker cycle failed: {exc}", file=sys.stderr, flush=True)
            time.sleep(max(interval, 1))
            continue
        commands = cycle["outcome"]["commands"]
        rules = cycle["outcome"]["rules"]
        approvals = cycle["outcome"]["approvals"]
        for outcome in commands["outcomes"]:
            print(f"command: {outcome['message']}", flush=True)
        if rules["triggered"]:
            print(
                f"rules: {rules['triggered']} triggered, "
                f"{approvals['required']} need approval, {rules['blocked']} blocked",
                flush=True,
            )
        print(
            f"worker: cycle #{cycle['id']} {cycle['status']} via {cycle['trigger']} in {cycle['duration_ms']:.2f} ms",
            flush=True,
        )
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
