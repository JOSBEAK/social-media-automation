from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.api.schemas import BatchResponse, JobCreate, JobDetailResponse, JobResponse
from src.config.settings import Settings
from src.domains.action_type import ActionType
from src.domains.platform import Platform
from src.domains.task import Task
from src.models.account import Account
from src.services.credential_cipher import CredentialCipher
from src.services.csv_account_parser import AccountCsvError, parse_account_csv
from src.services.job_dispatcher import JobDispatcher
from src.services.job_store import JobStore


SUPPORTED_PLATFORMS = (Platform.INSTAGRAM, Platform.TWITTER)
WEB_DIR = Path(__file__).resolve().parents[1] / "web"


def _parse_supported_platform(value: str) -> Platform:
    try:
        platform = Platform.parse(value)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=404, detail="Unsupported platform") from exc
    if platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(status_code=404, detail="Unsupported platform")
    return platform


def _build_store() -> JobStore:
    key_path = Path(Settings.DATA_DIR) / ".credential_key"
    cipher = CredentialCipher(Settings.CREDENTIAL_KEY, key_path)
    return JobStore(Settings.DATABASE_PATH, cipher)


def create_app(
    store: JobStore | None = None,
    dispatcher: JobDispatcher | None = None,
    start_dispatcher: bool = True,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.store = store or _build_store()
        application.state.dispatcher = dispatcher or JobDispatcher(application.state.store)
        if start_dispatcher:
            application.state.dispatcher.start()
        yield
        if start_dispatcher:
            application.state.dispatcher.stop()

    application = FastAPI(
        title="Relay Social Automation API",
        version="1.0.0",
        description="Upload independent account batches and schedule non-blocking social jobs.",
        lifespan=lifespan,
    )

    @application.get("/api/v1/health")
    async def health(request: Request):
        return {"status": "ok", **await run_in_threadpool(request.app.state.store.stats)}

    @application.get("/api/v1/platforms")
    async def platforms():
        actions = [action.value for action in ActionType]
        return [
            {"id": platform.value, "label": "X / Twitter" if platform is Platform.TWITTER else "Instagram", "actions": actions}
            for platform in SUPPORTED_PLATFORMS
        ]

    @application.post(
        "/api/v1/platforms/{platform_name}/batches",
        response_model=BatchResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def upload_batch(
        request: Request,
        platform_name: str,
        file: UploadFile = File(...),
        name: str | None = Form(default=None),
    ):
        platform = _parse_supported_platform(platform_name)
        filename = Path(file.filename or "accounts.csv").name
        content = await file.read(Settings.MAX_CSV_BYTES + 1)
        await file.close()
        if len(content) > Settings.MAX_CSV_BYTES:
            raise HTTPException(status_code=413, detail="CSV file is too large")
        try:
            accounts = await run_in_threadpool(
                parse_account_csv, content, Settings.MAX_ACCOUNTS_PER_BATCH
            )
        except AccountCsvError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        batch_name = (name or Path(filename).stem or f"{platform.value} accounts").strip()
        if not batch_name:
            raise HTTPException(status_code=422, detail="Batch name cannot be empty")
        return await run_in_threadpool(
            request.app.state.store.create_batch,
            platform,
            batch_name,
            filename,
            accounts,
        )

    @application.get(
        "/api/v1/platforms/{platform_name}/batches",
        response_model=list[BatchResponse],
    )
    async def list_batches(request: Request, platform_name: str):
        platform = _parse_supported_platform(platform_name)
        return await run_in_threadpool(request.app.state.store.list_batches, platform)

    @application.delete(
        "/api/v1/platforms/{platform_name}/batches/{batch_id}",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    async def delete_batch(request: Request, platform_name: str, batch_id: str):
        platform = _parse_supported_platform(platform_name)
        batch = await run_in_threadpool(request.app.state.store.get_batch, batch_id)
        if batch is None or batch.platform != platform.value:
            raise HTTPException(status_code=404, detail="Account batch not found")
        try:
            deleted = await run_in_threadpool(request.app.state.store.delete_batch, batch_id)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if not deleted:
            raise HTTPException(status_code=404, detail="Account batch not found")

    @application.post(
        "/api/v1/jobs",
        response_model=JobResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def create_job(request: Request, payload: JobCreate):
        batch = await run_in_threadpool(request.app.state.store.get_batch, payload.batch_id)
        if batch is None:
            raise HTTPException(status_code=404, detail="Account batch not found")
        platform = _parse_supported_platform(batch.platform)
        action = ActionType.parse(payload.action)
        params = {"comment_text": payload.comment_text} if payload.comment_text else {}
        validation_task = Task(
            Account("validation", "validation", platform.value),
            platform,
            action,
            payload.target_url,
            params,
        )
        validation_error = validation_task.validation_error()
        if validation_error:
            raise HTTPException(status_code=422, detail=validation_error)

        job = await run_in_threadpool(
            request.app.state.store.create_job,
            batch,
            action.value,
            payload.target_url,
            params,
        )
        request.app.state.dispatcher.notify()
        return job

    @application.get("/api/v1/jobs", response_model=list[JobResponse])
    async def list_jobs(request: Request, limit: int = 50):
        return await run_in_threadpool(
            request.app.state.store.list_jobs, min(max(limit, 1), 200)
        )

    @application.get("/api/v1/jobs/{job_id}", response_model=JobDetailResponse)
    async def get_job(request: Request, job_id: str):
        job = await run_in_threadpool(request.app.state.store.get_job, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        results = await run_in_threadpool(request.app.state.store.list_results, job_id)
        return {**job.__dict__, "results": results}

    @application.get("/", include_in_schema=False)
    async def index():
        return FileResponse(WEB_DIR / "index.html")

    application.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")
    return application


app = create_app()
