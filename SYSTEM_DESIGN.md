# Social Media Automation — System Design and Implementation

## 1. Purpose

This project is an extensible social-media automation service for Instagram and
X/Twitter. It can:

- Load accounts from JSON for command-line operation.
- Upload independent CSV account batches through a web interface or REST API.
- Schedule like, comment/reply, and repost/retweet actions.
- Run Selenium browser work outside the HTTP request lifecycle.
- Apply global, platform, and account-level concurrency controls.
- Persist batches, jobs, progress, and results in SQLite.
- Encrypt account passwords before storing them.
- Add new platforms without adding platform branches to the executor.

The current implementation is intended for a single machine running one API
process. Browser automation remains bounded because each Chrome process is
resource-intensive.

## 2. Supported capabilities

| Platform | Login | Like | Comment/Reply | Repost/Retweet |
|---|---:|---:|---:|---:|
| Instagram | Yes | Yes | Yes | Yes |
| X/Twitter | Yes | Yes | Yes | Yes |
| Facebook | Declared domain value only | No | No | No |

Facebook fails fast as unsupported rather than using unreliable generic selectors.

## 3. Architecture overview

```text
Browser / API client
        │
        ▼
FastAPI application
  ├── CSV upload endpoints
  ├── Account batch endpoints
  ├── Job endpoints
  └── Static web interface
        │
        ▼
SQLite JobStore
  ├── Encrypted accounts
  ├── Independent batches
  ├── Durable jobs
  └── Per-account results
        │
        ▼
JobDispatcher threads
        │
        ▼
Executor
  ├── Fair platform scheduling
  ├── Global worker limit
  ├── Per-platform worker limit
  ├── Same-account serialization
  └── Dispatcher-side cooldowns
        │
        ▼
Worker
  ├── Validate task
  ├── Select proxy
  ├── Create browser
  ├── Authenticate account
  └── Execute action strategy
        │
        ▼
Registry
  ├── Platform handler
  └── Action handler
        │
        ├── Instagram adapters
        └── X/Twitter adapters
```

The central dependency direction is:

```text
API → Dispatcher → Executor → Worker → Handler interfaces ← Platform adapters
```

The scheduling layer has no Twitter or Instagram selectors and does not contain
platform-specific conditional branches.

## 4. Project structure

```text
.
├── main.py                         # Command-line runner
├── server.py                       # Local FastAPI server entry point
├── README.md                       # Setup and usage guide
├── SYSTEM_DESIGN.md                # This document
├── requirements.txt                # Runtime dependencies
├── accounts.example.json           # CLI account example
├── src
│   ├── api
│   │   ├── app.py                  # FastAPI routes and application lifecycle
│   │   └── schemas.py              # Request/response models
│   ├── config
│   │   └── settings.py             # Environment-based runtime settings
│   ├── core
│   │   ├── executor.py             # Bounded task scheduler
│   │   ├── registry.py             # Handler catalog and platform bundles
│   │   └── worker.py               # One-task execution lifecycle
│   ├── domains
│   │   ├── action_type.py          # Canonical action enum and aliases
│   │   ├── execution_result.py     # Structured task results
│   │   ├── platform.py             # Canonical platform enum and aliases
│   │   └── task.py                 # Task model and validation
│   ├── handlers
│   │   ├── registry.py             # Default handler bundle assembly
│   │   ├── actions                 # Platform/action strategies
│   │   └── platforms               # Platform authentication adapters
│   ├── interfaces
│   │   ├── i_action_handler.py
│   │   ├── i_execution_observer.py
│   │   └── i_platform_handler.py
│   ├── models
│   │   └── account.py
│   ├── services
│   │   ├── browser_factory.py
│   │   ├── credential_cipher.py
│   │   ├── csv_account_parser.py
│   │   ├── execution_observer.py
│   │   ├── job_dispatcher.py
│   │   ├── job_store.py
│   │   └── proxy_manager.py
│   └── web
│       ├── index.html
│       ├── styles.css
│       └── app.js
└── tests
    ├── test_api.py
    ├── test_csv_accounts.py
    ├── test_domains.py
    ├── test_executor.py
    ├── test_job_dispatcher.py
    └── test_worker.py
```

## 5. Domain model

### 5.1 Platform

`Platform` defines canonical platform identifiers:

```python
Platform.INSTAGRAM
Platform.TWITTER
Platform.FACEBOOK
```

Aliases are normalized at the domain boundary:

