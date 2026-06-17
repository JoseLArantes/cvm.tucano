# CVM Data Updates Service - Architecture & Implementation Plan

## 1. Executive Summary

This document describes the architecture and implementation plan for a **CVM Data Updates Service** that provides controlled, manual-triggered management of CVM data file updates. 

**This is a data management project that is totally interfaced by the API endpoints it exposes and the jobs it manages.** All operations related to managing, triggering, starting, stopping, or controlling updates must be exposed as API endpoints to be consumed by diverse frontend layers. The only exception is the scanner job itself, which runs on a schedule to detect changes; however, the actual execution of updates (the ingestion process) must always originate from explicit API calls, never automatically.

The service complements the existing ingestion pipeline by introducing a **detection-first workflow** that separates change discovery from actual data ingestion.

### 1.1 Key Objectives

| Objective | Description |
|---|---|
| **Automated Scanning** | Scheduled job that performs daily remote probing of all CVM data sources to detect changes (this is the ONLY scheduled/automatic component) |
| **Deep Change Analysis** | When a ZIP update is detected, download and evaluate member-by-member to identify specific files with pending updates |
| **Update-Ready Session** | Maintain a persistent session/list of files that have been analyzed and are ready for ingestion |
| **API-Driven Control** | All update execution (triggering, starting, stopping) happens ONLY through API endpoints; never auto-execute ingestion |
| **Integration with Existing Pipeline** | Leverage existing `source_registry`, probing, and staging infrastructure |

### 1.2 Problem Statement

The current ingestion pipeline (via Celery beat) automatically triggers pre-processing and ingestion when changes are detected. While robust, this approach:
- **Lacks visibility**: No centralized dashboard of pending updates across all sources
- **Lacks granularity**: Cannot see which specific members within a ZIP have changes before ingestion
- **Lacks control**: Automatically processes all detected changes without manual oversight
- **Mixes concerns**: Detection, analysis, and ingestion are tightly coupled

The new service addresses these gaps by introducing a **detection and staging layer** that prepares updates for ingestion but requires manual trigger to execute.

---

## 2. Design Principles

### 2.1 API-First Architecture

**This service follows a strict API-first principle:**

- ✅ **ALL** operations for managing updates (triggering, starting, stopping, discarding, session management) **MUST** be exposed as REST API endpoints
- ✅ Diverse frontend layers (web UI, CLI, external systems, scripts) can consume these endpoints
- ✅ The API is the **sole interface** for controlling update execution
- ❌ **NO** automatic ingestion triggering - all update execution originates from API calls

### 2.2 Scheduled vs. API-Triggered Components

| Component | Type | Trigger Mechanism |
|---|---|---|
| `UpdateScanner` | Scheduled Job | Celery Beat (configurable cron schedule) |
| `DeepAnalyzer` | On-Demand Task | API call or auto-queued after detection (configurable) |
| Update Triggering | API Endpoint | Explicit `POST /api/updates/{id}/trigger` call |
| Session Management | API Endpoint | Explicit API calls |
| Bulk Operations | API Endpoint | Explicit API calls |

**The scanner is the ONLY component that runs automatically.** All other operations require explicit API calls.

---

## 3. Background: How CVM Updates Work

### 3.1 CVM Update Mechanism (from CVM.md)

The CVM employs **complete file regeneration**:

1. **Reapresentation Flow**: When a company corrects a submission, they send a reapresentation via Sistema Empresas.NET. Each submission receives a sequential `VERSAO` number (1 = original, 2 = first correction, etc.)

2. **File Replacement**: CVM does **NOT** use append or partial updates. Instead:
   - The **entire annual ZIP file** (e.g., `dfp_cia_aberta_2025.zip`) is regenerated
   - The new ZIP contains **ALL versions** of all forms submitted to date
   - Old versions are **NOT removed** - the CSV accumulates all versions
   - Consumers must filter by `MAX(VERSAO)` for each `CNPJ_CIA + DT_REFER` combination

3. **Logical Primary Key**: All CVM data files use the combination:
   ```
   CNPJ_CIA + DT_REFER + VERSAO
   ```

### 3.2 Update Cadence

| Source Type | Cadence | Notes |
|---|---|---|
| CAD (Cadastro) | Daily | Latest business day data |
| DFP, ITR, FRE, FCA, CGVN, VLMO | Weekly | Tue-Sat at 08h (current year & previous year) |
| IPE | Weekly | Tue-Sat at 08h (current year & previous year) |
| Older years (A-2+) | Weekly | Monday at 08h |

### 3.3 Detection Methods

Three methods to detect CVM updates (in order of robustness):

1. **HTTP HEAD**: Compare `Last-Modified` header
2. **HTTP ETag**: Compare entity tag
3. **CKAN Metadata**: Check package metadata modification date

---

## 4. Proposed Architecture

