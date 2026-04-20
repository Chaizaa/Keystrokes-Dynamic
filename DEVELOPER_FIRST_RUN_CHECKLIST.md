# Developer First-Run Checklist (Docker)

This checklist is for developers who want to run and validate the app locally using Docker.

## Prerequisites

1. Docker Desktop is installed and running.
2. Port `5000` is free on your machine.
3. You are in project root.

## First Run

1. Build and start containers:

```powershell
docker compose up --build -d
```

Expected:
- `app` container is created and running.
- first build can take a few minutes.

2. Verify container status:

```powershell
docker compose ps
```

Expected:
- service `app` shows `running` and then `healthy`.

3. Check health endpoints:

```powershell
Invoke-WebRequest http://localhost:5000/health/live
Invoke-WebRequest http://localhost:5000/health/ready
```

Expected:
- both return HTTP `200`.

4. Open app in browser:

```text
http://localhost:5000
```

## Manual User Flow Validation

1. Register a new user:
- open `/register`
- fill username + email
- type password in the keystroke capture form
- keep submitting samples until enrollment reaches target

Expected:
- enrollment progress increases each sample
- registration flow completes without server errors

2. Login as that user:
- open `/login`
- type the same password rhythm

Expected:
- successful login to dashboard

3. Dashboard API key checks:
- on dashboard, generate a key with partner name
- confirm key appears once in result panel
- deactivate the key

Expected:
- generate endpoint returns success
- key list updates correctly
- deactivate endpoint returns success

4. Reset password flow:
- click reset password from dashboard
- continue code verification + new password flow

Expected:
- if SMTP is configured: reset code flow works end-to-end
- if SMTP is not configured: user gets clear failure message, app stays stable

## Automated Quick Smoke

Run this from host:

```powershell
docker compose exec app python quick_smoke.py
```

Expected output:

```text
SMOKE_CHECK: PASS
```

## Useful Commands

View logs:

```powershell
docker compose logs -f app
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

## Quick Troubleshooting

1. `docker` command not found:
- install Docker Desktop or reopen terminal after installation.

2. service stuck `unhealthy`:
- run `docker compose logs -f app`
- check DB migration/startup errors.

3. port `5000` already in use:
- stop conflicting process, or change port mapping in `docker-compose.yml`.