| Input | Canonical platform |
|---|---|
| `twitter` | `twitter` |
| `x` | `twitter` |
| `x.com` | `twitter` |

### 5.2 ActionType

Canonical actions are:

- `like`
- `comment`
- `repost`

User-facing aliases are normalized:

| Input | Canonical action |
|---|---|
| `reply` | `comment` |
| `retweet` | `repost` |
| `share` | `repost` |

### 5.3 Account

An account contains:

- `username`
- `password`
- `platform`
- Optional `verification_identifier` for X login challenges
- Optional metadata for future extensions

Passwords are never included in API responses or application progress output.

### 5.4 Task

A `Task` represents one account performing one action against one target URL.

```python
Task(
    account=account,
    platform=Platform.TWITTER,
    action=ActionType.LIKE,
    target_url="https://x.com/user/status/123",
    params={},
)
```

Task validation checks:

- The account platform matches the task platform.
- The target URL is an absolute HTTP or HTTPS URL.
- The target host belongs to the selected platform.
- X and Twitter URL aliases are accepted.

### 5.5 ExecutionResult

Task execution returns structured data instead of only a Boolean.

Result codes:

| Code | Meaning |
|---|---|
| `success` | Action completed or was already in the requested state |
| `invalid_task` | Domain validation failed |
| `unsupported` | No platform/action handler is registered |
| `login_failed` | Account authentication failed |
| `action_failed` | The platform action could not be confirmed |
| `internal_error` | Browser or internal execution exception |

Every result retains the task, number of attempts, and an optional error message.

## 6. Registry and platform bundles

`Registry` stores two mappings:

```text
Platform → IPlatformHandler
(Platform, ActionType) → IActionHandler
```

A `PlatformBundle` groups one platform handler with all of its action handlers.

```python
PlatformBundle(
    TwitterHandler(),
    (
        TwitterLikeHandler(),
        TwitterCommentHandler(),
        TwitterRepostHandler(),
    ),
)
```

The registry validates that:

- A platform cannot be registered twice.
- An action cannot be registered twice for the same platform.
- A platform must be registered before its actions.
- All action handlers in a bundle belong to the same platform.

The earlier process-global singleton registry was removed. Registries are now
explicit instances, which prevents test leakage and enables different configurations
in different processes.

## 7. Platform and action adapters

### 7.1 Platform handlers

Platform handlers implement `IPlatformHandler` and own authentication behavior.

```python
login(driver, account) -> bool
get_post_url(identifier) -> str
platform -> Platform
```

The X handler supports the normal username/password flow and the additional
identifier challenge that X can display.

### 7.2 Action handlers

Action handlers implement `IActionHandler`:

```python
execute(driver, task) -> bool
platform -> Platform
action_type -> ActionType
```

Each platform/action pair is isolated in its own strategy. X DOM lookup helpers are
centralized in `TwitterActionMixin`, so selector changes remain inside the X adapter.

Like and repost handlers detect the already-liked/already-reposted state and treat it
as success. This improves idempotency.

## 8. Worker lifecycle

`Worker.execute(task)` performs the following steps:

1. Validate the task.
2. Resolve the platform and action handlers from the registry.
3. Obtain the next proxy.
4. Create a Chrome WebDriver.
5. Log into the platform.
6. Execute the action strategy.
7. Build an `ExecutionResult`.
8. Close the WebDriver in a `finally` block.

Browser creation and login failures may retry according to configuration. A failed
write action is not blindly retried because the click may have succeeded even when
the confirmation selector timed out. This avoids accidental duplicate comments or
replies.

## 9. Executor and concurrency model

The executor consumes a collection of tasks and schedules them through a bounded
`ThreadPoolExecutor`.

It enforces these invariants:

```text
Total running tasks <= SOCIAL_MAX_WORKERS

Running tasks for a platform <= configured platform worker limit

Running tasks for one (platform, username) account <= 1
```

### 9.1 Fair platform scheduling

Pending tasks are grouped into platform queues. A rotating platform order prevents
the first platform from permanently consuming all submission slots.

### 9.2 Account serialization

`account_key` is a tuple of platform and case-insensitive username. An account key is
marked active before submission and released after completion. Multiple operations
for the same account therefore never run concurrently.

### 9.3 Cooldowns

Account cooldown timestamps are maintained by the dispatcher. Cooldown waiting does
not occupy browser worker threads, leaving those threads available for ready work.

### 9.4 Execution observers

Progress output was separated from scheduling using `IExecutionObserver`.