### 4.1 High-Level Design

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CVM Data Updates Service                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────┐  │
│  │  Daily       │     │  On-Demand   │     │  Manual Trigger       │  │
│  │  Scanner     │────▶│  Deep        │────▶│  (API/CLI)           │  │
│  │              │     │  Analyzer    │     │                      │  │
│  └──────────────┘     └──────────────┘     └──────────┬───────────┘  │
│                                                      │                 │
│                      ┌───────────────────────────────────┼─────────┐ │
│                      │         Pending Updates Registry        │    │ │
│                      │  ┌───────────────────────────────────────┐ │    │ │
│                      │  │  • Source/Year combinations with changes│ │    │ │
│                      │  │  • Member-level change analysis       │ │    │ │
│                      │  │  • Ready-for-ingestion status           │ │    │ │
│                      │  │  • Manual trigger endpoints             │ │    │ │
│                      │  └───────────────────────────────────────┘ │    │ │
│                      └───────────────────────────────────┬─────────┘ │
│                                                              │          │
└──────────────────────────────────────────────────────────┼──────────┘
                                                               │
┌──────────────────────────────────────────────────────────▼──────────┐
│                 Existing Ingestion Pipeline (Reused)                 │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────┐  │
│  │ Pre-         │     │ Ingestion    │     │ Domain Tables        │  │
│  │ Processing   │────▶│ Phase        │────▶│ (Companhia, DFP, etc.)│  │
│  │ (Phase 1)    │     │ (Phase 2)    │     │                      │  │
│  └──────────────┘     └──────────────┘     └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Service Components

| Component | Type | Responsibility | Technology |
|---|---|---|---|
| `UpdateScanner` | Scheduled Task | Daily HTTP HEAD probe of all CVM sources | Celery Beat |
| `DeepAnalyzer` | On-Demand Task | Download ZIP, extract members, compare hashes | Celery Task |
| `PendingUpdatesRegistry` | Data Store | Track all detected and analyzed updates | PostgreSQL |
| `UpdatesAPI` | HTTP Service | REST endpoints for listing/triggering updates | FastAPI |
| `ChangeDetector` | Utility | Compare current vs. previous member hashes | Python |

### 4.3 Integration with Existing System

The service **reuses** existing infrastructure:

- ✅ `source_registry`: To enumerate all sources and their URLs
- ✅ `acquisition` module: For HTTP HEAD requests and remote probing
- ✅ `file_manager`: For ZIP extraction and SHA-256 computation
- ✅ `SourceArtifactSnapshot`: To compare against last successful processing
- ✅ `SourceMemberSnapshot`: To compare individual member hashes
- ✅ Celery: For task queueing
- ✅ PostgreSQL: For persistence

---

## 5. Data Model

### 5.1 New Database Tables

#### 5.1.1 `pending_update` (Main Registry)

Tracks all detected updates that are pending ingestion.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | UUID | NO | Primary key |
| `fonte` | String(50) | NO | Source identifier (e.g., 'dfp', 'itr', 'cadastro') |
| `ano` | Integer | YES | Year (NULL for cadastro which has no year) |
| `status` | String(32) | NO | Current status (see 4.2) |
| `detection_timestamp` | DateTime | NO | When the change was first detected |
| `last_probe_timestamp` | DateTime | YES | Last time remote probe was performed |
| `analysis_timestamp` | DateTime | YES | When deep analysis was completed |
| `resolved_timestamp` | DateTime | YES | When manual trigger was executed |
| `resolved_by` | String(64) | YES | User/process that triggered ingestion |
| `probe_etag` | String(255) | YES | ETag from last probe |
| `probe_last_modified` | String(255) | YES | Last-Modified header from probe |
| `probe_content_length` | BigInt | YES | Content-Length from probe |
| `artifact_url` | String(1000) | NO | URL of the detected artifact |
| `change_type` | String(32) | YES | 'artifact_changed', 'new_source_year', etc. |
| `change_summary` | JSON | YES | High-level summary of changes |
| `last_successful_run_id` | UUID | YES | Reference to last successful IngestionRun |
| `created_at` | DateTime | NO | Record creation timestamp |
| `updated_at` | DateTime | NO | Last update timestamp |

#### 5.1.2 `pending_update_member` (Member-Level Details)

Tracks which specific members within a ZIP have changes.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | UUID | NO | Primary key |
| `pending_update_id` | UUID | NO | FK to pending_update |
| `member_name` | String(255) | NO | Name of the CSV member (e.g., 'dfp_cia_aberta_2026.csv') |
| `member_role` | String(50) | YES | Role: 'header', 'dependent', 'index' |
| `previous_member_sha256` | String(64) | YES | SHA-256 from last successful processing |
| `current_member_sha256` | String(64) | YES | SHA-256 from current artifact |
| `previous_row_count` | Integer | YES | Row count from last processing |
| `current_row_count` | Integer | YES | Row count from current file |
| `previous_header_hash` | String(64) | YES | Header hash from last processing |
| `current_header_hash` | String(64) | YES | Header hash from current file |
| `change_category` | String(32) | NO | 'added', 'removed', 'modified', 'unchanged' |
| `change_details` | JSON | YES | Detailed diff (header changes, etc.) |
| `row_kind` | String(50) | YES | From source_registry |
| `is_required` | Boolean | YES | Whether member is required per source_registry |
| `status` | String(32) | NO | Member analysis status |

