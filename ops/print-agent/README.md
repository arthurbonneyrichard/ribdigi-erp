# Till print agent

Runs **on the till computer**, not in the browser. It collects this till's print
jobs from the ERP and sends ESC/POS bytes straight to the thermal printer, with
no print dialog. Python 3.10+ only; nothing to install with pip.

A job is reported **printed** only when the printer, or the Windows print queue,
accepted it. That is not a paper sensor: check the first slips by eye.

## 1. Check the printer first (no ERP needed)

```powershell
python agent.py test "windows:Xprinter XP-80"     # USB, LAN or Bluetooth printer installed in Windows
python agent.py test "tcp:192.168.1.130:9100"     # network printer by IP
python agent.py test "serial:COM5@19200"          # serial or Bluetooth COM port
```

Linux: `python3 agent.py test "file:/dev/usb/lp0"` (only from the till's own settings).
Android tablets are supported only through a network printer reached by an agent
on another computer on the same network.

## 2. Pair

1. Sign in as Company Admin (or a role with `printers:write`).
2. **Printers → Network or till agent → Issue till pairing code**.
3. On the till (PowerShell):

```powershell
$env:RIBDIGI_API_BASE = "https://YOUR-ERP/api/v1"
python agent.py pair ABCD1234 "Front till"
$env:RIBDIGI_AGENT_TOKEN = "rdp_..."     # shown once
python agent.py
```

Keep it running (Windows Task Scheduler, "At log on"). Do **not** commit tokens
or `.env` files.

## 3. Add the printer in the ERP

Connection **Paired till agent**, then say how the till reaches it: installed
Windows printer, IP address, COM port, or the till's own `RIBDIGI_PRINTER`.
Tick the jobs it prints. On each till open **Printers → Automatic receipt
printing on this till** to choose its printer.

## Offline sales

`python agent.py` also listens on `127.0.0.1:8765` (`RIBDIGI_OFFLINE_PORT`).
When the till has no connection, the ERP page sends the provisional receipt to
`/v1/print` there. Only the ERP's own web address may print: it is taken from
`RIBDIGI_API_BASE`; set `RIBDIGI_WEB_ORIGIN` if the web app has a different
address. The printer is `RIBDIGI_PRINTER`, or the one the last receipt used.
Chrome may ask once to allow the page to reach this computer.

The same listener keeps a copy of queued offline sales outside the browser:

- `RIBDIGI_OFFLINE_JOURNAL`, or
- `%LOCALAPPDATA%\Ribdigi\pos-offline-journal.json` on Windows

`python agent.py journal` runs only the listener. It does not need
`RIBDIGI_AGENT_TOKEN` and it does not upload the sale.

## Troubleshooting

| Message | Meaning |
|---|---|
| `did not print. Check that it is switched on and connected` | Windows kept the job; the agent removed it from the queue |
| `Could not reach the printer at …` | Wrong IP, printer off, or a different network |
| `The printer is out of paper` / `offline` | Network printer status answer |
| `Windows has no printer called …` | The name must match Windows exactly |

`python agent.py --dry-run` prints the text to the window and never reports a job
as printed.