- `ConsoleExecutionObserver` prints CLI progress.
- `JobProgressObserver` persists API job progress.

This lets the same executor serve CLI and API use cases without importing database
logic into the core scheduler.

## 10. Browser factory

`BrowserFactory` owns Chrome configuration:

- Automation-related Chrome options
- Headless mode
- Proxy configuration
- Window sizing
- ChromeDriver construction

ChromeDriver discovery is cached. A lock prevents multiple task threads from racing
through driver installation.

The original global TLS-verification override was removed. Driver downloads now use
normal certificate validation.

For containers or controlled hosts, `CHROMEDRIVER_PATH` can point to a preinstalled
driver and avoid runtime downloads.

## 11. CSV account batches

The Instagram and X UI sections are independent. The selected section or API path
defines the platform, so the CSV does not need a platform column.

Minimum valid CSV:

```csv
username,password
account_one,secret-one
account_two,secret-two
```

The parser:

- Accepts UTF-8 and UTF-8 with BOM.
- Treats header names case-insensitively.
- Requires `username` and `password` columns.
- Allows unrelated extra columns but does not use them.
- Rejects empty usernames or passwords.
- Rejects duplicate usernames within one batch.
- Enforces the configured account-count limit. The API enforces the upload byte limit
  before invoking the parser.

Each upload creates a new batch rather than merging into an existing batch. A batch
contains:

- Unique ID
- User-facing name
- Platform
- Original filename
- Account count
- Creation timestamp

This means multiple CSV files can be uploaded to the same platform and selected
independently when creating jobs.

## 12. Credential security

Passwords are encrypted with Fernet before SQLite persistence.

Key resolution order:

1. Use `SOCIAL_CREDENTIAL_KEY` when configured.
2. Otherwise create `data/.credential_key` with owner-only file permissions.

The database and generated key are ignored by Git. The key must be backed up together
with the database. If the key is lost, stored passwords cannot be recovered.

Security boundaries:

- Passwords are decrypted only when a worker loads a batch for execution.
- Passwords are not returned through batch or job APIs.
- Passwords are not written to task progress logs.
- CSV content is not retained after accounts are parsed and encrypted.
- The server binds to `127.0.0.1` by default.

Authentication and TLS must be placed in front of the service before it is exposed on
a network.

## 13. Persistence model

SQLite uses foreign keys, WAL mode, a busy timeout, and a new connection per store
operation so calls are safe across API and dispatcher threads.

### 13.1 `account_batches`

```text
id             TEXT PRIMARY KEY
name           TEXT
platform       TEXT
filename       TEXT
account_count  INTEGER
created_at     TEXT
```

### 13.2 `accounts`

```text
id                   INTEGER PRIMARY KEY
batch_id             TEXT REFERENCES account_batches
username             TEXT
password_ciphertext  TEXT
UNIQUE(batch_id, username)
```

### 13.3 `jobs`

```text
id            TEXT PRIMARY KEY
batch_id      TEXT REFERENCES account_batches
platform      TEXT
action        TEXT
target_url    TEXT
params_json   TEXT
status        TEXT
total         INTEGER
completed     INTEGER
succeeded     INTEGER
failed        INTEGER
error         TEXT
created_at    TEXT
started_at    TEXT
completed_at  TEXT
```

Job lifecycle:

```text
queued → running → completed
                 ↘ failed
```

`completed` describes a finished job lifecycle. Individual tasks inside a completed
job may still have failed, which is represented by the succeeded/failed counters and
result rows.

### 13.4 `job_results`

```text
id          INTEGER PRIMARY KEY
job_id      TEXT REFERENCES jobs
username    TEXT
code        TEXT
attempts    INTEGER
error       TEXT
created_at  TEXT
```

Batches with job history cannot be deleted, preserving referential integrity and
historical job reporting.

## 14. Non-blocking API execution

The API never runs Selenium inside an HTTP request.

Job submission flow:

```text
POST /api/v1/jobs
        │
        ├── Validate batch, action, and target URL
        ├── Insert queued job into SQLite
        ├── Notify dispatcher
        └── Return 202 Accepted
```

Background flow:

```text
JobDispatcher thread
        │
        ├── Atomically claim oldest queued job
        ├── Decrypt batch accounts
        ├── Build Task objects
        ├── Run Executor
        ├── Persist each result through observer
        └── Mark job completed or failed
```

The FastAPI event loop remains available while browser work runs in dedicated
dispatcher and executor threads. SQLite operations invoked from async routes are also
sent through FastAPI's thread pool.