#### 5.1.3 `update_session` (User Session Tracking)

Tracks user sessions for the "update available" view.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | UUID | NO | Primary key |
| `session_key` | String(64) | NO | Unique session identifier |
| `user_id` | String(64) | YES | User identifier (if authenticated) |
| `created_at` | DateTime | NO | Session creation |
| `expires_at` | DateTime | NO | Session expiration |
| `status` | String(32) | NO | 'active', 'expired' |

#### 5.1.4 `update_session_item` (Session Contents)

Items in a user's update session.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | UUID | NO | Primary key |
| `session_id` | UUID | NO | FK to update_session |
| `pending_update_id` | UUID | NO | FK to pending_update |
| `added_at` | DateTime | NO | When added to session |
| `action` | String(32) | YES | 'selected', 'deselected', 'triggered' |

### 5.2 Status Enumerations

#### 5.2.1 `pending_update.status`

| Status | Description |
|---|---|
| `change_detected` | Remote probe detected a change; deep analysis not yet performed |
| `analysis_queued` | Deep analysis task has been queued |
| `analyzing` | Deep analysis is in progress |
| `analysis_failed` | Deep analysis failed (with error details in change_summary) |
| `ready_for_ingestion` | Analysis complete; ready for manual trigger |
| `triggered` | Manual trigger executed; passed to ingestion pipeline |
| `discarded` | Manually discarded; no action taken |
| `stale` | Change was detected but artifact reverted to previous state |

#### 5.2.2 `pending_update_member.status`

| Status | Description |
|---|---|
| `pending_analysis` | Member not yet analyzed |
| `unchanged` | Member identical to last processing |
| `added` | New member in current artifact |
| `removed` | Member present in last processing but missing now |
| `modified` | Member content changed (hash differs) |
| `schema_changed` | Member header/schema changed |
| `required_missing` | Required member is missing from artifact |

---

## 6. Workflow

