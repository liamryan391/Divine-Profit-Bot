# Divine Tool

Divine Tool is a local command-line revenue cockpit. It tracks a weekly or monthly GBP quota, records lawful income, accepts queued commands, and can run as a small background daemon that watches the quota state.

It does not perform fraud, spam, unauthorized access, market manipulation, or autonomous real-money trading. It is built to help the Creator pursue legitimate revenue and decide what to upgrade next.

Project direction: this is moving toward a hybrid web app plus daemon worker. See [ROADMAP.md](ROADMAP.md) for phases, stages, and release gates.

## Quick Start

```powershell
python -m divine_tool init
python -m divine_tool status
python -m divine_tool quota set watchful 250 --period week
python -m divine_tool income add 75 --source "paid consultation"
python -m divine_tool opportunities
python -m divine_tool upgrade
```

For non-GBP income, provide the GBP equivalent so the quota accounting is explicit:

```powershell
python -m divine_tool income add 0.01 --currency BTC --gbp-equivalent 420 --source "crypto sale"
```

## Background Mode

Run one daemon pass:

```powershell
python -m divine_tool daemon --once
```

Queue commands for the daemon:

```powershell
python -m divine_tool command add-income 25 --source "queued invoice"
python -m divine_tool command set-mood hungry
python -m divine_tool daemon --once
```

Run continuously:

```powershell
python -m divine_tool daemon --interval 300
```

On Windows, you can start it hidden from PowerShell:

```powershell
Start-Process python -ArgumentList "-m divine_tool daemon --interval 300" -WindowStyle Hidden
```

## Data

By default, state lives in `.divine_tool/`:

- `config.json`: quota, moods, channels, automation settings, and boundaries.
- `divine_tool.sqlite3`: income ledger and exceptions.
- `commands.jsonl`: daemon command inbox.

Use another state directory with:

```powershell
python -m divine_tool --data-dir C:\path\to\state status
```

## Useful Commands

```powershell
python -m divine_tool mood set merciful
python -m divine_tool quota set hungry 1500 --period month
python -m divine_tool exception add --reason "payment processor outage" --until 2026-08-30
python -m divine_tool income list
python -m divine_tool config show
```