If the service restarts during a job, the interrupted job is marked failed and is not
automatically replayed. Automatic replay could duplicate non-idempotent comments.

## 15. REST API

FastAPI provides OpenAPI documentation at `/docs` and `/redoc`.

### 15.1 Health and metrics

```http
GET /api/v1/health
```

Returns service status and counts for accounts and job states.

### 15.2 Supported platforms

```http
GET /api/v1/platforms
```

Returns the platform and action choices supported by the API.

### 15.3 Upload account batch

```http
POST /api/v1/platforms/{platform}/batches
Content-Type: multipart/form-data
```

Form fields:

| Field | Required | Description |
|---|---:|---|
| `file` | Yes | UTF-8 CSV with username and password columns |
| `name` | No | Reusable batch name; filename stem is the default |

Success status: `201 Created`.

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/platforms/twitter/batches \
  -F 'name=Community accounts' \
  -F 'file=@accounts.csv'
```

### 15.4 List account batches

```http
GET /api/v1/platforms/{platform}/batches
```

Account records and passwords are never included.

### 15.5 Delete unused batch

```http
DELETE /api/v1/platforms/{platform}/batches/{batch_id}
```

Success status: `204 No Content`. A batch with job history returns `409 Conflict`.

### 15.6 Submit job

```http
POST /api/v1/jobs
Content-Type: application/json
```

Example body:

```json
{
  "batch_id": "BATCH_ID",
  "action": "like",
  "target_url": "https://x.com/user/status/123",
  "comment_text": null
}
```

Success status: `202 Accepted`. The response is the queued job record.

### 15.7 List jobs

```http
GET /api/v1/jobs?limit=50
```

The limit is constrained to 1–200.

### 15.8 Job details and task results

```http
GET /api/v1/jobs/{job_id}
```

Returns the job record and its per-account result list.

## 16. Web interface

The web interface is served by the same FastAPI process and uses the same public API.
It contains:

- Service status and global metrics
- Downloadable CSV template
- Independent Instagram and X workspaces
- Per-platform CSV uploads
- Reusable batch lists and deletion controls
- Action, target URL, and optional comment/reply input
- Immediate job submission feedback
- Automatically refreshed job ledger
- Progress bars and success/failure counts
- Responsive desktop, tablet, and mobile layouts
- Accessible form labels and live toast status messages

No platform information is requested inside the CSV because the page section already
provides it.

## 17. Configuration

All runtime controls are environment-based.

| Variable | Default | Purpose |
|---|---:|---|
| `SOCIAL_MAX_WORKERS` | `5` | Maximum task/browser workers inside one job |
| `SOCIAL_PLATFORM_WORKERS` | empty | Per-platform worker limits, e.g. `instagram=2,twitter=3` |
| `SOCIAL_JOB_WORKERS` | `1` | Number of whole API jobs allowed to run concurrently |
| `SOCIAL_MAX_RETRIES` | `1` | Browser/login retries |
| `SOCIAL_RETRY_DELAY` | `2` | Base retry delay in seconds |
| `SOCIAL_MIN_COOLDOWN` | `0` | Minimum same-account cooldown |
| `SOCIAL_MAX_COOLDOWN` | `0` | Maximum same-account cooldown |
| `SOCIAL_HEADLESS` | `false` | Run Chrome without a visible window |
| `SOCIAL_IMPLICIT_WAIT` | `10` | Selenium implicit element wait in seconds |
| `SOCIAL_LOGIN_TYPING_MIN` | `0.05` | Minimum delay between login keystrokes |
| `SOCIAL_LOGIN_TYPING_MAX` | `0.15` | Maximum delay between login keystrokes |
| `SOCIAL_LOGIN_SETTLE_SECONDS` | `6` | Wait after submitting login credentials |
| `SOCIAL_JOB_POLL_INTERVAL` | `0.5` | Dispatcher polling interval |
| `SOCIAL_MAX_CSV_BYTES` | `5242880` | Maximum CSV upload size |
| `SOCIAL_MAX_ACCOUNTS_PER_BATCH` | `10000` | Maximum accounts in one batch |
| `SOCIAL_DATA_DIR` | `data` | Local persistent-data directory |
| `SOCIAL_DATABASE_PATH` | `data/social.db` | SQLite database path |
| `SOCIAL_CREDENTIAL_KEY` | unset | Optional externally managed Fernet key |
| `CHROMEDRIVER_PATH` | unset | Optional preinstalled ChromeDriver path |

Capacity planning must consider both job and task concurrency:

```text
Maximum possible browsers ≈ SOCIAL_JOB_WORKERS × SOCIAL_MAX_WORKERS
```

Per-platform and same-account limits can reduce the actual number.

## 18. Running the application

Python 3.10 or newer is required.

### 18.1 Install dependencies

```bash
python -m pip install -r requirements.txt
```

Using a virtual environment is recommended.

### 18.2 Start the web application

```bash
python server.py
```

Open:

- UI: `http://127.0.0.1:8000`
- API documentation: `http://127.0.0.1:8000/docs`

