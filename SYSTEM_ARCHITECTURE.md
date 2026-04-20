# Badger Automation – System Architecture

# System Overview

Badger Automation integrates Karbon work-item operations with Drake E-file automation so users can process records from a web dashboard and monitor outcomes in near real time.

Core capabilities:

- Karbon work item retrieval and update
- Drake E-file status lookup automation
- Backend API orchestration and validation
- Queue-based background execution for batch flows
- Database-backed automation status tracking
- Frontend polling for live status updates

Main internal flow:

1. User selects records in the UI and starts processing.
2. Backend validates input and starts automation (queued for batch flows, direct for interactive single-check path).
3. Automation service runs Drake interaction and records status changes.
4. Frontend polls status APIs and updates row badges/state.

---

# High-Level Architecture

## Frontend

- Browser UI (`static/js/app.js`, `static/js/karbon_fi.js`, etc.)
- Queries Karbon records for display
- Lets users select and process records
- Polls backend endpoints for per-record automation status

## Backend API

- FastAPI service in `app.py` (Service A)
- Handles frontend HTTP requests
- Validates request payloads
- Coordinates calls to Service B and Karbon APIs
- Returns UI-oriented payloads and summaries

## Automation Queue

- Celery + Redis for asynchronous batch automation
- Decouples request handling from long-running Drake UI work
- Supports safe worker-side execution order for automation tasks

## Worker / Automation Service

- Service B (`drake_service`) owns status persistence and automation execution
- Executes Drake workflows:
  - open session
  - locate client by SSN/EIN
  - retrieve E-file status
- Writes automation status transitions to DB
- Applies Karbon updates when outcomes require it

## Database

- Owned by Service B
- Stores per-work-item automation status records
- Serves as source of truth for polling endpoints

---

# Automation Workflow

1. User selects work items in frontend.
2. Frontend sends selected keys to backend.
3. Backend creates automation work and status tracking records.
4. Tasks are pushed into queue for batch processing.
5. Worker pulls tasks and runs Drake automation.
6. Worker opens Drake and searches client.
7. Worker retrieves E-file status.
8. If result is Accepted/Rejected, Karbon work item is updated.
9. Worker/service writes final automation status to DB.
10. Frontend polls status endpoint and refreshes row badges/controls.

Flow view:

```text
Frontend
  -> Backend API
  -> Queue
  -> Worker
  -> Drake
  -> Database
  -> Frontend polling
```

---

# Key Backend Modules

- `services/karbon_service`
  - Karbon API integration and work item update logic.

- `services/drake_service`
  - Drake automation helpers (session setup, client lookup behavior).

- `drake_service/services/drake_automation_service.py`
  - Primary automation execution service for batch and interactive paths.

- `drake_service/core/celery_app.py` and `drake_service/tasks/automation_tasks.py`
  - Queue setup and worker task entrypoints.

- `drake_service/api/workitems_routes.py`
  - Read/write endpoints for automation status records.

- `api/automation_routes.py`
  - Service A proxy endpoints for frontend polling.

- API routers in `app.py` and `drake_service/api/*`
  - Expose UI-facing and internal automation REST endpoints.

---

# Important API Endpoints

## GET `/api/karbon/efile-status-work-items`

- Purpose: fetch Karbon records for E-file status processing UI.
- Typical behavior: returns list of work items for selection and rendering.

## POST `/api/karbon/efile-status/check-client`

- Purpose: check Drake E-file status for one client/work item.
- Request includes `client_id`, optional `client_name`, optional `work_item_key`.
- Response includes outcome/status payload used by UI row update flow.

## POST `/api/karbon/update-workitem-status`

- Purpose: write accepted/rejected result back to Karbon work item.

## GET `/api/workitems/status`

- Purpose: fetch automation status for multiple work item keys.
- Used by frontend polling to render badges/messages/timestamps dynamically.

## POST `/api/karbon/send-efile-summary`

- Purpose: send summary email after processing run completes.

---

# Automation Status Model

Primary statuses used in E-file automation:

- `NOT_STARTED`
- `IN_QUEUE`
- `PROCESSING` / `IN_PROCESSING`
- `SUCCESS`
- `FAIL`
- `CLIENT_NOT_FOUND`
- `MISSING_TAX_ID`

How these statuses affect behavior:

- Drive badge label/color in UI
- Control polling continuation/stopping conditions
- Influence row selection/interaction rules configured in frontend logic

---

# Frontend Status Polling

- Frontend calls `/api/workitems/status` with tracked keys.
- Backend reads DB status and returns status map.
- UI updates each row:
  - badge
  - message
  - timestamp
  - selectable state

Polling model:

```text
UI timer -> /api/workitems/status -> DB status map -> row-by-row render update
```

---

# Logging and Monitoring

Logging layers:

- Service A request/response and orchestration logs
- Service B automation and status transition logs
- Worker execution logs for queued tasks
- Exception traces with context fields (`work_item_key`, client id, status)

Operational value:

- Diagnose Drake session/open/search issues
- Trace failures in status update pipelines
- Understand per-batch success/failure distribution

---

# Error Handling

- Input validation errors return `400` with useful details.
- Unexpected failures return `500` and are logged with stack traces.
- Automation failures are recorded as `FAIL` in status tables.
- UI reflects failures via badges/messages; summaries include failure totals.

---

## 4. Database Setup (PostgreSQL)

**Database is owned by Service B.** Service A does not connect to PostgreSQL.

### Run PostgreSQL

```bash
docker run -d \
  -p 5432:5432 \
  -e POSTGRES_USER=automation \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=automation_db \
  postgres
```

### Run Migrations (from Service B)

```bash
cd BadgerAutomation/drake_service
alembic upgrade head
```

### Create migration (when schema changes)

