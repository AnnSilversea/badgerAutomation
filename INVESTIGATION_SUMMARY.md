# Investigation Summary – Drake Automation Endpoints

## 1. Automation Endpoints (Trigger Drake UI Automation)

| Endpoint | Method | Request Model | Response | Internal Calls |
|----------|--------|---------------|----------|-----------------|
| `/api/drake/launch` | POST | `DrakeLaunchRequest` (job_id, client_id, data) | `{status, message, job_id, client_id, form_type, items_processed, execution_time_seconds}` | `run_drake_fill_in_flow` (DrakeAutomation.drake_fill_in_flow) |
| `/api/drake/query-clients` | POST | (none) | List of `{Taxpayer ID, Taxpayer Name, Return Type}` | `run_export_client_flow` (DrakeAutomation.export_excel_client) |
| `/api/drake/print-return` | POST | `DrakePrintRequest` (client_id, return_type) | `{status, message, job_id}` or `{status, failed, message}` | OpenDrake, LoginFlow, ClientFlow, PackagePDF, wait_data_entry |
| `/api/drake/efile/open` | POST | (none) | `{status}` | OpenDrake, LoginFlow, EFPrepareFlow |
| `/api/drake/efile/select-clients` | POST | `DrakeEfileBatchRequest` (client_ids) | `{status, processed_count, client_status}` | ClientSelectionFlow |
| `/api/drake/efile/close` | POST | `DrakeEfileCloseRequest` (success_count) | `{status}` | ClientSelectionFlow, findwindows |
| `/api/karbon/process-fi` | POST | `EfileProcessRequest` (work_item_keys, user_email, close_drake, send_email) | `{processed_count, totals, details}` | OpenDrake, LoginFlow, ClientFlow, PackagePDF, KarbonClient.upload_file |
| `/api/karbon/process-efile-status` | POST | `EfileProcessRequest` (work_item_keys, user_email, send_email) | `{message, processed_count, updates_found, totals, details, karbon_update_result}` | `check_clients_status_in_drake` (services.drake_service) → open_efile_session, EfileStatus |
| `/api/karbon/efile-status/open` | POST | (none) | `{status, message}` | `open_efile_status_session_svc` → open_efile_session, EfileStatus |
| `/api/karbon/efile-status/check-client` | POST | `EfileStatusCheckRequest` (client_id, client_name) | `{status, drake_status}` | EfileStatus.get_client_status |
| `/api/karbon/efile-status/close` | POST | (none) | `{status, message}` | Closes GLOBAL_EFILE_STATUS_CONTEXT session |

## 2. Non-Automation Drake Endpoints (File/Data Only)

| Endpoint | Method | Notes |
|----------|--------|-------|
| `/api/drake/file-metadata` | GET | Reads EXPORT_FOLDER for latest CSV metadata |
| `/api/drake/latest-clients` | GET | Reads latest CSV from EXPORT_FOLDER |
| `/api/drake/efile/send-summary` | POST | Email only – no Drake UI |

## 3. DrakeAutomation Module Usage

- **DrakeAutomation.drake_fill_in_flow**: `run_drake_fill_in_flow(form_type, client_id, list_data)`
- **DrakeAutomation.export_excel_client**: `main()` as `run_export_client_flow`, `get_latest_file`, `EXPORT_FOLDER`
- **DrakeAutomation.core.app**: `OpenDrake`
- **DrakeAutomation.flows.login**: `LoginFlow`
- **DrakeAutomation.flows.efile_status**: `EfileStatus`
- **DrakeAutomation.flows.package**: `PackagePDF`
- **DrakeAutomation.flows.client**: `ClientFlow`
- **DrakeAutomation.flows.efile**: `EFPrepareFlow`
- **DrakeAutomation.flows.search_clientID**: `ClientSelectionFlow`
- **DrakeAutomation.ui.waits**: `wait_data_entry`
- **services.drake_service**: `check_clients_status_in_drake`, `open_efile_session`, `clear_find_client_dialog`

## 4. Frontend Files Calling Automation Endpoints

| File | Function/Context | Endpoint(s) |
|------|-----------------|-------------|
| `static/js/drake_app.js` | Launch Drake automation | `POST /api/drake/launch` |
| `static/js/client_table.js` | Query clients, print return, efile flow | `POST /api/drake/query-clients`, `POST /api/drake/print-return`, `POST /api/drake/efile/open`, `POST /api/drake/efile/select-clients`, `POST /api/drake/efile/close`, `POST /api/drake/efile/send-summary`, `GET /api/drake/file-metadata`, `GET /api/drake/latest-clients` |
| `static/js/app.js` | E-file status flow | `POST /api/karbon/efile-status/open`, `POST /api/karbon/efile-status/check-client`, `POST /api/karbon/update-workitem-status`, `POST /api/karbon/efile-status/close`, `POST /api/karbon/send-efile-summary`, `GET /api/karbon/efile-status-work-items` |
| `static/js/karbon_fi.js` | FI processing | `POST /api/karbon/process-fi`, `POST /api/karbon/send-fi-summary` |

## 5. Architecture Decision

- **Frontend unchanged** (except EF batch optimization): Frontend continues to call Service A (same URLs).
- **Service A**: Proxies automation requests to Service B via HTTP; keeps non-automation logic.
- **Service B**: Runs Drake automation via Celery queue; exposes automation endpoints.

## 6. Frontend Changes (Post-Refactor)

| File | Function | Change |
|------|----------|--------|
| `static/js/client_table.js` | `handleBatchEF()` | Replaced open → loop(select-clients) → close with single `select-clients` call passing all `client_ids` at once. Backend now runs full batch in one task. |