### 18.3 Run the CLI

```bash
cp accounts.example.json accounts.json
python main.py "https://x.com/user/status/123" --action like
python main.py "https://x.com/user/status/123" --action reply --comment "Thanks!"
python main.py "https://instagram.com/p/POST_ID/" --action repost
```

## 19. SOLID principles

### 19.1 Single Responsibility Principle

- `Executor` schedules tasks.
- `Worker` manages one task lifecycle.
- `Registry` catalogs implementations.
- Platform handlers authenticate.
- Action handlers execute one action.
- `JobDispatcher` consumes durable jobs.
- `JobStore` persists data.
- `CredentialCipher` encrypts secrets.
- `csv_account_parser` validates account CSVs.
- Execution observers report progress.

The observer refactor removed console and database reporting concerns from the core
scheduler.

### 19.2 Open/Closed Principle

New platforms are added through handler implementations and a platform bundle. The
executor, worker, dispatcher, and result model do not need platform branches.

The remaining extension point that requires modification is the default bundle
assembly in `src/handlers/registry.py`. Automatic plugin discovery could remove this
last centralized edit.

### 19.3 Liskov Substitution Principle

All `IPlatformHandler` implementations can be used through the same login contract.
All `IActionHandler` implementations can be used through the same execution contract.
Handlers return predictable success/failure values and declare their platform/action
identity.

### 19.4 Interface Segregation Principle

Authentication and action execution use separate focused interfaces. A platform
handler is not forced to implement all actions, and an action handler is not forced to
implement login behavior.

### 19.5 Dependency Inversion Principle

High-level execution code receives registries, proxy managers, browser factories,
worker factories, settings, and observers through constructor arguments. Tests inject
fake implementations without opening Chrome.

The default arguments still provide concrete implementations for convenient normal
use. Python protocols for browser and storage providers could make the abstraction
boundary stricter in a future iteration.

## 20. OOP principles

### Encapsulation

Mutable implementation details such as registry maps, proxy indexes, driver caching,
dispatcher events, and database connections are contained within their responsible
classes.

### Abstraction

The worker operates on handler contracts. It does not know platform selectors or login
screens. API routes operate on `JobStore` behavior rather than raw SQL.

### Polymorphism

Instagram and X handlers respond through identical `login` and `execute` methods. The
registry chooses the implementation at runtime.

### Inheritance

Abstract base classes define handler contracts. `TwitterActionMixin` provides small,
focused selector behavior shared across X actions.

### Composition

The system primarily uses composition:

- An executor has workers, settings, and observers.
- A worker has a registry, proxy manager, and browser factory.
- A platform bundle contains handlers.
- A dispatcher has a job store and executor factory.
- A task contains an account.

Composition keeps tests and runtime replacement simpler than a deep inheritance tree.

## 21. Design patterns

| Pattern | Usage |
|---|---|
| Strategy | One action handler per platform/action pair |
| Adapter | Platform DOM behavior adapted to common interfaces |
| Registry | Runtime mapping from domain identifiers to handlers |
| Factory | Centralized Chrome WebDriver creation |
| Command | `Task` represents schedulable work |
| Observer | Console and persistent job progress reporting |
| Repository | `JobStore` hides SQLite persistence details |
| Producer/Consumer | API produces jobs; dispatcher threads consume them |
| Dependency Injection | Runtime collaborators are constructor parameters |
| DTO/Result Object | Structured batch, job, task, and execution records |

## 22. Reliability decisions

- Every browser is closed in a `finally` block.
- Driver installation is protected from concurrent initialization.
- Proxy rotation is lock-protected.
- SQLite claims use `BEGIN IMMEDIATE` to prevent two dispatcher threads claiming the
  same queued job.
