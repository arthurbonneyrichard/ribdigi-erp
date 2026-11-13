# Server health (software owner)

Platform → **Server health** (`/platform/monitor`) shows the VPS that runs Ribdigi, live and over time.

## What is read

| Area | Reading |
|---|---|
| Machine | CPU %, load average per core, memory and swap, container memory cap, free disk on the system disk, backup and upload folders, server uptime |
| API | process memory, threads, uptime; request speed for the last 15 minutes (p50 / p95 / p99), requests per minute, server-error rate, slowest areas |
| Databases | main database reply time, size, connections vs `max_connections`, queries running over 30 s; each desk database's reply time |
| Redis | reply time, memory, clients |
| Workers | Celery workers answering a ping; when the scheduler last ran the monitor job |
| Backups | last finished backup, failures in 24 h |
| Public site | the `MONITOR_PUBLIC_URL` (or `FRONTEND_URL`) answers; TLS certificate days left |

Request speed is measured inside each API worker, so with several uvicorn workers the page shows the worker that answered.

## History and uptime

The Celery job `sample_server_health` records one reading a minute (Redis list `ribdigi:monitor:samples`, 7 days). The page also records one when the last is older than 55 s, so history exists without Celery. "24 h uptime" is the share of readings where the service was up: main and desk databases, Redis, workers and the public site answered. A failing backup, certificate, disk, CPU or slow-reply check still raises an alert and colours the timeline, but is not downtime. Each reading keeps `up` and `bad` (the critical check keys).

## Alerts

A check that turns **critical** notifies platform staff (category `server_health`: in-app and email by default; each person can change it under Notifications). It repeats at most once per `MONITOR_ALERT_COOLDOWN_MINUTES` and sends a "recovered" note when it clears. **Send test alert** on the Alerts tab proves delivery.

| Setting | Default |
|---|---|
| `MONITOR_CPU_ALERT_PCT` | 90 |
| `MONITOR_MEMORY_ALERT_PCT` | 90 |
| `MONITOR_DISK_ALERT_PCT` | 85 |
| `MONITOR_DB_LATENCY_ALERT_MS` | 500 |
| `MONITOR_P95_ALERT_MS` | 2000 |
| `MONITOR_ERROR_RATE_ALERT_PCT` | 5 |
| `MONITOR_BACKUP_MAX_AGE_HOURS` | 36 |
| `MONITOR_CERT_ALERT_DAYS` | 14 |
| `MONITOR_ALERT_COOLDOWN_MINUTES` | 30 |

The monitor runs on the same server it watches. If the whole VPS is down, nothing inside it can alert you: add one outside check (UptimeRobot, Better Stack or similar) on `https://<your domain>/api/v1/health`.

## Launch checks

The **Launch checks** tab lists what must be true before taking paying customers (production mode, https and certificate, 2FA, encryption keys, platform email, live payment gateway, recent backups, workers, off-server storage, metrics token), each with how to fix it. "Fix" items block "Ready"; "Improve" items are recommended.
