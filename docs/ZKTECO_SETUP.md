# ZKTeco terminals and BioTime: setting up on site

The HR desk takes fingerprint / face punches two ways (`backend/app/hrm_biometric.py`). It is built to ZKTeco's published behaviour and tested only with simulated traffic, so the first real terminal or BioTime server must be checked on site with the **Check** button (HR → Time → Terminals) before staff rely on it.

## Before you start

1. Every member of staff who punches needs their **terminal user ID (PIN)** on their HR staff record (field "Terminal ID"). It must match the user ID on the terminal exactly. Two records cannot share a PIN.
2. The company's timezone (Company settings) must be right: terminals send local time, and the ERP turns it into UTC.

## Option A: terminal pushes to the ERP (ADMS / "Cloud Server")

1. In the ERP: HR → Time → Terminals → add **Terminal push** with the terminal's **serial number** (Menu → System Info → Device Info on most models). Copy it exactly.
2. Production only, once: the web server must send `/iclock` to the backend. In Dokploy add a domain rule **Path `/iclock` → backend service** (the terminal calls `/iclock/cdata` at the root, not under `/api/v1`).
3. On the terminal: Menu → Comm. → **Cloud Server Setting** (or ADMS):
   - Server address: the ERP's web address (no `https://`, no path).
   - Port: 443 with HTTPS on, or 80 if the model has no HTTPS.
   - Proxy: off. Domain name: on if you typed a name rather than an IP.
4. Restart the terminal. Within a minute it should call in.
5. In the ERP press **Check**. "Working" with "last heard N min ago" means it is talking. Punch once and see the time appear on today's clock board.

The push protocol has no password: a terminal is known by its serial. Punches from terminals are marked *biometric* on the daily sheet for HR to review.

## Option B: the ERP reads from the company's BioTime server

1. In BioTime (8.x) make an API user that may read transactions.
2. The BioTime server must be reachable from the internet (usually HTTPS on a public address). The ERP refuses private and local addresses.
3. In the ERP: HR → Time → Terminals → add **BioTime** with its address, API user and password (stored encrypted).
4. Press **Check**: it signs in and reads one page without storing anything. "Working · N punches on the BioTime server" means it can read. Then **Sync now** (it reads from the last sync, up to 50 pages a time).

## Reading the Check result

| Result | What to do |
| --- | --- |
| Has not called in yet | Check the serial typed in the ERP, the Cloud Server address and port, and the `/iclock` rule. |
| Gone quiet | The terminal was heard before but not for over 15 minutes: power, network or its clock. |
| Sign-in refused | Wrong BioTime user or password, or the user may not use the API. |
| Cannot read punches | Signed in, but the user has no rights to transactions. |
| Cannot reach the server | The BioTime address is not reachable from the internet. |
| No terminal ID on their record | Add the PIN to those staff records, or their punches are not counted. |
| Terminal IDs that punched but match nobody | Someone punched with a PIN no staff record has. Put it on the right record; later punches will count. |

## What still needs a real device

- Exact state codes on your model (0/3/4 = in, 1/2/5 = out; others alternate). Check a day's in/out on the clock board.
- Terminals that send other tables (user info, photos) are answered OK and ignored.
- Clock drift on the terminal shows as wrong times; keep the terminal's time synced.