- API-side SQLite operations run outside the async event loop.
- Write actions do not retry after an ambiguous action failure.
- Interrupted jobs fail rather than automatically replay.
- Job errors are length-limited before persistence.
- CSV file size and account count are bounded.
- Cross-platform target URLs are rejected before a job enters the queue.
- Job history prevents deletion of referenced account batches.

## 23. Testing and verification

The suite uses Python's standard `unittest` framework.

Covered behavior includes:

- Platform and action alias normalization
- Cross-platform URL validation
- X and Twitter URL acceptance
- CSV headers, extra columns, and duplicate accounts
- Password encryption at rest and successful decryption for workers
- Platform-scoped API uploads
- Immediate queued job submission without opening a browser
- UI delivery
- Background dispatch and progress persistence
- Login retry behavior
- Prevention of blind write retries
- Driver cleanup
- Per-platform concurrency limits
- Same-account serialization

Run verification:

```bash
python -m compileall -q main.py server.py setup.py src tests
node --check src/web/app.js
python -m unittest discover -s tests -v
```

The implemented suite currently contains 14 passing tests. An HTTP smoke test also
verified:

- Server startup
- `GET /api/v1/health` returning `200`
- UI delivery returning `200`
- Multipart CSV upload returning `201`

Live social actions were not executed during automated verification because they
require real accounts and may trigger MFA, CAPTCHA, rate limits, or account controls.

## 24. Scaling boundaries

The current architecture scales safely within one host by bounding Chrome processes
and moving jobs away from HTTP request threads. SQLite provides durable local state but
is not the final design for multiple API hosts.

For horizontal production scaling, replace or extend:

- SQLite job claiming with Redis, RabbitMQ, SQS, Kafka, or another durable broker.
- SQLite persistence with PostgreSQL or another shared database.
- Local dispatcher threads with independently deployed worker processes.
- Local Fernet key storage with a managed secret store or KMS.
- Username/password browser login with official OAuth APIs where available.
- Console output with structured logs, metrics, tracing, and alerting.
- Round-robin proxy selection with proxy health scoring and quarantine.

Run one API process when using the bundled SQLite dispatcher. Multiple API processes
would each start local consumers and require leases/heartbeats for safe crash recovery.

## 25. Adding another platform

1. Add the platform to `Platform`.
2. Implement `IPlatformHandler` for login and URL construction.
3. Implement one or more `IActionHandler` strategies.
4. Assemble them in a `PlatformBundle`.
5. Register the bundle in `create_default_registry()`.
6. Add allowed target hosts to task validation.
7. Add the platform to the API-supported platform list.
8. Add a platform section or generate the UI section dynamically.
9. Add unit tests for registration, validation, login, and actions.

No changes should be required in `Executor`, `Worker`, `JobDispatcher`, or the result
model.

## 26. Known limitations

- Selenium selectors can change when social platforms update their user interfaces.
- CAPTCHA, MFA, suspicious-login challenges, and account locks require human action.
- X verification may require an email or phone identifier not present in a two-column
  CSV. The handler falls back to the username when an extra identifier is requested.
- Browser sessions are not currently persisted between tasks, so each task logs in
  again.
- Same-account serialization is scoped to one executor/job. The default
  `SOCIAL_JOB_WORKERS=1` prevents overlap across API jobs; when raising it, do not run
  overlapping batches until a shared account-lease service is added.
- The bundled UI/API has no application-level authentication.
- SQLite and local dispatcher threads are limited to a single-host deployment.
- Facebook is not implemented.
- Comments generated without explicit text use a local template manager.
- A stopped process cannot forcibly cancel an in-progress Selenium interaction safely.

## 27. Recommended next improvements

1. Add application authentication, authorization, and audit logs.
2. Persist encrypted browser cookies or session profiles per account.
3. Add explicit job cancellation and graceful task cancellation points.
4. Introduce PostgreSQL and an external job broker for horizontal workers.
5. Add an official X OAuth/API adapter alongside the browser adapter.
6. Add proxy health checks, failure scoring, and automatic quarantine.
7. Move target-host validation into platform handlers for even stronger OCP.
8. Generate platform UI sections from `/api/v1/platforms` metadata.
9. Add metrics for queue latency, browser startup, login failures, and action latency.
10. Add integration tests against controlled test pages rather than live social sites.

## 28. Operational warning

Use automation only for accounts you control and in accordance with each platform's
terms, rate limits, and applicable laws. Keep concurrency and cooldown settings
conservative. Official platform APIs are preferred for high-volume or production
workloads when the required capability is available.
