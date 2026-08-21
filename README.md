# Social media automation

An extensible, bounded-concurrency runner for Instagram and X/Twitter. It supports
like, comment/reply, and repost/retweet actions without putting platform-specific
logic in the executor.

For the complete architecture, API, database, security, SOLID/OOP, scaling, and
extension documentation, see [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md).

## Web UI and API

Start the local service:

```bash
python -m pip install -r requirements.txt
python server.py
```

Open `http://127.0.0.1:8000`. Interactive API documentation is available at
`http://127.0.0.1:8000/docs`.

The Instagram and X sections are independent. Each CSV upload creates a reusable
account batch, and the section supplies the platform, so a CSV only needs:

```csv
username,password
account_one,replace-me
account_two,replace-me
```

Submitting a job returns HTTP `202` immediately. Dedicated dispatcher threads claim
durable SQLite jobs and run Selenium executors away from FastAPI's event loop. Live
task totals and results are written back to the job ledger.

Upload a batch through the API:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/platforms/twitter/batches \
  -F 'name=Community accounts' \
  -F 'file=@accounts.csv'
```

Queue work using the returned batch ID:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "batch_id": "BATCH_ID",
    "action": "like",
    "target_url": "https://x.com/user/status/123"
  }'
```

Useful endpoints:

- `GET /api/v1/health`
- `GET|POST /api/v1/platforms/{platform}/batches`
- `DELETE /api/v1/platforms/{platform}/batches/{batch_id}`
- `GET|POST /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`

Uploaded passwords are encrypted before SQLite storage. The generated encryption key
and database live under `data/`, which is ignored by Git. Back up the key with the
database; losing it makes stored credentials unrecoverable. Keep this service bound to
localhost or place authentication and TLS in front of it before exposing it on a network.

## Run it

Use Python 3.10 or newer:

```bash
python -m pip install -r requirements.txt
cp accounts.example.json accounts.json
python main.py "https://x.com/some_user/status/123" --action like
python main.py "https://x.com/some_user/status/123" --action reply --comment "Thanks!"
python main.py "https://www.instagram.com/p/POST_ID/" --action repost
```

Only accounts matching the target URL's platform are scheduled. `x` and `x.com`
are accepted as aliases for `twitter` in account/task data. X may require
`verification_identifier` during login. CAPTCHA, MFA, account locks, and UI changes
still require human intervention.

Instagram login uses the validated DOM sequence from the working reference project:
multiple username/password/button selectors, human-paced typing, submit-form fallback,
and completion of the post-login `accounts/onetap` screen. Login is accepted only when
Instagram issues a `sessionid` cookie; the cookie is checked again after opening the
target post. A like is reported successful only after the control changes to `Unlike`.
If Instagram still blocks an account, open **View logs** for the job; challenge/2FA,
rejected credentials, missing sessions, and login-page timeouts are reported separately.

## Scale controls

Configuration is environment-based:

```bash
SOCIAL_MAX_WORKERS=6 \
SOCIAL_PLATFORM_WORKERS="instagram=2,twitter=4" \
SOCIAL_JOB_WORKERS=1 \
SOCIAL_MIN_COOLDOWN=10 \
SOCIAL_MAX_COOLDOWN=30 \
SOCIAL_HEADLESS=true \
python main.py "https://x.com/some_user/status/123" --action like
```

- Work is fair across platform queues.
- A platform cannot exceed its configured browser limit.
- The same account is never used concurrently.
- Cooldowns happen in the dispatcher rather than occupying browser workers.
- Browser startup and login failures retry; write actions do not blindly retry.
- Results retain a machine-readable failure code and attempt count.
- The API dispatcher is independent from browser worker threads.
- Uploaded batches and job status survive service restarts.

Set `CHROMEDRIVER_PATH` in containers to avoid runtime driver downloads. Proxy
entries in `proxies.json` should be full URLs such as `http://host:port`.

## Add another platform

Implement `IPlatformHandler` plus one or more `IActionHandler` classes, assemble a
`PlatformBundle`, then add that bundle in `src/handlers/registry.py`. The executor,
worker, scheduling, validation, and result reporting do not need platform branches.

For high-volume or production X workloads, prefer X's official OAuth API over UI
automation. Browser workers are intentionally bounded because each Chrome process
is expensive; horizontal scale should put task queues in durable external storage
and run this executor in multiple isolated worker processes.

`SOCIAL_JOB_WORKERS` controls how many whole jobs may execute at once. Each job can use
up to `SOCIAL_MAX_WORKERS` browsers, so keep the product of those settings within the
machine's Chrome capacity. Run one API process with the bundled SQLite dispatcher; use
an external queue and database before scaling to multiple API hosts.
