# Developer Runbook - Workspace Version (Keystrokes-Dynamic)

This is the workspace-specific first-run guide for this repository.

## Workspace Snapshot

1. Main app service in Docker Compose: `app`
2. App port mapping: `5000:5000`
3. Health endpoints:
- `/health/live`
- `/health/ready`
4. Data persistence mode:
- bind mount `./data:/app/data`

Note:
- Because this workspace uses bind mount for data, it is normal that Docker Desktop "Volumes" page does not show a named volume for this app.

## Prerequisites

1. Docker Desktop installed and running.
2. Port `5000` is available.
3. Run commands from repository root.

## First Run (PowerShell)

1. Create local env file:

```powershell
Copy-Item .env.example .env
```

2. Check Docker + Compose:

```powershell
docker --version
docker compose version
```

3. Validate compose config:

```powershell
docker compose config
```

Expected:
- no parse error
- service `app` appears

4. Build and start stack:

```powershell
docker compose up --build -d
```

5. Verify status:

```powershell
docker compose ps
```

Expected:
- `app` transitions to `healthy`

6. Verify health endpoints:

```powershell
Invoke-WebRequest http://localhost:5000/health/live -UseBasicParsing | Select-Object StatusCode
Invoke-WebRequest http://localhost:5000/health/ready -UseBasicParsing | Select-Object StatusCode
```

Expected:
- both return `200`

7. Open app:

```text
http://localhost:5000
```

## Manual Functional Validation

1. Registration flow:
- open `/register`
- submit username + email
- complete keystroke enrollment samples until target reached

2. Login flow:
- open `/login`
- type same password rhythm
- verify redirect to dashboard

3. Dashboard API key flow:
- generate one key
- verify key appears one-time in result panel
- deactivate key

4. Password reset flow:
- trigger reset from dashboard
- complete verification and set new password

Expected:
- no 500 errors
- clear validation messages for invalid input

## Automated Smoke Validation

Run from host:

```powershell
docker compose exec app python quick_smoke.py
```

Expected output:

```text
SMOKE_CHECK: PASS
```

## Runtime and Data Notes

1. Flask host behavior:
- local non-Docker default host: `127.0.0.1`
- Docker Compose sets `HOST=0.0.0.0`

2. Database persistence:
- SQLite file is persisted in local folder `./data`

3. Secrets:
- do not commit `.env`
- rotate any real credentials before sharing workspace

## Useful Commands

View logs:

```powershell
docker compose logs -f app
```

Restart app service:

```powershell
docker compose restart app
```

Stop stack:

```powershell
docker compose down
```

Rebuild from scratch:

```powershell
docker compose down
docker compose up --build -d
```

Inspect mount mode used by container:

```powershell
$cid = docker compose ps -q app
docker inspect $cid --format "{{json .Mounts}}"
```

## Troubleshooting

1. `docker` command not found:
- reopen terminal after Docker install
- confirm Docker Desktop is running

2. Container healthy but host cannot access app:
- ensure app binds to `0.0.0.0` in Docker (`HOST` env)
- check with `docker compose logs -f app`

3. Service stuck `unhealthy`:
- inspect logs and health endpoint route behavior
- run `docker compose logs --tail 100 app`

4. Port `5000` already in use:
- stop conflicting process or remap port in `docker-compose.yml`