### 6.1 Daily Scanner Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                        DAILY SCANNER                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. Enumerate all sources from source_registry                     │
│                                                                      │
│  2. For each source/year combination:                             │
│     ┌─────────────────────────────────────────────────────────┐  │
│     │  2.1 Check if already have pending_update in                │  │
│     │     status ∈ [change_detected, analyzing, ready_for_       │  │
│     │                ingestion]                                  │  │
│     │     └─ If YES: Skip (already being processed)             │  │
│     │     └─ If NO: Continue                                    │  │
│     │                                                             │  │
│     │  2.2 Perform HTTP HEAD on artifact URL                   │  │
│     │     └─ If HTTP error: Log and continue                    │  │
│     │     └─ If success: Extract ETag, Last-Modified,           │  │
│     │        Content-Length                                    │  │
│     │                                                             │  │
│     │  2.3 Query last SourceArtifactSnapshot for this          │  │
│     │     source/year                                           │  │
│     │     └─ If exists AND metadata matches:                    │  │
│     │        • No change detected                              │  │
│     │        • Update last_probe_timestamp                      │  │
│     │        • Continue to next source/year                    │  │
│     │     └─ If NO snapshot OR metadata differs:                │  │
│     │        • Change detected!                               │  │
│     │        • Create/update pending_update record              │  │
│     │        • status = 'change_detected'                      │  │
│     │        • Store probe metadata                            │  │
│     └─────────────────────────────────────────────────────────┘  │
│                                                                      │
│  3. Queue deep analysis for all new change_detected records       │
│     (or run immediately if configured to do so)                  │
│                                                                      │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 Deep Analysis Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                      DEEP ANALYSIS                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Input: pending_update with status = 'change_detected'            │
│                                                                      │
│  1. Update status to 'analyzing'                                   │
│                                                                      │
│  2. Download the artifact (ZIP or CSV):                           │
│     ┌─────────────────────────────────────────────────────────┐  │
│     │  • Use acquisition module's download_with_retry         │  │
│     │  • Compute SHA-256 on-the-fly                              │  │
│     │  • Store in temp directory                                 │  │
│     └─────────────────────────────────────────────────────────┘  │
│                                                                      │
│  3. If ZIP: Extract all member CSVs                              │
│     ┌─────────────────────────────────────────────────────────┐  │
│     │  • Use file_manager.extract_zip()                        │  │
│     │  • Get list of member files                                │  │
│     │  • For each member:                                        │  │
│     │    - Compute SHA-256 of member content                     │  │
│     │    - Count rows                                           │  │
│     │    - Extract header                                        │  │
│     │    - Store temp copy for analysis                         │  │
│     └─────────────────────────────────────────────────────────┘  │
│                                                                      │
│  4. Compare with last successful processing:                     │
│     ┌─────────────────────────────────────────────────────────┐  │
│     │  • Query last SourceArtifactSnapshot for this            │  │
│     │    source/year                                             │  │
│     │  • Query all SourceMemberSnapshot for that artifact     │  │
│     │  • For each current member:                               │  │
│     │    - Check if exists in previous snapshots                 │  │
│     │    - Compare SHA-256                                       │  │
│     │    - Compare row_count                                    │  │
│     │    - Compare header_hash                                  │  │
│     │    - Determine change_category                            │  │
│     │  • Identify added/removed/modified members                 │  │
│     │  • Identify required members that are missing             │  │
│     └─────────────────────────────────────────────────────────┘  │
│                                                                      │
│  5. Store analysis results:                                       │
│     ┌─────────────────────────────────────────────────────────┐  │
│     │  • Update pending_update.status = 'ready_for_ingestion'  │  │
│     │  • Set analysis_timestamp                                  │  │
│     │  • Store change_summary with:                              │  │
│     │    - artifact_changed: bool                               │  │
│     │    - members_added: list[str]                             │  │
│     │    - members_removed: list[str]                            │  │
│     │    - members_modified: list[str]                           │  │
│     │    - required_missing: list[str]                            │  │
│     │    - total_changes: int                                    │  │
│     │  • Create pending_update_member records for each member    │  │
│     │  • Link to last_successful_run_id                           │  │
│     └─────────────────────────────────────────────────────────┘  │
│                                                                      │
│  6. Cleanup: Remove temp files                                    │
│                                                                      │
│  7. On failure: Set status = 'analysis_failed' with error details │
│                                                                      │
└─────────────────────────────────────────────────────────────────┘
```

### 6.3 Update Available Session Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                    UPDATE AVAILABLE SESSION                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. User requests session (API: GET /api/updates/pending)         │
│     └─ Returns list of all pending_update with status              │
│        = 'ready_for_ingestion'                                    │
│     └─ Each item includes: source, year, change_summary,          │
│        detection_timestamp, member_count_changed                  │
│                                                                      │
│  2. User creates a session (API: POST /api/updates/session)       │
│     └─ Creates update_session record                               │
│     └─ Returns session_key                                        │
│                                                                      │
│  3. User adds items to session (API: POST /api/updates/session    │
│     /{session_key}/items)                                        │
│     └─ Creates update_session_item records                         │
│     └─ Each item references a pending_update_id                    │
│                                                                      │
│  4. User views session (API: GET /api/updates/session             │
│     /{session_key})                                               │
│     └─ Returns all items in session with full details             │
│                                                                      │
│  5. Session expires after configurable timeout (default: 24h)     │
│                                                                      │
└─────────────────────────────────────────────────────────────────┘
```