```bash
cd BadgerAutomation/drake_service
alembic revision --autogenerate -m "add workitem status table"
alembic upgrade head
```

### karbon_efile_status_jobs table

Tracks processing status of automation jobs that push Efile Status to Karbon.

| Column       | Type      | Description                                                                |
| ------------ | --------- | -------------------------------------------------------------------------- |
| id           | UUID      | Primary key                                                                |
| workitem_id  | VARCHAR   | Karbon `workItemKey` (unique, indexed)                                     |
| client_id    | VARCHAR   | Karbon client/registration number (optional)                                |
| status       | VARCHAR   | See **Status lifecycle** below                                             |
| message      | VARCHAR   | Optional error or result message from Drake / automation                   |
| created_at   | TIMESTAMP | Row creation time                                                          |
| updated_at   | TIMESTAMP | Last status update time                                                    |
| processed_at | TIMESTAMP | When automation completed                                                  |

### karbon_filing_instruction_jobs table

Tracks processing status of automation jobs that push Filing Instruction to Karbon.

| Column       | Type      | Description                                                                |
| ------------ | --------- | -------------------------------------------------------------------------- |
| id           | UUID      | Primary key                                                                |
| workitem_id  | VARCHAR   | Karbon `workItemKey` (unique, indexed)                                     |
| client_id    | VARCHAR   | Karbon client/registration number (optional)                                |
| status       | VARCHAR   | SUCCESS \| FAIL                                                             |
| message      | VARCHAR   | Error details on FAIL                                                      |
| created_at   | TIMESTAMP | Row creation time                                                          |
| updated_at   | TIMESTAMP | Last status update time                                                    |
| processed_at | TIMESTAMP | When automation completed                                                  |

#### Status lifecycle (database → UI)

Statuses stored in PostgreSQL:

- `NOT_STARTED`
- `IN_QUEUE`
- `IN_PROCESSING` (alias: `PROCESSING`)
- `SUCCESS`
- `FAIL` (canonical; aliases: `ERROR`, `FAILED`)
- `CLIENT_NOT_FOUND`
- `MISSING_TAX_ID`
- `AGENCY_ACCEPTED`, `AGENCY_REJECTED` (legacy; prefer `SUCCESS` + message)

Lifecycle for a typical automation run:

```text
NOT_STARTED
  → IN_QUEUE
  → IN_PROCESSING
  → (SUCCESS | CLIENT_NOT_FOUND | FAIL | MISSING_TAX_ID)
```

UI (`Drake Efile Status` column) shows:

| DB Status        | UI Text                  |
| -----------------| ------------------------- |
| NOT_STARTED      | Not Checked               |
| IN_QUEUE         | In Queue                  |
| IN_PROCESSING    | In Processing             |
| SUCCESS + accepted | Agency Accepted         |
| SUCCESS + rejected | Agency Rejected         |
| CLIENT_NOT_FOUND | Client Not Found in Drake |
| FAIL             | Error                     |
| MISSING_TAX_ID   | Missing Tax ID/SSN       |

---

## 5. How to Run the System

### 1. Start PostgreSQL

```bash
docker run -d -p 5432:5432 -e POSTGRES_USER=automation -e POSTGRES_PASSWORD=password -e POSTGRES_DB=automation_db postgres
```

### 2. Run Database Migrations (Service B)

```bash
cd BadgerAutomation/drake_service
alembic upgrade head
```

### 3. Run Redis

```bash
docker run -d -p 6379:6379 redis
```

Or use a local Redis installation.

### 4. Run Service B

```bash
cd BadgerAutomation
uvicorn drake_service.app:app --reload --port 8001
```

### 5. Run Celery Worker

From project root:

```bash
cd BadgerAutomation
celery -A drake_service.core.celery_app:celery_app worker --loglevel=info -Q drake_queue
```

On Windows:

```bash
celery -A drake_service.core.celery_app:celery_app worker --loglevel=info -Q drake_queue --pool=solo
```

Or use `start_drake_worker.bat`.

### 6. Run Service A

```bash
cd BadgerAutomation
uvicorn app:app --reload --port 8000
```

### 7. Open Frontend

Navigate to `http://localhost:8000` (served by Service A).

---

## 6. Environment Variables

### Service A (.env)

| Variable                                   | Description                            | Default                     |
| ------------------------------------------ | -------------------------------------- | --------------------------- |
| `SERVICE_B_BASE`                           | Service B base URL (used for status, enqueue, check-trigger) | `http://localhost:8001` |
| `SERVICE_B_URL`                            | Alias for SERVICE_B_BASE               |                             |
| `KARBON_ACCESS_KEY`, `KARBON_BEARER_TOKEN` | Karbon API                             | From .env                   |
| `DRAKE_EXE`, `DRAKE_CWD`, `DRAKE_TITLE`    | Drake application paths                | From .env                   |
| `USERNAME_DRAKE`, `PASSWORD_DRAKE`         | Drake credentials                      | From .env                   |
| `EXPORT_FOLDER`                            | Drake client export folder             | From DrakeAutomation config |

### Service B (.env)

| Variable                                   | Description                            | Default                     |
| ------------------------------------------ | -------------------------------------- | --------------------------- |
| `DATABASE_URL`                             | PostgreSQL connection                  | `postgresql://...`          |
| `REDIS_URL`                                | Redis connection for Celery            | `redis://localhost:6379/0`  |
| `SERVICE_A_BASE`                           | Service A base URL (if callbacks needed; currently unused) | `http://localhost:8000` |
| `DRAKE_EXE`, `DRAKE_CWD`, `DRAKE_TITLE`    | Drake application paths                | From .env                   |
| `USERNAME_DRAKE`, `PASSWORD_DRAKE`         | Drake credentials                      | From .env                   |