### 6.4 Manual Trigger Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                      MANUAL TRIGGER                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Prerequisite: pending_update with status = 'ready_for_ingestion' │
│                                                                      │
│  Option A: Trigger single update                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ POST /api/updates/{pending_update_id}/trigger                 │ │
│  │                                                             │ │
│  │  1. Validate pending_update exists and is ready               │ │
│  │  2. Update status to 'triggered'                             │ │
│  │  3. Set resolved_timestamp and resolved_by                     │ │
│  │  4. Call existing pre_processar_sincronizacao_task:          │ │
│  │     ┌─────────────────────────────────────────────────────┐ │ │
│  │     │ • Pass skip_probe=True (we already did probe)          │ │ │
│  │     │ • Pass source_artifact_snapshot_id from last success   │ │ │
│  │     │ • This creates IngestionRun with status                │ │ │
│  │     │   'aguardando_ingestao'                                 │ │ │
│  │     │ • Existing worker pipeline picks it up                │ │ │
│  │     └─────────────────────────────────────────────────────┘ │ │
│  │  5. Return success with IngestionRun ID                        │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  Option B: Trigger from session                                     │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ POST /api/updates/session/{session_key}/trigger                │ │
│  │                                                             │ │
│  │  1. Get all items in session with action = 'selected'          │ │
│  │  2. For each pending_update_id:                              │ │
│  │     • Execute Option A workflow                               │ │
│  │  3. Return summary of triggered updates                       │ │
│  │  4. Optionally: Auto-expire session after trigger             │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  Option C: Bulk trigger all ready updates                         │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ POST /api/updates/trigger-all                                 │ │
│  │                                                             │ │
│  │  1. Get all pending_update with status = 'ready_for_ingestion'│ │
│  │  2. For each: Execute Option A workflow                         │ │
│  │  3. Return summary                                            │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                      │
└─────────────────────────────────────────────────────────────────┘
```

### 6.5 Discard Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                      DISCARD UPDATE                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                      │
│  POST /api/updates/{pending_update_id}/discard                    │
│                                                                      │
│  1. Validate pending_update exists and is not yet triggered         │
│  2. Update status to 'discarded'                                    │
│  3. Optionally: Store discard reason in change_summary             │
│  4. Remove any temp files associated with this update              │
│  5. If in a session: Remove from session or mark as deselected    │
│                                                                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Service Endpoints

### 7.1 REST API (FastAPI)

Base path: `/api/updates`

#### 7.1.1 Scanner & Detection

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `GET` | `/scanner/status` | Get scanner status and last run info | No |
| `POST` | `/scanner/run` | Manually trigger scanner (admin) | Yes |
| `GET` | `/scanner/history` | Get scanner execution history | Yes |

#### 7.1.2 Pending Updates

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `GET` | `/pending` | List all pending updates (filterable) | Yes |
| `GET` | `/pending/{id}` | Get details of a pending update | Yes |
| `GET` | `/pending/{id}/members` | List member-level changes | Yes |
| `POST` | `/pending/{id}/analyze` | Trigger deep analysis | Yes |
| `POST` | `/pending/{id}/trigger` | Manual trigger ingestion | Yes |
| `POST` | `/pending/{id}/discard` | Discard pending update | Yes |
| `POST` | `/pending/trigger-all` | Trigger all ready updates | Yes |

#### 7.1.3 Update Sessions

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `POST` | `/session` | Create new session | Yes |
| `GET` | `/session/{session_key}` | Get session contents | Yes |
| `POST` | `/session/{session_key}/items` | Add items to session | Yes |
| `DELETE` | `/session/{session_key}/items/{item_id}` | Remove item from session | Yes |
| `POST` | `/session/{session_key}/trigger` | Trigger all selected in session | Yes |
| `DELETE` | `/session/{session_key}` | Delete session | Yes |

#### 7.1.4 Bulk Operations

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `GET` | `/summary` | Get summary statistics (total pending, by source, etc.) | Yes |
| `POST` | `/refresh-all` | Force refresh all sources | Yes (admin) |

### 7.2 CLI Commands

```bash
# Scanner
cvm-updates scanner run              # Run scanner manually
cvm-updates scanner status           # Check scanner status

# Pending updates
cvm-updates pending list             # List all pending updates
cvm-updates pending show <id>        # Show details
cvm-updates pending analyze <id>     # Run deep analysis
cvm-updates pending trigger <id>     # Trigger ingestion
cvm-updates pending discard <id>     # Discard update

# Sessions
cvm-updates session create           # Create session
cvm-updates session add <id>         # Add to current session
cvm-updates session list             # List session items
cvm-updates session trigger           # Trigger session

# Bulk
cvm-updates trigger-all              # Trigger all ready updates
```

---

## 8. Integration with Existing Pipeline

### 8.1 Reused Components

| Existing Component | Usage in New Service |
|---|---|
| `source_registry` | Enumerate all sources, get URLs, member definitions |
| `acquisition.remote_probe()` | HTTP HEAD and CKAN metadata probing |
| `acquisition.download_with_retry()` | Download artifacts with retry logic |
| `file_manager.compute_sha256()` | Compute file hashes |
| `file_manager.extract_zip()` | Extract ZIP members |
| `file_manager.detect_encoding()` | Detect CSV encoding |
| `SourceArtifactSnapshot` | Compare against last successful processing |
| `SourceMemberSnapshot` | Compare member-level changes |
| Celery | Task queue for scanner and analyzer |
| PostgreSQL | Persistence for new tables |

### 8.2 Modified Components

The following existing components need **minor modifications** to support the new service:

#### 8.2.1 `pre_processar_sincronizacao_zip`

Add parameter to skip remote probe:

```python
@task
def pre_processar_sincronizacao_zip(
    fonte: str,
    ano: int,
    skip_probe: bool = False,
    source_artifact_snapshot_id: Optional[UUID] = None,
    # ... other params
):
    if skip_probe:
        # Use the provided snapshot or query from pending_update
        pass
    else:
        # Existing probe logic
        pass
```

#### 8.2.2 Celery Beat Schedule

Modify existing schedule to **optionally** disable auto-triggering:

```python
# In celery_app.py

# Add configuration
AUTO_TRIGGER_UPDATES = os.getenv('AUTO_TRIGGER_UPDATES', 'false').lower() == 'true'

# Modify existing beat schedule
if AUTO_TRIGGER_UPDATES:
    # Keep existing automatic triggering
    app.conf.beat_schedule = {
        'sincronizar-cadastro-diario': {...},
        # ... all existing schedules
    }
else:
    # Only run scanner, no auto-trigger
    app.conf.beat_schedule = {
        'cvm-updates-scanner': {
            'task': 'updates.tasks.run_daily_scanner',
            'schedule': crontab(hour=0, minute=30),  # Daily at 00:30
        },
    }
```

### 8.3 New Components

#### 8.3.1 `updates/` Package Structure

```
updates/
├── __init__.py
├── config.py           # Configuration for update service
├── models.py           # New database models
├── schemas.py          # Pydantic schemas for API
├── router.py           # FastAPI router
├── service.py          # Core service logic
├── tasks.py            # Celery tasks (scanner, analyzer)
├── cli.py              # CLI commands
│
├── scanner/
│   ├── __init__.py
│   ├── probe.py         # Remote probing logic
│   └── detector.py      # Change detection
│
├── analyzer/
│   ├── __init__.py
│   ├── zip_analyzer.py  # ZIP member analysis
│   ├── csv_analyzer.py  # CSV analysis (for cadastro)
│   └── comparator.py    # Compare current vs. previous
│
├── session/
│   ├── __init__.py
│   └── manager.py       # Session management
│
└── utils/
    ├── __init__.py
    └── helpers.py        # Utility functions
```

---

## 9. Configuration

### 9.1 Environment Variables

| Variable | Default | Description |
|---|---|---|
| `UPDATES_SERVICE_ENABLED` | `true` | Enable the updates service |
| `AUTO_TRIGGER_UPDATES` | `false` | If true, keep existing auto-trigger behavior |
| `SCANNER_SCHEDULE` | `0 30 * * *` | Cron schedule for daily scanner |
| `AUTO_ANALYZE_ON_DETECT` | `true` | Auto-run deep analysis when change detected |
| `ANALYSIS_MAX_CONCURRENCY` | `2` | Max concurrent deep analysis tasks |
| `SESSION_TIMEOUT_HOURS` | `24` | Update session timeout in hours |
| `TEMP_DIR` | `/tmp/cvm-updates` | Directory for temp files during analysis |
| `MAX_TEMP_FILE_AGE_HOURS` | `24` | Max age of temp files before cleanup |

### 9.2 Feature Flags

| Flag | Description |
|---|---|
| `ENABLE_CKAN_PROBE` | Use CKAN metadata API for probing |
| `ENABLE_ETAG_PROBE` | Use ETag header for probing |
| `ENABLE_LASTMODIFIED_PROBE` | Use Last-Modified header for probing |
| `REQUIRE_STRONG_PROBE` | Only trust strong confidence probes |

---

## 10. Error Handling & Recovery

### 10.1 Scanner Errors

| Error | Handling |
|---|---|
| HTTP timeout | Retry with backoff, max 3 attempts |
| HTTP 404 | Log warning, mark as unavailable |
| HTTP 5xx | Retry, mark as temporarily unavailable |
| Network error | Retry with exponential backoff |
| Database error | Rollback, retry |

### 10.2 Analyzer Errors

| Error | Handling |
|---|---|
| Download failure | Retry 3x, then set status='analysis_failed' |
| ZIP extraction failure | Set status='analysis_failed' with details |
| SHA computation failure | Set status='analysis_failed' with details |
| Database comparison failure | Set status='analysis_failed' with details |
| Temp file write failure | Set status='analysis_failed', clean up |

### 10.3 Recovery Mechanisms

1. **Stale Update Detection**: 
   - If a pending_update stays in 'change_detected' for > 24h without analysis, auto-requeue
   - If in 'analyzing' for > 2h, mark as failed

2. **Temp File Cleanup**:
   - Scheduled task to clean temp files older than `MAX_TEMP_FILE_AGE_HOURS`

3. **Orphaned Records Cleanup**:
   - Clean pending_update records with status='triggered' older than 7 days
   - Clean expired sessions

---

## 11. Monitoring & Metrics

### 11.1 Prometheus Metrics

| Metric | Type | Labels | Description |
|---|---|---|---|
| `cvm_updates_scanner_runs_total` | Counter | `status` | Total scanner runs |
| `cvm_updates_scanner_duration_seconds` | Histogram | - | Scanner run duration |
| `cvm_updates_detection_total` | Counter | `source`, `change_detected` | Changes detected |
| `cvm_updates_analysis_total` | Counter | `source`, `status` | Deep analyses performed |
| `cvm_updates_analysis_duration_seconds` | Histogram | `source` | Analysis duration |
| `cvm_updates_pending_total` | Gauge | `source`, `status` | Current pending updates |
| `cvm_updates_session_total` | Gauge | - | Active sessions |
| `cvm_updates_trigger_total` | Counter | `source`, `trigger_type` | Manual triggers executed |

### 11.2 Health Checks

| Endpoint | Description |
|---|---|
| `GET /health` | Basic health check |
| `GET /health/scanner` | Scanner subsystem health |
| `GET /health/analyzer` | Analyzer subsystem health |
| `GET /health/database` | Database connectivity |

### 11.3 Alerts

| Condition | Severity | Description |
|---|---|---|
| Scanner not run in 24h | WARNING | Scanner may be stuck |
| Scanner failure rate > 50% | CRITICAL | Scanner failing repeatedly |
| Analysis queue size > 10 | WARNING | Analysis backlog growing |
| Analysis failure rate > 20% | CRITICAL | Analysis failing frequently |
| Pending updates > 50 | WARNING | Many updates waiting for trigger |

---

## 12. Implementation Phases

### Phase 1: Core Service (2-3 weeks)

**Goal**: Basic scanner and pending updates tracking

- [ ] Create new database tables (`pending_update`, `pending_update_member`)
- [ ] Implement `UpdateScanner` task
- [ ] Implement basic API endpoints for listing pending updates
- [ ] Implement CLI commands for scanner
- [ ] Add configuration to disable auto-trigger
- [ ] Basic integration tests

**Deliverables**:
- Scanner running daily
- API to view pending updates
- Manual trigger for single updates

### Phase 2: Deep Analysis (2 weeks)

**Goal**: Member-level change detection

- [ ] Implement `DeepAnalyzer` task
- [ ] Implement ZIP extraction and member comparison
- [ ] Implement member-level change tracking
- [ ] Auto-trigger analysis on detection (configurable)
- [ ] Enhanced API with member details
- [ ] Integration with SourceArtifactSnapshot/SourceMemberSnapshot

**Deliverables**:
- Deep analysis running automatically
- Member-level change details in API
- Accurate change detection

### Phase 3: Update Sessions (1-2 weeks)

**Goal**: Session-based update management

- [ ] Create session-related database tables
- [ ] Implement session management API
- [ ] Implement session CLI commands
- [ ] Bulk trigger from session
- [ ] Session timeout and cleanup

**Deliverables**:
- User can create sessions
- User can add/remove updates from sessions
- User can trigger all updates in a session

### Phase 4: UI Integration (2 weeks)

**Goal**: Admin UI for update management

- [ ] Add endpoints for UI-specific needs
- [ ] Create admin UI page for pending updates
- [ ] Session management in UI
- [ ] Manual trigger buttons in UI
- [ ] Change details visualization

**Deliverables**:
- Web interface for update management
- Visual change indicators
- One-click trigger from UI

### Phase 5: Monitoring & Polish (1 week)

**Goal**: Production readiness

- [ ] Prometheus metrics implementation
- [ ] Alert rules configuration
- [ ] Health check endpoints
- [ ] Documentation
- [ ] Performance optimization

**Deliverables**:
- Full observability
- Production-ready service
- Complete documentation

---

## 13. Migration Strategy

### 13.1 From Current State

The existing system has:
- Celery beat triggering `sincronizar_*_task` automatically
- No centralized pending updates view
- No member-level change analysis before ingestion

### 13.2 Migration Steps

1. **Deploy new service alongside existing**:
   - New service runs in parallel
   - Existing auto-trigger continues to work
   - Users can optionally use new service

2. **Gradual cutover**:
   - Set `AUTO_TRIGGER_UPDATES=false` for non-critical sources
   - Monitor new service behavior
   - Verify no regressions

3. **Full cutover**:
   - Set `AUTO_TRIGGER_UPDATES=false` for all sources
   - Users must use new service for all updates
   - Existing pipeline still handles the actual ingestion

4. **Cleanup (optional)**:
   - Remove old Celery beat schedules
   - Remove old admin endpoints that auto-trigger

### 13.3 Rollback Plan

If issues arise:
1. Set `AUTO_TRIGGER_UPDATES=true` to restore old behavior
2. New service continues to run but is not required
3. Investigate and fix issues
4. Re-attempt cutover

---

## 14. Testing Strategy

### 14.1 Unit Tests

- Scanner logic (probe detection)
- Analyzer logic (member comparison)
- API endpoint handlers
- Service layer functions

### 14.2 Integration Tests

- Full scanner workflow
- Full analysis workflow
- Database transactions
- Celery task execution

### 14.3 End-to-End Tests

- CVM publishes update → Scanner detects → Analysis runs → User triggers → Ingestion executes
- Session creation → Add items → Trigger session → All updates ingested
- Error scenarios (network failure, invalid data, etc.)

### 14.4 Test Data

- Mock CVM responses (different Last-Modified, ETag values)
- Sample ZIP files with known member structures
- Known change patterns (added member, modified member, etc.)

---

## 15. Security Considerations

### 15.1 Authentication & Authorization

- All API endpoints (except health checks) require authentication
- Use existing auth mechanism (Bearer token)
- Read-only endpoints: view pending updates, sessions
- Write endpoints: trigger, discard, create session
- Admin endpoints: scanner control, bulk operations

### 15.2 Rate Limiting

- API endpoints: 100 requests/minute per user
- Scanner: max 1 request/second per source
- Analyzer: max concurrent tasks configurable

### 15.3 Data Protection

- Temp files: stored in isolated directory, cleaned regularly
- Database: same security as existing system
- No sensitive data: all data is public CVM data

---

## 16. Performance Considerations

### 16.1 Scanner Performance

- **Parallelism**: Scanner can probe sources in parallel (max 5 concurrent)
- **Caching**: Cache probe results for 5 minutes to avoid duplicate requests
- **Timeout**: HTTP timeout of 30 seconds per probe
- **Expected duration**: ~2-5 minutes for all sources

### 16.2 Analyzer Performance

- **Download**: Use streaming download with SHA-256 on-the-fly
- **ZIP extraction**: Extract to temp directory, compute hashes during extraction
- **Comparison**: Use efficient database queries for snapshot comparison
- **Concurrency**: Configurable max concurrent analyses (default: 2)
- **Expected duration**: ~1-5 minutes per ZIP file (depending on size)

### 16.3 Storage

- **Temp files**: Maximum size configurable, auto-cleanup
- **Database**: New tables expected to add < 10MB for typical usage
- **Retention**: 
  - pending_update: 90 days (configurable)
  - pending_update_member: 90 days (configurable)
  - update_session: 7 days (configurable)

---

## 17. File Locations

### 17.1 New Files

```
├── docs/
│   └── cvm_data_updates_service.md    # This document
│
├── src/
│   ├── updates/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── tasks.py
│   │   ├── cli.py
│   │   ├── scanner/
│   │   │   ├── __init__.py
│   │   │   ├── probe.py
│   │   │   └── detector.py
│   │   ├── analyzer/
│   │   │   ├── __init__.py
│   │   │   ├── zip_analyzer.py
│   │   │   ├── csv_analyzer.py
│   │   │   └── comparator.py
│   │   └── session/
│   │       ├── __init__.py
│   │       └── manager.py
│   │
│   ├── ingestion/
│   │   └── tasks.py                # Modified to add skip_probe param
│   │
│   └── celery_app.py               # Modified beat schedule
│
├── migrations/
│   └── versions/
│       └── add_updates_service_tables.py  # Alembic migration
│
└── tests/
    └── updates/
        ├── test_scanner.py
        ├── test_analyzer.py
        ├── test_api.py
        └── test_session.py
```

### 17.2 Modified Files

| File | Changes |
|---|---|
| `src/ingestion/tasks.py` | Add `skip_probe` parameter to pre-processing tasks |
| `src/celery_app.py` | Conditional beat schedule based on `AUTO_TRIGGER_UPDATES` |
| `src/admin/router.py` | Optionally: add update management endpoints to existing admin API |

---

## 18. Open Questions & Decisions Needed

### 18.1 Questions

1. **Should the scanner run on the same Celery worker as ingestion?**
   - Option A: Same worker (simpler deployment)
   - Option B: Separate worker (better isolation)
   - **Recommended**: Option A for simplicity, with resource limits

2. **Should deep analysis be automatic or manual?**
   - Option A: Automatic on detection (faster, but more resource usage)
   - Option B: Manual trigger (more control, but slower)
   - **Recommended**: Option A with configurable `AUTO_ANALYZE_ON_DETECT`

3. **Should we support partial ZIP download?**
   - Download only changed members from ZIP
   - **Recommended**: No - CVM ZIPs are not too large, full download is simpler

4. **How to handle sources with no year (cadastro)?**
   - **Answer**: Use `ano = NULL` in database, handle in code

5. **Should discarded updates be preserved or deleted?**
   - **Recommended**: Preserve for 30 days (configurable), then delete

### 18.2 Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Auto-analysis | Yes, configurable | Faster workflow, can be disabled if needed |
| Separate worker | No | Simpler deployment, existing worker has capacity |
| Session storage | Database | Reliability, easier to query |
| Temp file cleanup | Scheduled task | Ensures cleanup even if service restarts |
| API auth | Existing mechanism | Consistency with existing system |

---

## 19. Glossary

| Term | Definition |
|---|---|
| **Artifact** | A single downloadable file from CVM (ZIP or CSV) |
| **Member** | A CSV file within a ZIP artifact |
| **Source** | A CVM data source (e.g., DFP, ITR, CAD) |
| **Pending Update** | A detected change that has not yet been ingested |
| **Deep Analysis** | Process of downloading and analyzing a changed artifact at member level |
| **Update Session** | User-created collection of pending updates for batch operations |
| **Manual Trigger** | Explicit user action to start ingestion of a pending update |

---

## 20. References

- [docs/ingestion.md](../ingestion.md) - Existing ingestion pipeline documentation
- [CVM.md](../CVM.md) - CVM data sources and update mechanisms
- [source_registry module](../../src/ingestion/source_registry.py) - Source definitions
- [acquisition module](../../src/ingestion/acquisition.py) - Remote probing and download
- [file_manager module](../../src/ingestion/file_manager.py) - File operations
- [change_tracking module](../../src/ingestion/change_tracking.py) - Existing change tracking

---

*Document version: 1.0*  
*Last updated: 2026-06-16*  
*Author: Tucano-CVM Team*
